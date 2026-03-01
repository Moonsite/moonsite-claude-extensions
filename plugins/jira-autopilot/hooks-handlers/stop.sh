#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
ROOT="$(find_project_root)"
python3 "$SCRIPT_DIR/jira_core.py" drain-buffer "$ROOT" 2>/dev/null || true
exit 0
