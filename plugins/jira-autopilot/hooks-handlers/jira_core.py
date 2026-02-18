#!/usr/bin/env python3
"""jira-autopilot core module — all business logic for hooks and commands."""

import json
import os
import re
import sys
import time
import math
import subprocess
from pathlib import Path
from datetime import datetime
from collections import Counter

# ── Constants ──────────────────────────────────────────────────────────────

CONFIG_NAME = "jira-autopilot.json"
LOCAL_CONFIG_NAME = "jira-autopilot.local.json"
GLOBAL_CONFIG_PATH = Path.home() / ".claude" / "jira-autopilot.global.json"
SESSION_NAME = "jira-session.json"
DEBUG_LOG_PATH = Path.home() / ".claude" / "jira-autopilot-debug.log"
MAX_LOG_SIZE = 1_000_000  # 1MB

READ_ONLY_TOOLS = frozenset([
    "Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch",
    "TodoRead", "NotebookRead", "AskUserQuestion",
])

BUG_SIGNALS = [
    "fix", "bug", "broken", "crash", "error", "fail",
    "regression", "not working", "issue with",
]
TASK_SIGNALS = [
    "add", "create", "implement", "build", "setup",
    "configure", "refactor", "update", "migrate",
]


# ── Config Loading ─────────────────────────────────────────────────────────

def load_config(root: str) -> dict:
    path = os.path.join(root, ".claude", CONFIG_NAME)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def load_local_config(root: str) -> dict:
    path = os.path.join(root, ".claude", LOCAL_CONFIG_NAME)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def load_global_config() -> dict:
    if GLOBAL_CONFIG_PATH.exists():
        with open(GLOBAL_CONFIG_PATH) as f:
            return json.load(f)
    return {}


def load_session(root: str) -> dict:
    path = os.path.join(root, ".claude", SESSION_NAME)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_session(root: str, data: dict):
    path = os.path.join(root, ".claude", SESSION_NAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_cred(root: str, field: str) -> str:
    """Load credential field with fallback: project-local -> global."""
    val = load_local_config(root).get(field, "")
    if not val:
        val = load_global_config().get(field, "")
    return val or ""


# ── Debug Logging ──────────────────────────────────────────────────────────

def debug_log(message: str, category: str = "general", enabled: bool = True,
              log_path: str = None, **kwargs):
    if not enabled:
        return
    path = Path(log_path) if log_path else DEBUG_LOG_PATH
    # Rotate if too large
    if path.exists() and path.stat().st_size > MAX_LOG_SIZE:
        backup = path.with_suffix(".log.1")
        if backup.exists():
            backup.unlink()
        path.rename(backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
    line = f"[{ts}] [{category}] {message}"
    if extra:
        line += f" {extra}"
    with open(path, "a") as f:
        f.write(line + "\n")


# ── CLI Dispatcher ─────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: jira_core.py <command> [args...]", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    commands = {
        "session-start": cmd_session_start,
        "log-activity": cmd_log_activity,
        "drain-buffer": cmd_drain_buffer,
        "session-end": cmd_session_end,
        "classify-issue": cmd_classify_issue,
        "suggest-parent": cmd_suggest_parent,
        "build-worklog": cmd_build_worklog,
        "debug-log": cmd_debug_log,
    }
    fn = commands.get(cmd)
    if not fn:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
    fn(args)


def cmd_debug_log(args):
    root = args[0] if args else "."
    msg = args[1] if len(args) > 1 else "test"
    cfg = load_config(root)
    debug_log(msg, enabled=cfg.get("debugLog", False))


# ── Commands ───────────────────────────────────────────────────────────────

OLD_CONFIG_NAMES = {
    "jira-tracker.json": CONFIG_NAME,
    "jira-tracker.local.json": LOCAL_CONFIG_NAME,
}


def _migrate_old_configs(root: str):
    """Rename old jira-tracker.* config files to jira-autopilot.*."""
    claude_dir = os.path.join(root, ".claude")
    if not os.path.isdir(claude_dir):
        return
    for old_name, new_name in OLD_CONFIG_NAMES.items():
        old_path = os.path.join(claude_dir, old_name)
        new_path = os.path.join(claude_dir, new_name)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            os.rename(old_path, new_path)
            debug_log(f"Migrated {old_name} → {new_name}", category="migration")


def _detect_issue_from_branch(root: str, cfg: dict) -> str | None:
    """Try to extract issue key from current git branch name."""
    pattern = cfg.get("branchPattern", "")
    project_key = cfg.get("projectKey", "")
    if not pattern or not project_key:
        return None
    # Replace {key} placeholder with actual project key
    pattern = pattern.replace("{key}", re.escape(project_key))
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=root, timeout=5,
        ).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    if not branch:
        return None
    m = re.search(pattern, branch)
    if m and m.groups():
        return m.group(1)
    return None


