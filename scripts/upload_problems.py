#!/usr/bin/env python3
"""
Upload all MiniZinc problems from problems/ directory to the API
"""
import sys
import requests
from pathlib import Path

API_BASE = "http://localhost/api/solverdirector/v1"
PROBLEMS_DIR = Path(__file__).parent.parent / "problems"


def get_or_create_minizinc_group():
    """Get or create the minizinc group"""
    # Try to find existing
    response = requests.get(f"{API_BASE}/groups")
    if response.status_code == 200:
        for group in response.json():
            if group["name"] == "minizinc":
                return group["id"]

    # Create new
    response = requests.post(
        f"{API_BASE}/groups",
        json={"name": "minizinc", "description": "Minizinc formats"}
    )
    response.raise_for_status()
    return response.json()["id"]


def upload_problem_with_file(name, mzn_file, group_id):
    """Upload problem with .mzn file"""
    with open(mzn_file, 'rb') as f:
        response = requests.post(
            f"{API_BASE}/problems",
            data={"name": name, "group_id": group_id},
            files={"file": (mzn_file.name, f, "text/plain")}
        )
    response.raise_for_status()
    return response.json()["id"]


def upload_problem_without_file(name, group_id):
    """Upload self-contained problem (no file)"""
    response = requests.post(
        f"{API_BASE}/problems",
        data={"name": name, "group_id": group_id}
    )
    response.raise_for_status()
    return response.json()["id"]


def upload_instance(problem_id, dzn_file):
    """Upload instance file for a problem"""
    with open(dzn_file, 'rb') as f:
        response = requests.post(
            f"{API_BASE}/problems/{problem_id}/instances",
            files={"file": (dzn_file.name, f, "text/plain")}
        )
    response.raise_for_status()
    return response.json()["id"]


def process_directory(dir_path, group_id):
    """Process a single problem directory"""
    # Check if directory contains only .mzn, .dzn, LICENSE, and README files
    all_files = [f for f in dir_path.iterdir() if f.is_file()]
    for file in all_files:
        # Allow .mzn, .dzn, LICENSE, and README* files
        if file.suffix not in [".mzn", ".dzn"] and file.name != "LICENSE" and not file.name.startswith("README"):
            print(f"SKIP: {dir_path.name} (contains the following file which is not supported: {file.name})", file=sys.stderr)
            return

    mzn_files = list(dir_path.glob("*.mzn"))
    dzn_files = list(dir_path.glob("*.dzn"))

    problem_name = dir_path.name

    # Case 1: Single .mzn + .dzn files (instances need problem file)
    if len(mzn_files) == 1 and len(dzn_files) > 0:
        problem_id = upload_problem_with_file(problem_name, mzn_files[0], group_id)
        # Upload all .dzn files as instances
        for dzn_file in dzn_files:
            upload_instance(problem_id, dzn_file)

    # Case 2: Multiple .mzn files (self-contained instances)
    elif len(mzn_files) > 1 and len(dzn_files) == 0:
        problem_id = upload_problem_without_file(problem_name, group_id)
        # Upload all .mzn files as instances
        for mzn_file in mzn_files:
            upload_instance(problem_id, mzn_file)
    else:
        print(f"SKIP: {dir_path.name} (contains no dzn files or more than one mzn file and contains dzn files)", file=sys.stderr)

def main():
    try:
        group_id = get_or_create_minizinc_group()

        for dir_path in sorted(PROBLEMS_DIR.iterdir()):
            if not dir_path.is_dir():
                continue

            try:
                process_directory(dir_path, group_id)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 400 and "already exists" in e.response.text.lower():
                    print(f"SKIP: {dir_path.name} (problem already exists)", file=sys.stderr)
                else:
                    print(f"ERROR: {dir_path.name}: {e}", file=sys.stderr)
            except Exception as e:
                print(f"ERROR: {dir_path.name}: {e}", file=sys.stderr)

        print("Upload complete")

    except Exception as e:
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
