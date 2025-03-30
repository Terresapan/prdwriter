import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI 
from langgraph.graph import END, StateGraph
from pydantic import BaseModel
from arcadepy import Arcade
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from github import Auth
from prompt import draft_template
from repository import get_repo_python_files_content
import os

# Set API keys from Streamlit secrets
os.environ["GOOGLE_API_KEY"] = st.secrets["general"]["GOOGLE_API_KEY"]
os.environ["ARCADE_API_KEY"] = st.secrets["general"]["ARCADE_API_KEY"]
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = st.secrets["tracing"]["LANGCHAIN_API_KEY"]
os.environ["LANGCHAIN_ENDPOINT"]="https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "PRD Writer"


# Constants
GEMINI_2_0_FLASH = "gemini-2.0-flash"
REPO_OWNER = "Terresapan"
REPO_NAME = "groupdebating"
REPO_PATH = "" 
RECURSIVE_SEARCH = False
DOUCUMENT_ID = "1YImcxcZ0zG2-cV7oubxBYvwob_IIEf2I4ZuwJrT4yqs" 


# Define the state model
class State(BaseModel):
    reponame: str = ""
    owner: str = ""
    document_id: str = ""
    repocontent: str = ""
    pdr: str = ""
    save_to_doc: bool = False

# initiate Arcade client
client = Arcade(api_key=os.environ["ARCADE_API_KEY"])

# Define LLM
def get_llm(model=GEMINI_2_0_FLASH, temperature=0):
    """Initialize and return the LLM based on the specified model."""    
    return ChatGoogleGenerativeAI(
        model=GEMINI_2_0_FLASH,
        temperature=temperature,
        api_key=os.environ["GOOGLE_API_KEY"]
    )


def get_code_content(state: State):
    """Fetch repository content using Arcade GitHub tool."""
    auth = Auth.Token(os.environ["GITHUB_TOKEN"])
    combined_code = get_repo_python_files_content(
        token_auth=auth,
        owner=REPO_OWNER,
        repo_name=REPO_NAME,
        path=REPO_PATH,
        recursive=RECURSIVE_SEARCH
    )

    if combined_code is not None:
        if combined_code:
            # print("\n--- Combined Python Code ---")
            # Only print the start for brevity if it's very long
            # print(combined_code[:2000] + ('...' if len(combined_code) > 2000 else ''))
            state.repocontent = combined_code
            # print("\n--- End of Combined Code ---")
        else:
            print("No Python code was extracted.")
    else:
        print("Script failed.") # Error messages were printed earlier

    return state

def draft_prd(state: State):
    try:
        llm = get_llm(temperature=0)
        if not state.repocontent:
            st.warning("Repository content is empty, cannot draft PRD.")
            state.pdr = "Error: Could not fetch repository content."
            return state

        prompt = draft_template.format(codebase=state.repocontent)
        result = llm.invoke(prompt)

        # Assign to pdr, not repocontent
        state.pdr = result.content # Assuming content is AIMessage with .content attribute

    except Exception as e:
        st.error(f"Error drafting prd: {e}")
        state.pdr = f"Error generating PRD: {e}" # Set error message in pdr
    return state


def update_google_doc_node(state: State):
        """Node to update Google Doc with the final PRD."""
        try:
            # Debug information
            # print("Debug - update_google_doc_node - PRD Length:", len(state.pdr) if state.pdr else 0)
            # print("Debug - update_google_doc_node - Document ID:", state.document_id)
            
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
                return {"draft": state.pdr}

            # Build the credentials and Docs client
            credentials = Credentials(token)
            google_doc = build("docs", "v1", credentials=credentials)
            
            # Get document to find the end
            try:
                document = google_doc.documents().get(documentId=state.document_id).execute()
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
                            "text": "\n\n" + state.pdr,  # Add newlines for separation
                        }
                    }
                ]
                # Debug the request
                # print("Debug - Google Doc Update Request:", {
                #     "documentId": state.document_id,
                #     "text_length": len(state.pdr) if state.pdr else 0,
                #     "insert_at_index": end_index - 1
                # })
                
                google_doc.documents().batchUpdate(
                    documentId=state.document_id,
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
                            "text": state.pdr + "\n\n",
                        }
                    }
                ]
                
                google_doc.documents().batchUpdate(
                    documentId=state.document_id,
                    body={"requests": requests}
                ).execute()
                
                st.success("✅ Case study added to Google Doc (at beginning)!")
            
            return {"pdr": state.pdr}
            
        except Exception as e:
            st.error(f"❌ Error updating Google Doc: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return {"pdr": state.pdr}


# Function to decide whether to update the Google Doc
def should_save_to_doc(state: State):
    """Conditional edge logic: route to update_google_doc or end."""
    if state.save_to_doc:
        # Debug information
        # print("Debug - should_save_to_doc - Routing to update_google_doc")
        # print("Debug - should_save_to_doc - PRD Length:", len(state.pdr) if state.pdr else 0)
        return "update_google_doc"
    else:
        print("Debug - should_save_to_doc - Routing to END")
        return END


def get_workflow():
    """Create and return the workflow with improved state handling."""
    
    # Define workflow
    workflow = StateGraph(State)
    
    workflow.add_node("get_code_content", get_code_content)
    workflow.add_node("draft_prd", draft_prd)
    workflow.add_node("update_google_doc", update_google_doc_node)

    # Determine entry point based on state
    def get_entry_point(state: State):
        if state.save_to_doc and state.pdr:
            # If we already have a PRD and want to save it, start from update_google_doc
            # print("Debug - Workflow Entry Point: update_google_doc (direct save)")
            return "update_google_doc"
        else:
            # Otherwise, start from the beginning
            # print("Debug - Workflow Entry Point: get_code_content (normal flow)")
            return "get_code_content"
    
    # Set conditional entry point
    workflow.set_conditional_entry_point(get_entry_point)

    workflow.add_edge("get_code_content", "draft_prd")

    # Conditional edge after drafting PRD
    workflow.add_conditional_edges(
        "draft_prd",
        should_save_to_doc, # Function to decide the next step
        {
            "update_google_doc": "update_google_doc", # If should_save_to_doc returns "update_google_doc"
            END: END # If should_save_to_doc returns END
        }
    )

    workflow.add_edge("update_google_doc", END) # End after updating doc

    return workflow.compile()
