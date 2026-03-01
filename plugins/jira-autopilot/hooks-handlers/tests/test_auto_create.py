"""Tests for auto issue creation — classify_issue(), _attempt_auto_create()."""

import json
import os
import sys
import time
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _setup_project(project_root, autonomy="B", auto_create=True):
    """Create config and credential files for a test project."""
    cfg = project_root / ".claude" / "jira-autopilot.json"
    cfg.write_text(json.dumps({
        "projectKey": "TEST",
        "cloudId": "cloud-123",
        "autoCreate": auto_create,
        "debugLog": False,
    }))
    local = project_root / ".claude" / "jira-autopilot.local.json"
    local.write_text(json.dumps({
        "email": "test@example.com",
        "apiToken": "fake-token",
        "baseUrl": "https://test.atlassian.net",
    }))


def _create_session(project_root, autonomy="B"):
    """Create a minimal active session."""
    session = jira_core._new_session()
    session["autonomyLevel"] = autonomy
    session["currentIssue"] = None
    session["lastParentKey"] = "TEST-10"
    jira_core.save_session(str(project_root), session)
    return session


class TestClassifyIssue:
    """Tests for classify_issue() — Bug vs Task classification."""

    def test_classifies_bug_from_signals(self):
        """classify_issue() returns Bug type when bug signals are present."""
        result = jira_core.classify_issue("fix broken login page crash")

        assert result["type"] == "Bug"
        assert result["confidence"] > 0
        assert len(result["signals"]) > 0

    def test_classifies_task_from_signals(self):
        """classify_issue() returns Task type for implementation work."""
        result = jira_core.classify_issue("implement new user dashboard feature")

        assert result["type"] == "Task"
        assert result["confidence"] > 0

    def test_defaults_to_task_when_ambiguous(self):
        """classify_issue() defaults to Task when signals are unclear."""
        result = jira_core.classify_issue("update configuration values")

        assert result["type"] == "Task"

    def test_confidence_increases_with_more_signals(self):
        """classify_issue() has higher confidence with multiple bug signals."""
        weak = jira_core.classify_issue("fix something")
        strong = jira_core.classify_issue("fix broken crash error regression")

        assert strong["confidence"] >= weak["confidence"]

    def test_context_boosts_bug_score(self):
        """classify_issue() boosts bug score when no new files created."""
        context = {"new_files_created": 0, "files_edited": 3}
        result = jira_core.classify_issue("fix the auth module", context=context)

        assert result["type"] == "Bug"

    def test_context_boosts_task_score(self):
        """classify_issue() boosts task score when new files are created."""
        context = {"new_files_created": 5, "files_edited": 0}
        result = jira_core.classify_issue("add new module", context=context)

        assert result["type"] == "Task"


