#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
ROOT="$(find_project_root)"
python3 "$SCRIPT_DIR/jira_core.py" session-end "$ROOT" 2>/dev/null || true
python3 "$SCRIPT_DIR/jira_core.py" post-worklogs "$ROOT" 2>/dev/null || true
exit 0
