#!/bin/bash
# Shared utilities for jira-auto-issue hooks

# Find project root by walking up from CWD looking for .git
find_project_root() {
  local dir="$PWD"
  while [[ "$dir" != "/" ]]; do
    if [[ -d "$dir/.git" || -f "$dir/.git" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# Read a JSON value using python (available on macOS)
json_get() {
  local file="$1" key="$2"
  python3 -c "import json; d=json.load(open('$file')); print(d.get('$key',''))" 2>/dev/null
}

# Read a nested JSON value: json_get_nested file "key1" "key2"
json_get_nested() {
  local file="$1"; shift
  local keys=""
  for k in "$@"; do keys="$keys['$k']"; done
  python3 -c "
import json
d=json.load(open('$file'))
try:
  v=d${keys}
  print(v if not isinstance(v, (dict,list)) else json.dumps(v))
except (KeyError, TypeError, IndexError):
  print('')
" 2>/dev/null
}

# Write/update session state atomically via python
session_update() {
  local session_file="$1" python_code="$2"
  python3 -c "
import json, os, sys
f = sys.argv[1]
if os.path.exists(f):
    with open(f) as fh: data = json.load(fh)
else:
    data = {}
${python_code}
with open(f, 'w') as fh: json.dump(data, fh, indent=2)
" "$session_file"
}

# Check if tracker is enabled (config exists, enabled=true, no local override)
is_enabled() {
  local root="$1"
  local config="$root/.claude/jira-tracker.json"
  local local_config="$root/.claude/jira-tracker.local.json"

  [[ ! -f "$config" ]] && return 1

  # Check local override first
  if [[ -f "$local_config" ]]; then
    local local_enabled
    local_enabled=$(json_get "$local_config" "enabled")
    [[ "$local_enabled" == "False" || "$local_enabled" == "false" ]] && return 1
  fi

  local enabled
  enabled=$(json_get "$config" "enabled")
  [[ "$enabled" == "False" || "$enabled" == "false" ]] && return 1

  return 0
}

# Extract issue key from current git branch
extract_issue_from_branch() {
  local root="$1"
  local config="$root/.claude/jira-tracker.json"
  local branch
  branch=$(git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null)
  [[ -z "$branch" ]] && return 1

  local project_key
  project_key=$(json_get "$config" "projectKey")
  [[ -z "$project_key" ]] && return 1

  # Match pattern like feature/PROJ-42-description
  if [[ "$branch" =~ ($project_key-[0-9]+) ]]; then
    echo "${BASH_REMATCH[1]}"
    return 0
  fi
  return 1
}

# Session file path
session_file() {
  echo "$1/.claude/jira-session.json"
}

# Legacy task file path (for migration)
task_file() {
  echo "$1/.claude/current-task.json"
}

# Initialize a new session state file
init_session() {
  local root="$1"
  local sf="$root/.claude/jira-session.json"
  local session_id
  session_id="$(date +%Y%m%d)-$$"

  mkdir -p "$root/.claude"
  python3 -c "
import json, sys, time
data = {
    'sessionId': sys.argv[1],
    'startTime': int(time.time()),
    'activeIssues': {},
    'currentIssue': None,
    'pendingIssues': [],
    'workChunks': [],
    'activityBuffer': []
}
with open(sys.argv[2], 'w') as f:
    json.dump(data, f, indent=2)
" "$session_id" "$sf"
  echo "$sf"
}

# Migrate old current-task.json to new session format
migrate_old_task() {
  local root="$1"
  local old_file="$root/.claude/current-task.json"
  local sf="$root/.claude/jira-session.json"

  [[ ! -f "$old_file" ]] && return 1

  python3 -c "
import json, sys, time, os
old_f = sys.argv[1]
new_f = sys.argv[2]
with open(old_f) as f:
    old = json.load(f)
key = old.get('issueKey', '')
if not key:
    sys.exit(1)
# Load or create session
if os.path.exists(new_f):
    with open(new_f) as f: data = json.load(f)
else:
    data = {
        'sessionId': '$(date +%Y%m%d)-$$',
        'startTime': int(time.time()),
        'activeIssues': {},
        'currentIssue': None,
        'pendingIssues': [],
        'workChunks': [],
        'activityBuffer': []
    }
data['activeIssues'][key] = {
    'summary': old.get('summary', ''),
    'startTime': old.get('startTime', int(time.time())),
    'totalSeconds': 0,
    'paused': False
}
data['currentIssue'] = key
with open(new_f, 'w') as f:
    json.dump(data, f, indent=2)
os.remove(old_f)
" "$old_file" "$sf" && return 0 || return 1
}
