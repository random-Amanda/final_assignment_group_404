import os
import json
import math
import re
from pydriller import RepositoryMining
from javalang.parse import parse as javalang_parse
import git
from datetime import datetime, timedelta
import javalang


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
                if modified_file.filename.endswith('.java') and modified_file.source_code:
                    # Parse the file's source code with javalang for class-level analysis
                    tree = javalang_parse(modified_file.source_code)

                    # Initialize metric variables
                    ND, NS, NDEV, NUC, CEXP, REXP, OEXP, EXP = 0, 0, 0, 0, 0, 0, 0, 0
                    SEXP, CBO, WMC, RFC, ELOC, NOM, NOPM, DIT, NOC = 0, 0, 0, 0, 0, 0, 0, 0, 0
                    NOF, NOSF, NOPF, NOSM, NOSI, HsLCOM, C3, ComRead = 0, 0, 0, 0, 0, 0, 0, 0

                    # Process class and method details
                    for path, node in tree:
                        if isinstance(node, javalang.tree.ClassDeclaration):
                            # Metrics on class level
                            classes_in_file = [node]  # List of class declarations
                            NOM = len([m for m in node.methods])  # Number of methods
                            NOPM = len([m for m in node.methods if m.modifiers == 'public'])
                            NOF = len(node.fields)
                            NOSF = len([f for f in node.fields if 'static' in f.modifiers])
                            NOPF = len([f for f in node.fields if 'public' in f.modifiers])

                            # Compute depth of inheritance (DIT)
                            DIT = 1  # Assumes a flat hierarchy, could expand with class hierarchies

                            # Compute number of direct children (NOC) and Weighted Methods per Class (WMC)
                            # WMC = sum(m.cyclomatic_complexity for m in node.methods if m.body)
                            NOC = 0  # This would require analyzing inheritance across files

                            # ELOC (Effective Lines of Code)
                            ELOC = len([line for line in modified_file.source_code.splitlines() if line.strip()])

                            # RFC - Response for a Class: count methods + remote methods called recursively
                            RFC = NOM + len([call for m in node.methods for call in m.body if hasattr(call, 'method')])

                    # Calculate additional file-level metrics using the commit history
                    file_commits = [
                        c for c in RepositoryMining(repo_path).traverse_commits()
                        if any(m.filename == modified_file.filename for m in c.modifications)
                    ]
                    authors = set(c.author.name for c in file_commits)
                    NDEV = len(authors)

                    directories = {os.path.dirname(mod.filename) for mod in commit.modifications}
                    ND = len(directories)
                    subsystems = {os.path.dirname(mod.filename).split(os.sep)[0] for mod in commit.modifications}
                    NS = len(subsystems)

                    time_deltas = [(commit.committer_date - file_commit.committer_date).days
                                   for file_commit in file_commits if file_commit.hash != commit.hash]
                    AGE = sum(time_deltas) / len(time_deltas) if time_deltas else 0

                    FIX = bool(re.search(r'\b[A-Za-z]+-\d+\b', commit.msg))

                    NUC = len([c for c in RepositoryMining(repo_path).traverse_commits() if any(
                        m.filename == modified_file.filename for m in c.modifications)])

                    CEXP = sum(1 for c in file_commits if c.author.name == commit.author.name)

                    one_month_ago = datetime.now(commit.committer_date.tzinfo) - timedelta(days=30)
                    REXP = len([c for c in file_commits if
                                c.author.name == commit.author.name and c.committer_date > one_month_ago])

                    contributions = {
                        author: sum(mod.added for c in file_commits for mod in c.modifications if
                                    mod.filename == modified_file.filename and c.author.name == author)
                        for author in authors
                    }
                    highest_contributor = max(contributions, key=contributions.get, default=None)
                    project_total_additions = sum(
                        mod.added for c in RepositoryMining(repo_path).traverse_commits() for mod in c.modifications)
                    highest_contributor_additions = contributions[highest_contributor] if highest_contributor else 0
                    OEXP = (
                                       highest_contributor_additions / project_total_additions) * 100 if project_total_additions > 0 else 0

                    author_experience = [sum(1 for mod in c.modifications if mod.filename == modified_file.filename)
                                         for c in RepositoryMining(repo_path).traverse_commits() for author in authors]
                    exp_product = math.prod(author_experience) if author_experience else 0
                    EXP = exp_product ** (1 / len(author_experience)) if author_experience else 0

                    # Append calculated metrics for each modified file in the commit
                    metrics = {
                        "commit hash": commit.hash,
                        "file": modified_file.filename,
                        "SEXP": SEXP,
                        "CBO": CBO,
                        "WMC": WMC,
                        "RFC": RFC,
                        "ELOC": ELOC,
                        "NOM": NOM,
                        "NOPM": NOPM,
                        "DIT": DIT,
                        "NOC": NOC,
                        "NOF": NOF,
                        "NOSF": NOSF,
                        "NOPF": NOPF,
                        "NOSM": NOSM,
                        "NOSI": NOSI,
                        "HsLCOM": HsLCOM,
                        "C3": C3,
                        "ComRead": ComRead,
                        "ND": ND,
                        "NS": NS,
                        "AGE": AGE,
                        "FIX": FIX,
                        "NUC": NUC,
                        "CEXP": CEXP,
                        "REXP": REXP,
                        "OEXP": OEXP,
                        "EXP": EXP
                    }
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