def cmd_session_start(args):
    root = args[0] if args else "."
    _migrate_old_configs(root)

    cfg = load_config(root)
    if not cfg.get("enabled", True):
        return

    existing = load_session(root)
    # If there's already an active session with issues, preserve it
    if existing.get("activeIssues"):
        # Update autonomy/accuracy from config in case it changed
        existing["autonomyLevel"] = cfg.get("autonomyLevel", "C")
        existing["accuracy"] = cfg.get("accuracy", 5)
        save_session(root, existing)
        debug_log(
            "Resuming existing session",
            category="session-start",
            enabled=cfg.get("debugLog", False),
            sessionId=existing.get("sessionId", ""),
        )
        return

    session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    session = {
        "sessionId": session_id,
        "autonomyLevel": cfg.get("autonomyLevel", "C"),
        "accuracy": cfg.get("accuracy", 5),
        "disabled": False,
        "activeIssues": {},
        "currentIssue": None,
        "lastParentKey": None,
        "workChunks": [],
        "pendingWorklogs": [],
        "activityBuffer": [],
    }

    # Detect issue from branch name
    branch_issue = _detect_issue_from_branch(root, cfg)
    if branch_issue:
        session["currentIssue"] = branch_issue
        session["activeIssues"][branch_issue] = {
            "startTime": int(time.time()),
            "totalSeconds": 0,
            "paused": False,
        }
        debug_log(
            f"Detected issue from branch: {branch_issue}",
            category="session-start",
            enabled=cfg.get("debugLog", False),
        )

    save_session(root, session)
    debug_log(
        "Session initialized",
        category="session-start",
        enabled=cfg.get("debugLog", False),
        root=root,
        sessionId=session_id,
    )


TOOL_TYPE_MAP = {
    "Edit": "file_edit",
    "Write": "file_write",
    "MultiEdit": "file_edit",
    "NotebookEdit": "file_edit",
    "Bash": "bash",
    "Task": "agent",
}


def cmd_log_activity(args):
    root = args[0] if args else "."
    tool_json_str = args[1] if len(args) > 1 else "{}"

    session = load_session(root)
    if not session:
        return

    try:
        tool_data = json.loads(tool_json_str)
    except json.JSONDecodeError:
        return

    tool_name = tool_data.get("tool_name", "")
    tool_input = tool_data.get("tool_input", {})

    # Skip read-only tools
    if tool_name in READ_ONLY_TOOLS:
        return

    activity_type = TOOL_TYPE_MAP.get(tool_name, "other")
    file_path = tool_input.get("file_path", "")
    command = tool_input.get("command", "")

    activity = {
        "timestamp": int(time.time()),
        "tool": tool_name,
        "type": activity_type,
        "issueKey": session.get("currentIssue"),
        "file": file_path,
    }
    if command:
        activity["command"] = command

    buffer = session.get("activityBuffer", [])
    buffer.append(activity)
    session["activityBuffer"] = buffer
    save_session(root, session)

    cfg = load_config(root)
    debug_log(
        f"tool={tool_name} file={file_path}",
        category="log-activity",
        enabled=cfg.get("debugLog", False),
        issueKey=session.get("currentIssue", ""),
    )


