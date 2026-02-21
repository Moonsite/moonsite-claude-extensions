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

# ── Task/fix intent ───────────────────────────────────────────────────────────
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

# ── Auto-create path (autonomy A/B) ──────────────────────────────────────────
RESULT=$(python3 "$SCRIPT_DIR/jira_core.py" auto-create-issue "$ROOT" "$PROMPT" 2>/dev/null || true)

if [[ -n "$RESULT" ]]; then
  IS_DUP=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('duplicate', False))" 2>/dev/null || echo "False")
  NEW_KEY=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('key',''))" 2>/dev/null || echo "")
  SUMMARY=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('summary',''))" 2>/dev/null || echo "")
  PARENT=$(echo "$RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('parent') or '')" 2>/dev/null || echo "")

  AUTONOMY=$(python3 -c "
import json, sys, os
root = sys.argv[1]
cfg_path = os.path.join(root, '.claude', 'jira-autopilot.json')
sess_path = os.path.join(root, '.claude', 'jira-session.json')
cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
sess = json.load(open(sess_path)) if os.path.exists(sess_path) else {}
raw = sess.get('autonomyLevel') or cfg.get('autonomyLevel', 'C')
if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
    n = int(raw)
    print('A' if n == 10 else ('B' if n >= 6 else 'C'))
else:
    print(str(raw).upper() if str(raw).upper() in ('A','B','C') else 'C')
" "$ROOT" 2>/dev/null || echo "C")

  if [[ "$IS_DUP" == "True" ]]; then
    # Duplicate: A is silent, B shows a notice
    if [[ "$AUTONOMY" == "B" ]]; then
      python3 - "$NEW_KEY" <<'PYEOF'
import json, sys
key = sys.argv[1]
msg = f"[jira-autopilot] Continuing work under {key} (already tracked)."
print(json.dumps({"systemMessage": msg}))
PYEOF
    fi
    exit 0
  else
    # New issue created
    if [[ "$AUTONOMY" == "B" ]]; then
      python3 - "$NEW_KEY" "$SUMMARY" "$PARENT" <<'PYEOF'
import json, sys
key, summary, parent = sys.argv[1], sys.argv[2], sys.argv[3]
parent_part = f" under {parent}" if parent and parent != "None" else ""
slug = summary.lower()[:40]
slug = __import__('re').sub(r'[^a-z0-9]+', '-', slug).strip('-')
msg = (
    f"[jira-autopilot] Auto-created {key}{parent_part}: {summary}.\n"
    f"  Create branch: feature/{key.lower()}-{slug}"
)
print(json.dumps({"systemMessage": msg}))
PYEOF
    else
      # Autonomy A: one-line system message with branch instruction
      python3 - "$NEW_KEY" "$SUMMARY" "$PARENT" <<'PYEOF'
import json, sys, re
key, summary, parent = sys.argv[1], sys.argv[2], sys.argv[3]
parent_part = f" under {parent}" if parent and parent != "None" else ""
slug = re.sub(r'[^a-z0-9]+', '-', summary.lower()[:40]).strip('-')
msg = f"Created {key}{parent_part}: {summary}. Create branch feature/{key.lower()}-{slug}."
print(json.dumps({"systemMessage": msg}))
PYEOF
    fi
    exit 0
  fi
fi

# ── C-mode fallback (or no creds / low confidence) ───────────────────────────
# No active issue — require /jira-start before any code
if [[ -z "$CURRENT" || "$CURRENT" == "None" ]]; then
  python3 - <<'PYEOF'
import json, sys
msg = (
    "[jira-autopilot] Work is being captured (no issue assigned yet). "
    "Run /jira-start to link to a Jira issue, or continue — work will be auto-attributed at session end."
)
print(json.dumps({"systemMessage": msg}))
PYEOF

# Issue already active — this is a NEW task/bug, create a sub-issue for it
else
  python3 - "$CURRENT" <<'PYEOF'
import json, sys
current = sys.argv[1]
msg = (
    f"[jira-autopilot] New task or bug detected while {current} is active. "
    f"Run /jira-start to create a new issue linked to {current}, or use it standalone."
)
print(json.dumps({"systemMessage": msg}))
PYEOF
fi
