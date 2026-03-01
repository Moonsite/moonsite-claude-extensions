import json
import sys
import os
import time
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestBuildWorklog:
    """Tests for worklog building (cmd_build_worklog / build_worklog)."""

    def test_builds_worklog_from_work_chunks(self, project_root):
        """Should aggregate work chunks for an issue into a worklog entry."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "accuracy": 5,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-1"
        session["activeIssues"] = {"TEST-1": {
            "summary": "Fix auth", "startTime": now - 1800,
            "totalSeconds": 0, "paused": False,
        }}
        session["workChunks"] = [
            {
                "id": "chunk-1",
                "issueKey": "TEST-1",
                "startTime": now - 1800,
                "endTime": now - 900,
                "activities": [
                    {"timestamp": now - 1800, "tool": "Edit", "file": "/src/auth.ts"},
                    {"timestamp": now - 1500, "tool": "Edit", "file": "/src/login.tsx"},
                ],
                "filesChanged": ["/src/auth.ts", "/src/login.tsx"],
                "idleGaps": [],
                "needsAttribution": False,
            },
        ]
        jira_core.save_session(str(project_root), session)

        result = jira_core.build_worklog(str(project_root), "TEST-1")
        assert result["issueKey"] == "TEST-1"
        assert result["seconds"] > 0
        assert "summary" in result
        assert "rawFacts" in result
        assert "files" in result["rawFacts"]

    def test_caps_at_max_worklog_seconds(self, project_root):
        """Worklog time should be capped at MAX_WORKLOG_SECONDS (4h)."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-1"
        session["activeIssues"] = {"TEST-1": {
            "summary": "Long task", "startTime": now - 20000,
            "totalSeconds": 0, "paused": False,
        }}
        # One huge chunk spanning more than 4 hours
        session["workChunks"] = [
            {
                "id": "chunk-1",
                "issueKey": "TEST-1",
                "startTime": now - 20000,
                "endTime": now,
                "activities": [
                    {"timestamp": now - 20000, "tool": "Edit", "file": "/src/a.ts"},
                    {"timestamp": now - 100, "tool": "Edit", "file": "/src/b.ts"},
                ],
                "filesChanged": ["/src/a.ts", "/src/b.ts"],
                "idleGaps": [],
                "needsAttribution": False,
            },
        ]
        jira_core.save_session(str(project_root), session)

        result = jira_core.build_worklog(str(project_root), "TEST-1")
        assert result["seconds"] <= jira_core.MAX_WORKLOG_SECONDS, \
            f"Worklog should be capped at {jira_core.MAX_WORKLOG_SECONDS}s, got {result['seconds']}s"
        assert result.get("capped") is True

    def test_generates_human_readable_summary(self, project_root):
        """Worklog summary should contain file names, not raw paths."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-1"
        session["activeIssues"] = {"TEST-1": {
            "summary": "Task", "startTime": now - 600,
            "totalSeconds": 0, "paused": False,
        }}
        session["workChunks"] = [
            {
                "id": "chunk-1",
                "issueKey": "TEST-1",
                "startTime": now - 600,
                "endTime": now - 300,
                "activities": [
                    {"timestamp": now - 600, "tool": "Edit", "file": "/project/src/auth.ts"},
                ],
                "filesChanged": ["/project/src/auth.ts"],
                "idleGaps": [],
                "needsAttribution": False,
            },
        ]
        jira_core.save_session(str(project_root), session)

        result = jira_core.build_worklog(str(project_root), "TEST-1")
        summary = result["summary"]
        assert isinstance(summary, str)
        assert len(summary) > 0
        # Should contain file basenames, not empty
        assert "auth.ts" in summary or "Work on task" in summary

    def test_includes_null_chunks_for_sole_active_issue(self, project_root):
        """When only one issue is active, null chunks should be included."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-1"
        session["activeIssues"] = {"TEST-1": {
            "summary": "Only task", "startTime": now - 600,
            "totalSeconds": 0, "paused": False,
        }}
        session["workChunks"] = [
            {
                "id": "chunk-attributed",
                "issueKey": "TEST-1",
                "startTime": now - 600,
                "endTime": now - 400,
                "activities": [],
                "filesChanged": ["/src/a.ts"],
                "idleGaps": [],
                "needsAttribution": False,
            },
            {
                "id": "chunk-null",
                "issueKey": None,
                "startTime": now - 300,
                "endTime": now - 100,
                "activities": [],
                "filesChanged": ["/src/b.ts"],
                "idleGaps": [],
                "needsAttribution": True,
            },
        ]
        jira_core.save_session(str(project_root), session)

        result = jira_core.build_worklog(str(project_root), "TEST-1")
        # Total seconds should include time from the null chunk
        assert result["seconds"] >= 200, \
            "Null chunks should be included when there is only one active issue"


