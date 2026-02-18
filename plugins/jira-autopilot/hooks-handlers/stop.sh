#!/bin/bash
# Stop hook: drain activity buffer into work chunk, suggest issue if none active
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT=$(find_project_root) || exit 0
SESSION_FILE=$(session_file "$ROOT")
[[ ! -f "$SESSION_FILE" ]] && exit 0
is_enabled "$ROOT" || exit 0

# Drain activity buffer into a work chunk
python3 -c "
import json, time, sys, os

sf = '$SESSION_FILE'
with open(sf) as f:
    data = json.load(f)

buf = data.get('activityBuffer', [])
if len(buf) < 2:
    # Not enough activity to create a chunk
    sys.exit(0)

# Build work chunk
files_changed = list(set(
    a.get('file', '') for a in buf
    if a.get('file') and a.get('type') in ('file_edit', 'file_write')
))

chunk = {
    'id': 'chunk-' + str(int(time.time())),
    'issueKey': data.get('currentIssue'),
    'startTime': buf[0].get('timestamp', int(time.time())),
    'endTime': buf[-1].get('timestamp', int(time.time())),
    'activities': buf,
    'filesChanged': files_changed,
    'summary': ''
}

data.setdefault('workChunks', []).append(chunk)
data['activityBuffer'] = []

# If no current issue and there are file edits, add to pending
current = data.get('currentIssue')
if not current and files_changed:
    pending = {
        'id': 'pending-' + str(int(time.time())),
        'suggestedSummary': 'Work on: ' + ', '.join(os.path.basename(f) for f in files_changed[:5]),
        'chunkIds': [chunk['id']],
        'status': 'awaiting_approval'
    }
    data.setdefault('pendingIssues', []).append(pending)

    # Output suggestion for Claude
    file_list = ', '.join(os.path.basename(f) for f in files_changed[:5])
    if len(files_changed) > 5:
        file_list += f' (+{len(files_changed)-5} more)'
    print(f'[jira-autopilot] Work detected but no active issue. Files: {file_list}. Use /jira-start to link or /jira-approve to create.')

with open(sf, 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null || true
