import os
import streamlit as st
from github import Github
from github import Auth # Use this for token authentication
from github.GithubException import UnknownObjectException, GithubException

os.environ["GITHUB_TOKEN"] = st.secrets["general"]["GITHUB_TOKEN"]

try:
    # Using Auth.Token is the recommended way
    auth = Auth.Token(os.environ["GITHUB_TOKEN"])
    # Or legacy way: GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
except KeyError:
    print("ERROR: GITHUB_TOKEN environment variable not set.")
    print("Please set it before running the script.")
    exit(1)


def get_repo_python_files_content(token_auth, owner, repo_name, path="", recursive=False):
    """
    Connects to GitHub, gets python files from a repo path,
    and returns their combined content.
    """
    all_python_content = ""
    separator = "\n" + "="*20 + " FILE: {filename} " + "="*20 + "\n\n"

    try:
        # 1. Authenticate and get Github instance
        # Using the Auth object is preferred
        g = Github(auth=token_auth) 
        # Legacy way: g = Github(GITHUB_TOKEN)

        # print(f"Authenticated as: {g.get_user().login}")

        # 2. Get the repository
        repo_full_name = f"{owner}/{repo_name}"
        # print(f"Accessing repository: {repo_full_name}")
        repo = g.get_repo(repo_full_name)

        # --- File Listing and Filtering ---
        # print(f"Listing files in path: '{path if path else 'root'}' (Recursive: {recursive})")
        
        contents_to_process = []
        if recursive:
            # Get all contents recursively if needed
            tree = repo.get_git_tree(repo.default_branch, recursive=True)
            # Filter for blobs (files) within the desired path (if specified)
            # and ending with .py
            for element in tree.tree:
                 if element.type == 'blob' and \
                    element.path.endswith(".py") and \
                    (not path or element.path.startswith(path)):
                     # Need to get the full ContentFile object to read content easily
                     # This makes an extra API call per file, could be slow for many files.
                     # Consider getting blob content directly if performance is critical.
                     try:
                         contents_to_process.append(repo.get_contents(element.path))
                     except GithubException as e:
                         print(f"Warning: Could not get content for {element.path}. Error: {e}")

        else:
             # 3. List Files (non-recursive)
             contents = repo.get_contents(path)
             # 4. Filter for .py files
             contents_to_process = [
                 item for item in contents 
                 if item.type == "file" and item.name.endswith(".py")
             ]

        if not contents_to_process:
            print("No Python files found in the specified path.")
            return ""

        # print(f"Found {len(contents_to_process)} Python files.")

        # 5. Get file content and 6. Combine into a single string
        for content_file in contents_to_process:
            # print(f"  - Reading file: {content_file.path}")
            try:
                # Get decoded content directly
                file_content = content_file.decoded_content.decode('utf-8', errors='replace') 
                
                # Add separator and content
                all_python_content += separator.format(filename=content_file.path)
                all_python_content += file_content
            except Exception as e:
                print(f"Error reading or decoding file {content_file.path}: {e}")
                # Optionally add error info to the combined string
                # all_python_content += separator.format(filename=content_file.path)
                # all_python_content += f"*** ERROR READING FILE: {e} ***\n"


        # print("\nSuccessfully combined content from Python files.")
        return all_python_content.strip() # Remove leading/trailing whitespace

    except UnknownObjectException:
        print(f"ERROR: Repository '{repo_full_name}' not found or token lacks permissions.")
        return None
    except GithubException as e:
        print(f"ERROR: GitHub API error: {e.status} - {e.data.get('message', 'No message')}")
        # Consider checking for rate limiting: e.status == 403
        return None
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        return None
