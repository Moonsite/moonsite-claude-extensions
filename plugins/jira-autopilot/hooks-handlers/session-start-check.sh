#!/bin/bash
# SessionStart hook: init session, detect branch, load config, announce status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT=$(find_project_root) || exit 0
python3 "$SCRIPT_DIR/jira_core.py" session-start "$ROOT"

# Emit a systemMessage so Claude announces the plugin status at session start
STATUS=$(bash "$SCRIPT_DIR/jira-status.sh" "$ROOT" 2>/dev/null) || STATUS=""
if [[ -n "$STATUS" ]]; then
  python3 -c "
import json, sys
status = sys.argv[1]
msg = f'[jira-autopilot] Active and monitoring this session.\n\n{status}'
print(json.dumps({'systemMessage': msg}))
" "$STATUS"
fi
