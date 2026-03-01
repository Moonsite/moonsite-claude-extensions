#!/usr/bin/env python3
"""jira_core.py — Core business logic for jira-autopilot v4."""

import base64
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

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


# ── Idle Threshold ─────────────────────────────────────────


def _get_idle_threshold(cfg):
    """Get idle threshold in seconds, scaled by accuracy."""
    base_minutes = cfg.get("idleThreshold", 15)
    accuracy = cfg.get("accuracy", 5)
    if accuracy >= 8:
        minutes = max(base_minutes / 3, 5)
    elif accuracy <= 3:
        minutes = base_minutes * 2
    else:
        minutes = base_minutes
    return int(minutes * 60)


# ── Issue Classification ──────────────────────────────────


def classify_issue(summary, context=None):
    """Classify a summary as Bug or Task with confidence.

    Returns: {type: "Bug"|"Task", confidence: float, signals: list[str]}
    """
    lower = summary.lower()
    bug_score = 0
    task_score = 0
    signals = []

    for signal in BUG_SIGNALS:
        if signal in lower:
            bug_score += 1
            signals.append(signal)

    for signal in TASK_SIGNALS:
        if signal in lower:
            task_score += 1
            signals.append(signal)

    # Context boosts
    if context:
        if context.get("new_files_created", 0) == 0 and context.get("files_edited", 0) > 0:
            bug_score += 1
        if context.get("new_files_created", 0) > 0:
            task_score += 1

    # Classification per spec 6.2
    if bug_score >= 2 or (bug_score > task_score and bug_score >= 1):
        issue_type = "Bug"
        score = bug_score
    else:
        issue_type = "Task"
        score = max(task_score, 1)

    confidence = min(0.5 + score * 0.15, 0.95)

    return {
        "type": issue_type,
        "confidence": confidence,
        "signals": signals,
    }


# ── Time Formatting ───────────────────────────────────────


def format_jira_time(seconds):
    """Format seconds into Jira time notation (e.g. '1h 30m').

    Minimum is '1m'. Zero seconds returns '1m'.
    """
    if seconds <= 0:
        return "1m"
    total_minutes = math.ceil(seconds / 60)
    if total_minutes < 1:
        total_minutes = 1
    hours = total_minutes // 60
    minutes = total_minutes % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "1m"


def _round_seconds(seconds, rounding_minutes, accuracy=5):
    """Round seconds up based on accuracy level.

    High accuracy (8+): granularity = max(rounding_minutes/15, 1) minutes
    Low accuracy (1-3): granularity = rounding_minutes * 2
    Mid (4-7): granularity = rounding_minutes
    Always round UP. Minimum one increment.
    """
    if accuracy >= 8:
        granularity_minutes = max(rounding_minutes / 15, 1)
    elif accuracy <= 3:
        granularity_minutes = rounding_minutes * 2
    else:
        granularity_minutes = rounding_minutes

    granularity_seconds = int(granularity_minutes * 60)
    if granularity_seconds <= 0:
        granularity_seconds = 60

    rounded = math.ceil(seconds / granularity_seconds) * granularity_seconds
    # Minimum one increment
    if rounded < granularity_seconds:
        rounded = granularity_seconds
    return rounded


# ── Worklog Building ──────────────────────────────────────


