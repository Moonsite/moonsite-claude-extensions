#!/bin/bash
# SessionStart hook: detect active Jira task or prompt to create one
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT=$(find_project_root) || exit 0
CONFIG="$ROOT/.claude/jira-tracker.json"
DECLINED="$ROOT/.claude/jira-tracker.declined"
TASK_FILE=$(task_file "$ROOT")

# No config exists
if [[ ! -f "$CONFIG" ]]; then
  if [[ ! -f "$DECLINED" ]]; then
    echo "💡 Jira tracking not configured for this project. Run /jira:setup to configure."
    touch "$DECLINED"
  fi
  exit 0
fi

# Check if enabled
if ! is_enabled "$ROOT"; then
  exit 0
fi

PROJECT_KEY=$(json_get "$CONFIG" "projectKey")

# Try to detect issue from branch
ISSUE_KEY=$(extract_issue_from_branch "$ROOT" || true)

if [[ -n "$ISSUE_KEY" ]]; then
  # Issue detected from branch
  if [[ -f "$TASK_FILE" ]]; then
    EXISTING_KEY=$(json_get "$TASK_FILE" "issueKey")
    if [[ "$EXISTING_KEY" == "$ISSUE_KEY" ]]; then
      START=$(json_get "$TASK_FILE" "startTime")
      NOW=$(date +%s)
      ELAPSED=$(( (NOW - START) / 60 ))
      echo "🎯 Active task: $ISSUE_KEY (${ELAPSED}m elapsed). Use /jira:status for details, /jira:stop to log time."
      exit 0
    fi
  fi
  # Create/update task file with detected issue
  NOW=$(date +%s)
  BRANCH=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
  mkdir -p "$ROOT/.claude"
  cat > "$TASK_FILE" <<EOF
{
  "issueKey": "$ISSUE_KEY",
  "summary": "",
  "startTime": $NOW,
  "branch": "$BRANCH"
}
EOF
  echo "🎯 Detected task $ISSUE_KEY from branch. Timer started. Use /jira:status for details, /jira:stop to log time."
  exit 0
fi

# Check for existing task file (from manual /jira:start)
if [[ -f "$TASK_FILE" ]]; then
  EXISTING_KEY=$(json_get "$TASK_FILE" "issueKey")
  START=$(json_get "$TASK_FILE" "startTime")
  NOW=$(date +%s)
  ELAPSED=$(( (NOW - START) / 60 ))
  echo "🎯 Active task: $EXISTING_KEY (${ELAPSED}m elapsed). Use /jira:status for details, /jira:stop to log time."
  exit 0
fi

# No task detected
echo "⚠️ No Jira task detected. Run /jira:start <ISSUE-KEY> to link existing, or /jira:start <summary> to create new."
