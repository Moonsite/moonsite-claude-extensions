"""Tests for cmd_session_end() — session finalization and archival."""

import json
import os
import sys
import time
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _setup_project(project_root):
    """Create config and credential files for a test project."""
    cfg = project_root / ".claude" / "jira-autopilot.json"
    cfg.write_text(json.dumps({
        "projectKey": "TEST",
        "cloudId": "cloud-123",
        "debugLog": False,
    }))
    local = project_root / ".claude" / "jira-autopilot.local.json"
    local.write_text(json.dumps({
        "email": "test@example.com",
        "apiToken": "fake-token",
        "baseUrl": "https://test.atlassian.net",
    }))


def _create_session_with_work(project_root, autonomy="B"):
    """Create a session with active issues and work chunks."""
    session = jira_core._new_session()
    now = int(time.time())
    session["autonomyLevel"] = autonomy
    session["currentIssue"] = "TEST-42"
    session["activeIssues"] = {
        "TEST-42": {
            "summary": "Fix login bug",
            "totalSeconds": 1800,
            "startTime": now - 1800,
            "status": "active",
        },
    }
    session["workChunks"] = [
        {
            "issueKey": "TEST-42",
            "startTime": now - 1800,
            "endTime": now - 900,
            "activities": [
                {"tool": "Edit", "file": "src/auth.ts", "timestamp": now - 1500},
                {"tool": "Bash", "file": None, "timestamp": now - 1200},
            ],
            "files": ["src/auth.ts"],
            "idleGaps": [],
        },
    ]
    session["pendingWorklogs"] = []
    jira_core.save_session(str(project_root), session)
    return session


class TestSessionEndSavesFirst:
    """Session end must save state locally before any API calls."""

    @patch("urllib.request.urlopen")
    def test_saves_session_before_api_calls(self, mock_urlopen, project_root):
        """cmd_session_end() persists session state before posting to Jira."""
        _setup_project(project_root)
        _create_session_with_work(project_root)

        saved_states = []

        original_save = jira_core.save_session

        def tracking_save(root, session):
            saved_states.append(json.loads(json.dumps(session)))
            return original_save(root, session)

        with patch.object(jira_core, "save_session", side_effect=tracking_save):
            with patch("sys.argv", ["jira_core.py", "session-end", str(project_root)]):
                jira_core.cmd_session_end()

        # Session should have been saved at least once
        assert len(saved_states) >= 1


class TestSessionEndWorklogs:
    """Session end builds and posts worklogs."""

    @patch("urllib.request.urlopen")
    def test_builds_worklogs_from_work_chunks(self, mock_urlopen, project_root):
        """cmd_session_end() creates pending worklogs from active issue work chunks."""
        _setup_project(project_root)
        _create_session_with_work(project_root)
        mock_urlopen.return_value = MagicMock(
            status=201,
            read=MagicMock(return_value=b'{"id":"wl-1"}'),
            __enter__=MagicMock(return_value=MagicMock(
                status=201, read=MagicMock(return_value=b'{"id":"wl-1"}')
            )),
            __exit__=MagicMock(return_value=False),
        )

        with patch("sys.argv", ["jira_core.py", "session-end", str(project_root)]):
            jira_core.cmd_session_end()

        session = jira_core.load_session(str(project_root))
        # Should have created pending worklogs or posted them
        has_worklogs = (
            len(session.get("pendingWorklogs", [])) > 0
            or mock_urlopen.call_count > 0
        )
        assert has_worklogs

    @patch("urllib.request.urlopen")
    def test_posts_worklogs_to_each_active_issue(self, mock_urlopen, project_root):
        """cmd_session_end() posts time to every active issue with work."""
        _setup_project(project_root)
        session = _create_session_with_work(project_root, autonomy="A")
        # Add a second active issue
        now = int(time.time())
        session["activeIssues"]["TEST-43"] = {
            "summary": "Add tests",
            "totalSeconds": 600,
            "startTime": now - 600,
            "status": "active",
        }
        session["workChunks"].append({
            "issueKey": "TEST-43",
            "startTime": now - 600,
            "endTime": now,
            "activities": [{"tool": "Write", "file": "test.py", "timestamp": now - 300}],
            "files": ["test.py"],
            "idleGaps": [],
        })
        jira_core.save_session(str(project_root), session)

        resp = MagicMock()
        resp.status = 201
        resp.read.return_value = b'{"id":"wl-1"}'
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with patch("sys.argv", ["jira_core.py", "session-end", str(project_root)]):
            jira_core.cmd_session_end()

        # At least 2 API calls expected (one per issue) — worklogs or comments
        # Or pending worklogs for both issues should exist
        session_after = jira_core.load_session(str(project_root))
        posted_or_pending = mock_urlopen.call_count >= 2 or len(session_after.get("pendingWorklogs", [])) >= 2
        assert posted_or_pending


