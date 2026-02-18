#!/usr/bin/env python3
"""jira-autopilot core module — all business logic for hooks and commands."""

import base64
import json
import os
import re
import sys
import time
import math
import subprocess
import urllib.request
import urllib.error
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
    "TaskList", "TaskGet", "ToolSearch", "Skill", "Task",
    "ListMcpResourcesTool", "BashOutput",
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
    # Allow override via env var (used by tests to avoid writing to global log)
    env_path = os.environ.get("JIRA_AUTOPILOT_DEBUG_LOG")
    path = Path(log_path) if log_path else (Path(env_path) if env_path else DEBUG_LOG_PATH)
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
        "post-worklogs": cmd_post_worklogs,
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
        # Always sync autonomy/accuracy from config (may have changed via /jira-setup)
        existing["autonomyLevel"] = cfg.get("autonomyLevel", "C")
        existing["accuracy"] = cfg.get("accuracy", 5)
        # Ensure activeTasks exists (may be missing in older sessions)
        existing.setdefault("activeTasks", {})
        # Assign sessionId if missing (sessions created by /jira-start may lack one)
        if not existing.get("sessionId"):
            existing["sessionId"] = datetime.now().strftime("%Y%m%d-%H%M%S")
        # Sanitize any credentials that may have been logged before the fix
        _sanitize_session_commands(existing)
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
        "activeTasks": {},
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

# Patterns to redact from logged bash commands
_SENSITIVE_PATTERNS = [
    # API tokens (Atlassian format: ATATT3x...)
    (re.compile(r'ATATT[A-Za-z0-9+/=_-]{20,}'), '[REDACTED_TOKEN]'),
    # Generic Bearer/Basic auth headers
    (re.compile(r'(Authorization:\s*(?:Basic|Bearer)\s+)\S+'), r'\1[REDACTED]'),
    # -u user:token patterns
    (re.compile(r'(-u\s+\S+:)\S+'), r'\1[REDACTED]'),
    # printf of email:token for base64
    (re.compile(r'(printf\s+["\'])[^"\']*[:@][^"\']*(["\'])'), r'\1[REDACTED]\2'),
    # apiToken values in JSON
    (re.compile(r'("apiToken"\s*:\s*")[^"]+(")', re.IGNORECASE), r'\1[REDACTED]\2'),
]


def _sanitize_command(command: str) -> str:
    """Remove credentials, tokens, and secrets from bash command strings."""
    if not command:
        return command
    for pattern, replacement in _SENSITIVE_PATTERNS:
        command = pattern.sub(replacement, command)
    return command



def _sanitize_session_commands(session: dict):
    """Retroactively sanitize commands in workChunks and activityBuffer."""
    for chunk in session.get("workChunks", []):
        for activity in chunk.get("activities", []):
            if activity.get("command"):
                activity["command"] = _sanitize_command(activity["command"])
    for activity in session.get("activityBuffer", []):
        if activity.get("command"):
            activity["command"] = _sanitize_command(activity["command"])


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
    tool_response = tool_data.get("tool_response", {})
    if not isinstance(tool_response, dict):
        tool_response = {}

    # Skip read-only tools
    if tool_name in READ_ONLY_TOOLS:
        return

    cfg = load_config(root)
    activity_type = TOOL_TYPE_MAP.get(tool_name, "other")
    file_path = tool_input.get("file_path", "")
    command = tool_input.get("command", "")

    # Skip writes to internal plugin state/config files — these are noise,
    # not user work, and may contain sensitive paths or credential data
    if file_path and "/.claude/" in file_path:
        return

    activity = {
        "timestamp": int(time.time()),
        "tool": tool_name,
        "type": activity_type,
        "issueKey": session.get("currentIssue"),
        "file": file_path,
    }
    if command:
        activity["command"] = _sanitize_command(command)

    buffer = session.get("activityBuffer", [])
    buffer.append(activity)
    session["activityBuffer"] = buffer

    # Track task start/completion for per-task time logging
    if tool_name in ("TaskCreate", "TaskUpdate"):
        _handle_task_event(root, session, tool_name, tool_input, tool_response, cfg)

    save_session(root, session)

    debug_log(
        f"tool={tool_name} file={file_path}",
        category="log-activity",
        enabled=cfg.get("debugLog", False),
        issueKey=session.get("currentIssue", ""),
    )