def build_worklog(root, issue_key):
    """Build a worklog entry from work chunks for a given issue.

    Returns: {issueKey, seconds, summary, rawFacts, [capped], logLanguage}
    """
    session = load_session(root)
    cfg = load_config(root)

    chunks = []
    sole_active = len(session.get("activeIssues", {})) <= 1

    for chunk in session.get("workChunks", []):
        if chunk.get("issueKey") == issue_key:
            chunks.append(chunk)
        elif chunk.get("issueKey") is None and sole_active:
            # Include null chunks when this is the sole active issue
            chunks.append(chunk)

    # Aggregate data
    all_files = []
    all_commands = []
    total_activities = 0
    total_seconds = 0

    for chunk in chunks:
        start = chunk.get("startTime", 0)
        end = chunk.get("endTime", 0)
        idle_gaps = chunk.get("idleGaps", [])
        idle_time = sum(g.get("seconds", 0) for g in idle_gaps)
        chunk_seconds = max(0, end - start - idle_time)
        total_seconds += chunk_seconds

        for f in chunk.get("filesChanged", []):
            if f not in all_files:
                all_files.append(f)

        for act in chunk.get("activities", []):
            total_activities += 1
            cmd = act.get("command", "")
            if cmd and cmd not in all_commands:
                all_commands.append(sanitize_for_log(cmd))

    capped = False
    if total_seconds > MAX_WORKLOG_SECONDS:
        total_seconds = MAX_WORKLOG_SECONDS
        capped = True

    # Build summary from file basenames
    basenames = list(dict.fromkeys(os.path.basename(f) for f in all_files))
    if basenames:
        if len(basenames) <= 8:
            summary = "Worked on " + ", ".join(basenames)
        else:
            shown = basenames[:8]
            summary = "Worked on " + ", ".join(shown) + f" +{len(basenames) - 8} more"
    else:
        summary = "Work on task"

    result = {
        "issueKey": issue_key,
        "seconds": total_seconds,
        "summary": summary,
        "rawFacts": {
            "files": all_files,
            "commands": all_commands,
            "activityCount": total_activities,
        },
        "logLanguage": cfg.get("logLanguage", "English"),
    }
    if capped:
        result["capped"] = True

    return result


# ── Command Implementations ───────────────────────────────


def cmd_session_start():
    """SessionStart hook handler."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    cfg = load_config(root)

    # If plugin is disabled, return silently
    if cfg.get("enabled") is False:
        return

    # If no config exists, return silently
    if not cfg:
        return

    session = load_session(root)

    if session:
        # Existing session — sync config values, prune stale, ensure structure
        session = _ensure_session_structure(session)
        if "autonomyLevel" in cfg:
            session["autonomyLevel"] = cfg["autonomyLevel"]
        if "accuracy" in cfg:
            session["accuracy"] = cfg["accuracy"]

        # Prune stale issues (>24h old, zero totalSeconds)
        now = int(time.time())
        active = session.get("activeIssues", {})
        to_prune = []
        for key, issue in active.items():
            age = now - issue.get("startTime", now)
            if age > STALE_ISSUE_SECONDS and issue.get("totalSeconds", 0) == 0:
                to_prune.append(key)
        for key in to_prune:
            del active[key]
            if session.get("currentIssue") == key:
                session["currentIssue"] = None

        save_session(root, session)
    else:
        # New session
        session = _new_session()
        if "autonomyLevel" in cfg:
            session["autonomyLevel"] = cfg["autonomyLevel"]
        if "accuracy" in cfg:
            session["accuracy"] = cfg["accuracy"]

        # Detect issue from git branch
        branch_pattern = cfg.get("branchPattern")
        if branch_pattern:
            try:
                branch = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
                match = re.search(branch_pattern, branch)
                if match:
                    issue_key = match.group(1)
                    session["currentIssue"] = issue_key
                    if issue_key not in session["activeIssues"]:
                        session["activeIssues"][issue_key] = {
                            "summary": f"From branch: {branch}",
                            "startTime": int(time.time()),
                            "totalSeconds": 0,
                            "paused": False,
                        }
            except (subprocess.CalledProcessError, OSError, IndexError):
                pass

        save_session(root, session)

    debug_log(f"session-start: session={session.get('sessionId')}", root)


def cmd_log_activity():
    """PostToolUse hook handler — log tool activity to buffer."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    cfg = load_config(root)

    # If disabled, skip
    if cfg.get("enabled") is False:
        return

    session = load_session(root)
    if not session:
        return

    if session.get("disabled"):
        return

    # Read tool JSON from stdin
    try:
        raw = sys.stdin.read()
        if not isinstance(raw, str):
            # Fallback for mock environments
            raw = sys.stdin.__class__.read()
        tool_data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        return

    tool_name = tool_data.get("tool_name", "")
    tool_input = tool_data.get("tool_input", {})

    # Skip read-only tools
    if tool_name in READ_ONLY_TOOLS:
        return

    # Extract file path
    file_path = (
        tool_input.get("file_path", "")
        or tool_input.get("path", "")
        or tool_input.get("pattern", "")
    )

    # Skip .claude/ directory writes
    if file_path and "/.claude/" in file_path:
        return

    # Determine activity type
    if tool_name in ("Edit", "MultiEdit"):
        activity_type = "file_edit"
    elif tool_name == "Write":
        activity_type = "file_write"
    elif tool_name == "Bash":
        activity_type = "bash"
    else:
        activity_type = "other"

    # Build command (for Bash tools)
    command = ""
    if tool_name == "Bash":
        command = sanitize_for_log(tool_input.get("command", ""))

    activity = {
        "timestamp": int(time.time()),
        "tool": tool_name,
        "type": activity_type,
        "issueKey": session.get("currentIssue"),
        "file": file_path,
        "command": command,
    }

    session["activityBuffer"].append(activity)
    save_session(root, session)

    debug_log(f"log-activity: tool={tool_name} file={file_path}", root)


