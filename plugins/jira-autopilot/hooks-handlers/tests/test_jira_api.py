"""Tests for Jira REST API client functions in jira_core.py."""

import base64
import io
import json
import sys
import os
from http.client import HTTPResponse
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _make_response(body, status=200, headers=None):
    """Create a mock urllib response object."""
    data = json.dumps(body).encode("utf-8") if isinstance(body, (dict, list)) else body.encode("utf-8")
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = data
    resp.getheader.side_effect = lambda name, default=None: (headers or {}).get(name, default)
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _setup_creds(project_root):
    """Write test credentials to project root."""
    local = project_root / ".claude" / "jira-autopilot.local.json"
    local.write_text(json.dumps({
        "email": "test@example.com",
        "apiToken": "fake-token-123",
        "baseUrl": "https://test.atlassian.net",
    }))
    cfg = project_root / ".claude" / "jira-autopilot.json"
    cfg.write_text(json.dumps({
        "projectKey": "TEST",
        "cloudId": "cloud-123",
    }))


class TestJiraRequest:
    """Tests for jira_request() — authenticated HTTP request helper."""

    @patch("urllib.request.urlopen")
    def test_sends_correct_auth_header(self, mock_urlopen, project_root):
        """jira_request() sends Basic auth with base64-encoded email:token."""
        _setup_creds(project_root)
        mock_urlopen.return_value = _make_response({"ok": True})

        jira_core.jira_request(str(project_root), "GET", "/rest/api/3/myself")

        req = mock_urlopen.call_args[0][0]
        auth_header = req.get_header("Authorization")
        assert auth_header is not None
        expected = "Basic " + base64.b64encode(b"test@example.com:fake-token-123").decode()
        assert auth_header == expected

    @patch("urllib.request.urlopen")
    def test_sends_json_content_type(self, mock_urlopen, project_root):
        """jira_request() sets Content-Type and Accept to application/json."""
        _setup_creds(project_root)
        mock_urlopen.return_value = _make_response({"ok": True})

        jira_core.jira_request(str(project_root), "POST", "/rest/api/3/issue", body={"fields": {}})

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"

    @patch("urllib.request.urlopen")
    def test_handles_401_unauthorized(self, mock_urlopen, project_root):
        """jira_request() returns error dict on 401 (bad credentials)."""
        _setup_creds(project_root)
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://test.atlassian.net/rest/api/3/myself",
            code=401, msg="Unauthorized", hdrs={}, fp=io.BytesIO(b""),
        )

        result = jira_core.jira_request(str(project_root), "GET", "/rest/api/3/myself")

        assert result.get("error") or result == {} or "error" in str(result).lower()

    @patch("urllib.request.urlopen")
    def test_handles_404_not_found(self, mock_urlopen, project_root):
        """jira_request() returns error on 404 (resource not found)."""
        _setup_creds(project_root)
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://test.atlassian.net/rest/api/3/issue/NOPE-999",
            code=404, msg="Not Found", hdrs={}, fp=io.BytesIO(b""),
        )

        result = jira_core.jira_request(str(project_root), "GET", "/rest/api/3/issue/NOPE-999")

        assert result.get("error") or result == {}

    @patch("urllib.request.urlopen")
    def test_handles_429_rate_limit_with_retry(self, mock_urlopen, project_root):
        """jira_request() retries on 429 (rate limited) then succeeds."""
        _setup_creds(project_root)
        from urllib.error import HTTPError
        rate_limit_error = HTTPError(
            url="https://test.atlassian.net/rest/api/3/myself",
            code=429, msg="Rate Limited",
            hdrs=MagicMock(), fp=io.BytesIO(b""),
        )
        rate_limit_error.headers = {"Retry-After": "1"}
        success_resp = _make_response({"accountId": "abc123"})

        mock_urlopen.side_effect = [rate_limit_error, success_resp]

        result = jira_core.jira_request(str(project_root), "GET", "/rest/api/3/myself")

        # Should have retried at least once
        assert mock_urlopen.call_count >= 2
        assert result.get("accountId") == "abc123"


