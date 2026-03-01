import pytest
import os


@pytest.fixture(autouse=True)
def isolate_global_config(tmp_path, monkeypatch):
    """Prevent tests from using real global credentials."""
    fake_global = str(tmp_path / "nonexistent-global.json")
    monkeypatch.setattr("jira_core.GLOBAL_CONFIG_PATH", fake_global)


@pytest.fixture
def project_root(tmp_path):
    """Create a project root with .claude directory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return tmp_path
