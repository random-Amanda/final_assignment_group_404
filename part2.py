import subprocess
import os
import json
from pydriller import RepositoryMining  # Import RepositoryMining from PyDriller

# Paths and configuration
refminer_path = r"C:\MyWork\settup\RefactoringMiner\build\libs\RM-fat.jar"
repo_list_file = "project_links.txt"
clone_dir = "cloned_repos"
output_dir = "rminer-outputs"
os.makedirs(clone_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

# Increase Git buffer size for larger repositories
subprocess.run(["git", "config", "--global", "http.postBuffer", "524288000"])

# Read repository links
with open(repo_list_file, "r") as file:
    repo_urls = [line.strip() for line in file if line.strip()]

for repo_url in repo_urls:
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(clone_dir, repo_name)
    output_file = os.path.join(output_dir, f"{repo_name}_refactorings.json")
    commit_message_file = os.path.join(output_dir, f"{repo_name}_commit_messages.json")
    diff_output_file = os.path.join(output_dir, f"{repo_name}_commit_diffs.json")

    # Clone repository
    if not os.path.exists(repo_path):
        subprocess.run(["git", "clone", repo_url, repo_path])

    # Run RefactoringMiner and save results
    command = ["java", "-jar", refminer_path, "-a", repo_path, "-json", output_file]
    subprocess.run(command)

    # Load refactoring data and extract commit messages
    try:
        with open(output_file, "r", encoding="utf-8") as json_file:
            refactoring_data = json.load(json_file)
            commit_messages = []
            diffs = []

            for refactoring in refactoring_data.get("commits", []):
                commit_sha = refactoring.get("sha1")
                if commit_sha:
                    # Fetch commit message
                    commit_message_cmd = ["git", "-C", repo_path, "log", "--format=%B", "-n", "1", commit_sha]
                    commit_message_result = subprocess.run(commit_message_cmd, capture_output=True, text=True,
                                                           encoding='utf-8')

                    # Check if the command was successful
                    if commit_message_result.returncode != 0:
                        print(f"Error fetching commit message for {commit_sha}: {commit_message_result.stderr}")
                        commit_message = "Unknown commit message"  # Default value
                    else:
                        commit_message = commit_message_result.stdout.strip() or "Unknown commit message"

                    # Determine previous commit hash manually
                    previous_commit_command = ["git", "-C", repo_path, "rev-list", "--parents", "-n", "1", commit_sha]
                    previous_commit_result = subprocess.run(previous_commit_command, capture_output=True, text=True,
                                                            encoding='utf-8')

                    # Check if the command was successful
                    if previous_commit_result.returncode != 0:
                        print(f"Error fetching previous commit for {commit_sha}: {previous_commit_result.stderr}")
                        previous_commit_hash = None
                    else:
                        previous_commit_hash = previous_commit_result.stdout.split()[
                            1] if previous_commit_result.stdout else None

                    # Check if it's the first commit (no previous commit hash)
                    if previous_commit_hash is None:
                        first_commit_info = {
                            "commit hash": commit_sha,
                            "commit message": commit_message,
                            # "previous commit hash": "None (First commit)"
                        }
                        commit_messages.append(first_commit_info)
                    else:
                        commit_messages.append({
                            "commit hash": commit_sha,
                            "commit message": commit_message,
                            # "previous commit hash": previous_commit_hash
                        })

                    # Calculate diff data with PyDriller
                    for commit in RepositoryMining(repo_path, single=commit_sha).traverse_commits():
                        if commit.hash == commit_sha:
                            for modified_file in commit.modifications:
                                diff_data = {
                                    "commit hash": commit.hash,
                                    "previous commit hash": previous_commit_hash,
                                    "diff stats": {
                                        "file_path": modified_file.filename,
                                        "additions": modified_file.added,
                                        "deletions": modified_file.removed
                                    },
                                    "diff content": modified_file.diff  # Raw diff content for the file
                                }
                                diffs.append(diff_data)
                            break

            # Save commit messages to JSON file
            with open(commit_message_file, "w", encoding='utf-8') as cm_file:
                json.dump(commit_messages, cm_file, indent=4)

            # Save diff data to JSON file
            with open(diff_output_file, "w", encoding='utf-8') as diff_file:
                json.dump(diffs, diff_file, indent=4)

    except Exception as e:
        print(f"Error processing {repo_name}: {e}")

print("Refactoring, commit message, and commit diff data have been saved.")
