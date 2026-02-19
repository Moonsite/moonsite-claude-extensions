#!/bin/bash
# UserPromptSubmit hook: gate implementation work behind Jira ticket + branch discipline
# If the user's prompt signals a new feature/fix and no issue is active, remind Claude
# to create a Jira ticket and feature branch before writing any code.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT=$(find_project_root) || exit 0
is_enabled "$ROOT" || exit 0

SESSION_FILE=$(session_file "$ROOT")
[[ ! -f "$SESSION_FILE" ]] && exit 0

# Read the incoming prompt
INPUT=$(cat)
PROMPT=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('user_prompt',''))" 2>/dev/null || true)
[[ -z "$PROMPT" ]] && exit 0

# If an issue is already active, nothing to enforce
CURRENT=$(json_get "$SESSION_FILE" "currentIssue")
[[ -n "$CURRENT" && "$CURRENT" != "None" ]] && exit 0

# Detect task/fix intent — look for implementation keywords
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

TASK_SIGNALS="implement\|add feature\|add a\|build\|create\|develop\|write a\|make a\|set up\|setup\|refactor\|migrate\|integrate\|scaffold"
BUG_SIGNALS="fix\|bug\|broken\|crash\|error\|not working\|failing\|regression\|issue with\|problem with\|debug"

MATCHED=0
if echo "$PROMPT_LOWER" | grep -qE "(${TASK_SIGNALS//\\|/|})" 2>/dev/null; then
  MATCHED=1
fi
if echo "$PROMPT_LOWER" | grep -qE "(${BUG_SIGNALS//\\|/|})" 2>/dev/null; then
  MATCHED=1
fi

[[ "$MATCHED" -eq 0 ]] && exit 0

# Output a systemMessage that Claude will see before responding
python3 - <<'PYEOF'
import json, sys

msg = (
    "[jira-autopilot] No active Jira issue detected. Before writing any code:\n"
    "  1. Run /jira-start to create or link a Jira ticket for this work.\n"
    "  2. A feature branch (feature/<KEY>-<slug>) will be created automatically.\n"
    "  3. Keep all changes for this ticket on that branch.\n"
    "  4. Commit with the ticket key in the message (e.g. 'PROJ-42: add login button').\n"
    "  5. When done, run /jira-stop — you will be prompted to open a PR.\n\n"
    "Proceed only after a Jira issue is active."
)

print(json.dumps({"systemMessage": msg}))
PYEOF
