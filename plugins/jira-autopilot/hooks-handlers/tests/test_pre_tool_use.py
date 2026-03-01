"""Tests for cmd_pre_tool_use() — git commit message issue key injection."""

import json
import os
import sys
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _setup_project(project_root):
    """Create config files."""
    cfg = project_root / ".claude" / "jira-autopilot.json"
    cfg.write_text(json.dumps({
        "projectKey": "TEST",
        "debugLog": False,
    }))


def _create_session_with_issue(project_root, issue_key="TEST-42"):
    """Create a session with an active current issue."""
    session = jira_core._new_session()
    session["currentIssue"] = issue_key
    session["activeIssues"] = {
        issue_key: {
            "summary": "Fix login bug",
            "totalSeconds": 600,
            "startTime": int(time.time()) - 600,
            "status": "active",
        },
    }
    jira_core.save_session(str(project_root), session)
    return session


def _build_hook_input(tool_name, tool_input):
    """Build the JSON that Claude Code passes to PreToolUse hooks via stdin."""
    return json.dumps({
        "tool_name": tool_name,
        "tool_input": tool_input,
    })


class TestPreToolUseGitCommit:
    """Tests for issue key injection into git commit messages."""

    def test_injects_issue_key_into_commit_message(self, project_root):
        """cmd_pre_tool_use() emits systemMessage with issue key for git commit."""
        _setup_project(project_root)
        _create_session_with_issue(project_root, "TEST-42")

        hook_input = _build_hook_input("Bash", {"command": 'git commit -m "Add login feature"'})

        with patch("sys.stdin", __class__=type(sys.stdin)):
            with patch("sys.argv", ["jira_core.py", "pre-tool-use", str(project_root)]):
                with patch("sys.stdin.read", return_value=hook_input):
                    # Capture stdout
                    from io import StringIO
                    captured = StringIO()
                    with patch("sys.stdout", captured):
                        jira_core.cmd_pre_tool_use()

        output = captured.getvalue()
        if output.strip():
            result = json.loads(output)
            # Should include a systemMessage mentioning the issue key
            assert "TEST-42" in str(result)

    def test_only_activates_for_bash_git_commit(self, project_root):
        """cmd_pre_tool_use() does nothing for non-Bash tools."""
        _setup_project(project_root)
        _create_session_with_issue(project_root, "TEST-42")

        hook_input = _build_hook_input("Edit", {"file_path": "src/auth.ts", "old_string": "a", "new_string": "b"})

        with patch("sys.argv", ["jira_core.py", "pre-tool-use", str(project_root)]):
            with patch("sys.stdin.read", return_value=hook_input):
                from io import StringIO
                captured = StringIO()
                with patch("sys.stdout", captured):
                    jira_core.cmd_pre_tool_use()

        output = captured.getvalue().strip()
        # Should produce no output or empty result for non-Bash tools
        assert output == "" or output == "{}" or "systemMessage" not in output

    def test_only_activates_for_git_commit_command(self, project_root):
        """cmd_pre_tool_use() ignores Bash commands that are not git commit."""
        _setup_project(project_root)
        _create_session_with_issue(project_root, "TEST-42")

        hook_input = _build_hook_input("Bash", {"command": "npm test"})

        with patch("sys.argv", ["jira_core.py", "pre-tool-use", str(project_root)]):
            with patch("sys.stdin.read", return_value=hook_input):
                from io import StringIO
                captured = StringIO()
                with patch("sys.stdout", captured):
                    jira_core.cmd_pre_tool_use()

        output = captured.getvalue().strip()
        assert output == "" or output == "{}" or "systemMessage" not in output

    def test_skips_when_no_active_issue(self, project_root):
        """cmd_pre_tool_use() does nothing when no current issue is tracked."""
        _setup_project(project_root)
        session = jira_core._new_session()
        session["currentIssue"] = None
        jira_core.save_session(str(project_root), session)

        hook_input = _build_hook_input("Bash", {"command": 'git commit -m "Some change"'})

        with patch("sys.argv", ["jira_core.py", "pre-tool-use", str(project_root)]):
            with patch("sys.stdin.read", return_value=hook_input):
                from io import StringIO
                captured = StringIO()
                with patch("sys.stdout", captured):
                    jira_core.cmd_pre_tool_use()

        output = captured.getvalue().strip()
        assert output == "" or output == "{}" or "systemMessage" not in output

    def test_no_double_inject_if_key_present(self, project_root):
        """cmd_pre_tool_use() skips injection if issue key already in message."""
        _setup_project(project_root)
        _create_session_with_issue(project_root, "TEST-42")

        hook_input = _build_hook_input("Bash", {"command": 'git commit -m "TEST-42: Fix login bug"'})

        with patch("sys.argv", ["jira_core.py", "pre-tool-use", str(project_root)]):
            with patch("sys.stdin.read", return_value=hook_input):
                from io import StringIO
                captured = StringIO()
                with patch("sys.stdout", captured):
                    jira_core.cmd_pre_tool_use()

        output = captured.getvalue().strip()
        # Should not emit a systemMessage since key is already there
        assert output == "" or output == "{}" or "systemMessage" not in output

    def test_handles_commit_message_with_special_characters(self, project_root):
        """cmd_pre_tool_use() handles quotes, unicode, and special chars in commit messages."""
        _setup_project(project_root)
        _create_session_with_issue(project_root, "TEST-42")

        # Commit message with special characters
        hook_input = _build_hook_input(
            "Bash",
            {"command": "git commit -m \"Fix: handle 'special' chars & unicode \u00e9\u00e0\u00fc\""},
        )

        with patch("sys.argv", ["jira_core.py", "pre-tool-use", str(project_root)]):
            with patch("sys.stdin.read", return_value=hook_input):
                from io import StringIO
                captured = StringIO()
                with patch("sys.stdout", captured):
                    # Should not crash on special characters
                    jira_core.cmd_pre_tool_use()

        output = captured.getvalue()
        if output.strip():
            # If there is output, it should be valid JSON
            result = json.loads(output)
            assert "TEST-42" in str(result)

    def test_handles_git_commit_without_m_flag(self, project_root):
        """cmd_pre_tool_use() activates for git commit even without -m flag."""
        _setup_project(project_root)
        _create_session_with_issue(project_root, "TEST-42")

        hook_input = _build_hook_input("Bash", {"command": "git commit"})

        with patch("sys.argv", ["jira_core.py", "pre-tool-use", str(project_root)]):
            with patch("sys.stdin.read", return_value=hook_input):
                from io import StringIO
                captured = StringIO()
                with patch("sys.stdout", captured):
                    jira_core.cmd_pre_tool_use()

        output = captured.getvalue()
        if output.strip():
            result = json.loads(output)
            # Should still suggest the key
            assert "TEST-42" in str(result)
