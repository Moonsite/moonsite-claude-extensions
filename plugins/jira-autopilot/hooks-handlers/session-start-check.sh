#!/bin/bash
# SessionStart hook: init session, detect branch, load config
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT=$(find_project_root) || exit 0
CONFIG="$ROOT/.claude/jira-autopilot.json"
DECLINED="$ROOT/.claude/jira-autopilot.declined"
SESSION_FILE=$(session_file "$ROOT")

# No config exists
if [[ ! -f "$CONFIG" ]]; then
  if [[ ! -f "$DECLINED" ]]; then
    echo "[jira-autopilot] Not configured. Run /jira-setup to configure."
    touch "$DECLINED"
  fi
  exit 0
fi

# Check if enabled (check project config + global fallback)
if ! is_enabled "$ROOT"; then
  exit 0
fi

PROJECT_KEY=$(json_get "$CONFIG" "projectKey")
# Ensure cloudId is available (fallback to global)
CLOUD_ID=$(json_get "$CONFIG" "cloudId")
if [[ -z "$CLOUD_ID" ]] && [[ -f "$GLOBAL_CONFIG" ]]; then
  CLOUD_ID=$(json_get "$GLOBAL_CONFIG" "cloudId")
fi

# Migrate old current-task.json if present
OLD_TASK=$(task_file "$ROOT")
if [[ -f "$OLD_TASK" ]]; then
  if migrate_old_task "$ROOT"; then
    echo "[jira-autopilot] Migrated old task state to new session format."
  fi
fi

# Initialize session if not present
if [[ ! -f "$SESSION_FILE" ]]; then
  init_session "$ROOT" >/dev/null
fi

# Update sessionId and startTime for this session
SESSION_ID="$(date +%Y%m%d)-$$"
python3 -c "
import json, time
f = '$SESSION_FILE'
with open(f) as fh: data = json.load(fh)
data['sessionId'] = '$SESSION_ID'
data['startTime'] = int(time.time())
data['activityBuffer'] = []
with open(f, 'w') as fh: json.dump(data, fh, indent=2)
"

# Try to detect issue from branch
ISSUE_KEY=$(extract_issue_from_branch "$ROOT" || true)

if [[ -n "$ISSUE_KEY" ]]; then
  # Check if already tracked
  CURRENT=$(json_get "$SESSION_FILE" "currentIssue")
  if [[ "$CURRENT" == "$ISSUE_KEY" ]]; then
    ELAPSED=$(python3 -c "
import json, time
with open('$SESSION_FILE') as f: d = json.load(f)
info = d.get('activeIssues', {}).get('$ISSUE_KEY', {})
total = info.get('totalSeconds', 0)
start = info.get('startTime', int(time.time()))
elapsed = total + (int(time.time()) - start)
print(elapsed // 60)
")
    echo "[jira-autopilot] Active: $ISSUE_KEY (${ELAPSED}m). /jira-status for details, /jira-stop to log time."
    exit 0
  fi

  # New issue detected from branch — add to session
  NOW=$(date +%s)
  python3 -c "
import json
f = '$SESSION_FILE'
with open(f) as fh: data = json.load(fh)
data['activeIssues']['$ISSUE_KEY'] = {
    'summary': '',
    'startTime': $NOW,
    'totalSeconds': 0,
    'paused': False
}
data['currentIssue'] = '$ISSUE_KEY'
with open(f, 'w') as fh: json.dump(data, fh, indent=2)
"
  echo "[jira-autopilot] Detected $ISSUE_KEY from branch. Timer started. /jira-status for details."
  exit 0
fi

# Check for existing active issues
CURRENT=$(json_get "$SESSION_FILE" "currentIssue")
if [[ -n "$CURRENT" && "$CURRENT" != "None" ]]; then
  echo "[jira-autopilot] Active: $CURRENT. /jira-status for details, /jira-stop to log time."
  exit 0
fi

# No task detected
echo "[jira-autopilot] No active Jira task. Use /jira-start <KEY> or /jira-start <summary> to begin."