def cmd_drain_buffer():
    """Stop hook handler — drain activity buffer into work chunks."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    cfg = load_config(root)
    session = load_session(root)

    if not session:
        return

    buffer = session.get("activityBuffer", [])
    if not buffer:
        save_session(root, session)
        return

    # Sort by timestamp
    buffer.sort(key=lambda a: a.get("timestamp", 0))

    idle_threshold = _get_idle_threshold(cfg)

    # Split into groups by idle gaps and issue key changes
    groups = []
    current_group = [buffer[0]]

    for i in range(1, len(buffer)):
        prev = buffer[i - 1]
        curr = buffer[i]
        gap = curr.get("timestamp", 0) - prev.get("timestamp", 0)
        issue_changed = curr.get("issueKey") != prev.get("issueKey")

        if gap > idle_threshold or issue_changed:
            groups.append(current_group)
            current_group = [curr]
        else:
            current_group.append(curr)

    groups.append(current_group)

    # Convert groups to work chunks
    new_chunks = []
    for group in groups:
        if not group:
            continue

        start_time = group[0].get("timestamp", 0)
        end_time = group[-1].get("timestamp", 0)
        issue_key = group[0].get("issueKey")

        # Collect unique files
        files_changed = []
        for act in group:
            f = act.get("file", "")
            if f and f not in files_changed:
                files_changed.append(f)

        chunk = {
            "id": f"chunk-{start_time}-{len(new_chunks)}",
            "issueKey": issue_key,
            "startTime": start_time,
            "endTime": end_time,
            "activities": group,
            "filesChanged": files_changed,
            "idleGaps": [],
            "needsAttribution": issue_key is None,
        }
        new_chunks.append(chunk)

    session["workChunks"].extend(new_chunks)
    session["activityBuffer"] = []
    save_session(root, session)

    debug_log(f"drain-buffer: created {len(new_chunks)} chunks from {len(buffer)} activities", root)


def cmd_session_end():
    """Finalize session: build worklogs, post to Jira, archive."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    session = load_session(root)
    if not session:
        return

    cfg = load_config(root)

    # Save session state first (local-first principle)
    save_session(root, session)

    active_issues = session.get("activeIssues", {})
    work_chunks = session.get("workChunks", [])

    # If no active issues, just archive
    if not active_issues:
        _archive_session(root, session)
        return

    # Build and post worklogs for each active issue with work
    for issue_key, issue_data in active_issues.items():
        total_seconds = issue_data.get("totalSeconds", 0)

        # Calculate time from work chunks if totalSeconds is 0
        if total_seconds <= 0:
            for chunk in work_chunks:
                if chunk.get("issueKey") == issue_key:
                    start = chunk.get("startTime", 0)
                    end = chunk.get("endTime", 0)
                    total_seconds += max(end - start, 0)

        if total_seconds <= 0:
            continue

        # Cap at max worklog seconds
        total_seconds = min(total_seconds, MAX_WORKLOG_SECONDS)

        # Build comment
        comment = _build_worklog_comment(issue_key, work_chunks)

        # Post worklog
        try:
            add_worklog(root, issue_key, total_seconds, comment=comment)
        except Exception:
            # On failure, save as pending worklog
            session.setdefault("pendingWorklogs", []).append({
                "issueKey": issue_key,
                "seconds": total_seconds,
                "comment": comment,
                "timestamp": int(time.time()),
            })

    # Save session with any pending worklogs
    save_session(root, session)

    # Archive the session
    _archive_session(root, session)