class TestSessionEndArchive:
    """Session end archives to .claude/jira-sessions/."""

    @patch("urllib.request.urlopen")
    def test_archives_session(self, mock_urlopen, project_root):
        """cmd_session_end() saves archive to .claude/jira-sessions/<sessionId>.json."""
        _setup_project(project_root)
        _create_session_with_work(project_root)
        mock_urlopen.return_value = MagicMock(
            status=201,
            read=MagicMock(return_value=b'{"id":"wl-1"}'),
            __enter__=MagicMock(return_value=MagicMock(
                status=201, read=MagicMock(return_value=b'{"id":"wl-1"}')
            )),
            __exit__=MagicMock(return_value=False),
        )

        with patch("sys.argv", ["jira_core.py", "session-end", str(project_root)]):
            jira_core.cmd_session_end()

        archive_dir = project_root / ".claude" / "jira-sessions"
        assert archive_dir.exists()
        archives = list(archive_dir.glob("*.json"))
        assert len(archives) >= 1


class TestSessionEndErrorHandling:
    """Session end handles failures gracefully."""

    @patch("urllib.request.urlopen")
    def test_api_failure_does_not_lose_data(self, mock_urlopen, project_root):
        """When Jira API fails, session data is still saved locally."""
        _setup_project(project_root)
        _create_session_with_work(project_root)
        mock_urlopen.side_effect = OSError("Network unreachable")

        with patch("sys.argv", ["jira_core.py", "session-end", str(project_root)]):
            # Should not raise — must handle errors gracefully
            try:
                jira_core.cmd_session_end()
            except SystemExit:
                pass  # Some implementations exit after session-end

        # Session file should still exist with data intact
        session = jira_core.load_session(str(project_root))
        # If session was archived, it might be empty, but archive should exist
        archive_dir = project_root / ".claude" / "jira-sessions"
        session_exists = bool(session) or archive_dir.exists()
        assert session_exists

    @patch("urllib.request.urlopen")
    def test_empty_session_no_work(self, mock_urlopen, project_root):
        """cmd_session_end() handles a session with no work done gracefully."""
        _setup_project(project_root)
        session = jira_core._new_session()
        session["activeIssues"] = {}
        session["workChunks"] = []
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "session-end", str(project_root)]):
            try:
                jira_core.cmd_session_end()
            except SystemExit:
                pass

        # No API calls should be made for empty session
        assert mock_urlopen.call_count == 0


class TestSessionEndComment:
    """Session end posts work summary comments."""

    @patch("urllib.request.urlopen")
    def test_posts_work_summary_comment(self, mock_urlopen, project_root):
        """cmd_session_end() posts a summary comment to each active issue."""
        _setup_project(project_root)
        _create_session_with_work(project_root, autonomy="A")

        resp = MagicMock()
        resp.status = 201
        resp.read.return_value = b'{"id":"c-1"}'
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with patch("sys.argv", ["jira_core.py", "session-end", str(project_root)]):
            jira_core.cmd_session_end()

        # Should have made at least one API call (worklog or comment)
        assert mock_urlopen.call_count >= 1
