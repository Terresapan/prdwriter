import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI 
from langgraph.graph import END, StateGraph
from pydantic import BaseModel
from arcadepy import Arcade
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from utils import extract_text_from_pdf, extract_text_from_docx, extract_text_from_txt
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
    
    def update_google_doc_node(state):
        """Node to update Google Doc with the final draft."""
        try:
            client = Arcade(api_key=os.environ["ARCADE_API_KEY"])
            USER_ID = "terresap2010@gmail.com"
            
            # Handle authorization
            if 'auth_complete' not in st.session_state:
                st.session_state.auth_complete = False

            auth_response = client.auth.start(
                user_id=USER_ID,
                provider="google",
                scopes=["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"],
            )

            if not st.session_state.auth_complete:
                if auth_response.status != "completed":
                    st.link_button("Authorize Google Drive Access", auth_response.url)
                    client.auth.wait_for_completion(auth_response)
                    st.session_state.auth_complete = True
                    st.rerun()
            
            # get the auth token
            token = auth_response.context.token
            
            if not token:
                st.error("No token found in auth response")
                return {"draft": state.draft}

            # Build the credentials and Docs client
            credentials = Credentials(token)
            google_doc = build("docs", "v1", credentials=credentials)
            document_id = "1YImcxcZ0zG2-cV7oubxBYvwob_IIEf2I4ZuwJrT4yqs"
            
            # Get document to find the end
            try:
                document = google_doc.documents().get(documentId=document_id).execute()
                # Get the document's content end index
                content = document.get("body", {}).get("content", [])
                if content:
                    # Find the last content element with an endIndex
                    end_indices = [item.get("endIndex", 1) for item in content if "endIndex" in item]
                    end_index = max(end_indices) if end_indices else 1
                else:
                    end_index = 1  # Default for empty document
                    
                # Build a batchUpdate request to insert the draft
                requests = [
                    {
                        "insertText": {
                            "location": {"index": end_index - 1},
                            "text": "\n\n" + state.draft,  # Add newlines for separation
                        }
                    }
                ]
                
                google_doc.documents().batchUpdate(
                    documentId=document_id, 
                    body={"requests": requests}
                ).execute()
                
                st.success("✅ Case study appended to Google Doc!")
                
            except Exception as doc_error:
                st.error(f"Error with document: {str(doc_error)}")
                # Fallback to inserting at the beginning
                requests = [
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": state.draft + "\n\n",
                        }
                    }
                ]
                
                google_doc.documents().batchUpdate(
                    documentId=document_id, 
                    body={"requests": requests}
                ).execute()
                
                st.success("✅ Case study added to Google Doc (at beginning)!")
            
            return {"draft": state.draft}
            
        except Exception as e:
            st.error(f"❌ Error updating Google Doc: {str(e)}")
            import traceback
            st.write(traceback.format_exc())
            return {"draft": state.draft}


       
           

    # Define workflow
    workflow = StateGraph(State)
    
    workflow.add_node("create_draft", draft_node)
    workflow.add_node("revise_draft", revise_node)
    workflow.add_node("update_google_doc", update_google_doc_node)
     
    workflow.set_entry_point("create_draft")
    
    # Modify conditional edges with better state tracking
    def after_create_draft(state):
        # print(f"After create_draft state: {state}")
        if state.confirmed and state.draft:
            return "update_google_doc"
        elif state.feedback:
            return "revise_draft"
        else:
            return END

    def after_revise_draft(state):
        # print(f"After revise_draft state: {state}")
        if state.confirmed:
            return "update_google_doc"
        else:
            return END

    workflow.add_conditional_edges("create_draft", after_create_draft)
    workflow.add_conditional_edges("revise_draft", after_revise_draft)
    workflow.add_edge("update_google_doc", END)
    
    return workflow.compile()
