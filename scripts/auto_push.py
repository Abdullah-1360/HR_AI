#!/usr/bin/env python3
import subprocess
import time
import random
import json
import os
import sys
import fcntl
from pathlib import Path

# Paths
REPO_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = REPO_DIR / "scripts" / ".pushed_history.json"
LOG_FILE = REPO_DIR / "scripts" / "auto_push.log"
LOCK_FILE = REPO_DIR / "scripts" / ".auto_push.lock"

# Files/folders to ignore explicitly
EXCLUDE_PATTERNS = [
    ".env",
    "auto_push.log",
    ".pushed_history.json",
    ".auto_push.lock",
    "__pycache__",
    ".venv",
    ".git"
]

def acquire_lock(lock_fd):
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False

def log(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")

def load_history():
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_history(history: set):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(history)), f, indent=2)

def run_cmd(cmd, cwd=REPO_DIR):
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, shell=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def get_eligible_files(history: set):
    code, out, err = run_cmd("git status -uall --porcelain")
    if code != 0 or not out:
        return []

    eligible = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        
        status_code = line[:2]
        file_path = line[2:].strip()
        
        if file_path.startswith('"') and file_path.endswith('"'):
            file_path = file_path[1:-1]

        # Check exclusions
        if any(pat in file_path for pat in EXCLUDE_PATTERNS):
            continue

        # Check history
        if file_path in history:
            continue

        # Ensure file actually exists (not deleted)
        full_path = REPO_DIR / file_path
        if os.path.exists(full_path) and os.path.isfile(full_path):
            eligible.append((file_path, status_code))

    return eligible

def generate_commit_message(file_path: str, status_code: str) -> str:
    path_obj = Path(file_path)
    filename = path_obj.name
    parent = path_obj.parent.name if path_obj.parent != Path(".") else ""
    scope = f"({parent})" if parent and parent != "." else ""
    
    ext = path_obj.suffix.lower()

    action = "add" if "??" in status_code or "A" in status_code else "update"

    if ext in [".md", ".txt"]:
        msg = f"docs{scope}: {action} {filename}"
    elif ext == ".py":
        if "test" in filename:
            msg = f"test{scope}: {action} {filename} unit test"
        else:
            msg = f"feat{scope}: {action} {filename} module"
    elif ext in [".yml", ".yaml", ".json", ".toml"]:
        msg = f"chore{scope}: {action} {filename} configuration"
    elif ext in [".css", ".html", ".js", ".ts", ".tsx"]:
        msg = f"style{scope}: {action} {filename} frontend component"
    else:
        msg = f"chore{scope}: {action} {filename}"

    return msg

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto push a single file to GitHub with state tracking.")
    # Default 270 minutes (4.5 hours) for 5-hour cron interval to randomize across full window
    parser.add_argument("--max-delay-minutes", type=int, default=270, help="Max random delay in minutes (default 270)")
    parser.add_argument("--no-delay", action="store_true", help="Skip random delay")
    args = parser.parse_args()

    # Prevent concurrent execution using file lock
    lock_fd = open(LOCK_FILE, "w")
    if not acquire_lock(lock_fd):
        log("Another instance of auto_push.py is already running. Exiting.")
        sys.exit(0)

    # 1. Random delay across the window (if enabled)
    if not args.no_delay and args.max_delay_minutes > 0:
        delay_seconds = random.randint(0, args.max_delay_minutes * 60)
        delay_min = round(delay_seconds / 60, 2)
        log(f"Sleeping for random delay of {delay_min} minutes ({delay_seconds} seconds)...")
        time.sleep(delay_seconds)

    log("Starting auto-push check...")

    history = load_history()
    eligible = get_eligible_files(history)

    if not eligible:
        log("No eligible unpushed files found.")
        return

    # Pick up to 3 files
    selected_files = eligible[:3]
    log(f"Selected files: {[f[0] for f in selected_files]}")

    for target_file, status_code in selected_files:
        commit_msg = generate_commit_message(target_file, status_code)
        log(f"Generated commit message for {target_file}: '{commit_msg}'")

        # Git stage
        code, out, err = run_cmd(f'git add "{target_file}"')
        if code != 0:
            log(f"Error staging {target_file}: {err}")
            continue

        # Git commit
        code, out, err = run_cmd(f'git commit -m "{commit_msg}"')
        if code != 0:
            log(f"Error committing {target_file}: {err}")
            continue

        history.add(target_file)

    # Get current branch
    code, branch, _ = run_cmd("git branch --show-current")
    if not branch:
        branch = "main"

    # Git push
    code, out, err = run_cmd(f'git push origin {branch}')
    if code != 0:
        log(f"Error pushing to GitHub: {err}")
        log("HINT: If seeing credential errors in cron, configure a GitHub Personal Access Token (PAT) or git credential store.")
        return

    log(f"Successfully pushed updates to GitHub on branch '{branch}'.")

    # Save to history ONLY after successful push
    save_history(history)

if __name__ == "__main__":
    main()