class TestJiraGetProjects:
    """Tests for jira_get_projects() — project listing with pagination."""

    @patch("urllib.request.urlopen")
    def test_fetches_projects(self, mock_urlopen, project_root):
        """jira_get_projects() returns list of {key, name} dicts."""
        _setup_creds(project_root)
        mock_urlopen.return_value = _make_response({
            "values": [
                {"key": "PROJ", "name": "My Project"},
                {"key": "TEST", "name": "Test Project"},
            ],
            "isLast": True,
        })

        result = jira_core.jira_get_projects(str(project_root))

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["key"] == "PROJ"
        assert result[1]["name"] == "Test Project"

    @patch("urllib.request.urlopen")
    def test_handles_pagination(self, mock_urlopen, project_root):
        """jira_get_projects() fetches multiple pages when isLast=False."""
        _setup_creds(project_root)
        page1 = _make_response({
            "values": [{"key": "P1", "name": "Project 1"}],
            "isLast": False,
            "startAt": 0,
            "maxResults": 1,
        })
        page2 = _make_response({
            "values": [{"key": "P2", "name": "Project 2"}],
            "isLast": True,
            "startAt": 1,
            "maxResults": 1,
        })
        mock_urlopen.side_effect = [page1, page2]

        result = jira_core.jira_get_projects(str(project_root))

        assert len(result) >= 2
        keys = [p["key"] for p in result]
        assert "P1" in keys
        assert "P2" in keys

    @patch("urllib.request.urlopen")
    def test_returns_empty_on_network_failure(self, mock_urlopen, project_root):
        """jira_get_projects() returns [] when network is unavailable."""
        _setup_creds(project_root)
        mock_urlopen.side_effect = OSError("Network unreachable")

        result = jira_core.jira_get_projects(str(project_root))

        assert result == []


class TestCreateIssue:
    """Tests for create_issue() — Jira issue creation."""

    @patch("urllib.request.urlopen")
    def test_sends_correct_payload(self, mock_urlopen, project_root):
        """create_issue() posts correct fields to POST /rest/api/3/issue."""
        _setup_creds(project_root)
        mock_urlopen.return_value = _make_response({
            "id": "10001",
            "key": "TEST-42",
        })

        result = jira_core.create_issue(
            str(project_root),
            project_key="TEST",
            summary="Fix login bug",
            issue_type="Bug",
            description="Users cannot log in",
        )

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["fields"]["project"]["key"] == "TEST"
        assert body["fields"]["summary"] == "Fix login bug"
        assert body["fields"]["issuetype"]["name"] == "Bug"
        # Description should be in ADF format
        assert "description" in body["fields"]
        assert result["key"] == "TEST-42"

    @patch("urllib.request.urlopen")
    def test_description_uses_adf_format(self, mock_urlopen, project_root):
        """create_issue() converts plain text description to ADF."""
        _setup_creds(project_root)
        mock_urlopen.return_value = _make_response({"id": "10002", "key": "TEST-43"})

        jira_core.create_issue(
            str(project_root),
            project_key="TEST",
            summary="Add feature",
            issue_type="Task",
            description="Implement new feature",
        )

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        desc = body["fields"]["description"]
        assert desc["type"] == "doc"
        assert desc["version"] == 1


class TestAddWorklog:
    """Tests for add_worklog() — posting time entries."""

    @patch("urllib.request.urlopen")
    def test_sends_time_spent_in_jira_notation(self, mock_urlopen, project_root):
        """add_worklog() converts seconds to Jira time notation (e.g. '1h 30m')."""
        _setup_creds(project_root)
        mock_urlopen.return_value = _make_response({"id": "worklog-1"}, status=201)

        jira_core.add_worklog(
            str(project_root),
            issue_key="TEST-42",
            seconds=5400,  # 1h 30m
            comment="Worked on feature",
        )

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        # Should contain timeSpentSeconds or timeSpent
        assert body.get("timeSpentSeconds") == 5400 or body.get("timeSpent") == "1h 30m"

    @patch("urllib.request.urlopen")
    def test_comment_in_adf_format(self, mock_urlopen, project_root):
        """add_worklog() sends comment in ADF format."""
        _setup_creds(project_root)
        mock_urlopen.return_value = _make_response({"id": "worklog-2"}, status=201)

        jira_core.add_worklog(
            str(project_root),
            issue_key="TEST-42",
            seconds=900,
            comment="Fixed tests",
        )

        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        comment = body.get("comment", {})
        assert comment.get("type") == "doc"


class TestGetIssue:
    """Tests for get_issue() — fetching issue details."""

    @patch("urllib.request.urlopen")
    def test_returns_issue_fields(self, mock_urlopen, project_root):
        """get_issue() fetches and returns issue data from Jira."""
        _setup_creds(project_root)
        mock_urlopen.return_value = _make_response({
            "key": "TEST-42",
            "fields": {
                "summary": "Fix login bug",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
            },
        })

        result = jira_core.get_issue(str(project_root), "TEST-42")

        assert result["key"] == "TEST-42"
        assert result["fields"]["summary"] == "Fix login bug"