def cmd_post_worklogs():
    """Post pending worklogs from session state to Jira."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    session = load_session(root)
    if not session:
        print(json.dumps({"error": "No active session"}))
        return

    pending = session.get("pendingWorklogs", [])
    if not pending:
        print(json.dumps({"posted": 0, "remaining": 0}))
        return

    posted = 0
    failed = []

    for worklog in pending:
        issue_key = worklog.get("issueKey", "")
        seconds = worklog.get("seconds", 0)
        comment = worklog.get("comment", "")

        if not issue_key or seconds <= 0:
            continue

        try:
            result = add_worklog(root, issue_key, seconds, comment=comment)
            if result and "error" not in result:
                posted += 1
            else:
                failed.append(worklog)
        except Exception:
            failed.append(worklog)

    session["pendingWorklogs"] = failed
    save_session(root, session)

    print(json.dumps({"posted": posted, "remaining": len(failed)}))
    debug_log(f"post-worklogs: posted={posted} remaining={len(failed)}", root)


def cmd_pre_tool_use():
    """PreToolUse hook: inject issue key into git commit messages."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    # Read hook input from stdin
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Only activate for Bash tool
    if tool_name != "Bash":
        return

    command = tool_input.get("command", "")

    # Only activate for git commit commands
    if "git commit" not in command:
        return

    # Load session to get current issue
    session = load_session(root)
    if not session:
        return

    current_issue = session.get("currentIssue")
    if not current_issue:
        return

    # Check if the issue key is already in the commit message
    if current_issue in command:
        return

    # Emit systemMessage suggesting the issue key
    result = {
        "systemMessage": f"Include the Jira issue key '{current_issue}' in the commit message. "
                         f"Prefix the commit message with '{current_issue}: ' if not already present.",
    }
    print(json.dumps(result))


def cmd_user_prompt_submit():
    """UserPromptSubmit hook: output statusline with active issue and elapsed time."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    session = load_session(root)
    if not session:
        return

    current = session.get("currentIssue")
    if not current:
        return

    active_issues = session.get("activeIssues", {})
    issue_data = active_issues.get(current)
    if not issue_data:
        return

    # Calculate elapsed time since issue startTime
    start_time = issue_data.get("startTime", 0)
    if start_time <= 0:
        return

    elapsed = int(time.time()) - start_time
    if elapsed < 0:
        elapsed = 0

    # Format as "Xh Ym"
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    if hours > 0:
        time_str = f"{hours}h {minutes:02d}m"
    else:
        time_str = f"{minutes}m"

    statusline = {"iconLabel": f"{current} \u23f1 {time_str}"}
    print(json.dumps(statusline))


def cmd_classify_issue():
    """CLI wrapper for classify_issue — prints JSON to stdout."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    summary = sys.argv[3] if len(sys.argv) > 3 else ""
    result = classify_issue(summary)
    print(json.dumps(result))


