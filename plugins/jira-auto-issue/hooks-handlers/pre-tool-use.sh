#!/bin/bash
# PreToolUse hook: suggest including issue key in git commit messages
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT=$(find_project_root) || exit 0
SESSION_FILE=$(session_file "$ROOT")
[[ ! -f "$SESSION_FILE" ]] && exit 0
is_enabled "$ROOT" || exit 0

# Read hook input from stdin
INPUT=$(cat)

# Only act on Bash tool with git commit
TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || true)
[[ "$TOOL_NAME" != "Bash" ]] && exit 0

COMMAND=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

# Check if this is a git commit command
echo "$COMMAND" | grep -q "git commit" || exit 0

# Get current issue
CURRENT=$(json_get "$SESSION_FILE" "currentIssue")
[[ -z "$CURRENT" || "$CURRENT" == "None" ]] && exit 0

# Check if issue key already in the commit message
echo "$COMMAND" | grep -q "$CURRENT" && exit 0

# Suggest including issue key
echo "[jira-auto-issue] Active issue: $CURRENT. Consider including in commit message: $CURRENT: <message>"
