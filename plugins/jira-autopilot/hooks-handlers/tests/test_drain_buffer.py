import json
import sys
import os
import time
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


def _make_activity(tool, file_path, ts, issue_key=None):
    """Create an activity record as produced by log-activity."""
    return {
        "timestamp": ts,
        "tool": tool,
        "type": "file_edit" if tool in ("Edit", "MultiEdit") else "file_write" if tool == "Write" else "bash" if tool == "Bash" else "other",
        "issueKey": issue_key,
        "file": file_path,
        "command": "",
    }


class TestCmdDrainBuffer:
    """Tests for cmd_drain_buffer() — Stop hook handler."""

    def test_drains_activity_buffer_into_work_chunks(self, project_root):
        """Activities in the buffer should be converted into work chunks."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "autonomyLevel": "C", "accuracy": 5,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-1"
        session["activeIssues"] = {"TEST-1": {
            "summary": "Task", "startTime": now - 600,
            "totalSeconds": 0, "paused": False,
        }}
        session["activityBuffer"] = [
            _make_activity("Edit", "/src/auth.ts", now - 300, "TEST-1"),
            _make_activity("Edit", "/src/auth.ts", now - 200, "TEST-1"),
            _make_activity("Write", "/src/utils.ts", now - 100, "TEST-1"),
        ]
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "drain-buffer", str(project_root)]):
            jira_core.cmd_drain_buffer()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded["workChunks"]) >= 1, "Should create at least one work chunk"
        chunk = reloaded["workChunks"][0]
        assert "startTime" in chunk
        assert "endTime" in chunk
        assert chunk["issueKey"] == "TEST-1"

    def test_groups_activities_by_idle_threshold(self, project_root):
        """Activities separated by more than idle threshold should be in different chunks."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "accuracy": 5,  # Default idle threshold
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-1"
        session["activeIssues"] = {"TEST-1": {
            "summary": "Task", "startTime": now - 3600,
            "totalSeconds": 0, "paused": False,
        }}
        # Two clusters separated by a large gap (30 minutes)
        session["activityBuffer"] = [
            _make_activity("Edit", "/src/a.ts", now - 3600, "TEST-1"),
            _make_activity("Edit", "/src/a.ts", now - 3500, "TEST-1"),
            # 30 minute gap
            _make_activity("Edit", "/src/b.ts", now - 1800, "TEST-1"),
            _make_activity("Edit", "/src/b.ts", now - 1700, "TEST-1"),
        ]
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "drain-buffer", str(project_root)]):
            jira_core.cmd_drain_buffer()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded["workChunks"]) >= 2, \
            "Activities separated by large idle gap should create separate chunks"

    def test_work_chunk_has_required_fields(self, project_root):
        """Each work chunk should have id, issueKey, startTime, endTime, activities."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "accuracy": 5,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["activityBuffer"] = [
            _make_activity("Edit", "/src/foo.ts", now - 60, "TEST-1"),
            _make_activity("Edit", "/src/foo.ts", now - 30, "TEST-1"),
        ]
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "drain-buffer", str(project_root)]):
            jira_core.cmd_drain_buffer()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded["workChunks"]) >= 1
        chunk = reloaded["workChunks"][0]
        assert "id" in chunk
        assert "issueKey" in chunk
        assert "startTime" in chunk
        assert "endTime" in chunk
        assert "activities" in chunk or "filesChanged" in chunk

    def test_clears_buffer_after_draining(self, project_root):
        """Activity buffer should be empty after drain."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["activityBuffer"] = [
            _make_activity("Edit", "/src/foo.ts", now - 30, "TEST-1"),
        ]
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "drain-buffer", str(project_root)]):
            jira_core.cmd_drain_buffer()

        reloaded = jira_core.load_session(str(project_root))
        assert reloaded["activityBuffer"] == [], \
            "Activity buffer should be cleared after drain"

    def test_handles_empty_buffer(self, project_root):
        """Empty buffer should produce no work chunks and not crash."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
        }))

        session = jira_core._new_session()
        session["activityBuffer"] = []
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "drain-buffer", str(project_root)]):
            jira_core.cmd_drain_buffer()

        reloaded = jira_core.load_session(str(project_root))
        assert reloaded["activityBuffer"] == []

    def test_splits_on_issue_key_change(self, project_root):
        """Activities with different issue keys should be in separate chunks."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
            "accuracy": 5,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["activeIssues"] = {
            "TEST-1": {"summary": "Task 1", "startTime": now - 600, "totalSeconds": 0, "paused": False},
            "TEST-2": {"summary": "Task 2", "startTime": now - 600, "totalSeconds": 0, "paused": False},
        }
        session["activityBuffer"] = [
            _make_activity("Edit", "/src/a.ts", now - 300, "TEST-1"),
            _make_activity("Edit", "/src/a.ts", now - 250, "TEST-1"),
            _make_activity("Edit", "/src/b.ts", now - 200, "TEST-2"),
            _make_activity("Edit", "/src/b.ts", now - 150, "TEST-2"),
        ]
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "drain-buffer", str(project_root)]):
            jira_core.cmd_drain_buffer()

        reloaded = jira_core.load_session(str(project_root))
        chunks = reloaded["workChunks"]
        assert len(chunks) >= 2, "Different issue keys should produce separate chunks"
        issue_keys = {c["issueKey"] for c in chunks}
        assert "TEST-1" in issue_keys
        assert "TEST-2" in issue_keys

    def test_aggregates_files_changed_in_chunk(self, project_root):
        """Work chunks should list the unique files changed."""
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({
            "projectKey": "TEST", "enabled": True,
        }))

        now = int(time.time())
        session = jira_core._new_session()
        session["activityBuffer"] = [
            _make_activity("Edit", "/src/a.ts", now - 60, "TEST-1"),
            _make_activity("Edit", "/src/a.ts", now - 50, "TEST-1"),
            _make_activity("Write", "/src/b.ts", now - 40, "TEST-1"),
        ]
        jira_core.save_session(str(project_root), session)

        with patch("sys.argv", ["jira_core.py", "drain-buffer", str(project_root)]):
            jira_core.cmd_drain_buffer()

        reloaded = jira_core.load_session(str(project_root))
        assert len(reloaded["workChunks"]) >= 1
        chunk = reloaded["workChunks"][0]
        files = chunk.get("filesChanged", [])
        assert "/src/a.ts" in files or "a.ts" in str(files)
        assert "/src/b.ts" in files or "b.ts" in str(files)
