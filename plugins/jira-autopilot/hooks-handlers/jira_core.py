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
import tempfile
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
API_LOG_PATH = Path.home() / ".claude" / "jira-autopilot-api.log"
MAX_LOG_SIZE = 1_000_000  # 1MB
MAX_WORKLOG_SECONDS = 14400  # 4 hours — sanity cap for a single worklog
STALE_ISSUE_SECONDS = 86400  # 24 hours — threshold for stale issue cleanup

READ_ONLY_TOOLS = frozenset([
    "Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch",
    "TodoRead", "NotebookRead", "AskUserQuestion",
    "TaskList", "TaskGet", "ToolSearch", "Skill", "Task",
    "ListMcpResourcesTool", "BashOutput",
])

# Skill names containing these substrings are treated as planning activities.
PLANNING_SKILL_PATTERNS = frozenset(["plan", "brainstorm", "spec", "explore", "research"])

# First file-write tool after plan mode ends planning automatically.
PLANNING_IMPL_TOOLS = frozenset(["Edit", "Write", "MultiEdit", "NotebookEdit"])

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
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            debug_log(f"Corrupt session file, resetting: {e}", category="session-load")
            return {}
    return {}


def save_session(root: str, data: dict):
    path = os.path.join(root, ".claude", SESSION_NAME)
    dir_path = os.path.dirname(path)
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_cred(root: str, field: str) -> str:
    """Load credential field with fallback: project-local -> global."""
    val = load_local_config(root).get(field, "")
    if not val:
        val = load_global_config().get(field, "")
    return val or ""


def get_log_language(root: str) -> str:
    """Return the configured worklog language. Project config overrides global default."""
    lang = load_config(root).get("logLanguage", "")
    if not lang:
        lang = load_global_config().get("logLanguage", "")
    return lang or "English"


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


def _log_api_call(method: str, path: str, status: int, elapsed_ms: int,
                  detail: str = "", log_path: str = None):
    """Always-on API call logger. Writes to ~/.claude/jira-autopilot-api.log."""
    env_path = os.environ.get("JIRA_AUTOPILOT_API_LOG")
    p = Path(log_path) if log_path else (Path(env_path) if env_path else API_LOG_PATH)
    # Rotate if too large
    if p.exists() and p.stat().st_size > MAX_LOG_SIZE:
        backup = p.with_suffix(".log.1")
        if backup.exists():
            backup.unlink()
        p.rename(backup)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [api] {method} {path} status={status} time={elapsed_ms}ms"
    if detail:
        line += f" {detail}"
    with open(p, "a") as f:
        f.write(line + "\n")


# ── AI Enrichment ─────────────────────────────────────────────────────

def _enrich_summary_via_ai(raw_facts: dict, language: str, api_key: str) -> str:
    """Call Anthropic API (Haiku) to produce a concise worklog description.

    Returns enriched text or "" on any failure.
    """
    files = raw_facts.get("files", [])
    commands = raw_facts.get("commands", [])
    activity_count = raw_facts.get("activityCount", 0)

    file_basenames = [os.path.basename(f) for f in files if f][:10]
    cmd_list = commands[:5]

    facts_text = (
        f"Files: {', '.join(file_basenames) if file_basenames else 'none'}\n"
        f"Commands: {', '.join(cmd_list) if cmd_list else 'none'}\n"
        f"Activity count: {activity_count}"
    )

    prompt = (
        f"Write a concise Jira worklog description (1-2 sentences, max 120 chars) "
        f"in {language} summarizing the work done. "
        f"Use professional tone, no markdown, no bullet points.\n\n"
        f"Facts:\n{facts_text}"
    )

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 150,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload, method="POST",
    )
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("Content-Type", "application/json")

    start_ts = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed_ms = int((time.time() - start_ts) * 1000)
            data = json.loads(resp.read())
            text = data.get("content", [{}])[0].get("text", "").strip()
            _log_api_call("POST", "/v1/messages", resp.status, elapsed_ms,
                          f"model=haiku chars={len(text)}")
            return text
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("POST", "/v1/messages", e.code, elapsed_ms,
                      f"error={e.reason}")
        return ""
    except Exception as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("POST", "/v1/messages", 0, elapsed_ms,
                      f"error={type(e).__name__}")
        return ""


def _maybe_enrich_worklog_summary(root: str, raw_facts: dict, fallback_summary: str) -> str:
    """Enrich worklog summary via AI if anthropicApiKey is configured.

    Returns fallback_summary if no key or on API failure.
    """
    api_key = get_cred(root, "anthropicApiKey")
    if not api_key:
        return fallback_summary
    language = get_log_language(root)
    enriched = _enrich_summary_via_ai(raw_facts, language, api_key)
    return enriched if enriched else fallback_summary


# ── CLI Dispatcher ─────────────────────────────────────────────────────────

