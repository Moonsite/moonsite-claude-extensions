#!/usr/bin/env python3
"""jira_core.py — Core business logic for jira-autopilot v4."""

import json
import os
import re
import sys
import tempfile
import time

# ── Constants ──────────────────────────────────────────────

GLOBAL_CONFIG_PATH = os.path.expanduser("~/.claude/jira-autopilot.global.json")
DEBUG_LOG_PATH = os.path.expanduser("~/.claude/jira-autopilot-debug.log")
API_LOG_PATH = os.path.expanduser("~/.claude/jira-autopilot-api.log")
MAX_LOG_SIZE = 1_000_000  # 1MB
MAX_WORKLOG_SECONDS = 14400  # 4 hours
STALE_ISSUE_SECONDS = 86400  # 24 hours

READ_ONLY_TOOLS = {
    "Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch",
    "TodoRead", "NotebookRead", "AskUserQuestion", "TaskList",
    "TaskGet", "ToolSearch", "Skill", "Task", "ListMcpResourcesTool",
    "BashOutput",
}

PLANNING_SKILL_PATTERNS = ["plan", "brainstorm", "spec", "explore", "research"]
PLANNING_IMPL_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

BUG_SIGNALS = [
    "fix", "bug", "broken", "crash", "error", "fail",
    "regression", "not working", "issue with",
]
TASK_SIGNALS = [
    "implement", "add", "create", "build", "refactor",
    "update", "improve", "migrate", "setup", "configure",
]

CREDENTIAL_PATTERNS = [
    (r"ATATT3x[A-Za-z0-9_/+=.\-]+", "[REDACTED_TOKEN]"),
    (r"Bearer [A-Za-z0-9_/+=.\-]+", "Bearer [REDACTED]"),
    (r"Basic [A-Za-z0-9_/+=]+", "Basic [REDACTED]"),
    (r"-u [^:]+:[^ ]+", "-u [REDACTED]"),
    (r'"apiToken"\s*:\s*"[^"]+"', '"apiToken": "[REDACTED]"'),
]

# ── Logging ────────────────────────────────────────────────


def _rotate_log(path):
    """Rotate log file if it exceeds MAX_LOG_SIZE."""
    try:
        if os.path.exists(path) and os.path.getsize(path) > MAX_LOG_SIZE:
            backup = path + ".1"
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(path, backup)
    except OSError:
        pass


def sanitize_for_log(text):
    """Redact credentials from text."""
    if not isinstance(text, str):
        text = str(text)
    for pattern, replacement in CREDENTIAL_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def debug_log(message, root=None):
    """Write sanitized message to debug log."""
    cfg = {}
    if root:
        cfg = load_config(root)
    if not cfg.get("debugLog", True):
        return
    _rotate_log(DEBUG_LOG_PATH)
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        with open(DEBUG_LOG_PATH, "a") as f:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {sanitize_for_log(message)}\n")
    except OSError:
        pass


def api_log(message):
    """Write sanitized message to API log."""
    _rotate_log(API_LOG_PATH)
    try:
        os.makedirs(os.path.dirname(API_LOG_PATH), exist_ok=True)
        with open(API_LOG_PATH, "a") as f:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {sanitize_for_log(message)}\n")
    except OSError:
        pass


# ── Atomic File I/O ────────────────────────────────────────


def atomic_write_json(path, data):
    """Write JSON atomically: temp file -> fsync -> os.replace."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(path) or ".",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ── Config Loading ─────────────────────────────────────────


def load_config(root):
    """Load project config from .claude/jira-autopilot.json."""
    path = os.path.join(root, ".claude", "jira-autopilot.json")
    return _load_json(path)


def _load_json(path):
    """Load JSON file, returning {} on any error."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def get_cred(root, key):
    """Get credential with local -> global fallback."""
    local_path = os.path.join(root, ".claude", "jira-autopilot.local.json")
    local = _load_json(local_path)
    if local.get(key):
        return local[key]
    global_cfg = _load_json(GLOBAL_CONFIG_PATH)
    return global_cfg.get(key, "")


# ── Session Management ─────────────────────────────────────


def _new_session():
    """Create a fresh session structure with all required fields."""
    return {
        "sessionId": time.strftime("%Y%m%d-%H%M%S"),
        "autonomyLevel": "C",
        "accuracy": 5,
        "disabled": False,
        "activeIssues": {},
        "currentIssue": None,
        "lastParentKey": None,
        "workChunks": [],
        "pendingWorklogs": [],
        "pendingIssues": [],
        "activityBuffer": [],
        "activeTasks": {},
        "taskSubjects": {},
        "activePlanning": None,
        "lastWorklogTime": int(time.time()),
    }


def _ensure_session_structure(session):
    """Fill missing keys with defaults. Additive only."""
    defaults = _new_session()
    for key, value in defaults.items():
        if key not in session:
            session[key] = value
    return session


def load_session(root):
    """Load session state, ensuring all required fields exist."""
    path = os.path.join(root, ".claude", "jira-session.json")
    session = _load_json(path)
    if session:
        session = _ensure_session_structure(session)
    return session


def save_session(root, session):
    """Save session state atomically."""
    path = os.path.join(root, ".claude", "jira-session.json")
    atomic_write_json(path, session)


# ── CLI Dispatcher (stub — expanded in later tasks) ────────


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: jira_core.py <command> [args...]"}))
        sys.exit(1)

    commands = {
        "session-start": cmd_session_start,
        "log-activity": cmd_log_activity,
        "drain-buffer": cmd_drain_buffer,
        "session-end": cmd_session_end,
        "post-worklogs": cmd_post_worklogs,
        "pre-tool-use": cmd_pre_tool_use,
        "user-prompt-submit": cmd_user_prompt_submit,
        "classify-issue": cmd_classify_issue,
        "auto-create-issue": cmd_auto_create_issue,
        "suggest-parent": cmd_suggest_parent,
        "build-worklog": cmd_build_worklog,
        "create-issue": cmd_create_issue,
        "get-issue": cmd_get_issue,
        "add-worklog": cmd_add_worklog,
        "get-projects": cmd_get_projects,
        "debug-log": cmd_debug_log,
    }

    cmd = sys.argv[1]
    if cmd not in commands:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
        sys.exit(1)

    commands[cmd]()


# ── Command stubs ──────────────────────────────────────────


def cmd_session_start():
    pass


def cmd_log_activity():
    pass


def cmd_drain_buffer():
    pass


def cmd_session_end():
    pass


def cmd_post_worklogs():
    pass


def cmd_pre_tool_use():
    pass


def cmd_user_prompt_submit():
    pass


def cmd_classify_issue():
    pass


def cmd_auto_create_issue():
    pass


def cmd_suggest_parent():
    pass


def cmd_build_worklog():
    pass


def cmd_create_issue():
    pass


def cmd_get_issue():
    pass


def cmd_add_worklog():
    pass


def cmd_get_projects():
    pass


def cmd_debug_log():
    pass


if __name__ == "__main__":
    main()
