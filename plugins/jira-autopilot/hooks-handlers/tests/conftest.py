"""Shared test fixtures for jira-autopilot tests."""
import os
import pytest


@pytest.fixture(autouse=True)
def isolate_debug_log(tmp_path, monkeypatch):
    """Redirect debug log to temp dir so tests don't write to ~/.claude/."""
    log_path = str(tmp_path / "test-debug.log")
    monkeypatch.setenv("JIRA_AUTOPILOT_DEBUG_LOG", log_path)
