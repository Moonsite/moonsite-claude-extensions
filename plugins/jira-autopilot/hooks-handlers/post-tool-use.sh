#!/bin/bash
# PostToolUse hook (async): log meaningful tool activity to session buffer
# Receives JSON on stdin with tool_name, tool_input, etc.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT=$(find_project_root) || exit 0
SESSION_FILE=$(session_file "$ROOT")
[[ ! -f "$SESSION_FILE" ]] && exit 0
is_enabled "$ROOT" || exit 0

# Read hook input from stdin
INPUT=$(cat)

# Parse tool info
TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null || true)
[[ -z "$TOOL_NAME" ]] && exit 0

# Skip read-only / noise tools
case "$TOOL_NAME" in
  Read|Glob|Grep|WebSearch|WebFetch|ToolSearch|LS|AskUserQuestion|TaskList|TaskGet)
    exit 0
    ;;
esac

# Extract relevant info based on tool type
python3 -c "
import json, sys, time

inp = json.loads('''$INPUT''') if '''$INPUT''' else {}
tool = inp.get('tool_name', '')
tool_input = inp.get('tool_input', {})

activity = {
    'timestamp': int(time.time()),
    'tool': tool,
}

if tool in ('Edit', 'MultiEdit'):
    activity['file'] = tool_input.get('file_path', '')
    activity['type'] = 'file_edit'
elif tool == 'Write':
    activity['file'] = tool_input.get('file_path', '')
    activity['type'] = 'file_write'
elif tool == 'NotebookEdit':
    activity['file'] = tool_input.get('notebook_path', '')
    activity['type'] = 'file_edit'
elif tool == 'Bash':
    cmd = tool_input.get('command', '')
    # Skip read-only commands
    read_only = ['ls', 'cat ', 'head ', 'tail ', 'git status', 'git log', 'git diff', 'git branch', 'pwd', 'echo ', 'which ', 'type ']
    if any(cmd.strip().startswith(ro) for ro in read_only):
        sys.exit(0)
    activity['command'] = cmd[:200]  # truncate long commands
    activity['type'] = 'bash'
elif tool == 'Task':
    activity['type'] = 'agent_spawn'
else:
    activity['type'] = 'other'

# Append to activity buffer
sf = '$SESSION_FILE'
with open(sf) as f:
    data = json.load(f)
data.setdefault('activityBuffer', []).append(activity)
with open(sf, 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null || true

# Silent — no stdout for async hooks
