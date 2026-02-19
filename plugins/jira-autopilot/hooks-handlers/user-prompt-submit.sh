#!/bin/bash
# UserPromptSubmit hook: intercept implementation work and time-logging shortcuts
# - If the user signals a new feature/fix with no active issue → require /jira-start first
# - If the user signals time logging intent → require /jira-stop instead of raw MCP
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

CURRENT=$(json_get "$SESSION_FILE" "currentIssue")
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

# ── Time-logging intent (fires regardless of whether an issue is active) ──────
# Matches: "1h", "30m", "2h30m", "log time", "log 1 hour", "45 minutes", etc.
TIME_SIGNALS="log time\|log.*hour\|log.*minute\|worklog\|time log\|spent.*hour\|spent.*minute"
TIME_SHORTHAND="^[0-9]+h[0-9]*m?$\|^[0-9]+m$\|^[0-9]+\.[0-9]+h$"

IS_TIME_LOG=0
if echo "$PROMPT_LOWER" | grep -qE "(${TIME_SIGNALS//\\|/|})" 2>/dev/null; then
  IS_TIME_LOG=1
fi
if echo "$PROMPT" | grep -qE "(${TIME_SHORTHAND//\\|/|})" 2>/dev/null; then
  IS_TIME_LOG=1
fi

if [[ "$IS_TIME_LOG" -eq 1 ]]; then
  python3 - "$CURRENT" <<'PYEOF'
import json, sys
current = sys.argv[1] if len(sys.argv) > 1 else ""
issue_hint = f" for {current}" if current and current != "None" else ""
msg = (
    f"[jira-autopilot] Use /jira-stop to log time{issue_hint} — do NOT call mcp__atlassian__addWorklogToJiraIssue directly.\n"
    "  /jira-stop will:\n"
    "  • Build an enriched worklog from actual activity (files edited, commands run)\n"
    "  • Apply time rounding from your config\n"
    "  • Go through the approval flow based on your autonomy level\n"
    "  • Prompt to open a PR if on a feature branch\n\n"
    "Run /jira-stop now."
)
print(json.dumps({"systemMessage": msg}))
PYEOF
  exit 0
fi

# ── Task/fix intent with no active issue ─────────────────────────────────────
[[ -n "$CURRENT" && "$CURRENT" != "None" ]] && exit 0

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
