import streamlit as st
from arcadepy import Arcade
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os


def update_google_doc_node(state):
    """Node to update Google Doc with the final draft."""
    try:
        client = Arcade(api_key=os.environ["ARCADE_API_KEY"])
        USER_ID = "terresap2010@gmail.com"
        
        # Authorize and execute the tool
        auth_response = client.auth.start(
            user_id=USER_ID,
            provider="google",
            scopes=["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"],
        )
        
        if auth_response.status != "completed":
            st.error(f"Authorization required: {auth_response.url}")
            return {"draft": state.draft}

        # Wait for the authorization to complete
        auth_response = client.auth.wait_for_completion(auth_response)
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


