#!/bin/bash
# Stop hook: drain activity buffer into work chunks, detect idle/context switches
# Rules: ALWAYS exit 0. Never block Claude's stop event.
# If work is captured but unattributed, output informational message only.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT=$(find_project_root) || exit 0

# Drain the activity buffer into work chunks
python3 "$SCRIPT_DIR/jira_core.py" drain-buffer "$ROOT" || true

# Check if there are unattributed work chunks (issueKey = null)
session_file="$ROOT/.claude/jira-session.json"
if [[ -f "$session_file" ]] && [[ -r "$session_file" ]]; then
    # Count unattributed chunks and check for active issues
    python3 -c "
import json
import sys
try:
    with open('$session_file') as f:
        session = json.load(f)
    unattributed_chunks = [c for c in session.get('workChunks', []) if c.get('issueKey') is None]
    active_issues = session.get('activeIssues', {})
    
    # If there's unattributed work and no active issue, output info message
    if unattributed_chunks and not active_issues:
        count = len(unattributed_chunks)
        print(f'[jira-autopilot] Work captured ({count} unattributed chunk(s)). It will be attributed at session end. Use /jira-start to assign now.')
except Exception as e:
    pass
" || true
fi

# Always exit 0 — never block
exit 0
