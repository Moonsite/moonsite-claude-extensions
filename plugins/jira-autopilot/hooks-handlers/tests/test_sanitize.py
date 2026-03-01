import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestSanitizeForLog:
    def test_redacts_atlassian_token(self):
        text = "token: ATATT3xABC123_/+=.-end"
        result = jira_core.sanitize_for_log(text)
        assert "ATATT3x" not in result
        assert "[REDACTED_TOKEN]" in result

    def test_redacts_bearer(self):
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9"
        result = jira_core.sanitize_for_log(text)
        assert "eyJ" not in result
        assert "Bearer [REDACTED]" in result

    def test_redacts_basic_auth(self):
        text = "Basic dXNlcjpwYXNz"
        result = jira_core.sanitize_for_log(text)
        assert "dXNlcjpwYXNz" not in result

    def test_redacts_curl_auth(self):
        text = "curl -u user@test.com:mytoken123 https://api"
        result = jira_core.sanitize_for_log(text)
        assert "mytoken123" not in result
        assert "-u [REDACTED]" in result

    def test_redacts_api_token_json(self):
        text = '{"apiToken": "secret123"}'
        result = jira_core.sanitize_for_log(text)
        assert "secret123" not in result

    def test_leaves_normal_text_alone(self):
        text = "Editing src/auth.ts line 42"
        assert jira_core.sanitize_for_log(text) == text

    def test_handles_non_string(self):
        result = jira_core.sanitize_for_log({"key": "value"})
        assert isinstance(result, str)

    def test_multiple_tokens_in_same_text(self):
        text = "Bearer abc123 and ATATT3xDEF456 and Basic eHl6"
        result = jira_core.sanitize_for_log(text)
        assert "abc123" not in result
        assert "ATATT3x" not in result
        assert "eHl6" not in result

    def test_empty_string(self):
        assert jira_core.sanitize_for_log("") == ""

    def test_api_token_with_spaces_around_colon(self):
        text = '"apiToken" : "mysecrettoken"'
        result = jira_core.sanitize_for_log(text)
        assert "mysecrettoken" not in result


class TestLogRotation:
    def test_rotates_at_threshold(self, tmp_path, monkeypatch):
        log_path = str(tmp_path / "test.log")
        monkeypatch.setattr("jira_core.DEBUG_LOG_PATH", log_path)
        # Write > 1MB
        with open(log_path, "w") as f:
            f.write("x" * (jira_core.MAX_LOG_SIZE + 100))
        jira_core._rotate_log(log_path)
        assert os.path.exists(log_path + ".1")
        assert not os.path.exists(log_path)

    def test_no_rotation_under_threshold(self, tmp_path):
        log_path = str(tmp_path / "test.log")
        with open(log_path, "w") as f:
            f.write("small")
        jira_core._rotate_log(log_path)
        assert not os.path.exists(log_path + ".1")

    def test_rotation_replaces_old_backup(self, tmp_path):
        log_path = str(tmp_path / "test.log")
        backup_path = log_path + ".1"
        # Create old backup
        with open(backup_path, "w") as f:
            f.write("old backup")
        # Create oversized log
        with open(log_path, "w") as f:
            f.write("x" * (jira_core.MAX_LOG_SIZE + 100))
        jira_core._rotate_log(log_path)
        assert os.path.exists(backup_path)
        with open(backup_path) as f:
            content = f.read()
        assert content.startswith("xxx")  # New content, not "old backup"

    def test_rotation_nonexistent_file(self, tmp_path):
        log_path = str(tmp_path / "nonexistent.log")
        jira_core._rotate_log(log_path)  # Should not raise


class TestDebugLog:
    def test_writes_to_log_file(self, tmp_path, monkeypatch):
        log_path = str(tmp_path / "debug.log")
        monkeypatch.setattr("jira_core.DEBUG_LOG_PATH", log_path)
        jira_core.debug_log("test message")
        with open(log_path) as f:
            content = f.read()
        assert "test message" in content

    def test_sanitizes_credentials(self, tmp_path, monkeypatch):
        log_path = str(tmp_path / "debug.log")
        monkeypatch.setattr("jira_core.DEBUG_LOG_PATH", log_path)
        jira_core.debug_log("token: ATATT3xSECRET123")
        with open(log_path) as f:
            content = f.read()
        assert "SECRET123" not in content
        assert "[REDACTED_TOKEN]" in content

    def test_respects_debug_disabled(self, project_root, tmp_path, monkeypatch):
        log_path = str(tmp_path / "debug.log")
        monkeypatch.setattr("jira_core.DEBUG_LOG_PATH", log_path)
        cfg_path = project_root / ".claude" / "jira-autopilot.json"
        cfg_path.write_text('{"debugLog": false}')
        jira_core.debug_log("should not appear", root=str(project_root))
        assert not os.path.exists(log_path)
