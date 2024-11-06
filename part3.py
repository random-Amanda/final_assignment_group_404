import os
import json
import math
from pydriller import RepositoryMining

# Paths and configuration for output directories
repo_list_file = "project_links.txt"
clone_dir = "cloned_repos"
output_dir = "rminer-outputs"
os.makedirs(clone_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

# Helper function to calculate metrics
def calculate_metrics(repo_path, commit_sha):
    metrics_data = []

    # Fetch the specific commit using RepositoryMining
    for commit in RepositoryMining(repo_path, single=commit_sha).traverse_commits():
        if commit.hash == commit_sha:
            for modified_file in commit.modifications:
                # Get all commits affecting this file
                file_commits = [
                    c for c in RepositoryMining(repo_path).traverse_commits()
                    if any(m.filename == modified_file.filename for m in c.modifications)
                ]

                # Calculate distinct authors and developers
                authors = set(c.author.name for c in file_commits for mod in c.modifications if mod.filename == modified_file.filename)

                metrics = {
                    "commit hash": commit.hash,
                    "file": modified_file.filename,
                    "COMM": len(file_commits),              # Number of commits for this file
                    "ADEV": len(authors),                   # Distinct authors
                    "DDEV": len(authors),                   # Distinct developers (same as authors)
                    "ADD": modified_file.added,
                    "DEL": modified_file.removed,
                    "OWN": 0,                               # Placeholder for OWN calculation
                    "MINOR": 0,                             # Minor contributors
                    "NADEV": 0,                             # Active developers on co-changed files
                    "NDDEV": 0,                             # Distinct developers for co-changed files
                    "NCOMM": 0,                             # Number of commits for co-changed files
                    "OEXP": 0,                              # Ownership experience
                    "EXP": 0                               # Geometric mean of experience
                }

                # Calculate OWN
                if modified_file.added > 0:  # Avoid division by zero
                    contributions = {
                        author: sum(
                            mod.added for c in file_commits for mod in c.modifications
                            if mod.filename == modified_file.filename and c.author.name == author
                        )
                        for author in authors
                    }
                    highest_contributor = max(contributions, key=contributions.get, default=None)
                    if highest_contributor:
                        metrics["OWN"] = (contributions[highest_contributor] / modified_file.added) * 100
                    else:
                        metrics["OWN"] = 0
                else:
                    metrics["OWN"] = 0  # If no lines were added, set OWN to 0

                # Calculate MINOR contributors (less than 5%)
                total_lines_added = sum(contributions.values())
                metrics["MINOR"] = sum(1 for contrib in contributions.values() if (contrib / total_lines_added) < 0.05)

                # Calculate NADEV, NDDEV, NCOMM, OEXP, EXP
                # For simplicity, assume all commits before the current commit are available for calculation
                # NADEV and NDDEV require checking co-changed files over the commit history

                # Calculate NADEV - active developers for co-changed files
                co_changed_authors = {
                    co_commit.author.name for co_commit in file_commits
                    if len(co_commit.modifications) > 1 and any(m.filename == modified_file.filename for m in co_commit.modifications)
                }
                metrics["NADEV"] = len(co_changed_authors)

                # Calculate NDDEV - distinct developers for co-changed files
                all_co_authors = set()
                for co_commit in file_commits:
                    if any(m.filename == modified_file.filename for m in co_commit.modifications):
                        all_co_authors.add(co_commit.author.name)
                metrics["NDDEV"] = len(all_co_authors)

                # Calculate NCOMM - number of commits for co-changed files
                co_change_commits = [
                    co_commit for co_commit in file_commits
                    if any(m.filename == modified_file.filename for m in co_commit.modifications) and len(co_commit.modifications) > 1
                ]
                metrics["NCOMM"] = len(co_change_commits)

                # Calculate OEXP - ownership experience of highest contributor
                if highest_contributor:
                    project_total_additions = sum(
                        mod.added for c in RepositoryMining(repo_path).traverse_commits() for mod in c.modifications
                    )
                    highest_contributor_additions = contributions[highest_contributor]
                    metrics["OEXP"] = (highest_contributor_additions / project_total_additions) * 100

                # Calculate EXP - geometric mean of experience for all developers
                author_experience = [
                    sum(1 for mod in c.modifications if mod.filename == modified_file.filename)
                    for c in RepositoryMining(repo_path).traverse_commits() for author in authors
                ]
                if author_experience:
                    exp_product = math.prod(author_experience)
                    metrics["EXP"] = exp_product ** (1 / len(author_experience)) if author_experience else 0

                # Append calculated metrics for each modified file in the commit
                metrics_data.append(metrics)
            break  # Exit after processing the specified commit
    return metrics_data

# Process each repository
with open(repo_list_file, "r") as file:
    repo_urls = [line.strip() for line in file if line.strip()]

for repo_url in repo_urls:
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(clone_dir, repo_name)
    output_file = os.path.join(output_dir, f"{repo_name}_refactorings.json")
    metrics_file = os.path.join(output_dir, f"{repo_name}_metrics.json")

    try:
        with open(output_file, "r", encoding="utf-8") as json_file:
            refactoring_data = json.load(json_file)
            metrics_results = []

            for refactoring in refactoring_data.get("commits", []):
                commit_sha = refactoring.get("sha1")
                if commit_sha:
                    metrics = calculate_metrics(repo_path, commit_sha)
                    metrics_results.extend(metrics)

            with open(metrics_file, "w", encoding='utf-8') as metrics_file_out:
                json.dump(metrics_results, metrics_file_out, indent=4)

    except Exception as e:
        print(f"Error processing {repo_name}: {e}")

print("Metrics data has been saved.")
