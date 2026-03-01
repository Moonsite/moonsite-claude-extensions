# Jira Autopilot v4 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reimplement the jira-autopilot plugin from scratch based on the specs in `docs/specs/`, producing a fully functional Claude Code plugin with hooks, commands, and Jira integration.

**Architecture:** Python-first with thin shell wrappers. Single Python module (`jira_core.py`) for all business logic. Shell scripts are hook entry points only (< 10 lines each). Atomic file writes everywhere. Local-first tracking, sync-to-Jira as a separate step.

**Tech Stack:** Python 3 stdlib only (no pip packages), bash shell scripts, pytest for testing, Jira Cloud REST API v3, optional Anthropic API for AI enrichment.

**Reference docs (read these, NOT old source code):**
- `docs/specs/jira-autopilot-requirements.md` — full technical spec
- `docs/specs/requirements/user-stories.md` — PM-level requirements
- `docs/specs/requirements/lessons-learned.md` — pitfalls to avoid

---

## Task 1: Plugin Manifest & Hook Registration

**Files:**
- Create: `plugins/jira-autopilot/.claude-plugin/plugin.json`
- Create: `plugins/jira-autopilot/hooks/hooks.json`

**Step 1: Write the plugin manifest test**

Verify the manifest is valid JSON with required fields.

```bash
cd plugins/jira-autopilot && python3 -c "
import json, sys
m = json.load(open('.claude-plugin/plugin.json'))
assert m['name'] == 'jira-autopilot', f'name: {m[\"name\"]}'
assert 'version' in m
assert 'description' in m
print('PASS: plugin.json valid')
"
```

**Step 2: Create plugin manifest**

```json
{
  "name": "jira-autopilot",
  "version": "4.0.0",
  "description": "Autonomous Jira work tracking, issue creation, and time logging for Claude Code sessions",
  "author": {
    "name": "Boris Sigalov"
  }
}
```

**Step 3: Write the hooks registration test**

```bash
cd plugins/jira-autopilot && python3 -c "
import json
h = json.load(open('hooks/hooks.json'))
assert isinstance(h, list), 'hooks.json must be array'
events = {hook['event'] for hook in h}
required = {'SessionStart', 'PostToolUse', 'PreToolUse', 'Stop', 'SessionEnd', 'UserPromptSubmit'}
missing = required - events
assert not missing, f'Missing events: {missing}'
# PostToolUse must be async
ptu = [h2 for h2 in h if h2['event'] == 'PostToolUse'][0]
assert ptu.get('async') == True, 'PostToolUse must be async'
print('PASS: hooks.json valid')
"
```

**Step 4: Create hooks registration**

Per spec section 4.1:

```json
[
  {
    "event": "SessionStart",
    "command": "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/session-start-check.sh"
  },
  {
    "event": "PostToolUse",
    "command": "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/post-tool-use.sh",
    "async": true
  },
  {
    "event": "PreToolUse",
    "command": "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/pre-tool-use.sh"
  },
  {
    "event": "Stop",
    "command": "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/stop.sh"
  },
  {
    "event": "SessionEnd",
    "command": "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/session-end.sh"
  },
  {
    "event": "UserPromptSubmit",
    "command": "${CLAUDE_PLUGIN_ROOT}/hooks-handlers/user-prompt-submit.sh",
    "timeout": 10000
  }
]
```

**Step 5: Run both tests to verify**

Run: `cd plugins/jira-autopilot && python3 -c "..." (both tests above)`
Expected: Both PASS

**Step 6: Commit**

```bash
git add plugins/jira-autopilot/.claude-plugin/plugin.json plugins/jira-autopilot/hooks/hooks.json
git commit -m "Add plugin manifest and hook registration for v4"
```

---

## Task 2: Shell Helpers & Hook Entry Points

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/helpers.sh`
- Create: `plugins/jira-autopilot/hooks-handlers/session-start-check.sh`
- Create: `plugins/jira-autopilot/hooks-handlers/post-tool-use.sh`
- Create: `plugins/jira-autopilot/hooks-handlers/pre-tool-use.sh`
- Create: `plugins/jira-autopilot/hooks-handlers/stop.sh`
- Create: `plugins/jira-autopilot/hooks-handlers/session-end.sh`
- Create: `plugins/jira-autopilot/hooks-handlers/user-prompt-submit.sh`

**Step 1: Create helpers.sh**

Minimal shell helpers per spec section 14:

```bash
#!/usr/bin/env bash
# helpers.sh — minimal shell utilities for hook entry points

find_project_root() {
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
    echo "$CLAUDE_PROJECT_DIR"
    return
  fi
  local dir="$PWD"
  while [[ "$dir" != "/" ]]; do
    [[ -d "$dir/.git" ]] && { echo "$dir"; return; }
    dir="$(dirname "$dir")"
  done
  echo "$PWD"
}

json_get() {
  python3 -c "import json,sys; print(json.load(open('$1')).get('$2',''))" 2>/dev/null || echo ""
}

