"""Tests for jira_core.py — the central business logic module."""
import json
import os
import sys
import time
import urllib.error
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock

from jira_core import (
    CONFIG_NAME,
    LOCAL_CONFIG_NAME,
    SESSION_NAME,
    debug_log,
    load_config,
    load_global_config,
    load_local_config,
    load_session,
    save_session,
    get_cred,
    cmd_session_start,
    cmd_log_activity,
    cmd_drain_buffer,
    classify_issue,
    build_worklog,
    cmd_session_end,
    cmd_post_worklogs,
    post_worklog_to_jira,
    suggest_parent,
    _migrate_old_configs,
    _detect_issue_from_branch,
    _sanitize_command,
    _sanitize_session_commands,
    _get_idle_threshold_seconds,
    _get_dir_cluster,
    _detect_context_switch,
    _round_seconds,
    _text_to_adf,
    _handle_task_event,
    _log_task_time,
    _create_jira_issue,
)


# ── Task 1.1: Debug logging + config loading ─────────────────────────────


class TestDebugLog:
    def test_writes_to_file(self, tmp_path):
        log_path = str(tmp_path / "test.log")
        debug_log("test message", log_path=log_path)
        content = (tmp_path / "test.log").read_text()
        assert "test message" in content

    def test_disabled_does_not_write(self, tmp_path):
        log_path = str(tmp_path / "test.log")
        debug_log("should not appear", enabled=False, log_path=log_path)
        assert not (tmp_path / "test.log").exists()

    def test_includes_timestamp_and_category(self, tmp_path):
        log_path = str(tmp_path / "test.log")
        debug_log("hello", category="session-start", log_path=log_path)
        content = (tmp_path / "test.log").read_text()
        assert "[session-start]" in content
        assert "hello" in content

    def test_includes_extra_kwargs(self, tmp_path):
        log_path = str(tmp_path / "test.log")
        debug_log("init", log_path=log_path, root="/tmp", sessionId="abc")
        content = (tmp_path / "test.log").read_text()
        assert "root=/tmp" in content
        assert "sessionId=abc" in content

    def test_log_rotation(self, tmp_path):
        log_path = str(tmp_path / "test.log")
        # Write >1MB of data
        with open(log_path, "w") as f:
            f.write("x" * 1_100_000)
        debug_log("after rotation", log_path=log_path)
        # Original should be small now (just the new line)
        assert os.path.getsize(log_path) < 1000
        # Backup should exist
        assert (tmp_path / "test.log.1").exists()


class TestConfigLoading:
    def test_load_config_returns_empty_when_missing(self, tmp_path):
        assert load_config(str(tmp_path)) == {}

    def test_load_config_reads_file(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"projectKey": "TEST"}))
        cfg = load_config(str(tmp_path))
        assert cfg["projectKey"] == "TEST"

    def test_load_local_config(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / LOCAL_CONFIG_NAME).write_text(
            json.dumps({"email": "a@b.com"})
        )
        cfg = load_local_config(str(tmp_path))
        assert cfg["email"] == "a@b.com"

    def test_load_session_returns_empty_when_missing(self, tmp_path):
        assert load_session(str(tmp_path)) == {}

    def test_save_and_load_session(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        data = {"sessionId": "test-123", "currentIssue": None}
        save_session(str(tmp_path), data)
        loaded = load_session(str(tmp_path))
        assert loaded["sessionId"] == "test-123"

    def test_get_cred_project_local_first(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / LOCAL_CONFIG_NAME).write_text(
            json.dumps({"email": "local@test.com"})
        )
        assert get_cred(str(tmp_path), "email") == "local@test.com"

    def test_get_cred_returns_empty_when_missing(self, tmp_path):
        assert get_cred(str(tmp_path), "nonexistent") == ""


# ── Task 1.2: session-start ──────────────────────────────────────────────


class TestSessionStart:
    def _setup_config(self, tmp_path, cfg=None):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(exist_ok=True)
        default_cfg = {
            "projectKey": "TEST",
            "enabled": True,
            "debugLog": False,
            "accuracy": 5,
            "autonomyLevel": "C",
        }
        if cfg:
            default_cfg.update(cfg)
        (claude_dir / CONFIG_NAME).write_text(json.dumps(default_cfg))
        return claude_dir

    def test_creates_session(self, tmp_path):
        self._setup_config(tmp_path)
        cmd_session_start([str(tmp_path)])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert "sessionId" in session
        assert session["activeIssues"] == {}
        assert session["currentIssue"] is None
        assert session["autonomyLevel"] == "C"
        assert session["accuracy"] == 5

    def test_reads_autonomy_level_from_config(self, tmp_path):
        self._setup_config(tmp_path, {"autonomyLevel": "A"})
        cmd_session_start([str(tmp_path)])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert session["autonomyLevel"] == "A"

    def test_preserves_existing_session(self, tmp_path):
        """If session already exists with active issues, don't overwrite."""
        claude_dir = self._setup_config(tmp_path)
        existing = {
            "sessionId": "old-session",
            "currentIssue": "TEST-5",
            "activeIssues": {"TEST-5": {"startTime": 1000, "totalSeconds": 300}},
            "activityBuffer": [],
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(existing))
        cmd_session_start([str(tmp_path)])
        session = json.loads((claude_dir / SESSION_NAME).read_text())
        # Should keep active issues
        assert "TEST-5" in session["activeIssues"]

    def test_migrates_old_config_name(self, tmp_path):
        """Old jira-tracker.json should be migrated to jira-autopilot.json."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        old_config = {"projectKey": "OLD", "enabled": True}
        (claude_dir / "jira-tracker.json").write_text(json.dumps(old_config))
        # No jira-autopilot.json exists yet
        cmd_session_start([str(tmp_path)])
        # Should have migrated
        assert (claude_dir / CONFIG_NAME).exists()
        cfg = json.loads((claude_dir / CONFIG_NAME).read_text())
        assert cfg["projectKey"] == "OLD"

    def test_initializes_empty_buffers(self, tmp_path):
        self._setup_config(tmp_path)
        cmd_session_start([str(tmp_path)])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert session["activityBuffer"] == []
        assert session["workChunks"] == []
        assert session["pendingWorklogs"] == []

    def test_initializes_active_tasks(self, tmp_path):
        """New session should include empty activeTasks dict."""
        self._setup_config(tmp_path)
        cmd_session_start([str(tmp_path)])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert "activeTasks" in session
        assert session["activeTasks"] == {}

    def test_resumed_session_gets_active_tasks_if_missing(self, tmp_path):
        """Resumed session from old format (no activeTasks) gets it back-filled."""
        claude_dir = self._setup_config(tmp_path)
        existing = {
            "sessionId": "old-session",
            "currentIssue": "TEST-5",
            "activeIssues": {"TEST-5": {"startTime": 1000, "totalSeconds": 300}},
            "activityBuffer": [],
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(existing))
        cmd_session_start([str(tmp_path)])
        session = json.loads((claude_dir / SESSION_NAME).read_text())
        assert "activeTasks" in session
        assert session["activeTasks"] == {}

    def test_resumed_session_gets_session_id_if_missing(self, tmp_path):
        """Sessions created without sessionId (e.g. by /jira-start) get one on resume."""
        claude_dir = self._setup_config(tmp_path)
        existing = {
            # No sessionId — simulates session created by /jira-start directly
            "currentIssue": "TEST-5",
            "activeIssues": {"TEST-5": {"startTime": 1000, "totalSeconds": 0}},
            "activityBuffer": [],
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(existing))
        cmd_session_start([str(tmp_path)])
        session = json.loads((claude_dir / SESSION_NAME).read_text())
        assert session.get("sessionId"), "sessionId must be assigned on resume"


# ── Task 1.3: log-activity ───────────────────────────────────────────────


def _make_session_with_issue(tmp_path, issue_key="TEST-1"):
    """Helper: create config + session with an active issue."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    (claude_dir / CONFIG_NAME).write_text(json.dumps({
        "enabled": True, "debugLog": False,
    }))
    session = {
        "sessionId": "test",
        "currentIssue": issue_key,
        "activeIssues": {issue_key: {"startTime": 1000, "totalSeconds": 0}},
        "activityBuffer": [],
        "workChunks": [],
    }
    (claude_dir / SESSION_NAME).write_text(json.dumps(session))
    return claude_dir