def _get_idle_threshold_seconds(cfg: dict) -> int:
    """Get idle threshold in seconds, scaled by accuracy."""
    accuracy = cfg.get("accuracy", 5)
    base = cfg.get("idleThreshold", 15)
    # High accuracy (8-10) → shorter threshold; low (1-3) → longer
    if accuracy >= 8:
        minutes = max(base // 3, 5)
    elif accuracy <= 3:
        minutes = base * 2
    else:
        minutes = base
    return minutes * 60


def _get_dir_cluster(file_path: str, depth: int = 2) -> str:
    """Extract directory cluster from file path up to given depth."""
    if not file_path:
        return ""
    parts = file_path.replace("\\", "/").split("/")
    # Return up to `depth` directory components
    dirs = [p for p in parts[:-1] if p]  # exclude filename
    return "/".join(dirs[:depth]) if dirs else ""


def _detect_context_switch(prev_activities: list, curr_activities: list,
                           accuracy: int) -> bool:
    """Check if file directory clusters shifted between two groups."""
    if not prev_activities or not curr_activities:
        return False

    prev_dirs = Counter(
        _get_dir_cluster(a.get("file", ""))
        for a in prev_activities if a.get("file")
    )
    curr_dirs = Counter(
        _get_dir_cluster(a.get("file", ""))
        for a in curr_activities if a.get("file")
    )
    if not prev_dirs or not curr_dirs:
        return False

    # Check overlap: if most common dirs differ, it's a switch
    prev_top = set(d for d, _ in prev_dirs.most_common(2))
    curr_top = set(d for d, _ in curr_dirs.most_common(2))
    overlap = prev_top & curr_top

    # High accuracy → any cluster change flags; low → need complete shift
    if accuracy >= 8:
        return len(overlap) == 0
    elif accuracy >= 4:
        return len(overlap) == 0 and len(prev_top) > 0 and len(curr_top) > 0
    else:
        # Low accuracy: only flag if completely different and enough activities
        return (len(overlap) == 0 and len(prev_activities) >= 3
                and len(curr_activities) >= 3)


def cmd_drain_buffer(args):
    root = args[0] if args else "."
    cfg = load_config(root)
    session = load_session(root)
    if not session:
        return

    buffer = session.get("activityBuffer", [])
    if not buffer:
        return

    idle_threshold = _get_idle_threshold_seconds(cfg)
    accuracy = cfg.get("accuracy", 5)
    chunks = session.get("workChunks", [])

    # Sort buffer by timestamp
    buffer.sort(key=lambda a: a.get("timestamp", 0))

    # Split buffer into groups on: idle gaps, issue key changes, dir cluster shifts
    groups = []
    current_group = [buffer[0]]

    for i in range(1, len(buffer)):
        prev = buffer[i - 1]
        curr = buffer[i]
        gap = curr.get("timestamp", 0) - prev.get("timestamp", 0)
        issue_changed = curr.get("issueKey") != prev.get("issueKey")

        # Detect directory cluster shift
        dir_shift = False
        prev_dir = _get_dir_cluster(prev.get("file", ""))
        curr_dir = _get_dir_cluster(curr.get("file", ""))
        if prev_dir and curr_dir and prev_dir != curr_dir:
            # Check if there's been a sustained shift (look back at recent group)
            recent_dirs = Counter(
                _get_dir_cluster(a.get("file", ""))
                for a in current_group if a.get("file")
            )
            if curr_dir not in recent_dirs and len(current_group) >= 2:
                dir_shift = True

        if gap > idle_threshold or issue_changed or dir_shift:
            groups.append({
                "activities": current_group,
                "idle_before": gap > idle_threshold,
                "idle_gap_seconds": gap if gap > idle_threshold else 0,
                "dir_shift": dir_shift,
            })
            current_group = [curr]
        else:
            current_group.append(curr)

    # Don't forget the last group
    groups.append({
        "activities": current_group,
        "idle_before": False,
        "idle_gap_seconds": 0,
        "dir_shift": False,
    })

    # Convert groups to work chunks
    for idx, group in enumerate(groups):
        activities = group["activities"]
        if not activities:
            continue

        start_time = activities[0].get("timestamp", 0)
        end_time = activities[-1].get("timestamp", 0)
        files_changed = list({
            a.get("file", "") for a in activities if a.get("file")
        })
        issue_key = activities[0].get("issueKey")

        idle_gaps = []
        if group["idle_before"] and group["idle_gap_seconds"] > 0:
            idle_gaps.append({
                "startTime": start_time - group["idle_gap_seconds"],
                "endTime": start_time,
                "seconds": group["idle_gap_seconds"],
            })

        # Check for context switch: either the dir_shift flag or heuristic
        needs_attribution = group.get("dir_shift", False)
        if not needs_attribution and idx > 0:
            prev_activities = groups[idx - 1]["activities"]
            needs_attribution = _detect_context_switch(
                prev_activities, activities, accuracy
            )

        chunk_id = f"chunk-{int(time.time())}-{idx}"
        chunk = {
            "id": chunk_id,
            "issueKey": issue_key,
            "startTime": start_time,
            "endTime": end_time,
            "activities": activities,
            "filesChanged": files_changed,
            "idleGaps": idle_gaps,
            "needsAttribution": needs_attribution,
        }
        chunks.append(chunk)

    session["workChunks"] = chunks
    session["activityBuffer"] = []
    save_session(root, session)

    debug_log(
        f"chunks={len(groups)} total_chunks={len(chunks)}",
        category="drain-buffer",
        enabled=cfg.get("debugLog", False),
    )

    # Output context switch info for Claude
    flagged = [c for c in chunks if c.get("needsAttribution")]
    if flagged:
        for c in flagged:
            files = ", ".join(c.get("filesChanged", [])[:5])
            print(f"[jira-autopilot] Context switch detected. "
                  f"Files: {files} → unattributed (issueKey={c['issueKey']})")


def classify_issue(summary: str, context: dict = None) -> dict:
    """Classify issue as Bug or Task from summary text and optional context."""
    lower = summary.lower()
    bug_score = sum(1 for s in BUG_SIGNALS if s in lower)
    task_score = sum(1 for s in TASK_SIGNALS if s in lower)

    if context:
        if context.get("new_files_created", 0) == 0 and context.get("files_edited", 0) > 0:
            bug_score += 1
        if context.get("new_files_created", 0) > 0:
            task_score += 1

    if bug_score >= 2 or (bug_score > task_score and bug_score >= 1):
        confidence = min(0.5 + bug_score * 0.15, 0.95)
        return {
            "type": "Bug",
            "confidence": confidence,
            "signals": [s for s in BUG_SIGNALS if s in lower],
        }

    confidence = min(0.5 + task_score * 0.15, 0.95)
    return {
        "type": "Task",
        "confidence": confidence,
        "signals": [s for s in TASK_SIGNALS if s in lower],
    }


def cmd_classify_issue(args):
    summary = args[0] if args else ""
    context_json = args[1] if len(args) > 1 else None
    context = json.loads(context_json) if context_json else None
    result = classify_issue(summary, context)
    print(json.dumps(result))


# Stubs — implemented in subsequent tasks
def cmd_session_end(args): pass
def cmd_suggest_parent(args): pass
def cmd_build_worklog(args): pass


if __name__ == "__main__":
    main()
