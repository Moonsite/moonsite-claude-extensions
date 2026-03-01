import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestLoadConfig:
    def test_missing_file_returns_empty(self, project_root):
        cfg = jira_core.load_config(str(project_root))
        assert cfg == {}

    def test_loads_valid_config(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text(json.dumps({"projectKey": "TEST", "enabled": True}))
        cfg = jira_core.load_config(str(project_root))
        assert cfg["projectKey"] == "TEST"

    def test_corrupt_json_returns_empty(self, project_root):
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text("{broken json")
        cfg = jira_core.load_config(str(project_root))
        assert cfg == {}


class TestGetCred:
    def test_local_config_takes_priority(self, project_root):
        local = project_root / ".claude" / "jira-autopilot.local.json"
        local.write_text(json.dumps({"email": "local@test.com"}))
        assert jira_core.get_cred(str(project_root), "email") == "local@test.com"

    def test_falls_back_to_global(self, project_root, tmp_path, monkeypatch):
        global_cfg = tmp_path / "global.json"
        global_cfg.write_text(json.dumps({"email": "global@test.com"}))
        monkeypatch.setattr("jira_core.GLOBAL_CONFIG_PATH", str(global_cfg))
        assert jira_core.get_cred(str(project_root), "email") == "global@test.com"

    def test_missing_creds_returns_empty(self, project_root):
        assert jira_core.get_cred(str(project_root), "email") == ""


class TestAtomicWrite:
    def test_roundtrip_integrity(self, project_root):
        path = str(project_root / "test.json")
        data = {"key": "value", "nested": {"a": 1}}
        jira_core.atomic_write_json(path, data)
        loaded = json.loads(open(path).read())
        assert loaded == data

    def test_no_temp_files_left(self, project_root):
        path = str(project_root / "test.json")
        jira_core.atomic_write_json(path, {"x": 1})
        files = os.listdir(str(project_root))
        # .claude dir + test.json
        assert "test.json" in files
        assert not any(f.endswith(".tmp") for f in files)


class TestSessionManagement:
    def test_new_session_has_required_fields(self):
        session = jira_core._new_session()
        required_fields = [
            "sessionId", "autonomyLevel", "accuracy", "disabled",
            "activeIssues", "currentIssue", "lastParentKey",
            "workChunks", "pendingWorklogs", "pendingIssues",
            "activityBuffer", "activeTasks", "taskSubjects",
            "activePlanning", "lastWorklogTime",
        ]
        for field in required_fields:
            assert field in session, f"Missing field: {field}"

    def test_ensure_session_structure_fills_missing(self):
        partial = {"sessionId": "test-123", "activeIssues": {"KEY-1": {}}}
        result = jira_core._ensure_session_structure(partial)
        assert result["sessionId"] == "test-123"
        assert result["activeIssues"] == {"KEY-1": {}}
        assert result["currentIssue"] is None
        assert result["workChunks"] == []

    def test_load_session_missing_file(self, project_root):
        session = jira_core.load_session(str(project_root))
        assert session == {}

    def test_save_and_load_session(self, project_root):
        session = jira_core._new_session()
        session["currentIssue"] = "TEST-42"
        jira_core.save_session(str(project_root), session)
        loaded = jira_core.load_session(str(project_root))
        assert loaded["currentIssue"] == "TEST-42"
