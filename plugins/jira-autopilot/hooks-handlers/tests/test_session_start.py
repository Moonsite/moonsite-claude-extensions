import json
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestCmdSessionStart:
    """Tests for cmd_session_start() — SessionStart hook handler."""

    def test_creates_new_session_when_none_exists(self, project_root):
        """When no jira-session.json exists, session-start should create one."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST",
            "enabled": True,
            "autonomyLevel": "C",
            "accuracy": 5,
        }))

        with patch("sys.argv", ["jira_core.py", "session-start", str(project_root)]):
            jira_core.cmd_session_start()

        session = jira_core.load_session(str(project_root))
        assert session != {}, "Session should be created"
        assert "sessionId" in session
        assert session["activeIssues"] == {} or isinstance(session["activeIssues"], dict)
        assert session["activityBuffer"] == [] or isinstance(session["activityBuffer"], list)

    def test_loads_existing_session_and_ensures_structure(self, project_root):
        """Existing session should be loaded and missing fields filled in."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))

        # Save a partial session (missing some fields)
        partial_session = {
            "sessionId": "existing-123",
            "activeIssues": {"TEST-1": {
                "summary": "Existing task",
                "startTime": 1740700000,
                "totalSeconds": 300,
                "paused": False,
            }},
            "currentIssue": "TEST-1",
        }
        jira_core.save_session(str(project_root), partial_session)

        with patch("sys.argv", ["jira_core.py", "session-start", str(project_root)]):
            jira_core.cmd_session_start()

        session = jira_core.load_session(str(project_root))
        assert session["currentIssue"] == "TEST-1"
        # _ensure_session_structure should have filled missing keys
        assert "workChunks" in session
        assert "activityBuffer" in session
        assert "pendingWorklogs" in session

    def test_detects_issue_key_from_git_branch(self, project_root):
        """Should detect issue key from branch name like feature/TEST-42-desc."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST",
            "enabled": True,
            "branchPattern": r"^(?:feature|fix|hotfix|chore|docs)/(TEST-\d+)",
        }))

        with patch("sys.argv", ["jira_core.py", "session-start", str(project_root)]), \
             patch("subprocess.check_output", return_value=b"feature/TEST-42-login-fix\n"):
            jira_core.cmd_session_start()

        session = jira_core.load_session(str(project_root))
        assert session.get("currentIssue") == "TEST-42"
        assert "TEST-42" in session.get("activeIssues", {})

    def test_sets_autonomy_level_and_accuracy_from_config(self, project_root):
        """Session should inherit autonomyLevel and accuracy from project config."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST",
            "enabled": True,
            "autonomyLevel": "A",
            "accuracy": 8,
        }))

        with patch("sys.argv", ["jira_core.py", "session-start", str(project_root)]):
            jira_core.cmd_session_start()

        session = jira_core.load_session(str(project_root))
        assert session["autonomyLevel"] == "A"
        assert session["accuracy"] == 8

    def test_handles_missing_config_gracefully(self, project_root):
        """When no config file exists, session-start should not crash."""
        # No jira-autopilot.json created
        with patch("sys.argv", ["jira_core.py", "session-start", str(project_root)]):
            # Should not raise
            jira_core.cmd_session_start()

    def test_disabled_plugin_returns_silently(self, project_root):
        """When enabled: false, session-start should exit without creating session."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": False}))

        with patch("sys.argv", ["jira_core.py", "session-start", str(project_root)]):
            jira_core.cmd_session_start()

        session = jira_core.load_session(str(project_root))
        # Either no session created, or session with disabled flag
        assert session == {} or session.get("disabled") is True

    def test_prunes_stale_issues(self, project_root):
        """Issues older than 24h with zero work should be pruned."""
        import time
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))

        stale_time = int(time.time()) - jira_core.STALE_ISSUE_SECONDS - 100
        session = jira_core._new_session()
        session["activeIssues"] = {
            "TEST-1": {
                "summary": "Stale task",
                "startTime": stale_time,
                "totalSeconds": 0,
                "paused": False,
            },
            "TEST-2": {
                "summary": "Active task",
                "startTime": int(time.time()) - 60,
                "totalSeconds": 300,
                "paused": False,
            },
        }
        session["currentIssue"] = "TEST-2"
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "session-start", str(project_root)]):
            jira_core.cmd_session_start()

        reloaded = jira_core.load_session(str(project_root))
        assert "TEST-1" not in reloaded.get("activeIssues", {}), \
            "Stale issue should be pruned"
        assert "TEST-2" in reloaded.get("activeIssues", {}), \
            "Active issue should be preserved"