def cmd_auto_create_issue():
    """CLI wrapper for _attempt_auto_create()."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    description = sys.argv[3] if len(sys.argv) > 3 else ""

    session = load_session(root)
    if not session:
        print(json.dumps({"error": "No active session"}))
        return

    cfg = load_config(root)
    result = _attempt_auto_create(root, description, session, cfg)
    print(json.dumps(result or {}))


def cmd_suggest_parent():
    """Suggest a parent issue for a new sub-task."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    session = load_session(root)
    if not session:
        print(json.dumps({"parentKey": None}))
        return

    # First check lastParentKey in session
    last_parent = session.get("lastParentKey")
    if last_parent:
        print(json.dumps({"parentKey": last_parent, "source": "session"}))
        return

    # Fall back to activeIssues keys
    active_issues = session.get("activeIssues", {})
    if active_issues:
        # Use the current issue if set, otherwise first active issue
        current = session.get("currentIssue")
        if current and current in active_issues:
            print(json.dumps({"parentKey": current, "source": "session"}))
            return
        first_key = next(iter(active_issues))
        print(json.dumps({"parentKey": first_key, "source": "session"}))
        return

    print(json.dumps({"parentKey": None}))


def cmd_build_worklog():
    """CLI wrapper for build_worklog — prints JSON to stdout."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    issue_key = sys.argv[3] if len(sys.argv) > 3 else None
    if not issue_key:
        print(json.dumps({"error": "Missing issue key"}))
        return
    result = build_worklog(root, issue_key)
    print(json.dumps(result))


def cmd_create_issue():
    """CLI wrapper for create_issue()."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    data = json.loads(sys.stdin.read())
    result = create_issue(
        root,
        project_key=data.get("projectKey", ""),
        summary=data.get("summary", ""),
        issue_type=data.get("issueType", "Task"),
        description=data.get("description", ""),
    )
    print(json.dumps(result))


def cmd_get_issue():
    """CLI wrapper for get_issue()."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    issue_key = sys.argv[3] if len(sys.argv) > 3 else ""
    result = get_issue(root, issue_key)
    print(json.dumps(result))


def cmd_add_worklog():
    """CLI wrapper for add_worklog()."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    data = json.loads(sys.stdin.read())
    result = add_worklog(
        root,
        issue_key=data.get("issueKey", ""),
        seconds=data.get("seconds", 0),
        comment=data.get("comment", ""),
    )
    print(json.dumps(result))


def cmd_get_projects():
    """CLI wrapper for jira_get_projects()."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    result = jira_get_projects(root)
    print(json.dumps(result))


def cmd_debug_log():
    """CLI wrapper for debug_log — log a message from the command line."""
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    # Message from argv or stdin
    if len(sys.argv) > 3:
        message = " ".join(sys.argv[3:])
    else:
        message = sys.stdin.read().strip()

    if message:
        debug_log(message, root)


# ── ADF Helpers ───────────────────────────────────────────


def _text_to_adf(text):
    """Convert plain text to Atlassian Document Format (ADF)."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": text},
                ],
            },
        ],
    }


# ── Jira REST API Client ─────────────────────────────────


def jira_request(root, method, path, body=None, max_retries=3):
    """Authenticated HTTP request to Jira REST API.

    Returns parsed JSON response dict. On error returns {"error": ...}.
    Retries on 429 (rate limited) with backoff.
    """
    base_url = get_cred(root, "baseUrl").rstrip("/")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")

    url = base_url + path
    auth_str = base64.b64encode(f"{email}:{api_token}".encode()).decode()

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Basic {auth_str}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req) as resp:
                resp_data = resp.read()
                if resp_data:
                    return json.loads(resp_data)
                return {}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                retry_after = 1
                try:
                    retry_after = int(e.headers.get("Retry-After", "1"))
                except (ValueError, TypeError, AttributeError):
                    pass
                time.sleep(retry_after)
                continue
            api_log(f"HTTP {e.code} {method} {path}")
            return {"error": f"HTTP {e.code}: {e.msg}"}
        except (urllib.error.URLError, OSError) as e:
            api_log(f"Network error {method} {path}: {e}")
            return {"error": str(e)}

    return {"error": "Max retries exceeded"}