def cmd_create_issue(args):
    """Create a Jira issue via REST API. Prints the new issue key on success.

    Usage: jira_core.py create-issue <root> --project KEY --summary TEXT
           [--type Task|Bug|Story|Subtask] [--parent KEY]
           [--account-id ID] [--cloud-id ID] [--labels l1,l2]
    """
    root = args[0] if args else "."
    # Parse flags
    params = {}
    i = 1
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            params[args[i][2:]] = args[i + 1]
            i += 2
        else:
            i += 1

    project_key = params.get("project", "")
    summary = params.get("summary", "")
    issue_type = params.get("type", "Task")
    parent_key = params.get("parent", "")
    assignee_id = params.get("account-id", "")
    labels_raw = params.get("labels", "")
    labels = [l.strip() for l in labels_raw.split(",") if l.strip()] if labels_raw else []

    if not project_key or not summary:
        print("Error: --project and --summary are required", file=sys.stderr)
        sys.exit(1)

    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    if not (base_url and email and api_token):
        print("Error: missing credentials in jira-autopilot.local.json", file=sys.stderr)
        sys.exit(1)

    url = f"{base_url.rstrip('/')}/rest/api/3/issue"
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    fields: dict = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }
    if parent_key:
        fields["parent"] = {"key": parent_key}
    if assignee_id:
        fields["assignee"] = {"id": assignee_id}
    if labels:
        fields["labels"] = labels

    payload = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    start_ts = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed_ms = int((time.time() - start_ts) * 1000)
            data = json.loads(resp.read())
            key = data.get("key", "")
            _log_api_call("POST", "/rest/api/3/issue", resp.status, elapsed_ms,
                          f"key={key}")
            print(json.dumps({"key": key, "id": data.get("id", "")}))
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        body = e.read().decode(errors="replace")
        _log_api_call("POST", "/rest/api/3/issue", e.code, elapsed_ms,
                      f"error={e.reason}")
        debug_log(f"create-issue HTTP {e.code} {e.reason}: {body[:200]}",
                  category="jira-api")
        print(f"Error: HTTP {e.code} {e.reason}: {body[:200]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("POST", "/rest/api/3/issue", 0, elapsed_ms,
                      f"error={type(e).__name__}")
        debug_log(f"create-issue error: {e}", category="jira-api")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_get_issue(args):
    """Fetch a Jira issue by key via REST API. Prints JSON with key/summary/status/type.

    Usage: jira_core.py get-issue <root> <ISSUE-KEY>
    """
    root = args[0] if args else "."
    issue_key = args[1] if len(args) > 1 else ""
    if not issue_key:
        print("Error: issue key required", file=sys.stderr)
        sys.exit(1)

    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    if not (base_url and email and api_token):
        print("Error: missing credentials", file=sys.stderr)
        sys.exit(1)

    url = (f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}"
           "?fields=summary,status,issuetype,parent,assignee")
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Accept", "application/json")
    api_path = f"/rest/api/3/issue/{issue_key}"
    start_ts = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed_ms = int((time.time() - start_ts) * 1000)
            data = json.loads(resp.read())
            fields = data.get("fields", {})
            _log_api_call("GET", api_path, resp.status, elapsed_ms,
                          f"key={issue_key}")
            print(json.dumps({
                "key": data.get("key"),
                "summary": fields.get("summary"),
                "status": fields.get("status", {}).get("name"),
                "type": fields.get("issuetype", {}).get("name"),
                "parent": fields.get("parent", {}).get("key") if fields.get("parent") else None,
            }))
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("GET", api_path, e.code, elapsed_ms, f"error={e.reason}")
        debug_log(f"get-issue HTTP {e.code} {e.reason}", category="jira-api")
        print(f"Error: HTTP {e.code} {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("GET", api_path, 0, elapsed_ms, f"error={type(e).__name__}")
        debug_log(f"get-issue error: {e}", category="jira-api")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_add_worklog(args):
    """Add a worklog to a Jira issue via REST API.

    Usage: jira_core.py add-worklog <root> <ISSUE-KEY> <seconds> [comment]
    """
    root = args[0] if args else "."
    issue_key = args[1] if len(args) > 1 else ""
    seconds = int(args[2]) if len(args) > 2 else 0
    comment = args[3] if len(args) > 3 else ""
    if not issue_key or seconds <= 0:
        print("Error: issue key and seconds required", file=sys.stderr)
        sys.exit(1)

    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    if not (base_url and email and api_token):
        print("Error: missing credentials", file=sys.stderr)
        sys.exit(1)

    ok = post_worklog_to_jira(base_url, email, api_token, issue_key, seconds, comment,
                              language=get_log_language(root))
    if ok:
        print(json.dumps({"ok": True, "issue": issue_key, "seconds": seconds}))
    else:
        print("Error: worklog post failed", file=sys.stderr)
        sys.exit(1)


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
        "auto-create-issue": cmd_auto_create_issue,
        "suggest-parent": cmd_suggest_parent,
        "build-worklog": cmd_build_worklog,
        "debug-log": cmd_debug_log,
        # REST API commands (no curl dependency)
        "create-issue": cmd_create_issue,
        "get-issue": cmd_get_issue,
        "add-worklog": cmd_add_worklog,
        "get-projects": cmd_get_projects,
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
    debug_log(f"Branch detection: branch={branch!r} pattern={pattern!r}",
              category="session-start")
    m = re.search(pattern, branch)
    if m and m.groups():
        return m.group(1)
    debug_log(f"Branch detection: no match for branch={branch!r}",
              category="session-start")
    return None


def _resolve_autonomy(session: dict, cfg: dict) -> str:
    """Return autonomy letter A/B/C from session or config (handles numeric 1-10 too)."""
    raw = session.get("autonomyLevel") or cfg.get("autonomyLevel", "C")
    if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
        n = int(raw)
        if n == 10:
            return "A"
        elif n >= 6:
            return "B"
        else:
            return "C"
    return str(raw).upper() if str(raw).upper() in ("A", "B", "C") else "C"


def extract_summary_from_prompt(prompt: str) -> str:
    """Extract a clean issue summary from a user prompt.

    Strips leading noise verbs, takes the first sentence, capitalizes,
    and truncates to 80 chars.
    """
    if not prompt:
        return ""
    # Take first sentence
    first = re.split(r'[.!?\n]', prompt.strip())[0].strip()
    # Strip leading noise phrases (case-insensitive)
    noise = r'^(?:please\s+|can you\s+|could you\s+|i need to\s+|i need you to\s+|i want to\s+|help me\s+|let\'s\s+|let me\s+)+'
    first = re.sub(noise, '', first, flags=re.IGNORECASE).strip()
    if not first:
        return ""
    # Capitalize first letter
    first = first[0].upper() + first[1:]
    return first[:80]


def _is_duplicate_issue(session: dict, summary: str) -> "str | None":
    """Return existing issue key if token overlap with summary exceeds 60%, else None."""
    if not summary:
        return None
    summary_tokens = set(re.findall(r'\w+', summary.lower()))
    if not summary_tokens:
        return None
    for key, data in session.get("activeIssues", {}).items():
        existing = data.get("summary", "")
        if not existing:
            continue
        existing_tokens = set(re.findall(r'\w+', existing.lower()))
        if not existing_tokens:
            continue
        overlap = len(summary_tokens & existing_tokens) / len(summary_tokens | existing_tokens)
        if overlap >= 0.60:
            return key
    return None


def _get_recent_commit_messages(root: str, n: int = 5) -> list:
    """Return last N git commit messages, empty list on any failure."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{n}"],
            capture_output=True, text=True, cwd=root, timeout=5,
        )
        if result.returncode != 0:
            return []
        lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        # Strip the short hash prefix (7 hex chars + space)
        messages = [re.sub(r'^[0-9a-f]{7,}\s+', '', line) for line in lines]
        return [m for m in messages if m]
    except Exception:
        return []


def _attempt_auto_create(root: str, summary: str, session: dict, cfg: dict) -> "dict | None":
    """Try to auto-create a Jira issue. Returns result dict or None on failure/skip."""
    autonomy = _resolve_autonomy(session, cfg)
    if autonomy == "C":
        return None
    if not cfg.get("autoCreate", False):
        return None

    # Check credentials
    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    if not (base_url and email and api_token):
        return None

    clean_summary = extract_summary_from_prompt(summary)
    if not clean_summary:
        return None

    # Check duplicate
    dup_key = _is_duplicate_issue(session, clean_summary)
    if dup_key:
        return {"key": dup_key, "summary": clean_summary, "duplicate": True}

    # Classify and check confidence
    classification = classify_issue(clean_summary)
    if classification.get("confidence", 0) < 0.65:
        return None

    project_key = cfg.get("projectKey", "")
    if not project_key:
        return None

    # Infer parent
    parent_key = (
        session.get("lastParentKey")
        or session.get("currentIssue")
        or None
    )

    issue_type = classification.get("type", "Task")
    url = f"{base_url.rstrip('/')}/rest/api/3/issue"
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    fields: dict = {
        "project": {"key": project_key},
        "summary": clean_summary,
        "issuetype": {"name": issue_type},
    }
    if parent_key:
        fields["parent"] = {"key": parent_key}

    payload = json.dumps({"fields": fields}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    start_ts = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed_ms = int((time.time() - start_ts) * 1000)
            data = json.loads(resp.read())
            new_key = data.get("key", "")
            _log_api_call("POST", "/rest/api/3/issue", resp.status, elapsed_ms,
                          f"auto-create key={new_key}")
            if not new_key:
                return None
    except Exception as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("POST", "/rest/api/3/issue", 0, elapsed_ms,
                      f"auto-create error={type(e).__name__}")
        debug_log(f"auto-create error: {e}", category="auto-create")
        return None

    # Update session
    session["activeIssues"][new_key] = {
        "startTime": int(time.time()),
        "totalSeconds": 0,
        "paused": False,
        "summary": clean_summary,
    }
    session["currentIssue"] = new_key
    # Retroactively claim work done before this issue was known
    claimed = _claim_null_chunks(session, new_key)
    if claimed > 0:
        debug_log(
            f"auto-create retroactively claimed {claimed} null chunks for {new_key}",
            category="auto-create",
            enabled=cfg.get("debugLog", False),
        )
    if parent_key:
        session["lastParentKey"] = parent_key
    save_session(root, session)

    debug_log(
        f"auto-created key={new_key} type={issue_type} parent={parent_key} "
        f"summary={clean_summary!r} autonomy={autonomy}",
        category="auto-create",
        enabled=cfg.get("debugLog", False),
    )

    return {
        "key": new_key,
        "summary": clean_summary,
        "type": issue_type,
        "parent": parent_key,
        "duplicate": False,
    }



def _claim_null_chunks(session: dict, issue_key: str) -> int:
    """Retroactively assign null-issueKey work chunks to issue_key.

    Called whenever currentIssue is set for the first time, so that work
    done before an issue was known gets attributed correctly.

    Returns the count of chunks claimed. Also adds the claimed time to
    session["activeIssues"][issue_key]["totalSeconds"] if the issue exists there.
    """
    claimed = 0
    total_claimed_seconds = 0
    for chunk in session.get("workChunks", []):
        if chunk.get("issueKey") is not None:
            continue
        chunk["issueKey"] = issue_key
        claimed += 1
        start = chunk.get("startTime", 0)
        end = chunk.get("endTime", 0)
        chunk_time = end - start
        for gap in chunk.get("idleGaps", []):
            chunk_time -= gap.get("seconds", 0)
        total_claimed_seconds += max(chunk_time, 0)

    if claimed > 0 and issue_key in session.get("activeIssues", {}):
        session["activeIssues"][issue_key]["totalSeconds"] = (
            session["activeIssues"][issue_key].get("totalSeconds", 0) + total_claimed_seconds
        )
    return claimed


def cmd_auto_create_issue(args):
    """Auto-create a Jira issue from a prompt. Exits silently (no output) on skip.

    Usage: jira_core.py auto-create-issue <root> <prompt_text>
    """
    root = args[0] if args else "."
    prompt = args[1] if len(args) > 1 else ""

    cfg = load_config(root)
    session = load_session(root)
    if not session:
        return

    autonomy = _resolve_autonomy(session, cfg)
    if autonomy == "C":
        return  # silent — caller falls back to blocking mode

    result = _attempt_auto_create(root, prompt, session, cfg)
    if result:
        print(json.dumps(result))


def _auto_setup_from_global(root: str) -> dict:
    """Auto-create project config from global credentials if available.

    Detects project key from git history and creates a minimal
    .claude/jira-autopilot.json so the plugin works in any project.
    Returns the new config dict, or {} if auto-setup is not possible.
    """
    gcfg = load_global_config()
    if not gcfg.get("apiToken") or not gcfg.get("baseUrl"):
        return {}

    # Detect project key from git commits/branches (may be None for non-git dirs)
    detected_key = _detect_project_key_from_git(root) or ""

    # Validate detected key against real Jira projects
    project_key = ""
    if detected_key:
        real_projects = jira_get_projects(root)
        real_keys = {p["key"] for p in real_projects}
        if detected_key in real_keys:
            project_key = detected_key
        else:
            debug_log(f"Auto-setup: git-detected key '{detected_key}' not found in Jira "
                      f"(available: {', '.join(sorted(real_keys)) or 'none'})",
                      category="session-start")

    cfg = {
        "projectKey": project_key,
        "cloudId": gcfg.get("cloudId", ""),
        "enabled": True,
        "autonomyLevel": "A",
        "accuracy": 10,
        "branchPattern": f"^(?:feature|fix|hotfix|chore|docs)/({re.escape(project_key)}-\\d+)" if project_key else "",
        "commitPattern": f"{re.escape(project_key)}-\\d+:" if project_key else "",
        "timeRounding": 1,
        "idleThreshold": 5,
        "autoCreate": True,
        "defaultLabels": ["jira-autopilot"],
        "logLanguage": gcfg.get("logLanguage", "English"),
    }

    config_path = os.path.join(root, ".claude", CONFIG_NAME)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)

    # Also create local config symlink/copy from global creds
    local_path = os.path.join(root, ".claude", LOCAL_CONFIG_NAME)
    if not os.path.exists(local_path):
        local_cfg = {
            "email": gcfg.get("email", ""),
            "apiToken": gcfg.get("apiToken", ""),
            "baseUrl": gcfg.get("baseUrl", ""),
            "accountId": gcfg.get("accountId", ""),
        }
        with open(local_path, "w") as f:
            json.dump(local_cfg, f, indent=2)

    debug_log(f"Auto-setup: created config for project {project_key or '(no key detected)'}",
              category="session-start")
    return cfg


def _detect_project_key_from_git(root: str) -> str | None:
    """Detect Jira project key from git commit messages and branch names."""
    try:
        log = subprocess.run(
            ["git", "log", "--oneline", "-100"],
            capture_output=True, text=True, cwd=root, timeout=5,
        ).stdout
        branches = subprocess.run(
            ["git", "branch", "-a"],
            capture_output=True, text=True, cwd=root, timeout=5,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

    text = log + "\n" + branches
    keys = re.findall(r'([A-Z][A-Z0-9]+-)\d+', text)
    if not keys:
        return None
    counted = Counter(keys)
    most_common = counted.most_common(1)[0][0].rstrip("-")
    return most_common


def jira_get_projects(root: str) -> list[dict]:
    """Fetch accessible Jira projects from the Jira Cloud API.

    Returns list of {key, name} dicts, or [] on failure.
    """
    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    if not base_url or not email or not api_token:
        return []

    url = f"{base_url.rstrip('/')}/rest/api/3/project/search?maxResults=50&orderBy=key"
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Accept", "application/json")
    api_path = "/rest/api/3/project/search"
    start_ts = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed_ms = int((time.time() - start_ts) * 1000)
            _log_api_call("GET", api_path, resp.status, elapsed_ms)
            data = json.loads(resp.read().decode())
            values = data.get("values", [])
            return [{"key": p["key"], "name": p.get("name", "")} for p in values]
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("GET", api_path, e.code, elapsed_ms, f"error={e.reason}")
        debug_log(f"jira_get_projects HTTP error status={e.code} reason={e.reason}",
                  category="jira-api")
        return []
    except Exception as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("GET", api_path, 0, elapsed_ms, f"error={type(e).__name__}")
        debug_log(f"jira_get_projects error={type(e).__name__}: {e}",
                  category="jira-api")
        return []


def cmd_get_projects(args):
    """CLI command: fetch and print accessible Jira projects as JSON."""
    root = args[0] if args else "."
    projects = jira_get_projects(root)
    print(json.dumps(projects))


def cmd_session_start(args):
    root = args[0] if args else "."
    _migrate_old_configs(root)

    cfg = load_config(root)

    # Auto-setup: if no project config exists, try creating one from global creds
    if not cfg:
        cfg = _auto_setup_from_global(root)

    if not cfg.get("enabled", True):
        debug_log("Plugin disabled via config — skipping session start",
                  category="session-start", enabled=cfg.get("debugLog", False))
        return

    existing = load_session(root)
    # If there's already an active session with issues, preserve it
    if existing.get("activeIssues"):
        # Prune stale issues: older than 24h with zero work chunks
        now = int(time.time())
        stale_keys = []
        for key, data in existing["activeIssues"].items():
            start = data.get("startTime", 0)
            if start > 0 and (now - start) > STALE_ISSUE_SECONDS:
                has_chunks = any(
                    c.get("issueKey") == key for c in existing.get("workChunks", [])
                )
                if not has_chunks and data.get("totalSeconds", 0) == 0:
                    stale_keys.append(key)
        for key in stale_keys:
            del existing["activeIssues"][key]
            if existing.get("currentIssue") == key:
                existing["currentIssue"] = None
            debug_log(f"Removed stale issue {key} (>24h, no work)",
                      category="session-start", enabled=cfg.get("debugLog", False))

        # Always sync autonomy/accuracy from config (may have changed via /jira-setup)
        existing["autonomyLevel"] = cfg.get("autonomyLevel", "C")
        existing["accuracy"] = cfg.get("accuracy", 5)
        # Ensure activeTasks / activePlanning / lastWorklogTime exist (may be missing in older sessions)
        existing.setdefault("activeTasks", {})
        existing.setdefault("activePlanning", None)
        existing.setdefault("lastWorklogTime", int(time.time()))
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
        "activePlanning": None,
        "lastWorklogTime": int(time.time()),
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
        claimed = _claim_null_chunks(session, branch_issue)
        if claimed > 0:
            debug_log(
                f"branch detection retroactively claimed {claimed} null chunks for {branch_issue}",
                category="session-start",
                enabled=cfg.get("debugLog", False),
            )
        debug_log(
            f"Detected issue from branch: {branch_issue}",
            category="session-start",
            enabled=cfg.get("debugLog", False),
        )
    elif _resolve_autonomy(session, cfg) == "A" and cfg.get("autoCreate", False):
        # Autonomy A + autoCreate: try to seed currentIssue from recent commits
        commit_msgs = _get_recent_commit_messages(root)
        if commit_msgs:
            save_session(root, session)  # save skeleton first so _attempt_auto_create can read it
            result = _attempt_auto_create(root, commit_msgs[0], session, cfg)
            if result and not result.get("duplicate"):
                debug_log(
                    f"Session start auto-created {result['key']} from commit: {commit_msgs[0]!r}",
                    category="session-start",
                    enabled=cfg.get("debugLog", False),
                )
                return  # session already saved by _attempt_auto_create

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

    cfg = load_config(root)

    # Planning Skill — track before the read-only skip so timing is captured.
    if tool_name == "Skill" and _is_planning_skill(tool_input.get("skill", "")):
        _handle_planning_event(root, session, tool_name, tool_input, tool_response, cfg)
        save_session(root, session)
        return  # Skill itself is still read-only; don't log to activity buffer

    # Skip read-only tools
    if tool_name in READ_ONLY_TOOLS:
        debug_log(f"Skipping read-only tool={tool_name}",
                  category="log-activity", enabled=cfg.get("debugLog", False))
        return
    activity_type = TOOL_TYPE_MAP.get(tool_name, "other")
    file_path = tool_input.get("file_path", "")
    command = tool_input.get("command", "")

    # Skip writes to internal plugin state/config files — these are noise,
    # not user work, and may contain sensitive paths or credential data
    if file_path and "/.claude/" in file_path:
        debug_log(f"Skipping internal .claude/ write tool={tool_name} file={file_path}",
                  category="log-activity", enabled=cfg.get("debugLog", False))
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

    # Track plan mode start/end and implementation-triggered plan end
    if tool_name in ("EnterPlanMode", "ExitPlanMode") or \
            (tool_name in PLANNING_IMPL_TOOLS and session.get("activePlanning")):
        _handle_planning_event(root, session, tool_name, tool_input, tool_response, cfg)

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



def _log_task_time(root: str, session: dict, cfg: dict, subject: str, seconds: int):
    """Log time for a completed task to the parent issue."""
    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    current_issue = session.get("currentIssue")
    debug = cfg.get("debugLog", False)
    if not (base_url and email and api_token):
        return
    if current_issue:
        enriched = _maybe_enrich_worklog_summary(
            root, {"files": [], "commands": [], "activityCount": 0}, subject)
        post_worklog_to_jira(base_url, email, api_token, current_issue, seconds, enriched)
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
    # Subject can come from response (TaskCreate) or input (TaskUpdate)
    subject = resp.get("subject", "") or tool_input.get("subject", "")
    status = resp.get("status", "") or tool_input.get("status", "")
    if not task_id:
        return
    debug = cfg.get("debugLog", False)
    active_tasks = session.setdefault("activeTasks", {})
    task_subjects = session.setdefault("taskSubjects", {})

    # Cache subject from TaskCreate so TaskUpdate can look it up
    if tool_name == "TaskCreate" and task_id and subject:
        task_subjects[task_id] = subject

    # For TaskUpdate, look up cached subject if none provided
    if not subject and task_id in task_subjects:
        subject = task_subjects[task_id]

    if not status:
        return
    if status == "in_progress" and task_id not in active_tasks:
        active_tasks[task_id] = {
            "subject": subject,
            "startTime": int(time.time()),
            "jiraKey": None,
        }
        debug_log(f"Task started taskId={task_id} subject={subject!r}",
                  category="task-worklog", enabled=debug)
    elif status == "completed" and task_id in active_tasks:
        task = active_tasks.pop(task_id)
        elapsed = int(time.time()) - task["startTime"]
        if elapsed < 60:
            debug_log(f"Task discarded (elapsed={elapsed}s < 60s) "
                      f"taskId={task_id} subject={task.get('subject', '')!r}",
                      category="task-worklog", enabled=debug)
        else:
            _log_task_time(root, session, cfg, task.get("subject") or subject, elapsed)


def _is_planning_skill(skill_name: str) -> bool:
    """Return True if the skill name matches a planning/research pattern."""
    lower = skill_name.lower()
    return any(p in lower for p in PLANNING_SKILL_PATTERNS)


def _log_planning_time(root: str, session: dict, cfg: dict,
                        subject: str, seconds: int, issue_key: "str | None" = None):
    """Log planning time to the target Jira issue."""
    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    # Fall back: planning issue → current issue → last parent
    target = issue_key or session.get("currentIssue") or session.get("lastParentKey")
    debug = cfg.get("debugLog", False)
    if not (base_url and email and api_token) or not target:
        debug_log(f"planning time skipped — no creds or target issue",
                  category="planning", enabled=debug)
        return
    enriched = _maybe_enrich_worklog_summary(
        root, {"files": [], "commands": [], "activityCount": 0}, subject)
    post_worklog_to_jira(base_url, email, api_token, target, seconds, enriched)
    debug_log(f"planning='{subject}' logged={seconds}s to {target}",
              category="planning", enabled=debug)


def _handle_planning_event(root: str, session: dict, tool_name: str,
                            tool_input: dict, tool_response: dict, cfg: dict):
    """Track plan mode / planning-skill start and end for Jira time logging."""
    active = session.get("activePlanning")
    is_start = tool_name in ("EnterPlanMode",) or \
               (tool_name == "Skill" and _is_planning_skill(tool_input.get("skill", "")))
    is_end = tool_name in ("ExitPlanMode",) or tool_name in PLANNING_IMPL_TOOLS

    debug = cfg.get("debugLog", False)
    if is_start and not active:
        skill_name = tool_input.get("skill", "")
        subject = f"Planning: {skill_name}" if skill_name else "Planning"
        session["activePlanning"] = {
            "startTime": int(time.time()),
            "issueKey": session.get("currentIssue"),
            "subject": subject,
        }
        debug_log(f"Planning started subject={subject!r} trigger={tool_name}",
                  category="planning", enabled=debug)
    elif is_end and active:
        elapsed = int(time.time()) - active["startTime"]
        session["activePlanning"] = None
        if elapsed < 60:
            debug_log(f"Planning discarded (elapsed={elapsed}s < 60s) "
                      f"subject={active.get('subject', '')!r}",
                      category="planning", enabled=debug)
            return
        _log_planning_time(
            root, session, cfg,
            active.get("subject", "Planning"),
            elapsed,
            active.get("issueKey"),
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


def _flush_periodic_worklogs(root: str, session: dict, cfg: dict):
    """Post a worklog for each active issue if worklogInterval minutes have elapsed."""
    interval_minutes = cfg.get("worklogInterval", 15)
    interval_seconds = interval_minutes * 60
    now = int(time.time())
    last = session.get("lastWorklogTime", now)
    debug = cfg.get("debugLog", False)

    if now - last < interval_seconds:
        return

    autonomy = session.get("autonomyLevel", cfg.get("autonomyLevel", "C"))
    accuracy = session.get("accuracy", cfg.get("accuracy", 5))
    time_rounding = cfg.get("timeRounding", 15)
    active_issues = session.get("activeIssues", {})

    flushed_any = False

    # --- Flush attributed (issued) work ---
    for issue_key in list(active_issues.keys()):
        worklog = build_worklog(root, issue_key)
        raw_seconds = worklog["seconds"]
        if raw_seconds <= 0:
            continue

        rounded = _round_seconds(raw_seconds, time_rounding, accuracy)
        summary = _maybe_enrich_worklog_summary(root, worklog["rawFacts"], worklog["summary"])
        entry = {
            "issueKey": issue_key,
            "seconds": rounded,
            "summary": summary,
            "rawFacts": worklog["rawFacts"],
            "status": "pending" if autonomy == "C" else "approved",
        }
        session.setdefault("pendingWorklogs", []).append(entry)
        flushed_any = True

        debug_log(
            f"periodic flush issue={issue_key} raw={raw_seconds}s rounded={rounded}s "
            f"autonomy={autonomy} interval={interval_minutes}m",
            category="periodic-worklog", enabled=debug,
        )

    # --- Flush unattributed (null-issueKey) work ---
    null_chunks = [c for c in session.get("workChunks", []) if c.get("issueKey") is None]
    if null_chunks:
        unattr = _build_unattributed_worklog(session)
        if unattr["seconds"] > 0:
            if autonomy == "A" and cfg.get("autoCreate", False):
                commit_msgs = _get_recent_commit_messages(root)
                summary_hint = commit_msgs[0] if commit_msgs else unattr["summary"]
                result = _attempt_auto_create(root, summary_hint, session, cfg)
                if result:
                    flushed_any = True
                    debug_log(
                        f"periodic auto-created {result['key']} for unattributed work",
                        category="periodic-worklog", enabled=debug,
                    )
            if not flushed_any or autonomy != "A":
                # B/C or auto-create failed: save as pending
                rounded = _round_seconds(unattr["seconds"], time_rounding, accuracy)
                entry = {
                    "issueKey": None,
                    "seconds": rounded,
                    "summary": unattr["summary"],
                    "rawFacts": unattr["rawFacts"],
                    "status": "unattributed",
                }
                session.setdefault("pendingWorklogs", []).append(entry)
                flushed_any = True
                debug_log(
                    f"periodic saved {rounded}s unattributed",
                    category="periodic-worklog", enabled=debug,
                )

    if not flushed_any:
        return

    # Clear chunks that were just summarised so session-end doesn't re-sum them
    processed_keys = set(active_issues.keys())
    session["workChunks"] = [
        c for c in session.get("workChunks", [])
        if c.get("issueKey") not in processed_keys
        and c.get("issueKey") is not None  # also clear null chunks that were flushed
    ]
    session["lastWorklogTime"] = now
    save_session(root, session)

    # Post immediately for autonomy A/B; autonomy C stays pending until /jira-approve
    if autonomy != "C":
        cmd_post_worklogs([root])


def cmd_drain_buffer(args):
    root = args[0] if args else "."
    cfg = load_config(root)
    session = load_session(root)
    if not session:
        return

    buffer = session.get("activityBuffer", [])
    if not buffer:
        # Buffer is empty but periodic flush may still be due
        _flush_periodic_worklogs(root, session, cfg)
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

    idle_splits = sum(1 for g in groups if g.get("idle_before"))
    issue_splits = sum(
        1 for i in range(1, len(groups))
        if (groups[i]["activities"][0].get("issueKey") !=
            groups[i - 1]["activities"][-1].get("issueKey"))
    )
    dir_splits = sum(1 for g in groups if g.get("dir_shift"))
    debug_log(
        f"new_chunks={len(groups)} total_chunks={len(chunks)} "
        f"splits(idle={idle_splits} issue_change={issue_splits} dir_shift={dir_splits})",
        category="drain-buffer",
        enabled=cfg.get("debugLog", False),
    )

    # Periodic worklog flush (every worklogInterval minutes)
    _flush_periodic_worklogs(root, session, cfg)

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
    active_keys = set(session.get("activeIssues", {}).keys())
    sole_active = len(active_keys) == 1 and issue_key in active_keys
    chunks = [
        c for c in session.get("workChunks", [])
        if c.get("issueKey") == issue_key
        or (sole_active and c.get("issueKey") is None)
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

    # Deduplicate files; keep relative basenames for readability
    unique_files = list(dict.fromkeys(all_files))
    unique_commands = list(dict.fromkeys(all_commands))
    file_basenames = [os.path.basename(f) for f in unique_files if f]

    # Build a clean file-list summary (no commands, no "N tool calls").
    # This is the auto-generated fallback used for periodic/autonomy-A posts.
    # For /jira-stop, Claude replaces this with a human-narrative summary
    # in the configured logLanguage.
    if file_basenames:
        shown = file_basenames[:8]
        rest = len(file_basenames) - len(shown)
        file_list = ", ".join(shown)
        if rest:
            file_list += f" +{rest}"
        summary = file_list
    else:
        lang = get_log_language(root)
        summary = "עבודה על המשימה" if lang == "Hebrew" else "Work on task"

    capped = False
    if total_seconds > MAX_WORKLOG_SECONDS:
        total_seconds = MAX_WORKLOG_SECONDS
        capped = True

    result = {
        "issueKey": issue_key,
        "seconds": total_seconds,
        "summary": summary,
        "rawFacts": {
            "files": unique_files,
            "commands": unique_commands,
            "activityCount": total_activities,
        },
    }
    if capped:
        result["capped"] = True
    return result



def _build_unattributed_worklog(session: dict) -> dict:
    """Build a worklog summary from all null-issueKey work chunks.

    Used at session-end and periodic flush to rescue unattributed work.
    """
    chunks = [c for c in session.get("workChunks", []) if c.get("issueKey") is None]
    all_files, all_commands, total_activities, total_seconds = [], [], 0, 0
    for chunk in chunks:
        all_files.extend(chunk.get("filesChanged", []))
        for act in chunk.get("activities", []):
            total_activities += 1
            if act.get("command"):
                all_commands.append(_sanitize_command(act["command"]))
        start = chunk.get("startTime", 0)
        end = chunk.get("endTime", 0)
        chunk_time = end - start
        for gap in chunk.get("idleGaps", []):
            chunk_time -= gap.get("seconds", 0)
        total_seconds += max(chunk_time, 0)
    unique_files = list(dict.fromkeys(all_files))
    file_basenames = [os.path.basename(f) for f in unique_files if f]
    if file_basenames:
        shown = file_basenames[:8]
        rest = len(file_basenames) - len(shown)
        summary = ", ".join(shown) + (f" +{rest}" if rest else "")
    else:
        summary = "Unattributed work"
    return {
        "seconds": total_seconds,
        "summary": summary,
        "rawFacts": {
            "files": unique_files,
            "commands": list(dict.fromkeys(all_commands)),
            "activityCount": total_activities,
        },
        "chunkCount": len(chunks),
    }

def cmd_build_worklog(args):
    root = args[0] if args else "."
    issue_key = args[1] if len(args) > 1 else ""
    if not issue_key:
        print("{}", file=sys.stderr)
        return
    result = build_worklog(root, issue_key)
    result["logLanguage"] = get_log_language(root)
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

    # Flush any in-progress planning session before archiving
    active_planning = session.get("activePlanning")
    if active_planning:
        elapsed = int(time.time()) - active_planning["startTime"]
        if elapsed >= 60:
            _log_planning_time(
                root, session, cfg,
                active_planning.get("subject", "Planning"),
                elapsed,
                active_planning.get("issueKey"),
            )
        session["activePlanning"] = None

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
            debug_log(
                f"issue={issue_key} skipped — no tracked activity (build_worklog returned 0s)",
                category="session-end", enabled=debug,
            )
            continue

        rounded = _round_seconds(raw_seconds, time_rounding, accuracy)
        summary = _maybe_enrich_worklog_summary(root, worklog["rawFacts"], worklog["summary"])

        entry = {
            "issueKey": issue_key,
            "seconds": rounded,
            "summary": summary,
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

    # Prune paused ghost issues: paused with no logged seconds and no work chunks.
    # These accumulate when issues are added via /jira-start but never worked on.
    ghost_keys = [
        key for key, data in active_issues.items()
        if data.get("paused", False)
        and data.get("totalSeconds", 0) == 0
        and not any(c.get("issueKey") == key for c in session.get("workChunks", []))
        and not any(w.get("issueKey") == key for w in pending if w.get("seconds", 0) > 0)
    ]
    for key in ghost_keys:
        del session["activeIssues"][key]
        debug_log(
            f"Pruned ghost issue {key} (paused, no activity)",
            category="session-end", enabled=debug,
        )

    # ── Rescue unattributed (null-issueKey) work ─────────────────────────────
    null_chunks = [c for c in session.get("workChunks", []) if c.get("issueKey") is None]
    if null_chunks:
        unattr = _build_unattributed_worklog(session)
        raw_seconds = unattr["seconds"]
        debug_log(
            f"unattributed chunks={len(null_chunks)} raw={raw_seconds}s",
            category="session-end", enabled=debug,
        )
        if raw_seconds > 0:
            autonomy = _resolve_autonomy(session, cfg)
            if autonomy == "A" and cfg.get("autoCreate", False):
                commit_msgs = _get_recent_commit_messages(root)
                summary_hint = commit_msgs[0] if commit_msgs else unattr["summary"]
                result = _attempt_auto_create(root, summary_hint, session, cfg)
                if result and not result.get("duplicate"):
                    debug_log(
                        f"session-end auto-created {result['key']} for {raw_seconds}s unattributed",
                        category="session-end", enabled=debug,
                    )
                    session = load_session(root)  # reload since _attempt_auto_create saved
                else:
                    # Auto-create failed or was disabled — fall back to pending
                    rounded = _round_seconds(raw_seconds, time_rounding, accuracy)
                    entry = {
                        "issueKey": None,
                        "seconds": rounded,
                        "summary": unattr["summary"],
                        "rawFacts": unattr["rawFacts"],
                        "status": "unattributed",
                    }
                    session.setdefault("pendingWorklogs", []).append(entry)
            else:
                # B/C: save as pending unattributed for /jira-approve
                rounded = _round_seconds(raw_seconds, time_rounding, accuracy)
                entry = {
                    "issueKey": None,
                    "seconds": rounded,
                    "summary": unattr["summary"],
                    "rawFacts": unattr["rawFacts"],
                    "status": "unattributed",
                }
                session.setdefault("pendingWorklogs", []).append(entry)
                debug_log(
                    f"session-end saved {rounded}s as pendingUnattributed",
                    category="session-end", enabled=debug,
                )

        # Archive the full session snapshot BEFORE clearing chunks — preserves
    # complete work history for /jira-summary and other tooling that reads archives.
    archive_dir = os.path.join(root, ".claude", "jira-sessions")
    os.makedirs(archive_dir, exist_ok=True)
    session_id = session.get("sessionId", datetime.now().strftime("%Y%m%d-%H%M%S"))
    archive_path = os.path.join(archive_dir, f"{session_id}.json")
    with open(archive_path, "w") as f:
        json.dump(session, f, indent=2)

    # Clear processed work chunks from the live session so the next session-end
    # doesn't re-sum them and post duplicate Jira worklogs.
    processed_keys = set(active_issues.keys())
    session["workChunks"] = [
        c for c in session.get("workChunks", [])
        if c.get("issueKey") not in processed_keys
    ]
    now = int(time.time())
    for issue_key in processed_keys:
        if issue_key in session.get("activeIssues", {}):
            session["activeIssues"][issue_key]["startTime"] = now

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
        # Skip blank lines — empty paragraph nodes render as blank description in Jira
    if not paragraphs:
        paragraphs.append(
            {"type": "paragraph", "content": [{"type": "text", "text": text or "—"}]}
        )
    return {"version": 1, "type": "doc", "content": paragraphs}


def post_worklog_to_jira(base_url: str, email: str, api_token: str,
                          issue_key: str, seconds: int, comment: str,
                          language: str = "English") -> bool:
    """POST a worklog entry to Jira Cloud REST API. Returns True on success."""
    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/worklog"
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    # Fallback description when caller provides no subject (e.g. empty task name)
    if not comment.strip():
        minutes = seconds // 60
        effective_comment = f"עבודה על המשימה ({minutes} דקות)" if language == "Hebrew" else f"Work on task ({minutes}m)"
    else:
        effective_comment = comment.strip()
    payload = json.dumps({
        "timeSpentSeconds": seconds,
        "comment": _text_to_adf(effective_comment),
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    api_path = f"/rest/api/3/issue/{issue_key}/worklog"
    start_ts = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed_ms = int((time.time() - start_ts) * 1000)
            _log_api_call("POST", api_path, resp.status, elapsed_ms,
                          f"issue={issue_key} seconds={seconds}")
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("POST", api_path, e.code, elapsed_ms,
                      f"issue={issue_key} error={e.reason}")
        debug_log(f"post_worklog HTTP error status={e.code} reason={e.reason} "
                  f"issue={issue_key} seconds={seconds}",
                  category="jira-api")
        return False
    except Exception as e:
        elapsed_ms = int((time.time() - start_ts) * 1000)
        _log_api_call("POST", api_path, 0, elapsed_ms,
                      f"issue={issue_key} error={type(e).__name__}")
        debug_log(f"post_worklog error={type(e).__name__}: {e} "
                  f"issue={issue_key} seconds={seconds}",
                  category="jira-api")
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
    lang = get_log_language(root)

    for entry in pending:
        if entry.get("status") != "approved":
            continue
        issue_key = entry.get("issueKey", "")
        seconds = entry.get("seconds", 0)
        summary = entry.get("summary", "")
        if not issue_key or seconds <= 0:
            continue

        # Rebuild summary from rawFacts if missing (e.g. older entries before summary was stored)
        if not summary.strip():
            raw_facts = entry.get("rawFacts", {})
            files = raw_facts.get("files", [])
            basenames = [os.path.basename(f) for f in files if f]
            if basenames:
                shown = basenames[:8]
                rest = len(basenames) - len(shown)
                summary = ", ".join(shown) + (f" +{rest}" if rest else "")

        ok = post_worklog_to_jira(base_url, email, api_token, issue_key, seconds, summary, language=lang)
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
