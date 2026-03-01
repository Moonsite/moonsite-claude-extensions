import json
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import jira_core


class TestClassifyIssue:
    """Tests for issue classification logic (cmd_classify_issue / classify_issue)."""

    def test_detects_bug_signals(self):
        """Summaries with bug keywords should classify as Bug."""
        # Per spec 6.2: bug_score >= 2, or bug_score > task_score and >= 1
        result = jira_core.classify_issue("Fix broken login crash on mobile")
        assert result["type"] == "Bug"
        assert result["confidence"] > 0.5
        # Should find signals like "fix", "broken", "crash"
        assert len(result["signals"]) >= 1

    def test_detects_task_signals(self):
        """Summaries with task keywords should classify as Task."""
        result = jira_core.classify_issue("Implement new user registration flow")
        assert result["type"] == "Task"
        assert result["confidence"] > 0.5
        assert len(result["signals"]) >= 1

    def test_returns_confidence_score(self):
        """Classification result should include a float confidence in [0, 1]."""
        result = jira_core.classify_issue("Fix authentication error regression")
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_confidence_scales_with_signal_count(self):
        """More matching signals should yield higher confidence."""
        # Per spec: confidence = min(0.5 + score * 0.15, 0.95)
        weak = jira_core.classify_issue("Fix a thing")
        strong = jira_core.classify_issue("Fix broken crash error regression bug")
        assert strong["confidence"] >= weak["confidence"]

    def test_handles_ambiguous_input(self):
        """Input with mixed or no signals should still return a valid result."""
        result = jira_core.classify_issue("Update the configuration settings")
        assert result["type"] in ("Bug", "Task")
        assert isinstance(result["confidence"], float)
        assert "signals" in result

    def test_classifies_from_work_chunk_summary(self):
        """Should classify from a work chunk summary (file list style)."""
        result = jira_core.classify_issue("Fix crash in auth.ts, login.tsx")
        assert result["type"] == "Bug"

    def test_pure_task_summary(self):
        """Summary with only task signals should classify as Task."""
        result = jira_core.classify_issue("Create build pipeline and configure CI")
        assert result["type"] == "Task"

    def test_case_insensitive(self):
        """Classification should be case-insensitive."""
        result = jira_core.classify_issue("FIX BROKEN AUTH CRASH")
        assert result["type"] == "Bug"

    def test_no_signals_defaults_to_task(self):
        """When no signals are found, should default to Task."""
        result = jira_core.classify_issue("Something about the system")
        assert result["type"] == "Task"

    def test_context_boosts_bug_score(self):
        """Context with no new files and edited files should boost bug score."""
        # Per spec 6.2: new_files_created == 0 && files_edited > 0 → +1 bug score
        context = {"new_files_created": 0, "files_edited": 3}
        result = jira_core.classify_issue("Fix the login page", context=context)
        assert result["type"] == "Bug"

    def test_context_boosts_task_score(self):
        """Context with new files created should boost task score."""
        # Per spec 6.2: new_files_created > 0 → +1 task score
        context = {"new_files_created": 5, "files_edited": 0}
        result = jira_core.classify_issue("Add authentication module", context=context)
        assert result["type"] == "Task"


class TestCmdClassifyIssue:
    """Tests for the CLI wrapper cmd_classify_issue()."""

    def test_outputs_json(self, project_root, capsys):
        """cmd_classify_issue should print JSON to stdout."""
        with patch("sys.argv", ["jira_core.py", "classify-issue", str(project_root), "Fix login bug"]):
            jira_core.cmd_classify_issue()

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "type" in result
        assert "confidence" in result
        assert "signals" in result
