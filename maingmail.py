import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI 
from langgraph.graph import END, StateGraph
from pydantic import BaseModel
from arcadepy import Arcade
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from utils import extract_text_from_pdf, extract_text_from_docx, extract_text_from_txt
import json
from prompt import draft_template, revise_template
import os

# Set API keys from Streamlit secrets
os.environ["GOOGLE_API_KEY"] = st.secrets["general"]["GOOGLE_API_KEY"]
os.environ["ARCADE_API_KEY"] = st.secrets["general"]["ARCADE_API_KEY"]
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = st.secrets["tracing"]["LANGCHAIN_API_KEY"]
os.environ["LANGCHAIN_ENDPOINT"]="https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "Client Success Story Teller"


# Define the state model
class State(BaseModel):
    project_desc: str = ""
    case_study: str = ""
    additional_text: str = ""
    draft: str = ""
    feedback: str | None = None
    confirmed: bool = False


def process_inputs(project_desc, case_study, additional_text, confirmed=False):
    # Process uploaded files
    def extract_text(uploaded_file):
        """Extract text from the uploaded file."""
        file_text = ""
        if uploaded_file.type == "application/pdf":
            file_text = extract_text_from_pdf(uploaded_file)
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            file_text = extract_text_from_docx(uploaded_file)
        elif uploaded_file.type == "text/plain":
            file_text = extract_text_from_txt(uploaded_file)
        else:
            st.error("❌ Unsupported file type")
        return file_text

   
    return State(
        project_desc=extract_text(project_desc),
        case_study=extract_text(case_study),
        additional_text=additional_text,
        confirmed=confirmed
    )

def get_workflow():
    """Create and return the workflow with improved state handling."""
    # Define LLM
    llm = ChatGoogleGenerativeAI (
        model="gemini-2.0-flash", 
        temperature=0,
        api_key=os.environ["GOOGLE_API_KEY"] 
    )

    # Define nodes
    def draft_node(state):
        prompt = ChatPromptTemplate.from_template(draft_template)
        chain = prompt | llm
        return {"draft": chain.invoke({
            "project_desc": state.project_desc,
            "case_study": state.case_study,
            "additional_text": state.additional_text
        }).content}

    def revise_node(state):
        prompt = ChatPromptTemplate.from_template(revise_template)
        chain = prompt | llm
        return {"draft": chain.invoke({
                "feedback": state.feedback,
                "draft": state.draft
            }).content}
    
    def send_google_email_node(state):
        """Node to update Google Doc with the final draft."""
                   
        # Initialize the Arcade client
        client = Arcade(api_key=os.environ["ARCADE_API_KEY"])
        USER_ID = "terresap2010@gmail.com"
        TOOL_NAME = "Google.SendEmail"

        # Handle authorization
        if 'auth_complete' not in st.session_state:
            st.session_state.auth_complete = False

        if not st.session_state.auth_complete:
            auth_response = client.tools.authorize(
                tool_name=TOOL_NAME,
                user_id=USER_ID,
            )
            if auth_response.status != "completed":
                st.link_button("Authorize Google Gmail Access", auth_response.url)
                client.auth.wait_for_completion(auth_response)
                st.session_state.auth_complete = True
                st.rerun()

        tool_input = {
            "subject": "Finalized Client Success Story",
            "body": state.draft,
            "recipient": "terresap@theaccelerationproject.org",
        }
        
        # Create event
        response = client.tools.execute(
            tool_name=TOOL_NAME,
            input=tool_input,
            user_id=USER_ID,
        )
        st.success(f"✅ Client success story successfully sent to Gmail!")
        return {"draft": state.draft}       
           

    # Define workflow
    workflow = StateGraph(State)
    
    workflow.add_node("create_draft", draft_node)
    workflow.add_node("revise_draft", revise_node)
    workflow.add_node("send_email", send_google_email_node)
    
    def set_entry_point(state):
       
        if state.confirmed:
            if state.draft:
                # If we have a confirmed draft, go straight to send_email
                return "send_email"
            else:
                # If confirmed but no draft, create one first
                return "create_draft"
        elif state.feedback and state.draft:
            # If we have feedback and a draft, go to revise
            return "revise_draft"
        else:
            # Default: create a draft
            return "create_draft"
    
    # Set a fixed entry point instead of a dynamic function
    workflow.set_entry_point("create_draft")
    
    # Modify conditional edges with better state tracking
    def after_create_draft(state):
        # print(f"After create_draft state: {state}")
        if state.confirmed and state.draft:
            return "send_email"
        elif state.feedback:
            return "revise_draft"
        else:
            return END

    def after_revise_draft(state):
        # print(f"After revise_draft state: {state}")
        if state.confirmed:
            return "send_email"
        else:
            return END

    workflow.add_conditional_edges("create_draft", after_create_draft)
    workflow.add_conditional_edges("revise_draft", after_revise_draft)
    workflow.add_edge("send_email", END)
    
    return workflow.compile()
