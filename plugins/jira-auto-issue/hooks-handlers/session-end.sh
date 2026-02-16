#!/bin/bash
# SessionEnd hook: log time + post work summary to Jira for each active issue, archive session
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
source "$SCRIPT_DIR/jira-rest.sh"

ROOT=$(find_project_root) || exit 0
SESSION_FILE=$(session_file "$ROOT")
[[ ! -f "$SESSION_FILE" ]] && exit 0
is_enabled "$ROOT" || exit 0

# Load credentials (silently fail if not configured — can't log to Jira without them)
jira_load_creds "$ROOT" 2>/dev/null || exit 0

# Process each active issue: log time and post summary
python3 -c "
import json, time, sys, os, subprocess, math

sf = sys.argv[1]
root = sys.argv[2]

with open(sf) as f:
    data = json.load(f)

active = data.get('activeIssues', {})
chunks = data.get('workChunks', [])
config_f = os.path.join(root, '.claude', 'jira-tracker.json')
rounding = 15
if os.path.exists(config_f):
    with open(config_f) as f:
        rounding = json.load(f).get('timeRounding', 15)

now = int(time.time())
results = []

for key, info in active.items():
    # Calculate total time
    total_secs = info.get('totalSeconds', 0)
    if not info.get('paused', False):
        total_secs += now - info.get('startTime', now)

    if total_secs < 60:
        results.append(f'{key}: <1m, skipping')
        continue

    # Round up to nearest increment
    minutes = total_secs / 60
    rounded_minutes = math.ceil(minutes / rounding) * rounding
    rounded_seconds = rounded_minutes * 60

    # Build work summary from chunks for this issue
    issue_chunks = [c for c in chunks if c.get('issueKey') == key]
    files = set()
    for c in issue_chunks:
        files.update(c.get('filesChanged', []))

    summary_lines = [f'Session work log ({rounded_minutes}m):']
    if files:
        summary_lines.append('Files changed:')
        for f in sorted(files)[:20]:
            summary_lines.append(f'  - {os.path.basename(f)}')
    summary_lines.append(f'Activities: {sum(len(c.get(\"activities\",[])) for c in issue_chunks)} tool calls')

    results.append(json.dumps({
        'key': key,
        'seconds': rounded_seconds,
        'summary': chr(10).join(summary_lines),
        'actual_minutes': int(minutes),
        'rounded_minutes': rounded_minutes
    }))

# Output results for bash to process
for r in results:
    print(r)
" "$SESSION_FILE" "$ROOT" | while IFS= read -r line; do
  # Skip plain text status lines
  if [[ "$line" != "{"* ]]; then
    continue
  fi

  KEY=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['key'])")
  SECONDS=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['seconds'])")
  SUMMARY=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['summary'])")
  ACTUAL=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['actual_minutes'])")
  ROUNDED=$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin)['rounded_minutes'])")

  # Log time
  if jira_log_time "$KEY" "$SECONDS" >/dev/null 2>&1; then
    echo "[jira-auto-issue] Logged ${ROUNDED}m to $KEY (actual: ${ACTUAL}m)"
  fi

  # Post summary comment
  if [[ -n "$SUMMARY" ]]; then
    jira_add_comment "$KEY" "$SUMMARY" >/dev/null 2>&1 || true
  fi
done

# Archive session
ARCHIVE_DIR="$ROOT/.claude/jira-sessions"
mkdir -p "$ARCHIVE_DIR"
SESSION_ID=$(json_get "$SESSION_FILE" "sessionId")
cp "$SESSION_FILE" "$ARCHIVE_DIR/${SESSION_ID}.json"

# Clean up session state (keep file but reset)
python3 -c "
import json
sf = '$SESSION_FILE'
with open(sf) as f: data = json.load(f)
data['activeIssues'] = {}
data['currentIssue'] = None
data['workChunks'] = []
data['activityBuffer'] = []
data['pendingIssues'] = []
with open(sf, 'w') as f: json.dump(data, f, indent=2)
"