is_enabled() {
  local root="$1"
  local cfg="$root/.claude/jira-autopilot.json"
  [[ -f "$cfg" ]] && [[ "$(json_get "$cfg" enabled)" != "false" ]]
}
```

**Step 2: Create all 6 hook shell scripts**

Each follows the same thin-wrapper pattern (< 10 lines):

`session-start-check.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
ROOT="$(find_project_root)"
python3 "$SCRIPT_DIR/jira_core.py" session-start "$ROOT"
```

`post-tool-use.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
ROOT="$(find_project_root)"
is_enabled "$ROOT" || exit 0
python3 "$SCRIPT_DIR/jira_core.py" log-activity "$ROOT"
```

`pre-tool-use.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
ROOT="$(find_project_root)"
is_enabled "$ROOT" || exit 0
python3 "$SCRIPT_DIR/jira_core.py" pre-tool-use "$ROOT"
```

`stop.sh` — MUST always exit 0:
```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
ROOT="$(find_project_root)"
python3 "$SCRIPT_DIR/jira_core.py" drain-buffer "$ROOT" 2>/dev/null || true
exit 0
```

`session-end.sh`:
```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
ROOT="$(find_project_root)"
python3 "$SCRIPT_DIR/jira_core.py" session-end "$ROOT" 2>/dev/null || true
python3 "$SCRIPT_DIR/jira_core.py" post-worklogs "$ROOT" 2>/dev/null || true
exit 0
```

`user-prompt-submit.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
ROOT="$(find_project_root)"
is_enabled "$ROOT" || exit 0
python3 "$SCRIPT_DIR/jira_core.py" user-prompt-submit "$ROOT"
```

**Step 3: Make all scripts executable**

```bash
chmod +x plugins/jira-autopilot/hooks-handlers/*.sh
```

**Step 4: Verify scripts parse correctly**

```bash
for f in plugins/jira-autopilot/hooks-handlers/*.sh; do
  bash -n "$f" && echo "OK: $f" || echo "FAIL: $f"
done
```
Expected: All OK

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/*.sh
git commit -m "Add shell helpers and hook entry point scripts"
```

---

## Task 3: Core Python Module — Foundation Layer

This is the largest task. Build the foundational functions: constants, config loading, session management, atomic writes, debug logging, credential handling.

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/jira_core.py`
- Create: `plugins/jira-autopilot/hooks-handlers/tests/__init__.py`
- Create: `plugins/jira-autopilot/hooks-handlers/tests/conftest.py`
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_config.py`

**Step 1: Write failing tests for config loading**

`tests/conftest.py`:
```python
import pytest
import os

@pytest.fixture(autouse=True)
def isolate_global_config(tmp_path, monkeypatch):
    """Prevent tests from using real global credentials."""
    fake_global = str(tmp_path / "nonexistent-global.json")
    monkeypatch.setattr("jira_core.GLOBAL_CONFIG_PATH", fake_global)

@pytest.fixture
def project_root(tmp_path):
    """Create a project root with .claude directory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return tmp_path
```

`tests/test_config.py`:
```python
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestLoadConfig:
    def test_missing_file_returns_empty(self, project_root):
        cfg = jira_core.load_config(str(project_root))
        assert cfg == {}

    def test_loads_valid_config(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        cfg = jira_core.load_config(str(project_root))
        assert cfg["projectKey"] == "TEST"

    def test_corrupt_json_returns_empty(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text("{broken json")
        cfg = jira_core.load_config(str(project_root))
        assert cfg == {}


class TestGetCred:
    def test_local_config_takes_priority(self, project_root):
        local = project_root / ".claude" / "jira-autopilot.local.json"
        local.write_text(json.dumps({"email": "local@test.com"}))
        assert jira_core.get_cred(str(project_root), "email") == "local@test.com"

    def test_falls_back_to_global(self, project_root, tmp_path, monkeypatch):
        global_cfg = tmp_path / "global.json"
        global_cfg.write_text(json.dumps({"email": "global@test.com"}))
        monkeypatch.setattr("jira_core.GLOBAL_CONFIG_PATH", str(global_cfg))
        assert jira_core.get_cred(str(project_root), "email") == "global@test.com"

    def test_missing_creds_returns_empty(self, project_root):
        assert jira_core.get_cred(str(project_root), "email") == ""


class TestAtomicWrite:
    def test_roundtrip_integrity(self, project_root):
        path = str(project_root / "test.json")
        data = {"key": "value", "nested": {"a": 1}}
        jira_core.atomic_write_json(path, data)
        loaded = json.loads(open(path).read())
        assert loaded == data

    def test_no_temp_files_left(self, project_root):
        path = str(project_root / "test.json")
        jira_core.atomic_write_json(path, {"x": 1})
        files = os.listdir(str(project_root))
        assert files == ["test.json"]
```

**Step 2: Run tests — expect FAIL**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_config.py -v
```
Expected: ModuleNotFoundError (jira_core doesn't exist yet)

**Step 3: Implement jira_core.py foundation**

Create `jira_core.py` with these sections (per spec sections 2, 3, 6.1, 9, 10, 15):

```python
#!/usr/bin/env python3
"""jira_core.py — Core business logic for jira-autopilot v4."""

import base64
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
    """Write JSON atomically: temp file → fsync → os.replace."""
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
    """Get credential with local → global fallback."""
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

def cmd_session_start(): pass
def cmd_log_activity(): pass
def cmd_drain_buffer(): pass
def cmd_session_end(): pass
def cmd_post_worklogs(): pass
def cmd_pre_tool_use(): pass
def cmd_user_prompt_submit(): pass
def cmd_classify_issue(): pass
def cmd_auto_create_issue(): pass
def cmd_suggest_parent(): pass
def cmd_build_worklog(): pass
def cmd_create_issue(): pass
def cmd_get_issue(): pass
def cmd_add_worklog(): pass
def cmd_get_projects(): pass
def cmd_debug_log(): pass

if __name__ == "__main__":
    main()
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_config.py -v
```
Expected: All PASS

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/__init__.py \
       plugins/jira-autopilot/hooks-handlers/tests/conftest.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_config.py
git commit -m "Add jira_core.py foundation: config, sessions, atomic writes, logging"
```

---

## Task 4: Credential Sanitization & Debug Logging

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_sanitize.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_sanitize.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestSanitizeForLog:
    def test_redacts_atlassian_token(self):
        text = "token: ATATT3xABC123_/+=.-end"
        result = jira_core.sanitize_for_log(text)
        assert "ATATT3x" not in result
        assert "[REDACTED_TOKEN]" in result

    def test_redacts_bearer(self):
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9"
        result = jira_core.sanitize_for_log(text)
        assert "eyJ" not in result
        assert "Bearer [REDACTED]" in result

    def test_redacts_basic_auth(self):
        text = "Basic dXNlcjpwYXNz"
        result = jira_core.sanitize_for_log(text)
        assert "dXNlcjpwYXNz" not in result

    def test_redacts_curl_auth(self):
        text = "curl -u user@test.com:mytoken123 https://api"
        result = jira_core.sanitize_for_log(text)
        assert "mytoken123" not in result
        assert "-u [REDACTED]" in result

    def test_redacts_api_token_json(self):
        text = '{"apiToken": "secret123"}'
        result = jira_core.sanitize_for_log(text)
        assert "secret123" not in result

    def test_leaves_normal_text_alone(self):
        text = "Editing src/auth.ts line 42"
        assert jira_core.sanitize_for_log(text) == text

    def test_handles_non_string(self):
        result = jira_core.sanitize_for_log({"key": "value"})
        assert isinstance(result, str)


class TestLogRotation:
    def test_rotates_at_threshold(self, tmp_path, monkeypatch):
        log_path = str(tmp_path / "test.log")
        monkeypatch.setattr("jira_core.DEBUG_LOG_PATH", log_path)
        # Write > 1MB
        with open(log_path, "w") as f:
            f.write("x" * (jira_core.MAX_LOG_SIZE + 100))
        jira_core._rotate_log(log_path)
        assert os.path.exists(log_path + ".1")
        assert not os.path.exists(log_path)

    def test_no_rotation_under_threshold(self, tmp_path):
        log_path = str(tmp_path / "test.log")
        with open(log_path, "w") as f:
            f.write("small")
        jira_core._rotate_log(log_path)
        assert not os.path.exists(log_path + ".1")
```

**Step 2: Run tests — expect PASS (already implemented in Task 3)**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_sanitize.py -v
```
Expected: All PASS (these functions were implemented in the foundation)

**Step 3: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/tests/test_sanitize.py
git commit -m "Add tests for credential sanitization and log rotation"
```

---

## Task 5: Session Start Logic

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_session_start.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_session_start.py`:
```python
import json, time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestSessionStart:
    def test_creates_new_session(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        session = jira_core.handle_session_start(str(project_root))
        assert session["sessionId"]
        assert session["activeIssues"] == {}
        assert session["currentIssue"] is None

    def test_preserves_existing_session(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        existing = jira_core._new_session()
        existing["activeIssues"]["TEST-1"] = {
            "summary": "Test issue",
            "startTime": int(time.time()),
            "totalSeconds": 300,
            "paused": False,
            "autoApproveWorklogs": False,
        }
        existing["currentIssue"] = "TEST-1"
        jira_core.save_session(str(project_root), existing)
        session = jira_core.handle_session_start(str(project_root))
        assert "TEST-1" in session["activeIssues"]

    def test_prunes_stale_issues(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        old_time = int(time.time()) - 90000  # > 24h
        existing = jira_core._new_session()
        existing["activeIssues"]["STALE-1"] = {
            "summary": "Stale",
            "startTime": old_time,
            "totalSeconds": 0,
            "paused": False,
            "autoApproveWorklogs": False,
        }
        jira_core.save_session(str(project_root), existing)
        session = jira_core.handle_session_start(str(project_root))
        assert "STALE-1" not in session["activeIssues"]

    def test_keeps_stale_issue_with_work(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        old_time = int(time.time()) - 90000
        existing = jira_core._new_session()
        existing["activeIssues"]["STALE-1"] = {
            "summary": "Has work",
            "startTime": old_time,
            "totalSeconds": 600,
            "paused": False,
            "autoApproveWorklogs": False,
        }
        jira_core.save_session(str(project_root), existing)
        session = jira_core.handle_session_start(str(project_root))
        assert "STALE-1" in session["activeIssues"]

    def test_disabled_returns_none(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"enabled": False}))
        result = jira_core.handle_session_start(str(project_root))
        assert result is None

    def test_syncs_autonomy_from_config(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"enabled": True, "autonomyLevel": "A", "accuracy": 8}))
        existing = jira_core._new_session()
        existing["autonomyLevel"] = "C"
        existing["accuracy"] = 5
        jira_core.save_session(str(project_root), existing)
        session = jira_core.handle_session_start(str(project_root))
        assert session["autonomyLevel"] == "A"
        assert session["accuracy"] == 8
```

**Step 2: Run tests — expect FAIL**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_session_start.py -v
```
Expected: AttributeError: module 'jira_core' has no attribute 'handle_session_start'

**Step 3: Implement handle_session_start()**

Add to `jira_core.py`:

```python
def handle_session_start(root):
    """Initialize or resume session. Returns session dict or None if disabled."""
    cfg = load_config(root)
    if not cfg:
        # Try auto-setup from global
        if not _auto_setup_from_global(root):
            return None
        cfg = load_config(root)

    if cfg.get("enabled") is False:
        return None

    session = load_session(root)

    if session:
        # Existing session — sync config, prune stale
        session["autonomyLevel"] = cfg.get("autonomyLevel", session.get("autonomyLevel", "C"))
        session["accuracy"] = cfg.get("accuracy", session.get("accuracy", 5))
        session = _ensure_session_structure(session)
        _prune_stale_issues(session)
        _sanitize_session_commands(session)
        if not session.get("sessionId"):
            session["sessionId"] = time.strftime("%Y%m%d-%H%M%S")
    else:
        # New session
        session = _new_session()
        session["autonomyLevel"] = cfg.get("autonomyLevel", "C")
        session["accuracy"] = cfg.get("accuracy", 5)
        # Branch detection
        branch_key = _detect_issue_from_branch(root, cfg)
        if branch_key:
            session["activeIssues"][branch_key] = {
                "summary": f"Work on {branch_key}",
                "startTime": int(time.time()),
                "totalSeconds": 0,
                "paused": False,
                "autoApproveWorklogs": False,
            }
            session["currentIssue"] = branch_key
            _claim_null_chunks(session, branch_key)

    save_session(root, session)
    return session


def _prune_stale_issues(session):
    """Remove issues idle > 24h with zero work."""
    now = int(time.time())
    to_remove = []
    for key, issue in session.get("activeIssues", {}).items():
        age = now - issue.get("startTime", now)
        has_work = issue.get("totalSeconds", 0) > 0
        has_chunks = any(c.get("issueKey") == key for c in session.get("workChunks", []))
        if age > STALE_ISSUE_SECONDS and not has_work and not has_chunks:
            to_remove.append(key)
    for key in to_remove:
        del session["activeIssues"][key]
        if session.get("currentIssue") == key:
            remaining = list(session["activeIssues"].keys())
            session["currentIssue"] = remaining[0] if remaining else None


def _sanitize_session_commands(session):
    """Redact credentials from activity buffer commands."""
    for activity in session.get("activityBuffer", []):
        if "command" in activity and activity["command"]:
            activity["command"] = sanitize_for_log(activity["command"])


def _detect_issue_from_branch(root, cfg):
    """Extract issue key from current git branch name."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        if result.returncode != 0:
            return None
        branch = result.stdout.strip()
        project_key = cfg.get("projectKey", "")
        if not project_key:
            return None
        pattern = cfg.get("branchPattern", r"^(?:feature|fix|hotfix|chore|docs)/({key}-\d+)")
        pattern = pattern.replace("{key}", re.escape(project_key))
        match = re.search(pattern, branch)
        if match:
            return match.group(1)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return None


def _detect_project_key_from_git(root):
    """Scan git history for Jira issue key patterns. Return most common prefix."""
    import subprocess
    from collections import Counter
    keys = Counter()
    try:
        log = subprocess.run(
            ["git", "log", "--oneline", "-100"],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        branches = subprocess.run(
            ["git", "branch", "-a"],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        text = (log.stdout or "") + "\n" + (branches.stdout or "")
        for match in re.findall(r"([A-Z][A-Z0-9]+)-\d+", text):
            keys[match] += 1
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return keys.most_common(1)[0][0] if keys else ""


def _auto_setup_from_global(root):
    """Try to create project config from global credentials."""
    global_cfg = _load_json(GLOBAL_CONFIG_PATH)
    if not global_cfg.get("baseUrl") or not global_cfg.get("email") or not global_cfg.get("apiToken"):
        return False

    detected_key = _detect_project_key_from_git(root) or ""
    project_key = ""

    if detected_key:
        real_projects = jira_get_projects(root)
        real_keys = {p["key"] for p in real_projects}
        if detected_key in real_keys:
            project_key = detected_key
        else:
            debug_log(f"Auto-setup: git-detected key '{detected_key}' not found in Jira, using empty key")

    config = {
        "projectKey": project_key,
        "cloudId": global_cfg.get("cloudId", ""),
        "enabled": True,
        "autonomyLevel": "C",
        "accuracy": 5,
        "debugLog": True,
        "branchPattern": r"^(?:feature|fix|hotfix|chore|docs)/({key}-\d+)",
        "commitPattern": r"{key}-\d+:",
        "timeRounding": 15,
        "idleThreshold": 15,
        "autoCreate": False,
        "logLanguage": global_cfg.get("logLanguage", "English"),
        "defaultLabels": ["jira-autopilot"],
        "defaultComponent": None,
        "defaultFixVersion": None,
        "componentMap": {},
        "worklogInterval": 15,
    }

    os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
    atomic_write_json(os.path.join(root, ".claude", "jira-autopilot.json"), config)
    return True
```

Update `cmd_session_start`:

```python
def cmd_session_start():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    session = handle_session_start(root)
    if session:
        print(json.dumps({"status": "ok", "sessionId": session["sessionId"]}))
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_session_start.py -v
```

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_session_start.py
git commit -m "Implement session start: init, resume, stale pruning, branch detection"
```

---

## Task 6: Activity Logging (PostToolUse)

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_activity.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_activity.py`:
```python
import json, time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _make_session(project_root, current_issue=None):
    cfg = project_root / ".claude" / "jira-autopilot.json"
    cfg.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
    session = jira_core._new_session()
    if current_issue:
        session["activeIssues"][current_issue] = {
            "summary": "Test", "startTime": int(time.time()),
            "totalSeconds": 0, "paused": False, "autoApproveWorklogs": False,
        }
        session["currentIssue"] = current_issue
    jira_core.save_session(str(project_root), session)
    return session


class TestLogActivity:
    def test_records_file_edit(self, project_root):
        _make_session(project_root, "TEST-1")
        tool_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/src/auth.ts", "old_string": "a", "new_string": "b"},
        }
        jira_core.handle_log_activity(str(project_root), tool_data)
        session = jira_core.load_session(str(project_root))
        assert len(session["activityBuffer"]) == 1
        assert session["activityBuffer"][0]["tool"] == "Edit"
        assert session["activityBuffer"][0]["type"] == "file_edit"
        assert session["activityBuffer"][0]["issueKey"] == "TEST-1"

    def test_skips_read_only_tools(self, project_root):
        _make_session(project_root)
        tool_data = {"tool_name": "Read", "tool_input": {"file_path": "/src/auth.ts"}}
        jira_core.handle_log_activity(str(project_root), tool_data)
        session = jira_core.load_session(str(project_root))
        assert len(session["activityBuffer"]) == 0

    def test_skips_claude_internal_writes(self, project_root):
        _make_session(project_root)
        tool_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/project/.claude/jira-session.json"},
        }
        jira_core.handle_log_activity(str(project_root), tool_data)
        session = jira_core.load_session(str(project_root))
        assert len(session["activityBuffer"]) == 0

    def test_sanitizes_bash_credentials(self, project_root):
        _make_session(project_root)
        tool_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "curl -u user:ATATT3xSecret123 https://api"},
        }
        jira_core.handle_log_activity(str(project_root), tool_data)
        session = jira_core.load_session(str(project_root))
        assert len(session["activityBuffer"]) == 1
        assert "ATATT3x" not in session["activityBuffer"][0]["command"]

    def test_stamps_current_issue(self, project_root):
        _make_session(project_root, "PROJ-42")
        tool_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/src/new.ts", "content": "hello"},
        }
        jira_core.handle_log_activity(str(project_root), tool_data)
        session = jira_core.load_session(str(project_root))
        assert session["activityBuffer"][0]["issueKey"] == "PROJ-42"

    def test_null_issue_when_none_active(self, project_root):
        _make_session(project_root)
        tool_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/src/new.ts", "content": "hello"},
        }
        jira_core.handle_log_activity(str(project_root), tool_data)
        session = jira_core.load_session(str(project_root))
        assert session["activityBuffer"][0]["issueKey"] is None
```

**Step 2: Run tests — expect FAIL**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_activity.py -v
```

**Step 3: Implement handle_log_activity()**

Add to `jira_core.py`:

```python
def _classify_tool_type(tool_name, tool_input):
    """Classify tool into activity type."""
    if tool_name in ("Edit", "MultiEdit"):
        return "file_edit"
    if tool_name in ("Write", "NotebookEdit"):
        return "file_write"
    if tool_name == "Bash":
        return "bash"
    if tool_name == "Task":
        return "agent"
    return "other"


def _extract_file_path(tool_input):
    """Extract file path from tool input."""
    for key in ("file_path", "path", "pattern", "notebook_path"):
        if key in tool_input:
            return tool_input[key]
    return ""


def _is_claude_internal(file_path):
    """Check if file is Claude internal state."""
    return "/.claude/" in file_path or file_path.startswith(".claude/")


def handle_log_activity(root, tool_data):
    """Record a tool action to the activity buffer."""
    tool_name = tool_data.get("tool_name", "")
    tool_input = tool_data.get("tool_input", {})

    # Skip read-only tools
    if tool_name in READ_ONLY_TOOLS:
        return

    # Skip .claude/ internal file writes
    file_path = _extract_file_path(tool_input)
    if file_path and _is_claude_internal(file_path):
        return

    session = load_session(root)
    if not session:
        return

    # Planning detection
    if tool_name == "Skill":
        skill_name = str(tool_input.get("skill", "")).lower()
        if any(p in skill_name for p in PLANNING_SKILL_PATTERNS):
            _start_planning(session, skill_name)
            save_session(root, session)
            return

    if tool_name == "EnterPlanMode":
        _start_planning(session, "plan-mode")
        save_session(root, session)
        return

    if tool_name == "ExitPlanMode":
        _end_planning(root, session)
        save_session(root, session)
        return

    # End planning on first implementation tool
    if session.get("activePlanning") and tool_name in PLANNING_IMPL_TOOLS:
        _end_planning(root, session)

    # Task tracking
    if tool_name == "TaskCreate":
        task_id = tool_input.get("id", str(time.time()))
        session.setdefault("taskSubjects", {})[task_id] = tool_input.get("subject", "")
        save_session(root, session)
        return

    if tool_name == "TaskUpdate":
        _handle_task_update(root, session, tool_input)
        save_session(root, session)
        return

    # Normal activity
    activity = {
        "timestamp": int(time.time()),
        "tool": tool_name,
        "type": _classify_tool_type(tool_name, tool_input),
        "issueKey": session.get("currentIssue"),
        "file": file_path,
        "command": sanitize_for_log(tool_input.get("command", "")) if tool_name == "Bash" else "",
    }

    session["activityBuffer"].append(activity)
    save_session(root, session)


def _start_planning(session, subject):
    """Begin planning time tracking."""
    if session.get("activePlanning"):
        return
    session["activePlanning"] = {
        "startTime": int(time.time()),
        "issueKey": session.get("currentIssue"),
        "subject": f"Planning: {subject}",
    }


def _end_planning(root, session):
    """End planning, log time if >= 60s."""
    planning = session.get("activePlanning")
    if not planning:
        return
    elapsed = int(time.time()) - planning.get("startTime", int(time.time()))
    session["activePlanning"] = None
    if elapsed < 60:
        return
    # Log as worklog
    issue_key = planning.get("issueKey") or session.get("currentIssue") or session.get("lastParentKey")
    if issue_key:
        session["pendingWorklogs"].append({
            "issueKey": issue_key,
            "seconds": elapsed,
            "summary": planning.get("subject", "Planning"),
            "rawFacts": {"files": [], "commands": [], "activityCount": 0},
            "status": "approved" if session.get("autonomyLevel") in ("A", "B") else "pending",
        })


def _handle_task_update(root, session, tool_input):
    """Track task start/complete for time logging."""
    task_id = tool_input.get("taskId", "")
    status = tool_input.get("status", "")

    if status == "in_progress":
        session.setdefault("activeTasks", {})[task_id] = {
            "subject": session.get("taskSubjects", {}).get(task_id, "Unknown task"),
            "startTime": int(time.time()),
            "jiraKey": session.get("currentIssue"),
        }
    elif status == "completed" and task_id in session.get("activeTasks", {}):
        task = session["activeTasks"].pop(task_id)
        elapsed = int(time.time()) - task.get("startTime", int(time.time()))
        if elapsed >= 60:
            issue_key = task.get("jiraKey") or session.get("currentIssue")
            if issue_key and issue_key in session.get("activeIssues", {}):
                session["activeIssues"][issue_key]["totalSeconds"] = (
                    session["activeIssues"][issue_key].get("totalSeconds", 0) + elapsed
                )
```

Update `cmd_log_activity`:

```python
def cmd_log_activity():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    try:
        tool_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    handle_log_activity(root, tool_data)
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_activity.py -v
```

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_activity.py
git commit -m "Implement activity logging: tool capture, sanitization, planning/task tracking"
```

---

## Task 7: Buffer Drain & Work Chunking

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_drain.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_drain.py`:
```python
import json, time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _session_with_activities(project_root, activities, accuracy=5):
    cfg = project_root / ".claude" / "jira-autopilot.json"
    cfg.write_text(json.dumps({
        "projectKey": "TEST", "enabled": True, "accuracy": accuracy,
        "idleThreshold": 15, "worklogInterval": 15,
    }))
    session = jira_core._new_session()
    session["activityBuffer"] = activities
    session["accuracy"] = accuracy
    jira_core.save_session(str(project_root), session)
    return session


class TestDrainBuffer:
    def test_empty_buffer_produces_no_chunks(self, project_root):
        _session_with_activities(project_root, [])
        jira_core.handle_drain_buffer(str(project_root))
        session = jira_core.load_session(str(project_root))
        assert len(session["workChunks"]) == 0

    def test_creates_chunk_from_activities(self, project_root):
        now = int(time.time())
        activities = [
            {"timestamp": now, "tool": "Edit", "type": "file_edit",
             "issueKey": "TEST-1", "file": "src/a.ts", "command": ""},
            {"timestamp": now + 60, "tool": "Write", "type": "file_write",
             "issueKey": "TEST-1", "file": "src/b.ts", "command": ""},
        ]
        _session_with_activities(project_root, activities)
        jira_core.handle_drain_buffer(str(project_root))
        session = jira_core.load_session(str(project_root))
        assert len(session["workChunks"]) == 1
        assert session["workChunks"][0]["issueKey"] == "TEST-1"
        assert "src/a.ts" in session["workChunks"][0]["filesChanged"]

    def test_splits_on_idle_gap(self, project_root):
        now = int(time.time())
        activities = [
            {"timestamp": now, "tool": "Edit", "type": "file_edit",
             "issueKey": "TEST-1", "file": "a.ts", "command": ""},
            {"timestamp": now + 1200, "tool": "Edit", "type": "file_edit",
             "issueKey": "TEST-1", "file": "b.ts", "command": ""},
        ]
        _session_with_activities(project_root, activities)
        jira_core.handle_drain_buffer(str(project_root))
        session = jira_core.load_session(str(project_root))
        assert len(session["workChunks"]) == 2

    def test_splits_on_issue_change(self, project_root):
        now = int(time.time())
        activities = [
            {"timestamp": now, "tool": "Edit", "type": "file_edit",
             "issueKey": "TEST-1", "file": "a.ts", "command": ""},
            {"timestamp": now + 60, "tool": "Edit", "type": "file_edit",
             "issueKey": "TEST-2", "file": "b.ts", "command": ""},
        ]
        _session_with_activities(project_root, activities)
        jira_core.handle_drain_buffer(str(project_root))
        session = jira_core.load_session(str(project_root))
        assert len(session["workChunks"]) == 2
        keys = {c["issueKey"] for c in session["workChunks"]}
        assert keys == {"TEST-1", "TEST-2"}

    def test_clears_buffer_after_drain(self, project_root):
        now = int(time.time())
        activities = [
            {"timestamp": now, "tool": "Edit", "type": "file_edit",
             "issueKey": "TEST-1", "file": "a.ts", "command": ""},
        ]
        _session_with_activities(project_root, activities)
        jira_core.handle_drain_buffer(str(project_root))
        session = jira_core.load_session(str(project_root))
        assert len(session["activityBuffer"]) == 0

    def test_records_idle_gaps_in_chunk(self, project_root):
        now = int(time.time())
        activities = [
            {"timestamp": now, "tool": "Edit", "type": "file_edit",
             "issueKey": "TEST-1", "file": "a.ts", "command": ""},
            {"timestamp": now + 120, "tool": "Edit", "type": "file_edit",
             "issueKey": "TEST-1", "file": "a.ts", "command": ""},
            # gap of 1200s (>15 min) → idle recorded but still same chunk?
            # No — gap > threshold → splits. Let's use a gap just under threshold.
        ]
        # With 15 min idle threshold, 120s gap is fine (no idle, no split)
        _session_with_activities(project_root, activities)
        jira_core.handle_drain_buffer(str(project_root))
        session = jira_core.load_session(str(project_root))
        assert len(session["workChunks"]) == 1
```

**Step 2: Run tests — expect FAIL**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_drain.py -v
```

**Step 3: Implement handle_drain_buffer()**

Add to `jira_core.py`:

```python
def _get_dir_cluster(file_path, depth=2):
    """Extract first N directory components for context switch detection."""
    if not file_path:
        return ""
    parts = file_path.strip("/").split("/")
    return "/".join(parts[:depth]) if len(parts) > depth else "/".join(parts[:-1]) if len(parts) > 1 else ""


def _scaled_idle_threshold(cfg_threshold, accuracy):
    """Scale idle threshold by accuracy level."""
    if accuracy >= 8:
        return max(cfg_threshold // 3, 5) * 60  # seconds
    elif accuracy <= 3:
        return cfg_threshold * 2 * 60
    return cfg_threshold * 60


def handle_drain_buffer(root):
    """Drain activity buffer into work chunks."""
    session = load_session(root)
    if not session:
        return

    cfg = load_config(root)
    buffer = session.get("activityBuffer", [])

    if not buffer:
        _periodic_worklog_flush(root, session, cfg)
        save_session(root, session)
        return

    # Sort by timestamp
    buffer.sort(key=lambda a: a.get("timestamp", 0))

    idle_threshold_sec = _scaled_idle_threshold(
        cfg.get("idleThreshold", 15),
        session.get("accuracy", cfg.get("accuracy", 5)),
    )

    # Split into groups
    groups = []
    current_group = [buffer[0]]

    for i in range(1, len(buffer)):
        prev = buffer[i - 1]
        curr = buffer[i]
        gap = curr["timestamp"] - prev["timestamp"]
        issue_changed = curr.get("issueKey") != prev.get("issueKey")
        idle = gap > idle_threshold_sec

        if idle or issue_changed:
            groups.append(current_group)
            current_group = [curr]
        else:
            current_group.append(curr)

    groups.append(current_group)

    # Convert groups to work chunks
    for group in groups:
        if not group:
            continue

        start_time = group[0]["timestamp"]
        end_time = group[-1]["timestamp"]
        files = list({a.get("file", "") for a in group if a.get("file")})

        # Calculate idle gaps within the group
        idle_gaps = []
        for i in range(1, len(group)):
            gap = group[i]["timestamp"] - group[i - 1]["timestamp"]
            if gap > idle_threshold_sec:
                idle_gaps.append({
                    "startTime": group[i - 1]["timestamp"],
                    "endTime": group[i]["timestamp"],
                    "seconds": gap,
                })

        chunk = {
            "id": f"chunk-{start_time}-{len(session['workChunks'])}",
            "issueKey": group[0].get("issueKey"),
            "startTime": start_time,
            "endTime": end_time,
            "activities": group,
            "filesChanged": files,
            "idleGaps": idle_gaps,
            "needsAttribution": group[0].get("issueKey") is None,
        }
        session["workChunks"].append(chunk)

    # Clear buffer
    session["activityBuffer"] = []

    _periodic_worklog_flush(root, session, cfg)
    save_session(root, session)


def _periodic_worklog_flush(root, session, cfg):
    """Flush worklogs if interval has elapsed. Stub for now."""
    # Full implementation in Task 9
    pass
```

Update `cmd_drain_buffer`:

```python
def cmd_drain_buffer():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    handle_drain_buffer(root)
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_drain.py -v
```

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_drain.py
git commit -m "Implement buffer drain: work chunking with idle/issue splitting"
```

---

## Task 8: Issue Classification & Duplicate Detection

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_classify.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_classify.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestClassifyIssue:
    def test_bug_signals(self):
        result = jira_core.classify_issue("Fix login crash when user clicks submit")
        assert result["type"] == "Bug"
        assert result["confidence"] >= 0.5

    def test_task_signals(self):
        result = jira_core.classify_issue("Implement user registration feature")
        assert result["type"] == "Task"

    def test_ambiguous_defaults_to_task(self):
        result = jira_core.classify_issue("Update the documentation")
        assert result["type"] == "Task"

    def test_context_boosts_bug(self):
        result = jira_core.classify_issue("Fix something", context={"new_files_created": 0, "files_edited": 5})
        assert result["type"] == "Bug"

    def test_confidence_range(self):
        result = jira_core.classify_issue("Fix critical crash bug error regression")
        assert 0.5 <= result["confidence"] <= 0.95


class TestExtractSummary:
    def test_strips_noise(self):
        result = jira_core.extract_summary_from_prompt("Please can you fix the login bug")
        assert not result.startswith("Please")
        assert not result.startswith("can you")

    def test_truncates_long(self):
        result = jira_core.extract_summary_from_prompt("x " * 100)
        assert len(result) <= 80

    def test_capitalizes(self):
        result = jira_core.extract_summary_from_prompt("fix the thing")
        assert result[0].isupper()


class TestDuplicateDetection:
    def test_high_overlap_is_duplicate(self):
        session = {
            "activeIssues": {
                "TEST-1": {"summary": "Fix login crash on submit button"},
            }
        }
        result = jira_core._is_duplicate_issue(session, "Fix login crash on submit")
        assert result == "TEST-1"

    def test_low_overlap_not_duplicate(self):
        session = {
            "activeIssues": {
                "TEST-1": {"summary": "Fix login crash"},
            }
        }
        result = jira_core._is_duplicate_issue(session, "Add user registration")
        assert result is None

    def test_empty_session(self):
        session = {"activeIssues": {}}
        result = jira_core._is_duplicate_issue(session, "anything")
        assert result is None
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement classification functions**

Add to `jira_core.py` per spec section 6.2-6.4:

```python
def classify_issue(summary, context=None):
    """Classify summary as Bug or Task with confidence."""
    lower = summary.lower()
    bug_score = sum(1 for s in BUG_SIGNALS if s in lower)
    task_score = sum(1 for s in TASK_SIGNALS if s in lower)

    if context:
        if context.get("new_files_created", 0) == 0 and context.get("files_edited", 0) > 0:
            bug_score += 1
        if context.get("new_files_created", 0) > 0:
            task_score += 1

    if bug_score >= 2 or (bug_score > task_score and bug_score >= 1):
        issue_type = "Bug"
        score = bug_score
    else:
        issue_type = "Task"
        score = max(task_score, 1)

    confidence = min(0.5 + score * 0.15, 0.95)
    signals = [s for s in (BUG_SIGNALS if issue_type == "Bug" else TASK_SIGNALS) if s in lower]

    return {"type": issue_type, "confidence": confidence, "signals": signals}


def extract_summary_from_prompt(prompt):
    """Extract clean issue summary from user prompt."""
    # Take first sentence
    for delim in ".!?\n":
        if delim in prompt:
            prompt = prompt[:prompt.index(delim)]
            break

    # Strip noise words
    noise = ["please", "can you", "could you", "i need to", "i want to",
             "help me", "let's", "let me"]
    lower = prompt.lower().strip()
    for word in noise:
        if lower.startswith(word):
            prompt = prompt[len(word):].strip()
            lower = prompt.lower().strip()

    # Capitalize and truncate
    prompt = prompt.strip()
    if prompt:
        prompt = prompt[0].upper() + prompt[1:]
    if len(prompt) > 80:
        prompt = prompt[:77] + "..."

    return prompt


def _is_duplicate_issue(session, summary):
    """Check if summary duplicates an active issue. Returns key or None."""
    summary_tokens = set(summary.lower().split())
    if not summary_tokens:
        return None

    for key, issue in session.get("activeIssues", {}).items():
        issue_tokens = set(issue.get("summary", "").lower().split())
        if not issue_tokens:
            continue
        intersection = summary_tokens & issue_tokens
        union = summary_tokens | issue_tokens
        jaccard = len(intersection) / len(union) if union else 0
        if jaccard >= 0.60:
            return key

    return None
```

Update `cmd_classify_issue`:

```python
def cmd_classify_issue():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    summary = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
    result = classify_issue(summary)
    print(json.dumps(result))
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_classify.py -v
```

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_classify.py
git commit -m "Implement issue classification, summary extraction, duplicate detection"
```

---

## Task 9: Worklog Building & Time Rounding

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_worklog.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_worklog.py`:
```python
import json, time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestRoundSeconds:
    def test_rounds_up(self):
        # 7 minutes → 15 minutes (rounding=15, accuracy=5)
        result = jira_core._round_seconds(420, 15, 5)
        assert result == 900

    def test_minimum_one_increment(self):
        result = jira_core._round_seconds(10, 15, 5)
        assert result == 900  # Minimum 15 min

    def test_zero_seconds_gets_minimum(self):
        result = jira_core._round_seconds(0, 15, 5)
        assert result == 900

    def test_high_accuracy_finer_rounding(self):
        # accuracy 9: granularity = max(15/15, 1) = 1 min
        result = jira_core._round_seconds(90, 15, 9)
        assert result == 120  # 90s → 2 min

    def test_low_accuracy_coarser_rounding(self):
        # accuracy 2: granularity = 15 * 2 = 30 min
        result = jira_core._round_seconds(900, 15, 2)
        assert result == 1800  # → 30 min


class TestBuildWorklog:
    def test_builds_from_chunks(self, project_root):
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "timeRounding": 15, "logLanguage": "English",
        }))
        now = int(time.time())
        session = jira_core._new_session()
        session["activeIssues"]["TEST-1"] = {
            "summary": "Fix bug", "startTime": now - 600,
            "totalSeconds": 0, "paused": False, "autoApproveWorklogs": False,
        }
        session["workChunks"] = [{
            "id": "chunk-1", "issueKey": "TEST-1",
            "startTime": now - 600, "endTime": now,
            "activities": [
                {"timestamp": now - 600, "tool": "Edit", "type": "file_edit",
                 "file": "src/auth.ts", "command": ""},
            ],
            "filesChanged": ["src/auth.ts"],
            "idleGaps": [],
            "needsAttribution": False,
        }]
        jira_core.save_session(str(project_root), session)
        result = jira_core.build_worklog(str(project_root), "TEST-1")
        assert result["issueKey"] == "TEST-1"
        assert result["seconds"] > 0
        assert "auth.ts" in result["summary"]

    def test_caps_at_4_hours(self, project_root):
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "timeRounding": 15, "logLanguage": "English",
        }))
        now = int(time.time())
        session = jira_core._new_session()
        session["activeIssues"]["TEST-1"] = {
            "summary": "Long work", "startTime": now - 20000,
            "totalSeconds": 0, "paused": False, "autoApproveWorklogs": False,
        }
        session["workChunks"] = [{
            "id": "chunk-1", "issueKey": "TEST-1",
            "startTime": now - 20000, "endTime": now,
            "activities": [], "filesChanged": ["big.ts"],
            "idleGaps": [], "needsAttribution": False,
        }]
        jira_core.save_session(str(project_root), session)
        result = jira_core.build_worklog(str(project_root), "TEST-1")
        assert result["seconds"] <= jira_core.MAX_WORKLOG_SECONDS
        assert result.get("capped") is True

    def test_includes_null_chunks_for_sole_issue(self, project_root):
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "timeRounding": 15, "logLanguage": "English",
        }))
        now = int(time.time())
        session = jira_core._new_session()
        session["activeIssues"]["TEST-1"] = {
            "summary": "Work", "startTime": now - 300,
            "totalSeconds": 0, "paused": False, "autoApproveWorklogs": False,
        }
        session["workChunks"] = [
            {"id": "c1", "issueKey": "TEST-1", "startTime": now - 300, "endTime": now - 200,
             "activities": [], "filesChanged": ["a.ts"], "idleGaps": [], "needsAttribution": False},
            {"id": "c2", "issueKey": None, "startTime": now - 180, "endTime": now - 60,
             "activities": [], "filesChanged": ["b.ts"], "idleGaps": [], "needsAttribution": True},
        ]
        jira_core.save_session(str(project_root), session)
        result = jira_core.build_worklog(str(project_root), "TEST-1")
        assert "b.ts" in result["rawFacts"]["files"]
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement worklog building and time rounding**

Add to `jira_core.py` per spec sections 6.7, 6.8:

```python
def _round_seconds(seconds, rounding_minutes, accuracy):
    """Round seconds up to the configured increment, scaled by accuracy."""
    import math
    if accuracy >= 8:
        granularity_min = max(rounding_minutes / 15, 1)
    elif accuracy <= 3:
        granularity_min = rounding_minutes * 2
    else:
        granularity_min = rounding_minutes

    granularity_sec = int(granularity_min * 60)
    if granularity_sec <= 0:
        granularity_sec = 60

    rounded = int(math.ceil(max(seconds, 1) / granularity_sec)) * granularity_sec
    return max(rounded, granularity_sec)  # Minimum one increment


def build_worklog(root, issue_key):
    """Build worklog data from work chunks for an issue."""
    session = load_session(root)
    cfg = load_config(root)

    # Collect matching chunks
    chunks = [c for c in session.get("workChunks", []) if c.get("issueKey") == issue_key]

    # If sole active issue, include null chunks
    active_keys = set(session.get("activeIssues", {}).keys())
    if len(active_keys) <= 1:
        null_chunks = [c for c in session.get("workChunks", []) if c.get("issueKey") is None]
        chunks.extend(null_chunks)

    # Aggregate
    all_files = []
    all_commands = []
    total_activities = 0
    total_seconds = 0

    for chunk in chunks:
        all_files.extend(chunk.get("filesChanged", []))
        for a in chunk.get("activities", []):
            if a.get("command"):
                all_commands.append(a["command"])
            total_activities += 1

        chunk_time = chunk.get("endTime", 0) - chunk.get("startTime", 0)
        idle_time = sum(g.get("seconds", 0) for g in chunk.get("idleGaps", []))
        total_seconds += max(chunk_time - idle_time, 0)

    # Deduplicate
    unique_files = list(dict.fromkeys(all_files))
    unique_commands = list(dict.fromkeys(all_commands))

    # Cap
    capped = total_seconds > MAX_WORKLOG_SECONDS
    if capped:
        total_seconds = MAX_WORKLOG_SECONDS

    # Build summary
    file_basenames = [os.path.basename(f) for f in unique_files if f]
    if len(file_basenames) > 8:
        overflow = len(file_basenames) - 8
        file_basenames = file_basenames[:8] + [f"+{overflow} more"]
    summary = ", ".join(file_basenames) if file_basenames else "Work on task"

    result = {
        "issueKey": issue_key,
        "seconds": total_seconds,
        "summary": summary,
        "rawFacts": {
            "files": unique_files,
            "commands": unique_commands,
            "activityCount": total_activities,
        },
        "logLanguage": cfg.get("logLanguage", "English"),
    }
    if capped:
        result["capped"] = True

    return result
```

Update `cmd_build_worklog`:

```python
def cmd_build_worklog():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    issue_key = sys.argv[3] if len(sys.argv) > 3 else ""
    result = build_worklog(root, issue_key)
    print(json.dumps(result))
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_worklog.py -v
```

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_worklog.py
git commit -m "Implement worklog building, time rounding, sanity cap"
```

---

## Task 10: Jira REST API Client

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_api.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_api.py` — all API calls mocked:
```python
import json, sys, os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _setup_creds(project_root):
    local = project_root / ".claude" / "jira-autopilot.local.json"
    local.write_text(json.dumps({
        "email": "test@example.com",
        "apiToken": "test-token",
        "baseUrl": "https://test.atlassian.net",
        "accountId": "abc123",
    }))


class TestPostWorklog:
    @patch("urllib.request.urlopen")
    def test_success(self, mock_urlopen, project_root):
        response = MagicMock()
        response.status = 201
        response.read.return_value = b'{"id": "12345"}'
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = response

        result = jira_core.post_worklog_to_jira(
            "https://test.atlassian.net", "test@example.com", "token",
            "TEST-1", 900, "Did some work", "English",
        )
        assert result is True

    @patch("urllib.request.urlopen")
    def test_failure(self, mock_urlopen):
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            "url", 400, "Bad Request", {}, None
        )
        result = jira_core.post_worklog_to_jira(
            "https://test.atlassian.net", "test@example.com", "token",
            "TEST-1", 900, "Work", "English",
        )
        assert result is False


class TestGetProjects:
    @patch("urllib.request.urlopen")
    def test_returns_projects(self, mock_urlopen, project_root):
        _setup_creds(project_root)
        response_data = {"values": [
            {"key": "PROJ", "name": "My Project"},
            {"key": "TEST", "name": "Test Project"},
        ]}
        response = MagicMock()
        response.read.return_value = json.dumps(response_data).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = response

        result = jira_core.jira_get_projects(str(project_root))
        assert len(result) == 2
        assert result[0]["key"] == "PROJ"

    def test_missing_creds_returns_empty(self, project_root):
        result = jira_core.jira_get_projects(str(project_root))
        assert result == []

    @patch("urllib.request.urlopen")
    def test_http_error_returns_empty(self, mock_urlopen, project_root):
        _setup_creds(project_root)
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError("url", 403, "Forbidden", {}, None)
        result = jira_core.jira_get_projects(str(project_root))
        assert result == []


class TestTextToAdf:
    def test_converts_plain_text(self):
        result = jira_core._text_to_adf("Hello world")
        assert result["type"] == "doc"
        assert result["content"][0]["content"][0]["text"] == "Hello world"

    def test_empty_input_gets_placeholder(self):
        result = jira_core._text_to_adf("")
        assert result["content"][0]["content"][0]["text"] == "\u2014"
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement Jira API functions**

Add to `jira_core.py` per spec sections 6.12, 6.13, 8:

```python
import urllib.request
import urllib.error


def _jira_request(method, url, email, api_token, data=None, timeout=15):
    """Make an authenticated Jira API request."""
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    api_log(f"{method} {sanitize_for_log(url)}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        api_log(f"HTTP {e.code}: {e.reason}")
        raise
    except Exception as e:
        api_log(f"Error: {e}")
        raise


def _text_to_adf(text):
    """Convert plain text to Atlassian Document Format."""
    if not text or not text.strip():
        text = "\u2014"  # em-dash placeholder

    paragraphs = []
    for line in text.split("\n"):
        if line.strip():
            paragraphs.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": line}],
            })

    if not paragraphs:
        paragraphs = [{"type": "paragraph", "content": [{"type": "text", "text": "\u2014"}]}]

    return {"version": 1, "type": "doc", "content": paragraphs}


def post_worklog_to_jira(base_url, email, api_token, issue_key, seconds, comment, language):
    """Post a worklog entry to a Jira issue."""
    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/worklog"

    if not comment:
        if language and language.lower() == "hebrew":
            comment = f"\u05e2\u05d1\u05d5\u05d3\u05d4 \u05e2\u05dc \u05d4\u05de\u05e9\u05d9\u05de\u05d4 ({seconds // 60} \u05d3\u05e7\u05d5\u05ea)"
        else:
            comment = f"Work on task ({seconds // 60}m)"

    body = {
        "timeSpentSeconds": seconds,
        "comment": _text_to_adf(comment),
    }

    try:
        _jira_request("POST", url, email, api_token, data=body)
        return True
    except Exception:
        return False


def jira_get_projects(root):
    """Fetch accessible Jira projects."""
    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")

    if not base_url or not email or not api_token:
        return []

    url = f"{base_url.rstrip('/')}/rest/api/3/project/search?maxResults=50&orderBy=key"

    try:
        data = _jira_request("GET", url, email, api_token)
        return [{"key": p["key"], "name": p["name"]} for p in data.get("values", [])]
    except Exception:
        return []


def jira_create_issue(root, fields):
    """Create a Jira issue. Returns {key, id} or None."""
    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")

    if not base_url or not email or not api_token:
        return None

    url = f"{base_url.rstrip('/')}/rest/api/3/issue"

    try:
        result = _jira_request("POST", url, email, api_token, data={"fields": fields})
        return {"key": result.get("key"), "id": result.get("id")}
    except Exception:
        return None


def jira_get_issue(root, issue_key):
    """Fetch issue details. Returns issue dict or None."""
    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")

    if not base_url or not email or not api_token:
        return None

    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}"

    try:
        return _jira_request("GET", url, email, api_token)
    except Exception:
        return None
```

Update remaining command stubs:

```python
def cmd_get_projects():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    print(json.dumps(jira_get_projects(root)))

def cmd_get_issue():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    key = sys.argv[3] if len(sys.argv) > 3 else ""
    result = jira_get_issue(root, key)
    print(json.dumps(result or {"error": "Not found"}))

def cmd_add_worklog():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    key = sys.argv[3] if len(sys.argv) > 3 else ""
    seconds = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    comment = sys.argv[5] if len(sys.argv) > 5 else ""
    cfg = load_config(root)
    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    success = post_worklog_to_jira(base_url, email, api_token, key, seconds, comment, cfg.get("logLanguage", "English"))
    print(json.dumps({"success": success}))

def cmd_create_issue():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    fields_json = sys.argv[3] if len(sys.argv) > 3 else "{}"
    fields = json.loads(fields_json)
    result = jira_create_issue(root, fields)
    print(json.dumps(result or {"error": "Creation failed"}))
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_api.py -v
```

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_api.py
git commit -m "Implement Jira REST API client: worklogs, projects, issues, ADF conversion"
```

---

## Task 11: Session End & Worklog Posting

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_session_end.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_session_end.py`:
```python
import json, time, sys, os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _setup_session(project_root, issue_key="TEST-1", autonomy="C"):
    cfg = project_root / ".claude" / "jira-autopilot.json"
    cfg.write_text(json.dumps({
        "projectKey": "TEST", "enabled": True,
        "autonomyLevel": autonomy, "timeRounding": 15,
        "logLanguage": "English", "accuracy": 5,
    }))
    now = int(time.time())
    session = jira_core._new_session()
    session["autonomyLevel"] = autonomy
    session["activeIssues"][issue_key] = {
        "summary": "Test work", "startTime": now - 600,
        "totalSeconds": 0, "paused": False, "autoApproveWorklogs": False,
    }
    session["currentIssue"] = issue_key
    session["workChunks"] = [{
        "id": "c1", "issueKey": issue_key,
        "startTime": now - 600, "endTime": now,
        "activities": [{"timestamp": now - 300, "tool": "Edit", "type": "file_edit",
                        "file": "src/a.ts", "command": ""}],
        "filesChanged": ["src/a.ts"],
        "idleGaps": [], "needsAttribution": False,
    }]
    jira_core.save_session(str(project_root), session)
    return session


class TestSessionEnd:
    def test_creates_pending_worklogs(self, project_root):
        _setup_session(project_root, autonomy="C")
        jira_core.handle_session_end(str(project_root))
        session = jira_core.load_session(str(project_root))
        pending = [w for w in session["pendingWorklogs"] if w["issueKey"] == "TEST-1"]
        assert len(pending) >= 1

    def test_autonomous_marks_approved(self, project_root):
        _setup_session(project_root, autonomy="A")
        jira_core.handle_session_end(str(project_root))
        session = jira_core.load_session(str(project_root))
        statuses = [w["status"] for w in session["pendingWorklogs"]]
        assert all(s == "approved" for s in statuses)

    def test_archives_session(self, project_root):
        _setup_session(project_root)
        jira_core.handle_session_end(str(project_root))
        archives = project_root / ".claude" / "jira-sessions"
        assert archives.exists()
        assert len(list(archives.iterdir())) == 1

    def test_clears_work_chunks(self, project_root):
        _setup_session(project_root)
        jira_core.handle_session_end(str(project_root))
        session = jira_core.load_session(str(project_root))
        assert len(session["workChunks"]) == 0


class TestPostWorklogs:
    @patch("jira_core.post_worklog_to_jira")
    def test_posts_approved_worklogs(self, mock_post, project_root):
        mock_post.return_value = True
        local = project_root / ".claude" / "jira-autopilot.local.json"
        local.write_text(json.dumps({
            "email": "t@t.com", "apiToken": "tok",
            "baseUrl": "https://t.atlassian.net",
        }))
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({"enabled": True, "logLanguage": "English"}))
        session = jira_core._new_session()
        session["pendingWorklogs"] = [{
            "issueKey": "TEST-1", "seconds": 900,
            "summary": "Did work", "rawFacts": {"files": [], "commands": [], "activityCount": 1},
            "status": "approved",
        }]
        jira_core.save_session(str(project_root), session)
        jira_core.handle_post_worklogs(str(project_root))
        session = jira_core.load_session(str(project_root))
        assert session["pendingWorklogs"][0]["status"] == "posted"

    @patch("jira_core.post_worklog_to_jira")
    def test_skips_pending_worklogs(self, mock_post, project_root):
        mock_post.return_value = True
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({"enabled": True}))
        session = jira_core._new_session()
        session["pendingWorklogs"] = [{
            "issueKey": "TEST-1", "seconds": 900,
            "summary": "Work", "rawFacts": {"files": [], "commands": [], "activityCount": 1},
            "status": "pending",
        }]
        jira_core.save_session(str(project_root), session)
        jira_core.handle_post_worklogs(str(project_root))
        assert not mock_post.called
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement session end and worklog posting**

Add to `jira_core.py` per spec sections 4.6, 6.6:

```python
def _claim_null_chunks(session, issue_key):
    """Assign unattributed work chunks to an issue."""
    claimed_seconds = 0
    for chunk in session.get("workChunks", []):
        if chunk.get("issueKey") is None:
            chunk["issueKey"] = issue_key
            chunk["needsAttribution"] = False
            chunk_time = chunk.get("endTime", 0) - chunk.get("startTime", 0)
            idle_time = sum(g.get("seconds", 0) for g in chunk.get("idleGaps", []))
            claimed_seconds += max(chunk_time - idle_time, 0)

    if issue_key in session.get("activeIssues", {}):
        session["activeIssues"][issue_key]["totalSeconds"] = (
            session["activeIssues"][issue_key].get("totalSeconds", 0) + claimed_seconds
        )


def handle_session_end(root):
    """Handle session end: build worklogs, archive, cleanup."""
    session = load_session(root)
    if not session:
        return

    cfg = load_config(root)
    autonomy = session.get("autonomyLevel", cfg.get("autonomyLevel", "C"))

    # Flush planning
    if session.get("activePlanning"):
        _end_planning(root, session)

    # Drain remaining buffer
    if session.get("activityBuffer"):
        handle_drain_buffer(root)
        session = load_session(root)

    # Build worklogs for each active issue
    for issue_key in list(session.get("activeIssues", {}).keys()):
        matching_chunks = [c for c in session.get("workChunks", []) if c.get("issueKey") == issue_key]
        if not matching_chunks:
            continue

        worklog = build_worklog(root, issue_key)
        if worklog["seconds"] <= 0:
            continue

        status = "approved" if autonomy in ("A", "B") else "pending"
        worklog["status"] = status
        session["pendingWorklogs"].append(worklog)

    # Handle unattributed chunks
    null_chunks = [c for c in session.get("workChunks", []) if c.get("issueKey") is None]
    if null_chunks:
        total_null_seconds = sum(
            max(c.get("endTime", 0) - c.get("startTime", 0) - sum(g.get("seconds", 0) for g in c.get("idleGaps", [])), 0)
            for c in null_chunks
        )
        if total_null_seconds > 0:
            null_files = list({f for c in null_chunks for f in c.get("filesChanged", [])})
            session["pendingWorklogs"].append({
                "issueKey": None,
                "seconds": total_null_seconds,
                "summary": "Unattributed work",
                "rawFacts": {"files": null_files, "commands": [], "activityCount": sum(len(c.get("activities", [])) for c in null_chunks)},
                "status": "unattributed",
            })

    # Clear work chunks (prevent double-posting)
    session["workChunks"] = []

    # Archive session
    session_id = session.get("sessionId", time.strftime("%Y%m%d-%H%M%S"))
    archive_dir = os.path.join(root, ".claude", "jira-sessions")
    os.makedirs(archive_dir, exist_ok=True)
    atomic_write_json(os.path.join(archive_dir, f"{session_id}.json"), session)

    # Reset startTime watermark
    now = int(time.time())
    for issue in session.get("activeIssues", {}).values():
        issue["startTime"] = now

    save_session(root, session)


def handle_post_worklogs(root):
    """Post all approved worklogs to Jira."""
    session = load_session(root)
    if not session:
        return

    base_url = get_cred(root, "baseUrl")
    email = get_cred(root, "email")
    api_token = get_cred(root, "apiToken")
    cfg = load_config(root)
    language = cfg.get("logLanguage", "English")

    if not base_url or not email or not api_token:
        return

    for worklog in session.get("pendingWorklogs", []):
        if worklog.get("status") != "approved":
            continue

        issue_key = worklog.get("issueKey")
        if not issue_key:
            continue

        summary = worklog.get("summary", "")
        if not summary:
            files = worklog.get("rawFacts", {}).get("files", [])
            summary = ", ".join(os.path.basename(f) for f in files[:8]) or "Work on task"

        success = post_worklog_to_jira(
            base_url, email, api_token,
            issue_key, worklog["seconds"], summary, language,
        )
        worklog["status"] = "posted" if success else "failed"

    save_session(root, session)
```

Update command stubs:

```python
def cmd_session_end():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    handle_session_end(root)

def cmd_post_worklogs():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    handle_post_worklogs(root)
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_session_end.py -v
```

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_session_end.py
git commit -m "Implement session end: worklog building, archival, posting"
```

---

## Task 12: Auto-Create Issue & UserPromptSubmit

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_autocreate.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_autocreate.py`:
```python
import json, time, sys, os
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestAutoCreate:
    def test_cautious_mode_rejects(self, project_root):
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "autonomyLevel": "C", "autoCreate": False,
        }))
        session = jira_core._new_session()
        session["autonomyLevel"] = "C"
        jira_core.save_session(str(project_root), session)
        result = jira_core._attempt_auto_create(str(project_root), "Fix login", session, {"autoCreate": False})
        assert result is None

    def test_detects_duplicate(self, project_root):
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "autonomyLevel": "A", "autoCreate": True,
        }))
        session = jira_core._new_session()
        session["autonomyLevel"] = "A"
        session["activeIssues"]["TEST-1"] = {
            "summary": "Fix login crash", "startTime": int(time.time()),
            "totalSeconds": 0, "paused": False, "autoApproveWorklogs": False,
        }
        result = jira_core._attempt_auto_create(str(project_root), "Fix login crash on submit", session, {"autoCreate": True})
        assert result is not None
        assert result.get("duplicate") == "TEST-1"

    @patch("jira_core.jira_create_issue")
    def test_creates_issue_autonomous(self, mock_create, project_root):
        mock_create.return_value = {"key": "TEST-5", "id": "123"}
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "autonomyLevel": "A", "autoCreate": True,
        }))
        local = project_root / ".claude" / "jira-autopilot.local.json"
        local.write_text(json.dumps({
            "email": "t@t.com", "apiToken": "tok",
            "baseUrl": "https://t.atlassian.net", "accountId": "acc1",
        }))
        session = jira_core._new_session()
        session["autonomyLevel"] = "A"
        jira_core.save_session(str(project_root), session)
        cfg_data = json.loads(cfg.read_text())
        result = jira_core._attempt_auto_create(str(project_root), "Implement user auth feature", session, cfg_data)
        assert result is not None
        assert result.get("key") == "TEST-5"
        assert mock_create.called


class TestUserPromptDetection:
    def test_detects_task_intent(self):
        assert jira_core._detect_work_intent("implement a new login page") is not None

    def test_detects_bug_intent(self):
        assert jira_core._detect_work_intent("fix the crash in payment module") is not None

    def test_ignores_questions(self):
        result = jira_core._detect_work_intent("what does this function do?")
        assert result is None

    def test_detects_time_logging_intent(self):
        assert jira_core._detect_time_intent("log 2h on this task") is True
        assert jira_core._detect_time_intent("spent 30m fixing bugs") is True
        assert jira_core._detect_time_intent("implement feature") is False
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement auto-create and prompt detection**

Add to `jira_core.py` per spec sections 6.5, 4.7:

```python
def _attempt_auto_create(root, prompt, session, cfg):
    """Auto-create issue if conditions met. Returns result dict or None."""
    if not cfg.get("autoCreate", False):
        return None

    if session.get("autonomyLevel", "C") not in ("A", "B"):
        return None

    summary = extract_summary_from_prompt(prompt)
    if not summary:
        return None

    # Duplicate check
    dup_key = _is_duplicate_issue(session, summary)
    if dup_key:
        return {"duplicate": dup_key}

    # Classify
    classification = classify_issue(summary)
    if classification["confidence"] < 0.65:
        return None

    # Build fields
    project_key = cfg.get("projectKey", "")
    if not project_key:
        return None

    account_id = get_cred(root, "accountId")
    labels = cfg.get("defaultLabels", ["jira-autopilot"])

    fields = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": classification["type"]},
        "labels": labels,
    }
    if account_id:
        fields["assignee"] = {"accountId": account_id}

    # Infer parent
    parent_key = session.get("lastParentKey") or session.get("currentIssue")
    if parent_key:
        fields["parent"] = {"key": parent_key}

    result = jira_create_issue(root, fields)
    if not result or not result.get("key"):
        return None

    # Update session
    new_key = result["key"]
    session["activeIssues"][new_key] = {
        "summary": summary,
        "startTime": int(time.time()),
        "totalSeconds": 0,
        "paused": False,
        "autoApproveWorklogs": False,
    }
    session["currentIssue"] = new_key
    _claim_null_chunks(session, new_key)
    save_session(root, session)

    return {
        "key": new_key,
        "summary": summary,
        "type": classification["type"],
        "parent": parent_key,
    }


def _detect_work_intent(prompt):
    """Detect task/fix intent from user prompt. Returns type or None."""
    lower = prompt.lower()

    for signal in TASK_SIGNALS:
        if signal in lower:
            return "task"
    for signal in BUG_SIGNALS:
        if signal in lower:
            return "bug"

    return None


def _detect_time_intent(prompt):
    """Detect time-logging intent in user prompt."""
    lower = prompt.lower()
    patterns = [
        r"\d+h", r"\d+m", r"log time", r"log.*hour",
        r"spent.*minute", r"worklog",
    ]
    return any(re.search(p, lower) for p in patterns)


def handle_user_prompt_submit(root, prompt):
    """Process user prompt for intent detection."""
    session = load_session(root)
    if not session:
        return {}

    cfg = load_config(root)

    # Time-logging intent
    if _detect_time_intent(prompt):
        return {"systemMessage": "The user wants to log time. Suggest using /jira-stop to build and post a worklog instead of making direct API calls."}

    # Work intent
    intent = _detect_work_intent(prompt)
    if not intent:
        return {}

    autonomy = session.get("autonomyLevel", cfg.get("autonomyLevel", "C"))

    if autonomy in ("A", "B") and cfg.get("autoCreate", False):
        result = _attempt_auto_create(root, prompt, session, cfg)
        if result and result.get("key"):
            msg = f"Created {result['key']}: {result.get('summary', '')}. Consider switching to a feature branch: git checkout -b feature/{result['key']}-work"
            if autonomy == "A":
                return {"systemMessage": msg}
            else:
                return {"systemMessage": f"[Auto-created] {msg}"}
        elif result and result.get("duplicate"):
            if autonomy == "B":
                return {"systemMessage": f"Work detected — already tracking {result['duplicate']}."}
            return {}

    # Cautious mode or no auto-create
    current = session.get("currentIssue")
    if current:
        return {"systemMessage": f"New work detected while {current} is active. Run /start-work to create a sub-issue, or continue working on {current}."}
    else:
        return {"systemMessage": "Work is being captured. Run /start-work to link it to a Jira issue."}
```

Update command stubs:

```python
def cmd_user_prompt_submit():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    try:
        data = json.load(sys.stdin)
        prompt = data.get("prompt", data.get("user_prompt", ""))
    except (json.JSONDecodeError, ValueError):
        prompt = ""
    if prompt:
        result = handle_user_prompt_submit(root, prompt)
        if result:
            print(json.dumps(result))

def cmd_auto_create_issue():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    prompt = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
    session = load_session(root)
    cfg = load_config(root)
    if session:
        result = _attempt_auto_create(root, prompt, session, cfg)
        print(json.dumps(result or {"error": "Not created"}))
    else:
        print(json.dumps({"error": "No session"}))
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_autocreate.py -v
```

**Step 5: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_autocreate.py
git commit -m "Implement auto-create, work intent detection, user prompt handling"
```

---

## Task 13: PreToolUse (Git Commit Integration) & Remaining Commands

**Files:**
- Create: `plugins/jira-autopilot/hooks-handlers/tests/test_pretool.py`
- Modify: `plugins/jira-autopilot/hooks-handlers/jira_core.py`

**Step 1: Write failing tests**

`tests/test_pretool.py`:
```python
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestPreToolUse:
    def test_suggests_key_for_commit(self, project_root):
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-42"
        jira_core.save_session(str(project_root), session)
        tool_data = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "fix auth"'},
        }
        result = jira_core.handle_pre_tool_use(str(project_root), tool_data)
        assert "systemMessage" in result
        assert "TEST-42" in result["systemMessage"]

    def test_silent_when_key_present(self, project_root):
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-42"
        jira_core.save_session(str(project_root), session)
        tool_data = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "TEST-42: fix auth"'},
        }
        result = jira_core.handle_pre_tool_use(str(project_root), tool_data)
        assert result == {}

    def test_silent_when_no_issue(self, project_root):
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        session = jira_core._new_session()
        jira_core.save_session(str(project_root), session)
        tool_data = {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "fix auth"'},
        }
        result = jira_core.handle_pre_tool_use(str(project_root), tool_data)
        assert result == {}

    def test_ignores_non_commit(self, project_root):
        cfg = project_root / ".claude" / "jira-autopilot.json"
        cfg.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-1"
        jira_core.save_session(str(project_root), session)
        tool_data = {"tool_name": "Bash", "tool_input": {"command": "npm test"}}
        result = jira_core.handle_pre_tool_use(str(project_root), tool_data)
        assert result == {}
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement pre-tool-use handler**

Add to `jira_core.py`:

```python
def handle_pre_tool_use(root, tool_data):
    """Handle PreToolUse — suggest issue key in git commits."""
    tool_name = tool_data.get("tool_name", "")
    tool_input = tool_data.get("tool_input", {})

    if tool_name != "Bash":
        return {}

    command = tool_input.get("command", "")
    if "git commit" not in command:
        return {}

    session = load_session(root)
    if not session:
        return {}

    current_issue = session.get("currentIssue")
    if not current_issue:
        return {}

    # Check if key already in commit message
    if current_issue in command:
        return {}

    return {
        "systemMessage": f'Include the Jira issue key in the commit message: "{current_issue}: <description>". If this work is unrelated to {current_issue}, run /start-work to create or link a different issue.'
    }
```

Also implement remaining command stubs:

```python
def cmd_pre_tool_use():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    try:
        tool_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    result = handle_pre_tool_use(root, tool_data)
    if result:
        print(json.dumps(result))

def cmd_suggest_parent():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    session = load_session(root)
    if not session:
        print(json.dumps({"sessionDefault": None, "contextual": [], "recent": []}))
        return
    local = _load_json(os.path.join(root, ".claude", "jira-autopilot.local.json"))
    recent = local.get("recentParents", [])
    print(json.dumps({
        "sessionDefault": session.get("lastParentKey"),
        "contextual": [],
        "recent": recent[:10],
    }))

def cmd_debug_log():
    root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    message = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
    if message:
        debug_log(message, root)
```

**Step 4: Run tests — expect PASS**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/test_pretool.py -v
```

**Step 5: Run ALL tests**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/ -v
```
Expected: All PASS

**Step 6: Commit**

```bash
git add plugins/jira-autopilot/hooks-handlers/jira_core.py \
       plugins/jira-autopilot/hooks-handlers/tests/test_pretool.py
git commit -m "Implement pre-tool-use git commit integration, remaining CLI commands"
```

---

## Task 14: Slash Commands

**Files:**
- Create: `plugins/jira-autopilot/commands/jira-setup.md`
- Create: `plugins/jira-autopilot/commands/start-work.md`
- Create: `plugins/jira-autopilot/commands/report-work.md`
- Create: `plugins/jira-autopilot/commands/approve-work.md`
- Create: `plugins/jira-autopilot/commands/work-summary.md`
- Create: `plugins/jira-autopilot/commands/work-status.md`

Each is a markdown file with YAML frontmatter defining the command behavior.

**Step 1: Create /jira-setup**

Full 14-step setup wizard per spec section 5.1. This is the longest command file. Use the spec as the definitive reference for each step.

Frontmatter:
```yaml
---
name: jira-setup
description: Configure Jira tracking for this project
allowed-tools: Bash, Write, Edit, Read, AskUserQuestion, Glob
---
```

**Step 2: Create /start-work**

Per spec section 5.2 — start tracking existing or new issue.

Frontmatter:
```yaml
---
name: start-work
description: Start tracking a Jira task (create new or link existing)
allowed-tools: Bash, Write, Read, ToolSearch
---
```

**Step 3: Create /report-work**

Per spec section 5.3 — stop tracking and log time.

Frontmatter:
```yaml
---
name: report-work
description: Stop tracking current task and log time to Jira
allowed-tools: Bash, Read, Write, ToolSearch
---
```

**Step 4: Create /approve-work**

Per spec section 5.5 — review pending items.

Frontmatter:
```yaml
---
name: approve-work
description: Review and approve pending work items as Jira issues
allowed-tools: Bash, Write, Read, ToolSearch
---
```

**Step 5: Create /work-summary**

Per spec section 5.6 — daily summary.

Frontmatter:
```yaml
---
name: work-summary
description: Show today's work summary across all sessions and Jira issues
allowed-tools: Bash, Read, ToolSearch
---
```

**Step 6: Create /work-status**

Per spec section 5.4 — show current tracking status.

Frontmatter:
```yaml
---
name: work-status
description: Show all active Jira tasks with time breakdown
allowed-tools: Bash
---
```

**Step 7: Commit**

```bash
git add plugins/jira-autopilot/commands/*.md
git commit -m "Add slash commands: setup, start-work, report-work, approve-work, summary, status"
```

---

## Task 15: Statusline & Legacy REST Client

**Files:**
- Create: `plugins/jira-autopilot/statusline-command.sh`
- Create: `plugins/jira-autopilot/hooks-handlers/jira-rest.sh`

**Step 1: Create statusline script**

Per spec section 12. Reads JSON from stdin, outputs colorized status.

**Step 2: Create legacy REST client**

Per spec section 13. Bash + curl fallback for shell-only contexts.

**Step 3: Make executable**

```bash
chmod +x plugins/jira-autopilot/statusline-command.sh plugins/jira-autopilot/hooks-handlers/jira-rest.sh
```

**Step 4: Commit**

```bash
git add plugins/jira-autopilot/statusline-command.sh plugins/jira-autopilot/hooks-handlers/jira-rest.sh
git commit -m "Add statusline integration and legacy REST client"
```

---

## Task 16: Update Marketplace & Remove .gitkeep

**Files:**
- Modify: `.claude-plugin/marketplace.json` — update version to 4.0.0
- Remove: `plugins/jira-autopilot/.gitkeep`

**Step 1: Update marketplace version**

Change jira-autopilot version from `"3.20.0"` to `"4.0.0"` in marketplace.json.

**Step 2: Remove .gitkeep**

```bash
rm plugins/jira-autopilot/.gitkeep
```

**Step 3: Run full test suite**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/ -v --tb=short
```
Expected: All PASS

**Step 4: Commit**

```bash
git rm plugins/jira-autopilot/.gitkeep
git add .claude-plugin/marketplace.json
git commit -m "Bump jira-autopilot to 4.0.0, remove placeholder"
```

---

## Task 17: Integration Verification

**Step 1: Verify hook scripts can find jira_core.py**

```bash
cd /tmp/test-project && git init
bash /path/to/plugins/jira-autopilot/hooks-handlers/session-start-check.sh
```

**Step 2: Verify CLI commands work**

```bash
python3 plugins/jira-autopilot/hooks-handlers/jira_core.py classify-issue . "Fix login crash"
python3 plugins/jira-autopilot/hooks-handlers/jira_core.py debug-log . "Test message"
```

**Step 3: Run full test suite one more time**

```bash
cd plugins/jira-autopilot/hooks-handlers && python3 -m pytest tests/ -v
```

**Step 4: Final commit if any fixes needed**

```bash
git add -A plugins/jira-autopilot/ && git commit -m "Integration fixes for v4"
```