def _create_jira_issue(base_url: str, email: str, api_token: str,
                        project_key: str, summary: str, parent_key: str) -> "str | None":
    """Create a Jira sub-task under parent_key. Returns new issue key or None."""
    url = f"{base_url.rstrip('/')}/rest/api/3/issue"
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    payload = json.dumps({
        "fields": {
            "project": {"key": project_key},
            "parent": {"key": parent_key},
            "summary": summary,
            "issuetype": {"name": "Subtask"},
        }
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("key")
    except Exception:
        return None


def _log_task_time(root: str, session: dict, cfg: dict, subject: str, seconds: int):
    """Log time for a completed task to a sub-issue (accuracy>=8) or the parent issue."""
    accuracy = session.get("accuracy", cfg.get("accuracy", 5))
    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    current_issue = session.get("currentIssue")
    debug = cfg.get("debugLog", False)
    if not (base_url and email and api_token):
        return
    if accuracy >= 8 and current_issue:
        project_key = cfg.get("projectKey", current_issue.split("-")[0])
        new_key = _create_jira_issue(base_url, email, api_token, project_key, subject, current_issue)
        if new_key:
            post_worklog_to_jira(base_url, email, api_token, new_key, seconds, subject)
            debug_log(
                f"task='{subject}' created={new_key} logged={seconds}s",
                category="task-worklog",
                enabled=debug,
            )
            return
    if current_issue:
        post_worklog_to_jira(base_url, email, api_token, current_issue, seconds, subject)
        debug_log(
            f"task='{subject}' logged={seconds}s to {current_issue}",
            category="task-worklog",
            enabled=debug,
        )


def _handle_task_event(root: str, session: dict, tool_name: str,
                        tool_input: dict, tool_response: dict, cfg: dict):
    """Track task start/completion for per-task time logging."""
    resp = tool_response if isinstance(tool_response, dict) else {}
    task_id = str(resp.get("taskId") or tool_input.get("taskId", ""))
    subject = resp.get("subject", "")
    status = resp.get("status", "") or tool_input.get("status", "")
    if not task_id or not status:
        return
    active_tasks = session.setdefault("activeTasks", {})
    if status == "in_progress" and task_id not in active_tasks:
        active_tasks[task_id] = {
            "subject": subject,
            "startTime": int(time.time()),
            "jiraKey": None,
        }
    elif status == "completed" and task_id in active_tasks:
        task = active_tasks.pop(task_id)
        elapsed = int(time.time()) - task["startTime"]
        if elapsed >= 60:
            _log_task_time(root, session, cfg, task.get("subject") or subject, elapsed)


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


def build_worklog(root: str, issue_key: str) -> dict:
    """Build worklog summary from work chunks for an issue."""
    session = load_session(root)
    chunks = [
        c for c in session.get("workChunks", [])
        if c.get("issueKey") == issue_key
    ]

    all_files = []
    all_commands = []
    total_activities = 0
    total_seconds = 0

    for chunk in chunks:
        all_files.extend(chunk.get("filesChanged", []))
        for act in chunk.get("activities", []):
            total_activities += 1
            if act.get("command"):
                all_commands.append(_sanitize_command(act["command"]))

        start = chunk.get("startTime", 0)
        end = chunk.get("endTime", 0)
        chunk_time = end - start
        # Subtract idle gaps
        for gap in chunk.get("idleGaps", []):
            chunk_time -= gap.get("seconds", 0)
        total_seconds += max(chunk_time, 0)

    # Deduplicate files, keep just basenames for summary
    unique_files = list(dict.fromkeys(all_files))
    file_basenames = [os.path.basename(f) for f in unique_files if f]
    unique_commands = list(dict.fromkeys(all_commands))

    # Build human-readable summary
    parts = []
    if file_basenames:
        parts.append(f"Edited {', '.join(file_basenames[:5])}")
        if len(file_basenames) > 5:
            parts.append(f"and {len(file_basenames) - 5} more files")
    if unique_commands:
        cmd_str = ", ".join(unique_commands[:3])
        parts.append(f"Ran: {cmd_str}")
    parts.append(f"{total_activities} tool calls")
    summary = ". ".join(parts) + "."

    return {
        "issueKey": issue_key,
        "seconds": total_seconds,
        "summary": summary,
        "rawFacts": {
            "files": unique_files,
            "commands": unique_commands,
            "activityCount": total_activities,
        },
    }


def cmd_build_worklog(args):
    root = args[0] if args else "."
    issue_key = args[1] if len(args) > 1 else ""
    if not issue_key:
        print("{}", file=sys.stderr)
        return
    result = build_worklog(root, issue_key)
    print(json.dumps(result))


def _round_seconds(seconds: int, rounding_minutes: int, accuracy: int) -> int:
    """Round seconds to rounding_minutes increments, scaled by accuracy."""
    if seconds <= 0:
        return 0
    # High accuracy → finer rounding
    if accuracy >= 8:
        rounding = max(rounding_minutes // 15, 1)  # 1-min granularity
    elif accuracy <= 3:
        rounding = rounding_minutes * 2
    else:
        rounding = rounding_minutes
    rounding_secs = rounding * 60
    return max(math.ceil(seconds / rounding_secs) * rounding_secs, rounding_secs)


def cmd_session_end(args):
    root = args[0] if args else "."
    cfg = load_config(root)
    session = load_session(root)
    if not session:
        return

    autonomy = session.get("autonomyLevel", cfg.get("autonomyLevel", "C"))
    accuracy = session.get("accuracy", cfg.get("accuracy", 5))
    time_rounding = cfg.get("timeRounding", 15)
    debug = cfg.get("debugLog", False)

    # Drain any remaining activity buffer first
    buffer = session.get("activityBuffer", [])
    if buffer:
        cmd_drain_buffer(args)
        session = load_session(root)

    pending = session.get("pendingWorklogs", [])
    active_issues = session.get("activeIssues", {})

    for issue_key, issue_data in active_issues.items():
        worklog = build_worklog(root, issue_key)
        raw_seconds = worklog["seconds"]

        if raw_seconds <= 0:
            # Fallback to wallclock only when there's evidence of real activity.
            # Buffer has already been drained above, so check work chunks.
            # Without this guard, auto-detected branch issues with no actual work
            # would report the entire elapsed wall time (e.g. 42 hours).
            has_chunks = any(
                c.get("issueKey") == issue_key
                for c in session.get("workChunks", [])
            )
            start = issue_data.get("startTime", 0)
            if start > 0 and has_chunks:
                raw_seconds = int(time.time()) - start
            if raw_seconds <= 0:
                continue

        rounded = _round_seconds(raw_seconds, time_rounding, accuracy)

        entry = {
            "issueKey": issue_key,
            "seconds": rounded,
            "summary": worklog["summary"],
            "rawFacts": worklog["rawFacts"],
            "status": "pending" if autonomy == "C" else "approved",
        }
        pending.append(entry)

        debug_log(
            f"issue={issue_key} raw={raw_seconds}s rounded={rounded}s "
            f"autonomy={autonomy}",
            category="session-end",
            enabled=debug,
        )

    session["pendingWorklogs"] = pending

    # Archive session
    archive_dir = os.path.join(root, ".claude", "jira-sessions")
    os.makedirs(archive_dir, exist_ok=True)
    session_id = session.get("sessionId", datetime.now().strftime("%Y%m%d-%H%M%S"))
    archive_path = os.path.join(archive_dir, f"{session_id}.json")
    with open(archive_path, "w") as f:
        json.dump(session, f, indent=2)

    save_session(root, session)

    debug_log(
        f"Session ended, archived to {archive_path}",
        category="session-end",
        enabled=debug,
    )


def _text_to_adf(text: str) -> dict:
    """Convert plain text to Atlassian Document Format."""
    paragraphs = []
    for line in text.split("\n"):
        if line.strip():
            paragraphs.append(
                {"type": "paragraph", "content": [{"type": "text", "text": line}]}
            )
        else:
            paragraphs.append({"type": "paragraph", "content": []})
    return {"version": 1, "type": "doc", "content": paragraphs}


def post_worklog_to_jira(base_url: str, email: str, api_token: str,
                          issue_key: str, seconds: int, comment: str) -> bool:
    """POST a worklog entry to Jira Cloud REST API. Returns True on success."""
    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/worklog"
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    payload = json.dumps({
        "timeSpentSeconds": seconds,
        "comment": _text_to_adf(comment),
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        return False
    except Exception:
        return False


def cmd_post_worklogs(args):
    """Post all 'approved' pendingWorklogs to Jira, then mark them 'posted'."""
    root = args[0] if args else "."
    cfg = load_config(root)
    session = load_session(root)
    if not session:
        return

    debug = cfg.get("debugLog", False)

    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")

    if not (base_url and email and api_token):
        debug_log("No credentials — skipping worklog posting", category="post-worklogs", enabled=debug)
        return

    pending = session.get("pendingWorklogs", [])
    posted_any = False

    for entry in pending:
        if entry.get("status") != "approved":
            continue
        issue_key = entry.get("issueKey", "")
        seconds = entry.get("seconds", 0)
        summary = entry.get("summary", "")
        if not issue_key or seconds <= 0:
            continue

        ok = post_worklog_to_jira(base_url, email, api_token, issue_key, seconds, summary)
        entry["status"] = "posted" if ok else "failed"
        posted_any = True
        debug_log(
            f"issue={issue_key} seconds={seconds} status={entry['status']}",
            category="post-worklogs",
            enabled=debug,
        )
        if ok:
            print(f"[jira-autopilot] Logged {seconds//60}m to {issue_key}", flush=True)

    if posted_any:
        save_session(root, session)


def suggest_parent(root: str, summary: str) -> dict:
    """Suggest parent issues from session history and local config."""
    session = load_session(root)
    local = load_local_config(root)

    last_parent = session.get("lastParentKey")
    recent_parents = local.get("recentParents", [])

    recent = [{"key": k} for k in recent_parents]

    # Contextual search would require Jira API credentials.
    # Return empty contextual list — Claude fills via MCP instead.
    contextual = []

    return {
        "sessionDefault": last_parent,
        "contextual": contextual,
        "recent": recent,
    }


def cmd_suggest_parent(args):
    root = args[0] if args else "."
    summary = args[1] if len(args) > 1 else ""
    result = suggest_parent(root, summary)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
