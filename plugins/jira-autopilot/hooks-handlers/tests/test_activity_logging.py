import json
import sys
import os
import time
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _make_tool_input(tool_name, tool_input=None, tool_response="OK"):
    """Create a tool use JSON payload as Claude Code would send via stdin."""
    return json.dumps({
        "tool_name": tool_name,
        "tool_input": tool_input or {},
        "tool_response": tool_response,
    })


class TestCmdLogActivity:
    """Tests for cmd_log_activity() — PostToolUse hook handler."""

    def test_appends_tool_call_to_activity_buffer(self, project_root):
        """A file-editing tool call should be appended to activityBuffer."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))

        session = jira_core._new_session()
        session["currentIssue"] = "TEST-1"
        session["activeIssues"] = {"TEST-1": {
            "summary": "Task", "startTime": int(time.time()),
            "totalSeconds": 0, "paused": False,
        }}
        jira_core.save_session(str(project_root), session)

        tool_json = _make_tool_input("Edit", {
            "file_path": "/src/auth.ts",
            "old_string": "foo",
            "new_string": "bar",
        })

        with patch("sys.argv", ["jira_core.py", "log-activity", str(project_root)]), \
             patch("sys.stdin", __class__=type("FakeStdin", (), {"read": lambda self: tool_json})()):
            jira_core.cmd_log_activity()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded["activityBuffer"]) >= 1
        activity = reloaded["activityBuffer"][-1]
        assert activity["tool"] == "Edit"

    def test_includes_timestamp_tool_name_and_file(self, project_root):
        """Activity records should contain timestamp, tool, and file path."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))

        session = jira_core._new_session()
        jira_core.save_session(str(project_root), session)

        tool_json = _make_tool_input("Write", {"file_path": "/src/new-file.ts"})

        with patch("sys.argv", ["jira_core.py", "log-activity", str(project_root)]), \
             patch("sys.stdin", __class__=type("FakeStdin", (), {"read": lambda self: tool_json})()):
            jira_core.cmd_log_activity()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded["activityBuffer"]) >= 1
        activity = reloaded["activityBuffer"][-1]
        assert "timestamp" in activity
        assert isinstance(activity["timestamp"], (int, float))
        assert activity["tool"] == "Write"
        assert "file" in activity or "file_path" in activity.get("tool_input", {})

    def test_skips_read_only_tools(self, project_root):
        """Read-only tools (Read, Glob, Grep, etc.) should NOT be logged."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))

        session = jira_core._new_session()
        jira_core.save_session(str(project_root), session)

        for tool in ["Read", "Glob", "Grep", "WebSearch"]:
            tool_json = _make_tool_input(tool, {"file_path": "/src/foo.ts"})
            with patch("sys.argv", ["jira_core.py", "log-activity", str(project_root)]), \
                 patch("sys.stdin", __class__=type("FakeStdin", (), {"read": lambda self: tool_json})()):
                jira_core.cmd_log_activity()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded["activityBuffer"]) == 0, \
            "Read-only tools should not be logged"

    def test_skips_claude_dir_file_writes(self, project_root):
        """Writes to .claude/ directory should not be logged (internal state)."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))

        session = jira_core._new_session()
        jira_core.save_session(str(project_root), session)

        tool_json = _make_tool_input("Write", {
            "file_path": "/project/.claude/jira-session.json",
        })

        with patch("sys.argv", ["jira_core.py", "log-activity", str(project_root)]), \
             patch("sys.stdin", __class__=type("FakeStdin", (), {"read": lambda self: tool_json})()):
            jira_core.cmd_log_activity()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded["activityBuffer"]) == 0, \
            ".claude/ file writes should not be logged"

    def test_handles_missing_session_gracefully(self, project_root):
        """If no session exists, log-activity should not crash."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))

        tool_json = _make_tool_input("Edit", {"file_path": "/src/foo.ts"})

        with patch("sys.argv", ["jira_core.py", "log-activity", str(project_root)]), \
             patch("sys.stdin", __class__=type("FakeStdin", (), {"read": lambda self: tool_json})()):
            # Should not raise
            jira_core.cmd_log_activity()

    def test_sanitizes_credentials_in_bash_commands(self, project_root):
        """Bash commands containing credentials should be sanitized."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))

        session = jira_core._new_session()
        jira_core.save_session(str(project_root), session)

        tool_json = _make_tool_input("Bash", {
            "command": "curl -u user@test.com:ATATT3xSECRET123 https://jira.example.com"
        })

        with patch("sys.argv", ["jira_core.py", "log-activity", str(project_root)]), \
             patch("sys.stdin", __class__=type("FakeStdin", (), {"read": lambda self: tool_json})()):
            jira_core.cmd_log_activity()

        reloaded = jira_core.load_session(str(project_root))
        if len(reloaded["activityBuffer"]) > 0:
            activity = reloaded["activityBuffer"][-1]
            command = activity.get("command", "")
            assert "ATATT3xSECRET123" not in command, \
                "Credentials should be sanitized in logged commands"

    def test_assigns_current_issue_key_to_activity(self, project_root):
        """Activity should be tagged with the current active issue key."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))

        session = jira_core._new_session()
        session["currentIssue"] = "TEST-42"
        session["activeIssues"] = {"TEST-42": {
            "summary": "My task", "startTime": int(time.time()),
            "totalSeconds": 0, "paused": False,
        }}
        jira_core.save_session(str(project_root), session)

        tool_json = _make_tool_input("Edit", {"file_path": "/src/auth.ts"})

        with patch("sys.argv", ["jira_core.py", "log-activity", str(project_root)]), \
             patch("sys.stdin", __class__=type("FakeStdin", (), {"read": lambda self: tool_json})()):
            jira_core.cmd_log_activity()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded["activityBuffer"]) >= 1
        activity = reloaded["activityBuffer"][-1]
        assert activity.get("issueKey") == "TEST-42"

    def test_disabled_plugin_skips_logging(self, project_root):
        """When plugin is disabled, no activity should be logged."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": False}))

        session = jira_core._new_session()
        session["disabled"] = True
        jira_core.save_session(str(project_root), session)

        tool_json = _make_tool_input("Edit", {"file_path": "/src/foo.ts"})

        with patch("sys.argv", ["jira_core.py", "log-activity", str(project_root)]), \
             patch("sys.stdin", __class__=type("FakeStdin", (), {"read": lambda self: tool_json})()):
            jira_core.cmd_log_activity()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded.get("activityBuffer", [])) == 0