def jira_get_projects(root):
    """Fetch all Jira projects with pagination. Returns list of {key, name}."""
    projects = []
    start_at = 0
    max_results = 50

    while True:
        try:
            result = jira_request(
                root, "GET",
                f"/rest/api/3/project/search?startAt={start_at}&maxResults={max_results}",
            )
        except Exception:
            return []

        if not result or "error" in result:
            if not projects:
                return []
            break

        values = result.get("values", [])
        for p in values:
            projects.append({"key": p["key"], "name": p["name"]})

        if result.get("isLast", True):
            break

        start_at += len(values)
        if not values:
            break

    return projects


def create_issue(root, project_key, summary, issue_type="Task", description="", parent_key=None):
    """Create a Jira issue. Returns API response dict with 'key' on success."""
    fields = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }

    if description:
        fields["description"] = _text_to_adf(description)

    if parent_key:
        fields["parent"] = {"key": parent_key}

    body = {"fields": fields}
    return jira_request(root, "POST", "/rest/api/3/issue", body=body)


def add_worklog(root, issue_key, seconds, comment=""):
    """Post a worklog entry to a Jira issue."""
    body = {
        "timeSpentSeconds": seconds,
    }

    if comment:
        body["comment"] = _text_to_adf(comment)

    return jira_request(root, "POST", f"/rest/api/3/issue/{issue_key}/worklog", body=body)


def get_issue(root, issue_key):
    """Fetch issue details from Jira."""
    return jira_request(root, "GET", f"/rest/api/3/issue/{issue_key}")


# ── Auto Issue Creation ───────────────────────────────────


def _attempt_auto_create(root, description, session, cfg):
    """Attempt to automatically create a Jira issue.

    Returns dict with key/type/parent on success, None or {} on skip.
    Respects autonomy level and autoCreate config flag.
    """
    autonomy = session.get("autonomyLevel", "C")
    auto_create = cfg.get("autoCreate", False)
    project_key = cfg.get("projectKey", "")

    # Cautious mode never auto-creates
    if autonomy == "C":
        return None

    # If autoCreate is disabled, don't create
    if not auto_create:
        return None

    # No project key means monitoring mode
    if not project_key:
        return None

    # Classify the issue
    classification = classify_issue(description)
    issue_type = classification["type"]

    # Get parent key from session context
    parent_key = session.get("lastParentKey")

    # Create the issue
    result = create_issue(
        root,
        project_key=project_key,
        summary=description,
        issue_type=issue_type,
        parent_key=parent_key,
    )

    if not result or "error" in result:
        return result

    # Return enriched result
    result["type"] = issue_type
    if parent_key:
        result["parent"] = parent_key

    return result


# ── Session End Helpers ───────────────────────────────────


def _build_worklog_comment(issue_key, work_chunks):
    """Build a summary comment from work chunks for an issue."""
    chunks = [c for c in work_chunks if c.get("issueKey") == issue_key]
    if not chunks:
        return "Work session"

    all_files = set()
    all_tools = set()
    for chunk in chunks:
        for f in chunk.get("files", chunk.get("filesChanged", [])):
            all_files.add(f)
        for act in chunk.get("activities", []):
            all_tools.add(act.get("tool", ""))

    parts = ["Work session:"]
    if all_files:
        parts.append(f"Files: {', '.join(sorted(all_files)[:5])}")
    if all_tools:
        parts.append(f"Tools: {', '.join(sorted(all_tools))}")

    return " ".join(parts)


def _archive_session(root, session):
    """Archive session to .claude/jira-sessions/<sessionId>.json."""
    session_id = session.get("sessionId", time.strftime("%Y%m%d-%H%M%S"))
    archive_dir = os.path.join(root, ".claude", "jira-sessions")
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(archive_dir, f"{session_id}.json")
    atomic_write_json(archive_path, session)


if __name__ == "__main__":
    main()