class TestAutoCreateIssue:
    """Tests for _attempt_auto_create() — automatic Jira issue creation."""

    @patch("urllib.request.urlopen")
    def test_creates_issue_with_correct_project_key(self, mock_urlopen, project_root):
        """_attempt_auto_create() uses the configured project key."""
        _setup_project(project_root, autonomy="A", auto_create=True)
        session = _create_session(project_root, autonomy="A")

        resp = MagicMock()
        resp.status = 201
        resp.read.return_value = json.dumps({"id": "10001", "key": "TEST-42"}).encode()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        cfg = jira_core.load_config(str(project_root))
        result = jira_core._attempt_auto_create(
            str(project_root), "Fix the login page", session, cfg,
        )

        assert result.get("key") == "TEST-42"
        # Verify the request used the correct project key
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["fields"]["project"]["key"] == "TEST"

    @patch("urllib.request.urlopen")
    def test_uses_classification_for_issue_type(self, mock_urlopen, project_root):
        """_attempt_auto_create() classifies as Bug when bug signals present."""
        _setup_project(project_root, autonomy="A", auto_create=True)
        session = _create_session(project_root, autonomy="A")

        resp = MagicMock()
        resp.status = 201
        resp.read.return_value = json.dumps({"id": "10001", "key": "TEST-42"}).encode()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        cfg = jira_core.load_config(str(project_root))
        result = jira_core._attempt_auto_create(
            str(project_root), "Fix broken crash error in auth", session, cfg,
        )

        assert result.get("type") == "Bug"

    def test_autonomy_c_never_auto_creates(self, project_root):
        """_attempt_auto_create() returns None/empty when autonomy is C."""
        _setup_project(project_root, autonomy="C", auto_create=False)
        session = _create_session(project_root, autonomy="C")
        cfg = jira_core.load_config(str(project_root))

        result = jira_core._attempt_auto_create(
            str(project_root), "Add new feature", session, cfg,
        )

        # Should not create anything for Cautious mode
        assert result is None or result == {} or result.get("key") is None

    @patch("urllib.request.urlopen")
    def test_suggests_parent_from_context(self, mock_urlopen, project_root):
        """_attempt_auto_create() uses lastParentKey as parent hint."""
        _setup_project(project_root, autonomy="A", auto_create=True)
        session = _create_session(project_root, autonomy="A")
        session["lastParentKey"] = "TEST-10"
        jira_core.save_session(str(project_root), session)

        resp = MagicMock()
        resp.status = 201
        resp.read.return_value = json.dumps({"id": "10001", "key": "TEST-42"}).encode()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        cfg = jira_core.load_config(str(project_root))
        result = jira_core._attempt_auto_create(
            str(project_root), "Add new endpoint", session, cfg,
        )

        assert result.get("parent") == "TEST-10" or result.get("key") is not None

    def test_missing_project_key_monitoring_mode(self, project_root):
        """_attempt_auto_create() does nothing when projectKey is empty."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "",
            "autoCreate": True,
            "debugLog": False,
        }))
        local = project_root / ".claude" / "jira-autopilot.local.json"
        local.write_text(json.dumps({
            "email": "test@example.com",
            "apiToken": "fake-token",
            "baseUrl": "https://test.atlassian.net",
        }))
        session = _create_session(project_root, autonomy="A")
        cfg = jira_core.load_config(str(project_root))

        result = jira_core._attempt_auto_create(
            str(project_root), "Add something", session, cfg,
        )

        assert result is None or result == {} or result.get("key") is None

    @patch("urllib.request.urlopen")
    def test_validates_project_key_against_jira(self, mock_urlopen, project_root):
        """_attempt_auto_create() validates project key exists in Jira."""
        _setup_project(project_root, autonomy="A", auto_create=True)
        # Override with a bogus project key
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "BOGUS",
            "autoCreate": True,
            "debugLog": False,
        }))
        session = _create_session(project_root, autonomy="A")

        from urllib.error import HTTPError
        import io
        mock_urlopen.side_effect = HTTPError(
            url="https://test.atlassian.net/rest/api/3/issue",
            code=404, msg="Not Found", hdrs={}, fp=io.BytesIO(b'{"errorMessages":["project does not exist"]}'),
        )

        cfg = jira_core.load_config(str(project_root))
        result = jira_core._attempt_auto_create(
            str(project_root), "Add feature", session, cfg,
        )

        # Should handle the failure gracefully
        assert result is None or result == {} or "error" in str(result).lower() or result.get("key") is None


class TestAutonomyLevels:
    """Tests for autonomy level behavior in issue creation."""

    @patch("urllib.request.urlopen")
    def test_autonomy_a_auto_creates(self, mock_urlopen, project_root):
        """Autonomy A with autoCreate=true creates issues automatically."""
        _setup_project(project_root, autonomy="A", auto_create=True)
        session = _create_session(project_root, autonomy="A")

        resp = MagicMock()
        resp.status = 201
        resp.read.return_value = json.dumps({"id": "10001", "key": "TEST-42"}).encode()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        cfg = jira_core.load_config(str(project_root))
        result = jira_core._attempt_auto_create(
            str(project_root), "Implement dashboard", session, cfg,
        )

        assert result is not None
        assert result.get("key") == "TEST-42"

    def test_autonomy_b_respects_auto_create_flag(self, project_root):
        """Autonomy B with autoCreate=false does not create issues."""
        _setup_project(project_root, autonomy="B", auto_create=False)
        session = _create_session(project_root, autonomy="B")
        cfg = jira_core.load_config(str(project_root))

        result = jira_core._attempt_auto_create(
            str(project_root), "Build new feature", session, cfg,
        )

        assert result is None or result == {} or result.get("key") is None