class TestLogActivity:
    def test_stamps_current_issue(self, tmp_path):
        _make_session_with_issue(tmp_path, "TEST-1")
        tool_json = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/auth.ts"},
        })
        cmd_log_activity([str(tmp_path), tool_json])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert len(session["activityBuffer"]) == 1
        act = session["activityBuffer"][0]
        assert act["issueKey"] == "TEST-1"
        assert act["file"] == "src/auth.ts"
        assert act["tool"] == "Edit"

    def test_skips_read_only_tools(self, tmp_path):
        _make_session_with_issue(tmp_path)
        for tool in ["Read", "Glob", "Grep", "LS", "WebSearch",
                     "TaskList", "TaskGet", "ToolSearch", "Skill", "Task",
                     "ListMcpResourcesTool", "BashOutput"]:
            tool_json = json.dumps({
                "tool_name": tool,
                "tool_input": {"file_path": "src/x.ts"},
            })
            cmd_log_activity([str(tmp_path), tool_json])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert len(session["activityBuffer"]) == 0

    def test_records_bash_command(self, tmp_path):
        _make_session_with_issue(tmp_path)
        tool_json = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "npm test"},
        })
        cmd_log_activity([str(tmp_path), tool_json])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert len(session["activityBuffer"]) == 1
        assert session["activityBuffer"][0]["command"] == "npm test"
        assert session["activityBuffer"][0]["type"] == "bash"

    def test_no_current_issue_still_logs(self, tmp_path):
        """Activities without a current issue get issueKey=None."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "enabled": True, "debugLog": False,
        }))
        session = {
            "sessionId": "test", "currentIssue": None,
            "activeIssues": {}, "activityBuffer": [], "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        tool_json = json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "new.ts"},
        })
        cmd_log_activity([str(tmp_path), tool_json])
        session = json.loads((claude_dir / SESSION_NAME).read_text())
        assert len(session["activityBuffer"]) == 1
        assert session["activityBuffer"][0]["issueKey"] is None

    def test_extracts_file_from_write(self, tmp_path):
        _make_session_with_issue(tmp_path)
        tool_json = json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "src/new-file.ts", "content": "..."},
        })
        cmd_log_activity([str(tmp_path), tool_json])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert session["activityBuffer"][0]["file"] == "src/new-file.ts"
        assert session["activityBuffer"][0]["type"] == "file_write"


# ── Task 1.4: drain-buffer ───────────────────────────────────────────────


class TestDrainBuffer:
    def _setup(self, tmp_path, accuracy=5, idle_threshold=15):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(exist_ok=True)
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "enabled": True, "debugLog": False,
            "accuracy": accuracy, "idleThreshold": idle_threshold,
        }))
        return claude_dir

    def test_detects_idle_gap(self, tmp_path):
        """Activities with >15min gap should produce chunks with idle marker."""
        claude_dir = self._setup(tmp_path, accuracy=5, idle_threshold=15)
        now = int(time.time())
        session = {
            "sessionId": "test", "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": now - 3600, "totalSeconds": 0}},
            "activityBuffer": [
                {"timestamp": now - 3600, "tool": "Edit", "file": "a.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
                {"timestamp": now - 3500, "tool": "Edit", "file": "b.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
                # 20 min gap — idle
                {"timestamp": now - 2300, "tool": "Edit", "file": "c.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
            ],
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_drain_buffer([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        chunks = updated["workChunks"]
        assert len(chunks) >= 1
        has_idle = any(c.get("idleGaps") for c in chunks)
        assert has_idle

    def test_detects_context_switch(self, tmp_path):
        """Activities switching file directories should flag needsAttribution."""
        claude_dir = self._setup(tmp_path, accuracy=7)
        now = int(time.time())
        session = {
            "sessionId": "test", "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": now - 600, "totalSeconds": 0}},
            "activityBuffer": [
                {"timestamp": now - 600, "tool": "Edit", "file": "src/auth/login.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
                {"timestamp": now - 500, "tool": "Edit", "file": "src/auth/token.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
                {"timestamp": now - 400, "tool": "Edit", "file": "src/payments/stripe.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
                {"timestamp": now - 300, "tool": "Edit", "file": "src/payments/webhook.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
            ],
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_drain_buffer([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        flagged = [c for c in updated["workChunks"] if c.get("needsAttribution")]
        assert len(flagged) > 0

    def test_clears_activity_buffer(self, tmp_path):
        """After draining, activityBuffer should be empty."""
        claude_dir = self._setup(tmp_path)
        now = int(time.time())
        session = {
            "sessionId": "test", "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": now - 60, "totalSeconds": 0}},
            "activityBuffer": [
                {"timestamp": now - 60, "tool": "Edit", "file": "a.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
            ],
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_drain_buffer([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        assert updated["activityBuffer"] == []
        assert len(updated["workChunks"]) == 1

    def test_splits_on_issue_key_change(self, tmp_path):
        """Different issueKeys should produce separate chunks."""
        claude_dir = self._setup(tmp_path)
        now = int(time.time())
        session = {
            "sessionId": "test", "currentIssue": "TEST-2",
            "activeIssues": {
                "TEST-1": {"startTime": now - 600, "totalSeconds": 0},
                "TEST-2": {"startTime": now - 300, "totalSeconds": 0},
            },
            "activityBuffer": [
                {"timestamp": now - 600, "tool": "Edit", "file": "a.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
                {"timestamp": now - 500, "tool": "Edit", "file": "b.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
                {"timestamp": now - 300, "tool": "Edit", "file": "c.ts",
                 "type": "file_edit", "issueKey": "TEST-2"},
            ],
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_drain_buffer([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        chunks = updated["workChunks"]
        issue_keys = {c["issueKey"] for c in chunks}
        assert "TEST-1" in issue_keys
        assert "TEST-2" in issue_keys

    def test_empty_buffer_noop(self, tmp_path):
        """No activities → no chunks created."""
        claude_dir = self._setup(tmp_path)
        session = {
            "sessionId": "test", "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": 1000, "totalSeconds": 0}},
            "activityBuffer": [],
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_drain_buffer([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        assert updated["workChunks"] == []


# ── Task 1.5: classify-issue ─────────────────────────────────────────────


class TestClassifyIssue:
    def test_classify_bug_from_fix(self):
        result = classify_issue("Fix login redirect crash")
        assert result["type"] == "Bug"
        assert result["confidence"] > 0.5

    def test_classify_bug_from_multiple_signals(self):
        result = classify_issue("Fix broken error handling regression")
        assert result["type"] == "Bug"
        assert result["confidence"] > 0.7

    def test_classify_task(self):
        result = classify_issue("Add payment processing module")
        assert result["type"] == "Task"

    def test_classify_task_from_create(self):
        result = classify_issue("Create user registration page")
        assert result["type"] == "Task"

    def test_classify_ambiguous_defaults_to_task(self):
        result = classify_issue("Update dependencies")
        assert result["type"] == "Task"

    def test_context_no_new_files_boosts_bug(self):
        result = classify_issue("Fix auth flow", context={
            "new_files_created": 0, "files_edited": 3,
        })
        assert result["type"] == "Bug"
        assert result["confidence"] > 0.6

    def test_context_new_files_boosts_task(self):
        result = classify_issue("Setup new module", context={
            "new_files_created": 2, "files_edited": 0,
        })
        assert result["type"] == "Task"

    def test_returns_signals(self):
        result = classify_issue("Fix login crash")
        assert "fix" in result["signals"]
        assert "crash" in result["signals"]


# ── Task 1.6: build-worklog ──────────────────────────────────────────────


class TestBuildWorklog:
    def test_summary_includes_files(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5,
        }))
        session = {
            "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": 1000, "totalSeconds": 600}},
            "workChunks": [{
                "id": "chunk-1", "issueKey": "TEST-1",
                "startTime": 1000, "endTime": 1600,
                "filesChanged": ["src/auth.ts", "src/middleware.ts"],
                "activities": [
                    {"tool": "Edit", "type": "file_edit"},
                    {"tool": "Edit", "type": "file_edit"},
                    {"tool": "Bash", "type": "bash", "command": "npm test"},
                ],
                "idleGaps": [],
            }],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        result = build_worklog(str(tmp_path), "TEST-1")
        assert "auth.ts" in result["summary"] or "middleware.ts" in result["summary"]
        assert result["seconds"] > 0
        assert result["issueKey"] == "TEST-1"

    def test_raw_facts_contains_files_and_commands(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5,
        }))
        session = {
            "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": 1000, "totalSeconds": 0}},
            "workChunks": [{
                "id": "c1", "issueKey": "TEST-1",
                "startTime": 1000, "endTime": 1300,
                "filesChanged": ["a.ts"],
                "activities": [
                    {"tool": "Edit", "type": "file_edit"},
                    {"tool": "Bash", "type": "bash", "command": "npm test"},
                    {"tool": "Bash", "type": "bash", "command": "npm run lint"},
                ],
                "idleGaps": [],
            }],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        result = build_worklog(str(tmp_path), "TEST-1")
        assert "a.ts" in result["rawFacts"]["files"]
        assert "npm test" in result["rawFacts"]["commands"]
        assert result["rawFacts"]["activityCount"] == 3

    def test_no_chunks_returns_zero(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": False}))
        session = {
            "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": 1000, "totalSeconds": 0}},
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        result = build_worklog(str(tmp_path), "TEST-1")
        assert result["seconds"] == 0
        assert result["rawFacts"]["activityCount"] == 0


# ── Task 1.7: session-end ────────────────────────────────────────────────


class TestSessionEnd:
    def test_builds_pending_worklogs_autonomy_c(self, tmp_path):
        """Autonomy C: worklogs go to pendingWorklogs, not auto-posted."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5,
            "timeRounding": 15, "autonomyLevel": "C",
        }))
        now = int(time.time())
        session = {
            "sessionId": "test", "currentIssue": "TEST-1",
            "autonomyLevel": "C", "accuracy": 5,
            "activeIssues": {
                "TEST-1": {"startTime": now - 1800, "totalSeconds": 0, "paused": False},
            },
            "workChunks": [{
                "id": "c1", "issueKey": "TEST-1",
                "startTime": now - 1800, "endTime": now,
                "filesChanged": ["a.ts"],
                "activities": [{"tool": "Edit", "type": "file_edit"}] * 5,
                "idleGaps": [],
            }],
            "activityBuffer": [],
            "pendingWorklogs": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_session_end([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        assert len(updated.get("pendingWorklogs", [])) > 0
        assert updated["pendingWorklogs"][0]["status"] == "pending"
        assert updated["pendingWorklogs"][0]["issueKey"] == "TEST-1"

    def test_rounds_time_per_config(self, tmp_path):
        """Time should be rounded per timeRounding setting."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5,
            "timeRounding": 15, "autonomyLevel": "C",
        }))
        now = int(time.time())
        # 25 minutes of work → should round to 30 min (15-min increments)
        session = {
            "sessionId": "test", "currentIssue": "TEST-1",
            "autonomyLevel": "C", "accuracy": 5,
            "activeIssues": {
                "TEST-1": {"startTime": now - 1500, "totalSeconds": 0, "paused": False},
            },
            "workChunks": [{
                "id": "c1", "issueKey": "TEST-1",
                "startTime": now - 1500, "endTime": now,
                "filesChanged": ["a.ts"],
                "activities": [{"tool": "Edit", "type": "file_edit"}],
                "idleGaps": [],
            }],
            "activityBuffer": [],
            "pendingWorklogs": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_session_end([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        pending = updated["pendingWorklogs"][0]
        # 25 min → rounded to 30 min (1800s) with 15-min rounding
        assert pending["seconds"] % (15 * 60) == 0

    def test_archives_session(self, tmp_path):
        """Session should be archived after end."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        sessions_dir = claude_dir / "jira-sessions"
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5,
            "timeRounding": 15, "autonomyLevel": "C",
        }))
        now = int(time.time())
        session = {
            "sessionId": "test-archive", "currentIssue": None,
            "autonomyLevel": "C", "accuracy": 5,
            "activeIssues": {},
            "workChunks": [],
            "activityBuffer": [],
            "pendingWorklogs": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_session_end([str(tmp_path)])
        # Archived session should exist
        assert sessions_dir.exists()
        archives = list(sessions_dir.glob("*.json"))
        assert len(archives) >= 1

    def test_handles_multiple_issues(self, tmp_path):
        """Multiple active issues should each get a pending worklog."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5,
            "timeRounding": 15, "autonomyLevel": "C",
        }))
        now = int(time.time())
        session = {
            "sessionId": "test", "currentIssue": "TEST-2",
            "autonomyLevel": "C", "accuracy": 5,
            "activeIssues": {
                "TEST-1": {"startTime": now - 3600, "totalSeconds": 0, "paused": False},
                "TEST-2": {"startTime": now - 1800, "totalSeconds": 0, "paused": False},
            },
            "workChunks": [
                {
                    "id": "c1", "issueKey": "TEST-1",
                    "startTime": now - 3600, "endTime": now - 1800,
                    "filesChanged": ["a.ts"],
                    "activities": [{"tool": "Edit", "type": "file_edit"}] * 3,
                    "idleGaps": [],
                },
                {
                    "id": "c2", "issueKey": "TEST-2",
                    "startTime": now - 1800, "endTime": now,
                    "filesChanged": ["b.ts"],
                    "activities": [{"tool": "Edit", "type": "file_edit"}] * 2,
                    "idleGaps": [],
                },
            ],
            "activityBuffer": [],
            "pendingWorklogs": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_session_end([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        issue_keys = {w["issueKey"] for w in updated["pendingWorklogs"]}
        assert "TEST-1" in issue_keys
        assert "TEST-2" in issue_keys


# ── Task 1.8: suggest-parent ─────────────────────────────────────────────


class TestSuggestParent:
    def test_returns_recent_parents(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / LOCAL_CONFIG_NAME).write_text(json.dumps({
            "recentParents": ["TEST-10", "TEST-8"],
        }))
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "projectKey": "TEST", "debugLog": False,
        }))
        session = {"lastParentKey": "TEST-10"}
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        result = suggest_parent(str(tmp_path), "Fix auth bug")
        recent_keys = [r["key"] for r in result.get("recent", [])]
        assert "TEST-10" in recent_keys
        assert "TEST-8" in recent_keys

    def test_session_default_from_last_parent(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / LOCAL_CONFIG_NAME).write_text(json.dumps({
            "recentParents": ["TEST-10"],
        }))
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "projectKey": "TEST", "debugLog": False,
        }))
        session = {"lastParentKey": "TEST-10"}
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        result = suggest_parent(str(tmp_path), "Some task")
        assert result["sessionDefault"] == "TEST-10"

    def test_no_recent_parents(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "projectKey": "TEST", "debugLog": False,
        }))
        (claude_dir / SESSION_NAME).write_text(json.dumps({}))
        result = suggest_parent(str(tmp_path), "Some task")
        assert result["sessionDefault"] is None
        assert result["recent"] == []
        assert result["contextual"] == []


# ── Task 1.9: post-worklogs ──────────────────────────────────────────────


class TestPostWorklogs:
    def _setup(self, tmp_path, autonomy="A"):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "autonomyLevel": autonomy,
        }))
        (claude_dir / LOCAL_CONFIG_NAME).write_text(json.dumps({
            "email": "test@example.com",
            "apiToken": "test-token",
            "baseUrl": "https://test.atlassian.net",
        }))
        return claude_dir

    def test_posts_approved_entries(self, tmp_path):
        claude_dir = self._setup(tmp_path)
        session = {
            "pendingWorklogs": [
                {"issueKey": "TEST-1", "seconds": 900, "summary": "Fixed bug", "status": "approved"},
            ],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        with patch("jira_core.post_worklog_to_jira", return_value=True) as mock_post:
            cmd_post_worklogs([str(tmp_path)])
        mock_post.assert_called_once_with(
            "https://test.atlassian.net", "test@example.com", "test-token",
            "TEST-1", 900, "Fixed bug",
        )
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        assert updated["pendingWorklogs"][0]["status"] == "posted"

    def test_skips_pending_and_deferred(self, tmp_path):
        claude_dir = self._setup(tmp_path)
        session = {
            "pendingWorklogs": [
                {"issueKey": "TEST-1", "seconds": 900, "summary": "a", "status": "pending"},
                {"issueKey": "TEST-2", "seconds": 900, "summary": "b", "status": "deferred"},
            ],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        with patch("jira_core.post_worklog_to_jira", return_value=True) as mock_post:
            cmd_post_worklogs([str(tmp_path)])
        mock_post.assert_not_called()

    def test_marks_failed_on_api_error(self, tmp_path):
        claude_dir = self._setup(tmp_path)
        session = {
            "pendingWorklogs": [
                {"issueKey": "TEST-1", "seconds": 900, "summary": "x", "status": "approved"},
            ],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        with patch("jira_core.post_worklog_to_jira", return_value=False):
            cmd_post_worklogs([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        assert updated["pendingWorklogs"][0]["status"] == "failed"

    def test_noop_without_credentials(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": False}))
        session = {
            "pendingWorklogs": [
                {"issueKey": "TEST-1", "seconds": 900, "summary": "x", "status": "approved"},
            ],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        # Patch global config to return empty so no fallback credentials exist
        with patch("jira_core.load_global_config", return_value={}), \
             patch("jira_core.post_worklog_to_jira", return_value=True) as mock_post:
            cmd_post_worklogs([str(tmp_path)])
        mock_post.assert_not_called()


# ── Task-level time tracking ─────────────────────────────────────────────


class TestTaskEventHandling:
    def _setup(self, tmp_path, accuracy=5, issue_key="TEST-1"):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(exist_ok=True)
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "enabled": True, "debugLog": False,
            "accuracy": accuracy, "projectKey": "TEST",
        }))
        (claude_dir / LOCAL_CONFIG_NAME).write_text(json.dumps({
            "email": "test@example.com",
            "apiToken": "test-token",
            "baseUrl": "https://test.atlassian.net",
        }))
        session = {
            "sessionId": "test",
            "currentIssue": issue_key,
            "activeIssues": {issue_key: {"startTime": 1000, "totalSeconds": 0}},
            "accuracy": accuracy,
            "activityBuffer": [],
            "workChunks": [],
            "activeTasks": {},
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        return claude_dir

    def test_task_start_records_in_active_tasks(self, tmp_path):
        """TaskUpdate → in_progress records task in activeTasks."""
        self._setup(tmp_path)
        tool_json = json.dumps({
            "tool_name": "TaskUpdate",
            "tool_input": {"taskId": "1", "status": "in_progress"},
            "tool_response": {"taskId": "1", "subject": "Create TitleBadge", "status": "in_progress"},
        })
        cmd_log_activity([str(tmp_path), tool_json])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert "1" in session["activeTasks"]
        assert session["activeTasks"]["1"]["subject"] == "Create TitleBadge"
        assert "startTime" in session["activeTasks"]["1"]

    def test_task_complete_removes_from_active_tasks(self, tmp_path):
        """TaskUpdate → completed removes task from activeTasks."""
        self._setup(tmp_path)
        # Seed activeTasks with a task that started 2 minutes ago
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        session["activeTasks"]["1"] = {
            "subject": "Create TitleBadge",
            "startTime": int(time.time()) - 120,
            "jiraKey": None,
        }
        (tmp_path / ".claude" / SESSION_NAME).write_text(json.dumps(session))

        complete_json = json.dumps({
            "tool_name": "TaskUpdate",
            "tool_input": {"taskId": "1", "status": "completed"},
            "tool_response": {"taskId": "1", "subject": "Create TitleBadge", "status": "completed"},
        })
        with patch("jira_core.post_worklog_to_jira", return_value=True):
            cmd_log_activity([str(tmp_path), complete_json])

        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert "1" not in session.get("activeTasks", {})

    def test_task_complete_low_accuracy_logs_to_parent_issue(self, tmp_path):
        """accuracy < 8 → worklog posted to currentIssue with task subject as comment."""
        self._setup(tmp_path, accuracy=5)
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        session["activeTasks"]["1"] = {
            "subject": "Build payment feature",
            "startTime": int(time.time()) - 120,
            "jiraKey": None,
        }
        (tmp_path / ".claude" / SESSION_NAME).write_text(json.dumps(session))

        complete_json = json.dumps({
            "tool_name": "TaskUpdate",
            "tool_input": {"taskId": "1", "status": "completed"},
            "tool_response": {"taskId": "1", "subject": "Build payment feature", "status": "completed"},
        })
        with patch("jira_core.post_worklog_to_jira", return_value=True) as mock_post:
            cmd_log_activity([str(tmp_path), complete_json])

        mock_post.assert_called_once()
        args = mock_post.call_args[0]
        assert args[3] == "TEST-1"  # posted to currentIssue
        assert "Build payment feature" in args[5]  # subject in comment

    def test_task_complete_high_accuracy_creates_subissue(self, tmp_path):
        """accuracy >= 8 → creates sub-issue then logs worklog to it."""
        self._setup(tmp_path, accuracy=8)
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        session["activeTasks"]["2"] = {
            "subject": "Add OAuth integration",
            "startTime": int(time.time()) - 300,
            "jiraKey": None,
        }
        (tmp_path / ".claude" / SESSION_NAME).write_text(json.dumps(session))

        complete_json = json.dumps({
            "tool_name": "TaskUpdate",
            "tool_input": {"taskId": "2", "status": "completed"},
            "tool_response": {"taskId": "2", "subject": "Add OAuth integration", "status": "completed"},
        })
        with patch("jira_core._create_jira_issue", return_value="TEST-99") as mock_create, \
             patch("jira_core.post_worklog_to_jira", return_value=True) as mock_post:
            cmd_log_activity([str(tmp_path), complete_json])

        mock_create.assert_called_once()
        create_args = mock_create.call_args[0]
        assert create_args[3] == "TEST"           # project_key
        assert create_args[4] == "Add OAuth integration"  # summary
        assert create_args[5] == "TEST-1"         # parent_key

        mock_post.assert_called_once()
        post_args = mock_post.call_args[0]
        assert post_args[3] == "TEST-99"          # logged to new sub-issue

    def test_elapsed_less_than_60s_skips_logging(self, tmp_path):
        """Micro-tasks (< 60s elapsed) produce no worklog."""
        self._setup(tmp_path, accuracy=5)
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        session["activeTasks"]["3"] = {
            "subject": "Tiny tweak",
            "startTime": int(time.time()) - 10,  # only 10s ago
            "jiraKey": None,
        }
        (tmp_path / ".claude" / SESSION_NAME).write_text(json.dumps(session))

        complete_json = json.dumps({
            "tool_name": "TaskUpdate",
            "tool_input": {"taskId": "3", "status": "completed"},
            "tool_response": {"taskId": "3", "subject": "Tiny tweak", "status": "completed"},
        })
        with patch("jira_core.post_worklog_to_jira", return_value=True) as mock_post:
            cmd_log_activity([str(tmp_path), complete_json])

        mock_post.assert_not_called()


# ── load_global_config ───────────────────────────────────────────────────


class TestLoadGlobalConfig:
    def test_returns_empty_when_missing(self, tmp_path, monkeypatch):
        import jira_core
        monkeypatch.setattr(jira_core, "GLOBAL_CONFIG_PATH", tmp_path / "nonexistent.json")
        assert load_global_config() == {}

    def test_reads_when_present(self, tmp_path, monkeypatch):
        import jira_core
        p = tmp_path / "global.json"
        p.write_text(json.dumps({"email": "g@test.com"}))
        monkeypatch.setattr(jira_core, "GLOBAL_CONFIG_PATH", p)
        assert load_global_config()["email"] == "g@test.com"


# ── debug_log rotation edge case ─────────────────────────────────────────


class TestDebugLogRotationBackup:
    def test_unlinks_existing_backup_before_rotate(self, tmp_path):
        log_path = str(tmp_path / "test.log")
        backup_path = tmp_path / "test.log.1"
        backup_path.write_text("old backup")
        with open(log_path, "w") as f:
            f.write("x" * 1_100_000)
        debug_log("rotate again", log_path=log_path)
        assert backup_path.exists()
        assert backup_path.stat().st_size > 1_000_000


# ── _migrate_old_configs ─────────────────────────────────────────────────


class TestMigrateOldConfigs:
    def test_noop_when_no_claude_dir(self, tmp_path):
        _migrate_old_configs(str(tmp_path))  # no exception

    def test_noop_when_new_config_already_exists(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "jira-tracker.json").write_text(json.dumps({"old": True}))
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"new": True}))
        _migrate_old_configs(str(tmp_path))
        cfg = json.loads((claude_dir / CONFIG_NAME).read_text())
        assert cfg == {"new": True}


# ── _detect_issue_from_branch ────────────────────────────────────────────


class TestDetectIssueFromBranch:
    def _cfg(self, pattern="({key}-\\d+)", project_key="TEST"):
        return {"branchPattern": pattern, "projectKey": project_key}

    def test_extracts_key_from_branch(self, tmp_path):
        cfg = self._cfg()
        with patch("jira_core.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="fix/TEST-42-my-feature\n")
            result = _detect_issue_from_branch(str(tmp_path), cfg)
        assert result == "TEST-42"

    def test_returns_none_when_no_match(self, tmp_path):
        cfg = self._cfg()
        with patch("jira_core.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="main\n")
            result = _detect_issue_from_branch(str(tmp_path), cfg)
        assert result is None

    def test_returns_none_on_git_error(self, tmp_path):
        import subprocess
        cfg = self._cfg()
        with patch("jira_core.subprocess.run", side_effect=subprocess.SubprocessError):
            result = _detect_issue_from_branch(str(tmp_path), cfg)
        assert result is None

    def test_returns_none_when_empty_branch(self, tmp_path):
        cfg = self._cfg()
        with patch("jira_core.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            result = _detect_issue_from_branch(str(tmp_path), cfg)
        assert result is None

    def test_returns_none_without_pattern(self, tmp_path):
        result = _detect_issue_from_branch(str(tmp_path), {"projectKey": "TEST"})
        assert result is None

    def test_returns_none_without_project_key(self, tmp_path):
        result = _detect_issue_from_branch(str(tmp_path), {"branchPattern": "(.+)"})
        assert result is None


# ── cmd_session_start extra branches ─────────────────────────────────────


class TestSessionStartExtra:
    def _setup_config(self, tmp_path, extra=None):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(exist_ok=True)
        cfg = {"projectKey": "TEST", "enabled": True, "debugLog": False,
               "accuracy": 5, "autonomyLevel": "C"}
        if extra:
            cfg.update(extra)
        (claude_dir / CONFIG_NAME).write_text(json.dumps(cfg))
        return claude_dir

    def test_does_not_create_session_when_disabled(self, tmp_path):
        self._setup_config(tmp_path, {"enabled": False})
        cmd_session_start([str(tmp_path)])
        assert not (tmp_path / ".claude" / SESSION_NAME).exists()

    def test_detects_branch_issue_on_new_session(self, tmp_path):
        self._setup_config(tmp_path, {
            "branchPattern": "({key}-\\d+)",
            "projectKey": "TEST",
        })
        with patch("jira_core._detect_issue_from_branch", return_value="TEST-99"):
            cmd_session_start([str(tmp_path)])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert session["currentIssue"] == "TEST-99"
        assert "TEST-99" in session["activeIssues"]


# ── _sanitize_command + _sanitize_session_commands ───────────────────────


class TestSanitize:
    def test_sanitize_empty_string_returns_empty(self):
        assert _sanitize_command("") == ""

    def test_sanitize_none_returns_none(self):
        assert _sanitize_command(None) is None

    def test_sanitize_redacts_api_token(self):
        cmd = 'curl -H "Authorization: Basic ATATT3xFfGF0test123456789012345678901234567890"'
        result = _sanitize_command(cmd)
        assert "ATATT" not in result

    def test_sanitize_session_commands_workchunks(self):
        session = {
            "workChunks": [{"activities": [
                {"tool": "Bash", "command": "curl -u user:ATATT3xFfGF0secret12345678901234567890abc"},
            ]}],
            "activityBuffer": [],
        }
        _sanitize_session_commands(session)
        assert "ATATT" not in session["workChunks"][0]["activities"][0]["command"]

    def test_sanitize_session_commands_activity_buffer(self):
        session = {
            "workChunks": [],
            "activityBuffer": [
                {"tool": "Bash", "command": 'printf "user:ATATT3xFfGF0secret12345" | base64'},
            ],
        }
        _sanitize_session_commands(session)
        assert "ATATT" not in session["activityBuffer"][0]["command"]

    def test_sanitize_session_skips_no_command(self):
        session = {
            "workChunks": [{"activities": [{"tool": "Edit"}]}],
            "activityBuffer": [{"tool": "Read"}],
        }
        _sanitize_session_commands(session)  # no exception


# ── cmd_log_activity edge cases ──────────────────────────────────────────


class TestLogActivityEdgeCases:
    def test_returns_early_when_no_session(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"enabled": True}))
        tool_json = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "a.ts"}})
        cmd_log_activity([str(tmp_path), tool_json])  # no exception

    def test_returns_early_on_invalid_json(self, tmp_path):
        _make_session_with_issue(tmp_path)
        cmd_log_activity([str(tmp_path), "not-valid-json"])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert session["activityBuffer"] == []

    def test_normalizes_non_dict_tool_response(self, tmp_path):
        _make_session_with_issue(tmp_path)
        tool_json = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": "a.ts"},
            "tool_response": "some string response",
        })
        cmd_log_activity([str(tmp_path), tool_json])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert len(session["activityBuffer"]) == 1

    def test_skips_claude_internal_file(self, tmp_path):
        _make_session_with_issue(tmp_path)
        tool_json = json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "/repo/.claude/jira-session.json"},
        })
        cmd_log_activity([str(tmp_path), tool_json])
        session = json.loads((tmp_path / ".claude" / SESSION_NAME).read_text())
        assert session["activityBuffer"] == []


# ── _create_jira_issue HTTP ───────────────────────────────────────────────


class TestCreateJiraIssue:
    def test_returns_issue_key_on_success(self):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({"key": "TEST-42"}).encode()
        with patch("jira_core.urllib.request.urlopen", return_value=mock_resp):
            key = _create_jira_issue(
                "https://test.atlassian.net", "u@t.com", "token",
                "TEST", "Do something", "TEST-1",
            )
        assert key == "TEST-42"

    def test_returns_none_on_exception(self):
        with patch("jira_core.urllib.request.urlopen", side_effect=Exception("network")):
            key = _create_jira_issue(
                "https://test.atlassian.net", "u@t.com", "token",
                "TEST", "Do something", "TEST-1",
            )
        assert key is None


# ── _log_task_time no-credentials path ───────────────────────────────────


class TestLogTaskTimeNoCreds:
    def test_returns_early_when_no_credentials(self, tmp_path):
        session = {"currentIssue": "TEST-1", "accuracy": 5}
        with patch("jira_core.get_cred", return_value=""), \
             patch("jira_core.post_worklog_to_jira") as mock_post:
            _log_task_time(str(tmp_path), session, {}, "Some task", 120)
        mock_post.assert_not_called()


# ── _handle_task_event edge cases ────────────────────────────────────────


class TestHandleTaskEventEdgeCases:
    def _session(self):
        return {"currentIssue": "TEST-1", "accuracy": 5, "activeTasks": {}}

    def test_skips_when_no_task_id(self):
        session = self._session()
        _handle_task_event(".", session, "TaskUpdate", {}, {}, {})
        assert session["activeTasks"] == {}

    def test_skips_when_no_status(self):
        session = self._session()
        _handle_task_event(
            ".", session, "TaskUpdate",
            {"taskId": "1"}, {"taskId": "1", "subject": "x"}, {},
        )
        assert session["activeTasks"] == {}

    def test_does_not_double_start_task(self):
        session = self._session()
        old_start = int(time.time()) - 60
        session["activeTasks"]["1"] = {"subject": "x", "startTime": old_start, "jiraKey": None}
        _handle_task_event(
            ".", session, "TaskUpdate",
            {"taskId": "1", "status": "in_progress"},
            {"taskId": "1", "subject": "x", "status": "in_progress"},
            {},
        )
        assert session["activeTasks"]["1"]["startTime"] == old_start


# ── _get_idle_threshold_seconds ──────────────────────────────────────────


class TestIdleThreshold:
    def test_high_accuracy(self):
        result = _get_idle_threshold_seconds({"accuracy": 8, "idleThreshold": 15})
        assert result == 5 * 60

    def test_low_accuracy(self):
        result = _get_idle_threshold_seconds({"accuracy": 3, "idleThreshold": 15})
        assert result == 30 * 60

    def test_default_accuracy(self):
        result = _get_idle_threshold_seconds({"accuracy": 5, "idleThreshold": 15})
        assert result == 15 * 60


# ── _get_dir_cluster ─────────────────────────────────────────────────────


class TestGetDirCluster:
    def test_empty_path_returns_empty(self):
        assert _get_dir_cluster("") == ""

    def test_extracts_two_levels(self):
        assert _get_dir_cluster("src/auth/token/helpers.ts") == "src/auth"

    def test_top_level_file(self):
        assert _get_dir_cluster("README.md") == ""


# ── _detect_context_switch ───────────────────────────────────────────────


class TestDetectContextSwitch:
    def test_empty_prev_returns_false(self):
        assert _detect_context_switch([], [{"file": "a.ts"}], 5) is False

    def test_empty_curr_returns_false(self):
        assert _detect_context_switch([{"file": "a.ts"}], [], 5) is False

    def test_activities_with_no_files_returns_false(self):
        prev = [{"tool": "Bash"}, {"tool": "Bash"}]
        curr = [{"tool": "Bash"}, {"tool": "Bash"}]
        assert _detect_context_switch(prev, curr, 5) is False

    def test_high_accuracy_detects_any_cluster_change(self):
        prev = [{"file": "src/auth/a.ts"}, {"file": "src/auth/b.ts"}]
        curr = [{"file": "src/payments/x.ts"}, {"file": "src/payments/y.ts"}]
        assert _detect_context_switch(prev, curr, 8) is True

    def test_low_accuracy_needs_enough_activities(self):
        prev = [{"file": "src/auth/a.ts"}]
        curr = [{"file": "src/payments/x.ts"}]
        assert _detect_context_switch(prev, curr, 2) is False

    def test_low_accuracy_triggers_with_enough_activities(self):
        prev = [{"file": "src/auth/a.ts"}] * 3
        curr = [{"file": "src/payments/x.ts"}] * 3
        assert _detect_context_switch(prev, curr, 2) is True


# ── build_worklog edge cases ─────────────────────────────────────────────


class TestBuildWorklogEdgeCases:
    def test_subtracts_idle_gaps(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": False}))
        session = {
            "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": 1000, "totalSeconds": 0}},
            "workChunks": [{
                "id": "c1", "issueKey": "TEST-1",
                "startTime": 1000, "endTime": 2000,
                "filesChanged": ["a.ts"],
                "activities": [{"tool": "Edit", "type": "file_edit"}],
                "idleGaps": [{"startTime": 1400, "endTime": 1600, "seconds": 200}],
            }],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        result = build_worklog(str(tmp_path), "TEST-1")
        assert result["seconds"] == 800

    def test_more_than_five_files(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": False}))
        files = [f"src/file{i}.ts" for i in range(7)]
        session = {
            "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": 1000, "totalSeconds": 0}},
            "workChunks": [{
                "id": "c1", "issueKey": "TEST-1",
                "startTime": 1000, "endTime": 2000,
                "filesChanged": files,
                "activities": [{"tool": "Edit"}],
                "idleGaps": [],
            }],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        result = build_worklog(str(tmp_path), "TEST-1")
        assert "more files" in result["summary"]


# ── _round_seconds ───────────────────────────────────────────────────────


class TestRoundSeconds:
    def test_zero_or_negative_returns_zero(self):
        assert _round_seconds(0, 15, 5) == 0
        assert _round_seconds(-10, 15, 5) == 0

    def test_high_accuracy_uses_fine_rounding(self):
        result = _round_seconds(61, 15, 9)
        assert result == 120  # ceil(61/60)*60 = 2 min

    def test_low_accuracy_uses_coarse_rounding(self):
        result = _round_seconds(100, 15, 2)
        assert result == 1800  # ceil(100/1800)*1800 = 30 min

    def test_mid_accuracy_uses_base_rounding(self):
        result = _round_seconds(100, 15, 5)
        assert result == 900  # ceil(100/900)*900 = 15 min


# ── cmd_session_end extra branches ───────────────────────────────────────


class TestSessionEndExtra:
    def test_returns_early_when_no_session(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": False}))
        cmd_session_end([str(tmp_path)])  # no exception

    def test_drains_activity_buffer_before_ending(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5, "timeRounding": 15, "autonomyLevel": "C",
        }))
        now = int(time.time())
        session = {
            "sessionId": "buf-test", "currentIssue": "TEST-1",
            "autonomyLevel": "C", "accuracy": 5,
            "activeIssues": {"TEST-1": {"startTime": now - 600, "totalSeconds": 0, "paused": False}},
            "workChunks": [],
            "activityBuffer": [
                {"timestamp": now - 600, "tool": "Edit", "file": "a.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
                {"timestamp": now - 500, "tool": "Edit", "file": "b.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
            ],
            "pendingWorklogs": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_session_end([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        assert updated["activityBuffer"] == []
        assert len(updated.get("pendingWorklogs", [])) > 0

    def test_fallback_to_wallclock_only_when_issue_has_activity(self, tmp_path):
        """Wallclock fallback fires only when the issue has buffered activity."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5, "timeRounding": 15, "autonomyLevel": "C",
        }))
        now = int(time.time())
        session = {
            "sessionId": "wc-test", "currentIssue": "TEST-1",
            "autonomyLevel": "C", "accuracy": 5,
            "activeIssues": {
                "TEST-1": {"startTime": now - 1800, "totalSeconds": 0, "paused": False},
            },
            "workChunks": [],
            # Activity buffer has an entry for TEST-1 → wallclock fallback should fire
            "activityBuffer": [
                {"timestamp": now - 60, "tool": "Edit", "file": "a.ts",
                 "type": "file_edit", "issueKey": "TEST-1"},
            ],
            "pendingWorklogs": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_session_end([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        assert len(updated["pendingWorklogs"]) == 1
        assert updated["pendingWorklogs"][0]["seconds"] > 0

    def test_no_phantom_worklog_for_branch_issue_with_no_activity(self, tmp_path):
        """Auto-detected branch issue with no activity must not generate a worklog.

        Regression for the bug where wallclock fallback reported ~42 hours for
        an issue auto-detected from branch name but never actually worked on.
        """
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5, "timeRounding": 15, "autonomyLevel": "C",
        }))
        now = int(time.time())
        session = {
            "sessionId": "phantom-test", "currentIssue": "BRANCH-1",
            "autonomyLevel": "C", "accuracy": 5,
            "activeIssues": {
                # startTime set 42 hours ago, never worked on
                "BRANCH-1": {"startTime": now - 153527, "totalSeconds": 0, "paused": False},
            },
            "workChunks": [],
            "activityBuffer": [],  # no activity at all
            "pendingWorklogs": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_session_end([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        assert updated["pendingWorklogs"] == []


# ── _text_to_adf ─────────────────────────────────────────────────────────


class TestTextToAdf:
    def test_single_line(self):
        result = _text_to_adf("Hello world")
        assert result["version"] == 1
        assert result["type"] == "doc"
        assert result["content"][0]["content"][0]["text"] == "Hello world"

    def test_multi_line_with_blank(self):
        result = _text_to_adf("Line one\n\nLine two")
        content = result["content"]
        assert len(content) == 3
        assert content[1]["content"] == []  # blank line → empty paragraph


# ── post_worklog_to_jira HTTP paths ──────────────────────────────────────


class TestPostWorklogToJiraHttp:
    def test_returns_true_on_201(self):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 201
        with patch("jira_core.urllib.request.urlopen", return_value=mock_resp):
            result = post_worklog_to_jira(
                "https://t.atlassian.net", "u@t.com", "tok", "TEST-1", 900, "did stuff"
            )
        assert result is True

    def test_returns_false_on_http_error(self):
        err = urllib.error.HTTPError(
            url="https://t.atlassian.net", code=400,
            msg="Bad Request", hdrs=None, fp=None,
        )
        with patch("jira_core.urllib.request.urlopen", side_effect=err):
            result = post_worklog_to_jira(
                "https://t.atlassian.net", "u@t.com", "tok", "TEST-1", 900, "did stuff"
            )
        assert result is False

    def test_returns_false_on_generic_exception(self):
        with patch("jira_core.urllib.request.urlopen", side_effect=Exception("timeout")):
            result = post_worklog_to_jira(
                "https://t.atlassian.net", "u@t.com", "tok", "TEST-1", 900, "did stuff"
            )
        assert result is False


# ── cmd_post_worklogs extra branches ─────────────────────────────────────


class TestPostWorklogsExtra:
    def _setup(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": False}))
        (claude_dir / LOCAL_CONFIG_NAME).write_text(json.dumps({
            "email": "t@t.com", "apiToken": "tok",
            "baseUrl": "https://test.atlassian.net",
        }))
        return claude_dir

    def test_returns_early_when_no_session(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": False}))
        cmd_post_worklogs([str(tmp_path)])  # no exception

    def test_skips_entry_with_zero_seconds(self, tmp_path):
        claude_dir = self._setup(tmp_path)
        session = {"pendingWorklogs": [
            {"issueKey": "TEST-1", "seconds": 0, "summary": "x", "status": "approved"},
        ]}
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        with patch("jira_core.post_worklog_to_jira") as mock_post:
            cmd_post_worklogs([str(tmp_path)])
        mock_post.assert_not_called()

    def test_skips_entry_with_missing_issue_key(self, tmp_path):
        claude_dir = self._setup(tmp_path)
        session = {"pendingWorklogs": [
            {"issueKey": "", "seconds": 900, "summary": "x", "status": "approved"},
        ]}
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        with patch("jira_core.post_worklog_to_jira") as mock_post:
            cmd_post_worklogs([str(tmp_path)])
        mock_post.assert_not_called()


# ── cmd_drain_buffer no-session guard ────────────────────────────────────


class TestDrainBufferNoSession:
    def test_returns_early_when_no_session(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": False}))
        cmd_drain_buffer([str(tmp_path)])  # no exception, no session file


# ── cmd_session_end: issue with zero startTime is skipped ────────────────


class TestSessionEndZeroStartTime:
    def test_skips_issue_with_zero_start_and_no_chunks(self, tmp_path):
        """Active issue with startTime=0 and no chunks → no worklog entry."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({
            "debugLog": False, "accuracy": 5, "timeRounding": 15, "autonomyLevel": "C",
        }))
        session = {
            "sessionId": "zero-test", "currentIssue": "TEST-1",
            "autonomyLevel": "C", "accuracy": 5,
            "activeIssues": {
                "TEST-1": {"startTime": 0, "totalSeconds": 0, "paused": False},
            },
            "workChunks": [],
            "activityBuffer": [],
            "pendingWorklogs": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        cmd_session_end([str(tmp_path)])
        updated = json.loads((claude_dir / SESSION_NAME).read_text())
        assert updated["pendingWorklogs"] == []


# ── CLI wrapper functions ─────────────────────────────────────────────────


class TestCliWrappers:
    """Thin-wrapper CLI commands that delegate to core functions."""

    def test_cmd_classify_issue(self, capsys):
        import jira_core
        with patch.object(sys, "argv", ["jira_core.py", "classify-issue", "Fix login bug"]):
            jira_core.cmd_classify_issue(["Fix login bug"])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert result["type"] in ("Bug", "Task")

    def test_cmd_build_worklog_no_issue_key(self, capsys):
        import jira_core
        jira_core.cmd_build_worklog([])
        err = capsys.readouterr().err
        assert "{}" in err

    def test_cmd_build_worklog_with_issue_key(self, tmp_path, capsys):
        import jira_core
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": False}))
        session = {
            "currentIssue": "TEST-1",
            "activeIssues": {"TEST-1": {"startTime": 1000, "totalSeconds": 0}},
            "workChunks": [],
        }
        (claude_dir / SESSION_NAME).write_text(json.dumps(session))
        jira_core.cmd_build_worklog([str(tmp_path), "TEST-1"])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert result["issueKey"] == "TEST-1"

    def test_cmd_suggest_parent(self, tmp_path, capsys):
        import jira_core
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"projectKey": "TEST"}))
        (claude_dir / SESSION_NAME).write_text(json.dumps({}))
        jira_core.cmd_suggest_parent([str(tmp_path), "some task"])
        out = capsys.readouterr().out
        result = json.loads(out)
        assert "sessionDefault" in result

    def test_cmd_debug_log(self, tmp_path):
        import jira_core
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / CONFIG_NAME).write_text(json.dumps({"debugLog": True}))
        log_path = str(tmp_path / "debug.log")
        with patch("jira_core.DEBUG_LOG_PATH", tmp_path / "debug.log"):
            jira_core.cmd_debug_log([str(tmp_path), "hello from test"])

    def test_main_unknown_command_exits(self):
        import jira_core
        with patch.object(sys, "argv", ["jira_core.py", "not-a-command"]), \
             pytest.raises(SystemExit) as exc:
            jira_core.main()
        assert exc.value.code == 1

    def test_main_no_args_exits(self):
        import jira_core
        with patch.object(sys, "argv", ["jira_core.py"]), \
             pytest.raises(SystemExit) as exc:
            jira_core.main()
        assert exc.value.code == 1

    def test_main_dispatches_known_command(self, tmp_path):
        """main() calls fn(args) for a valid command (classify-issue path)."""
        import jira_core
        with patch.object(sys, "argv", ["jira_core.py", "classify-issue", "Fix bug"]), \
             patch("jira_core.cmd_classify_issue") as mock_fn:
            jira_core.main()
        mock_fn.assert_called_once_with(["Fix bug"])
