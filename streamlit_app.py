import streamlit as st
from maindoc import get_workflow, State, client  # Import State and client

# Streamlit UI setup
st.set_page_config(page_title="PRD Writer", layout="wide", page_icon="✍️")

# Setup sidebar with instructions
def setup_sidebar():
    """Setup the sidebar with instructions."""
    st.sidebar.header("✍️ PRD Writer")
    st.sidebar.markdown(
        "This app fetches code from a GitHub repository, generates a "
        "Product Requirements Document (PRD) using an LLM, and saves it to a Google Doc."
    )

    st.sidebar.write("### Instructions")
    st.sidebar.write(
        "1. :heart_eyes_cat: Enter the GitHub repository name (ensure Arcade has access).\n"
        "2. :writing_hand: Generate the PRD draft.\n"
        "3. :eyes: Review the draft.\n"
        "4. :floppy_disk: Save the final PRD to your Google Doc.\n"
    )

def main():
    """Main application function for PRD generation."""
    setup_sidebar()

    st.title("✍️ PRD Writer from GitHub Repo")

    # Initialize session state
    if 'prd_draft' not in st.session_state:
        st.session_state.prd_draft = None
    if 'repo_content_fetched' not in st.session_state:
        st.session_state.repo_content_fetched = False
    if 'prd_generated' not in st.session_state:
        st.session_state.prd_generated = False
    if 'doc_updated' not in st.session_state:
        st.session_state.doc_updated = False
    if 'auth_complete' not in st.session_state: # Keep track of Google Auth
        st.session_state.auth_complete = False
    if 'github_auth_complete' not in st.session_state: # Keep track of GitHub Auth
        st.session_state.github_auth_complete = False
    
    # Initialize reset state variables
    if 'repo_name_reset' not in st.session_state:
        st.session_state.repo_name_reset = False
    if 'owner_name_reset' not in st.session_state:
        st.session_state.owner_name_reset = False
    if 'document_id_reset' not in st.session_state:
        st.session_state.document_id_reset = False


    # Input for repository name and document ID with reset handling
    default_repo_name = "" if st.session_state.repo_name_reset else None
    default_owner_name = "Terresapan" if st.session_state.owner_name_reset else "Terresapan"
    default_document_id = "1Bd_AeFPhUl_4GH3wl2lHL635sMUrcKUOuWzvfT-LPpQ" if st.session_state.document_id_reset else "1Bd_AeFPhUl_4GH3wl2lHL635sMUrcKUOuWzvfT-LPpQ"
    
    # Reset the flags after using them
    if st.session_state.repo_name_reset:
        st.session_state.repo_name_reset = False
    if st.session_state.owner_name_reset:
        st.session_state.owner_name_reset = False
    if st.session_state.document_id_reset:
        st.session_state.document_id_reset = False
    
    repo_name = st.text_input("Enter GitHub Repository Name (e.g., 'my-awesome-project')", value=default_repo_name, key="repo_name_input")
    owner_name = st.text_input("Enter GitHub Repository Owner (e.g., 'octocat')", value=default_owner_name, key="owner_name_input") # Defaulting owner based on maindoc.py
    document_id = st.text_input("Enter Google Document ID", value=default_document_id, key="document_id_input") # Default from maindoc.py

    # Button to trigger the workflow
    if st.button("✨ Generate PRD Draft"):
        if repo_name and owner_name:
            with st.spinner('⚙️ Fetching repository and generating PRD...'):
                # Reset states on new generation
                st.session_state.prd_draft = None
                st.session_state.repo_content_fetched = False
                st.session_state.prd_generated = False
                st.session_state.doc_updated = False

                try:
                    # --- GitHub Authorization ---
                    USER_ID = "terresap2010@gmail.com" # As defined in maindoc.py
                    TOOL_NAME = "Github.GetRepository" # As defined in maindoc.py

                    if 'github_auth_complete' not in st.session_state or not st.session_state.github_auth_complete:
                        auth_response_github = client.tools.authorize(
                            tool_name=TOOL_NAME,
                            user_id=USER_ID,
                        )
                        if auth_response_github.status != "completed":
                            st.info(f"GitHub authorization required. Please click the link below if it doesn't open automatically.")
                            st.link_button("Authorize GitHub Access", auth_response_github.url)
                            # Wait for authorization - this might block, consider async or background task for better UX in production
                            client.auth.wait_for_completion(auth_response_github)
                            st.session_state.github_auth_complete = True
                            st.success("GitHub Authorized!")
                            st.rerun() # Rerun to proceed after auth
                        else:
                             st.session_state.github_auth_complete = True


                    # --- Google Authorization ---
                    if 'auth_complete' not in st.session_state or not st.session_state.auth_complete:
                         auth_response_google = client.auth.start(
                             user_id=USER_ID,
                             provider="google",
                             scopes=["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"],
                         )
                         if auth_response_google.status != "completed":
                             st.info(f"Google authorization required for saving the document. Please click the link below.")
                             st.link_button("Authorize Google Drive Access", auth_response_google.url)
                             client.auth.wait_for_completion(auth_response_google)
                             st.session_state.auth_complete = True
                             st.success("Google Drive Authorized!")
                             st.rerun() # Rerun to proceed after auth
                         else:
                             st.session_state.auth_complete = True


                    # --- Execute Workflow ---
                    if st.session_state.github_auth_complete and st.session_state.auth_complete:
                        # Prepare initial state
                        initial_state = State(reponame=repo_name, owner=owner_name, document_id=document_id)

                        # Get and compile the workflow
                        workflow = get_workflow()

                        # Run workflow to generate initial draft (up to draft_prd node)
                        # We run step-by-step to show progress
                        # Step 1: Get Code Content
                        st.write("📋 Fetching repository content...")
                        state_after_fetch = workflow.invoke(initial_state, config={"run_name": "Fetch Repo Content"})
                        st.session_state.repo_content_fetched = True
                        st.write("Repository content fetched.")

                        # Check if content was fetched
                        if not state_after_fetch.get("repocontent"):
                             st.error("Failed to fetch repository content. Please check the repository name, owner, and GitHub authorization.")
                             st.stop()
                        
                        # Store repository content in session state for later use
                        st.session_state.repocontent = state_after_fetch.get("repocontent", "")

                        # Step 2: Draft PRD (Assuming draft_prd is the next step after get_code_content)
                        # Note: LangGraph executes sequentially based on edges.
                        # The invoke call runs the graph until an END or interruption.
                        # We'll rely on the full invoke and extract the draft later.
                        st.write("✍️ Generating PRD draft...")
                        final_result = state_after_fetch # Result from the full run up to a potential stop or END

                        # Extract draft from the final state after draft_prd node runs
                        # The draft_prd function in maindoc.py updates state.pdr
                        if final_result and final_result.get("pdr"):
                            st.session_state.prd_draft = final_result["pdr"]
                            st.session_state.prd_generated = True
                            st.write("PRD draft generated.")
                            st.rerun() # Rerun to display the draft
                        else:
                            st.error("Failed to generate PRD draft.")
                            # Optionally display the state for debugging: st.write(final_result)

                except Exception as e:
                    st.error(f"An error occurred during PRD generation: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc(), language="python")
        else:
            st.warning("Please enter both GitHub Repository Name and Owner.")

    # Display PRD draft
    if st.session_state.prd_draft and not st.session_state.doc_updated:
        st.subheader("**📋 PRD Draft:**")
        st.markdown(st.session_state.prd_draft) # Use markdown for better formatting if PRD includes it

        # Button to save to Google Doc
        if st.button("📚 Save PRD to Google Doc", type="secondary"):
             if st.session_state.auth_complete:
                with st.spinner("⏳ Saving finalized PRD to Google doc..."):
                    try:
                        # Prepare state for the final update step
                        # Ensure all necessary fields for update_google_doc_node are present
                        # Create state with all required fields
                        update_state = State(
                            reponame=st.session_state.get("repo_name_input", repo_name),
                            owner=st.session_state.get("owner_name_input", owner_name),
                            document_id=st.session_state.get("document_id_input", document_id),
                            repocontent=st.session_state.repocontent,  # Use the stored repository content
                            pdr=st.session_state.prd_draft,
                            save_to_doc=True
                        )

                        # Get the workflow again
                        workflow = get_workflow()

                        # Debug: Print state values before invoking workflow
                        print("Debug - PRD Content Length:", len(st.session_state.prd_draft) if st.session_state.prd_draft else 0)
                        print("Debug - Repository Content Length:", len(st.session_state.repocontent) if hasattr(st.session_state, 'repocontent') else 0)
                        
                        # Invoke the workflow, specifically targeting or ensuring the update node runs
                        # LangGraph's invoke will run from the start unless checkpoints are used.
                        # We rely on the state carrying the necessary 'pdr' value.
                        # The update_google_doc_node in maindoc.py now uses state.pdr
                        result = workflow.invoke(update_state, config={"run_name": "Update Google Doc"})
                        
                        # Debug: Print result after workflow execution
                        print("Debug - Workflow Result Keys:", list(result.keys()) if result else "No result")

                        # Check result or assume success if no error
                        st.session_state.doc_updated = True
                        st.rerun()

                    except Exception as e:
                        st.error(f"Failed to save to Google Doc: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc(), language="python")
             else:
                 st.warning("Google Drive authorization is required. Please try generating the draft again to authorize.")


    # Display final confirmation
    if st.session_state.doc_updated:
        st.subheader("📝 Final PRD:")
        st.markdown(st.session_state.prd_draft)
        st.success("✅ PRD has been generated and saved in Google doc!")

        # Add reset function to handle form reset properly
        def reset_form():
            # Reset relevant states to start fresh
            st.session_state.prd_draft = None
            st.session_state.repo_content_fetched = False
            st.session_state.prd_generated = False
            st.session_state.doc_updated = False
            
            # Use a different approach to reset input fields
            # Instead of directly modifying widget keys, set separate state variables
            if "repo_name_reset" not in st.session_state:
                st.session_state.repo_name_reset = True
            if "owner_name_reset" not in st.session_state:
                st.session_state.owner_name_reset = True
            if "document_id_reset" not in st.session_state:
                st.session_state.document_id_reset = True

        if st.button("📝 Generate New PRD"):
            reset_form()
            st.rerun()

if __name__ == "__main__":
    main()
