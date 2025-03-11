import streamlit as st
from maindoc import process_inputs, get_workflow
from utils import check_password, save_feedback

# Streamlit UI setup
st.set_page_config(page_title="Case Study Generator", layout="wide", page_icon="✍️")
# Setup sidebar with instructions and feedback form
def setup_sidebar():
    """Setup the sidebar with instructions and feedback form."""
    st.sidebar.header("✍️  Client Success Story Teller")
    st.sidebar.markdown(
        "This app helps you generate client success stories based on "
        "project description and consultant case study."
    )
    
    st.sidebar.write("### Instructions")
    st.sidebar.write(
        "1. :key: Enter password to access the app\n"
        "2. :pencil: Upload project desc and consultant case study\n"
        "3. :writing_hand: Generate a draft and refine it through feedback\n"
        "4. ⏳ Finalize the story and save it in your Google Doc\n"
    )

    # st.sidebar.write("### 🎧 Listen to our Podcast for more insights")

    # Feedback section
    if 'feedback' not in st.session_state:
        st.session_state.feedback = ""

    st.sidebar.markdown("---")
    st.sidebar.subheader("💭 Feedback")
    feedback = st.sidebar.text_area(
        "Share your thoughts",
        value=st.session_state.feedback,
        placeholder="Your feedback helps us improve..."
    )

    if st.sidebar.button("📤 Submit Feedback"):
        if feedback:
            try:
                save_feedback(feedback)
                st.session_state.feedback = ""
                st.sidebar.success("✨ Thank you for your feedback!")
            except Exception as e:
                st.sidebar.error(f"❌ Error saving feedback: {str(e)}")
        else:
            st.sidebar.warning("⚠️ Please enter feedback before submitting")

    st.sidebar.image("assets/bot01.jpg", use_container_width=True)



def main():
    """Main application function with improved document update workflow."""
    setup_sidebar()
    
    if not check_password():
        st.stop()
    
    st.title(" ✍️ Client Success Story Teller")
    
    # Initialize session state
    if 'draft' not in st.session_state:
        st.session_state.draft = None
    if 'feedback' not in st.session_state:
        st.session_state.feedback = None
    if 'confirmed' not in st.session_state:
        st.session_state.confirmed = False
    if 'doc_updated' not in st.session_state:
        st.session_state.doc_updated = False
    
    # File upload sections
    col1, col2 = st.columns(2)
    with col1:
        project_desc = st.file_uploader("Project Description", type=["pdf", "docx", "txt"])
    with col2:
        case_study = st.file_uploader("Consultant Case Study", type=["pdf", "docx", "txt"])
    
    # Additional materials
    additional_text = st.text_area("Additional Materials (optional)")
    
    # Generate button
    if st.button("✨ Generate client story draft"):
        with st.spinner('⚙️ Generating client story draft...'):
            if project_desc is not None and case_study is not None:
                # Reset confirmation status on new generation
                st.session_state.confirmed = False
                st.session_state.doc_updated = False
                
                # Process inputs and get workflow
                state = process_inputs(project_desc, case_study, additional_text)
                workflow = get_workflow()
                
                # Run workflow to generate initial draft
                result = workflow.invoke(state)
                st.session_state.draft = result["draft"]
                st.rerun()
            else:
                st.warning("Please upload both Project Description and Consultant Case Study files.")
    
    # Display draft and handle feedback
    if st.session_state.draft and not st.session_state.doc_updated:
        st.subheader("**📋 Client Success Story Draft:**")
        st.write(st.session_state.draft)
        
        # Feedback section if not confirmed
        if not st.session_state.confirmed:
            st.subheader("Feedback")
            feedback = st.text_area("Provide feedback for revision")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(":eyes: Request Revision"):
                    with st.spinner('⚙️ Regenerating client story draft...'):
                        if feedback:
                            # Update state with feedback and run workflow again
                            state = process_inputs(project_desc, case_study, additional_text)
                            state.draft = st.session_state.draft
                            state.feedback = feedback
                            workflow = get_workflow()
                            
                            result = workflow.invoke(state)
                            st.session_state.draft = result["draft"]
                            st.rerun()
                        else:
                            st.warning("Please provide feedback for revision.")
            
            with col2:
                if st.button(":ok_hand: Confirm and Save to Google Doc", type="secondary"):
                    st.session_state.confirmed = True
                    st.rerun()
        
        # If confirmed but not yet updated, show the update interface
        if st.session_state.confirmed:
            st.success("✅ Draft confirmed! Ready to save to Google doc.")
            
            if st.button("📚 Save to Google Doc Now", type="secondary"):
                with st.spinner("⏳ Saving finalized client story to Google doc..."):
                    # Process the confirmed state
                    state = process_inputs(
                        project_desc, 
                        case_study, 
                        additional_text, 
                        confirmed=True
                    )
                    state.draft = st.session_state.draft  # Ensure draft is carried over
                    
                    # Setup and run workflow with explicit doc update
                    workflow = get_workflow()
                    try:
                        # Create a complete state for Google Doc update
                        from maingmail import State
                        update_state = State(
                            project_desc=state.project_desc,
                            case_study=state.case_study,
                            additional_text=state.additional_text,
                            draft=st.session_state.draft,
                            confirmed=True
                        )

                        # Actually run the workflow with the update_state
                        result = workflow.invoke(update_state)
                        
                        # Update session state and rerun
                        st.session_state.doc_updated = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to save to Google Doc: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc(), language="python")
    
    # Display final confirmed and updated version
    if st.session_state.doc_updated:
        st.subheader("Final Client Success Story:")
        st.write(st.session_state.draft)
        st.success("✅ Client success story has been finalized and saved in Google doc!")
        
        if st.button("📝 Create New Client Success Story"):
            # Reset all states to start fresh
            st.session_state.draft = None
            st.session_state.feedback = None
            st.session_state.confirmed = False
            st.session_state.doc_updated = False
            st.rerun()

if __name__ == "__main__":
    main()