class TestFormatJiraTime:
    """Tests for Jira time notation formatting."""

    def test_formats_hours_and_minutes(self):
        """90 minutes should format as '1h 30m'."""
        result = jira_core.format_jira_time(5400)  # 90 minutes
        assert result == "1h 30m"

    def test_formats_only_minutes(self):
        """45 minutes should format as '45m'."""
        result = jira_core.format_jira_time(2700)  # 45 minutes
        assert result == "45m"

    def test_formats_only_hours(self):
        """2 hours exactly should format as '2h'."""
        result = jira_core.format_jira_time(7200)  # 120 minutes
        assert result == "2h"

    def test_minimum_one_minute(self):
        """Very short durations should round up to at least 1m."""
        result = jira_core.format_jira_time(30)  # 30 seconds
        assert result == "1m"

    def test_zero_seconds(self):
        """Zero seconds should return '1m' (minimum)."""
        result = jira_core.format_jira_time(0)
        assert result == "1m"


class TestRoundSeconds:
    """Tests for time rounding based on accuracy level."""

    def test_rounds_up(self):
        """Should always round up, never down."""
        # 7 minutes with 5-minute rounding → 10 minutes
        result = jira_core._round_seconds(420, 5, accuracy=5)
        assert result >= 420
        assert result == 600  # 10 minutes in seconds

    def test_high_accuracy_finer_granularity(self):
        """High accuracy (8+) should use finer granularity."""
        # Per spec: granularity = max(rounding_minutes/15, 1) minutes
        result_high = jira_core._round_seconds(90, 15, accuracy=9)
        result_low = jira_core._round_seconds(90, 15, accuracy=2)
        # High accuracy should produce a smaller or equal rounded value
        assert result_high <= result_low

    def test_minimum_one_increment(self):
        """Should never return zero — always at least one rounding increment."""
        result = jira_core._round_seconds(1, 5, accuracy=5)
        assert result >= 300  # At least 5 minutes (one increment)

    def test_low_accuracy_coarser_granularity(self):
        """Low accuracy (1-3) should use coarser granularity."""
        # Per spec: granularity = rounding_minutes * 2
        result = jira_core._round_seconds(600, 15, accuracy=2)
        # With 30-minute granularity, 10 minutes → 30 minutes
        assert result == 1800  # 30 minutes

    def test_mid_accuracy_uses_rounding_minutes(self):
        """Mid accuracy (4-7) should use rounding_minutes as granularity."""
        result = jira_core._round_seconds(600, 15, accuracy=5)
        # 10 minutes with 15-minute rounding → 15 minutes
        assert result == 900  # 15 minutes


class TestCmdBuildWorklog:
    """Tests for the CLI wrapper cmd_build_worklog()."""

    def test_outputs_json(self, project_root, capsys):
        """cmd_build_worklog should print JSON to stdout."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-1"
        session["activeIssues"] = {"TEST-1": {
            "summary": "Task", "startTime": now - 600,
            "totalSeconds": 0, "paused": False,
        }}
        session["workChunks"] = [{
            "id": "chunk-1",
            "issueKey": "TEST-1",
            "startTime": now - 600,
            "endTime": now - 300,
            "activities": [{"timestamp": now - 600, "tool": "Edit", "file": "/src/a.ts"}],
            "filesChanged": ["/src/a.ts"],
            "idleGaps": [],
            "needsAttribution": False,
        }]
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "build-worklog", str(project_root), "TEST-1"]):
            jira_core.cmd_build_worklog()

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "issueKey" in result
        assert "seconds" in result
        assert "summary" in result
