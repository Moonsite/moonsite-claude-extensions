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
    cmd_drain_buffer,
    classify_issue,
    build_worklog,
    cmd_session_end,
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
