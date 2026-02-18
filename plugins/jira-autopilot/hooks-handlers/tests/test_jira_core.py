"""Tests for jira_core.py — the central business logic module."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jira_core import (
    CONFIG_NAME,
    LOCAL_CONFIG_NAME,
    SESSION_NAME,
    debug_log,
    load_config,
    load_local_config,
    load_session,
    save_session,
    get_cred,
    cmd_session_start,
    cmd_log_activity,
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
        for tool in ["Read", "Glob", "Grep", "LS", "WebSearch"]:
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
