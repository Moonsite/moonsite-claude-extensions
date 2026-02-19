#!/bin/bash
# jira-autopilot statusline script
#
# Setup: point Claude Code's statusLine command at this file, or use a thin wrapper:
#
#   ~/.claude/settings.json:
#   "statusLine": { "type": "command", "command": "bash /path/to/statusline-command.sh" }
#
#   Or create ~/.claude/statusline-command.sh containing:
#   #!/bin/bash
#   exec bash "/path/to/plugins/jira-autopilot/statusline-command.sh"
#
# Shows: folder · repo · branch · ±dirty · ↑unpushed · ⏱ ISSUE vX.X.X time · 📐 planning · model · ctx · cost
# When jira-autopilot is not configured for the project: ⏱ Jira Autopilot not set vX.X.X (red)

input=$(cat)

# Colors
RESET='\033[0m'
C_FOLDER='\033[1;36m'       # bold cyan
C_REPO='\033[1;35m'         # bold magenta
C_BRANCH='\033[1;33m'       # bold yellow
C_MODEL='\033[1;32m'        # bold green
C_COST='\033[1;34m'         # bold blue
C_CTX_OK='\033[1;32m'       # green (plenty of context)
C_CTX_WARN='\033[1;33m'     # yellow (getting low)
C_CTX_CRIT='\033[1;31m'     # red (critical)
C_SEP='\033[2;37m'          # dim white separator
C_ICON='\033[90m'           # dark grey icons
C_JIRA_UNSET='\033[1;31m'   # bold red — not configured
C_JIRA='\033[1;34m'         # bold blue — Jira issue key
C_JIRA_TIME='\033[1;32m'    # bold green — time tracked
C_JIRA_WARN='\033[1;33m'    # bold yellow — pending worklogs
C_DIRTY='\033[1;33m'        # bold yellow — uncommitted changes
C_UNPUSHED='\033[1;35m'     # bold magenta — unpushed commits
C_PLANNING='\033[1;36m'     # bold cyan — plan mode

SEP=" ${C_SEP}·${RESET} "

# Parse stdin JSON
cwd=$(echo "$input" | jq -r '.cwd // empty')
model_name=$(echo "$input" | jq -r '.model.display_name // empty')
output_style=$(echo "$input" | jq -r '.output_style.name // "default"')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
remaining_pct=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')
total_cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')

# Fallback: model from settings.json
if [ -z "$model_name" ]; then
  model_raw=$(jq -r '.model // "sonnet"' ~/.claude/settings.json 2>/dev/null)
  case "$model_raw" in
    *opus*)   model_name="Opus 4.6" ;;
    *sonnet*) model_name="Sonnet 4.6" ;;
    *haiku*)  model_name="Haiku 4.5" ;;
    *)        model_name="$model_raw" ;;
  esac
fi

# Append output style if not default
model_label="$model_name"
if [ -n "$output_style" ] && [ "$output_style" != "default" ] && [ "$output_style" != "null" ]; then
  model_label="${model_name} (${output_style})"
fi

# Git info
project_dir="${cwd:-${CLAUDE_PROJECT_DIR:-$PWD}}"
folder_name="$(basename "$project_dir")"
cd "$project_dir" 2>/dev/null
git_branch=$(git --no-optional-locks rev-parse --abbrev-ref HEAD 2>/dev/null)
repo_name=$(git --no-optional-locks remote get-url origin 2>/dev/null \
  | sed 's|.*/||; s|\.git$||')
[ -z "$repo_name" ] && repo_name="$folder_name"

# Dirty files (staged + unstaged, excluding untracked)
git_dirty=$(git --no-optional-locks diff --name-only HEAD 2>/dev/null | wc -l | tr -d ' ')
[ "$git_dirty" = "0" ] && git_dirty=""

# Unpushed commits
git_unpushed=$(git --no-optional-locks rev-list --count @{u}..HEAD 2>/dev/null)
[ "$git_unpushed" = "0" ] && git_unpushed=""

# Context color based on usage
ctx_color="$C_CTX_OK"
if [ -n "$used_pct" ]; then
  if [ "$used_pct" -ge 80 ]; then
    ctx_color="$C_CTX_CRIT"
  elif [ "$used_pct" -ge 60 ]; then
    ctx_color="$C_CTX_WARN"
  fi
fi

# Jira autopilot — walk up from project_dir to find .claude/jira-session.json
jira_label=""
jira_root=""
_dir="$project_dir"
while [[ "$_dir" != "/" ]]; do
  if [[ -f "$_dir/.claude/jira-session.json" ]]; then
    jira_root="$_dir"
    break
  fi
  _dir="$(dirname "$_dir")"
done
jira_session="$jira_root/.claude/jira-session.json"
if [ ! -f "$jira_session" ]; then
  # Try project plugin.json first, fall back to latest in global cache
  _plugin_ver=$(jq -r '.version // empty' "$jira_root/plugins/jira-autopilot/.claude-plugin/plugin.json" 2>/dev/null)
  if [ -z "$_plugin_ver" ]; then
    _cache="$HOME/.claude/plugins/cache/moonsite-claude-extensions/jira-autopilot"
    _plugin_ver=$(ls "$_cache" 2>/dev/null | sort -V | tail -1)
  fi
  _ver_suffix=""
  [ -n "$_plugin_ver" ] && _ver_suffix=" ${C_ICON}v${_plugin_ver}${RESET}"
  jira_label="${C_ICON}⏱${RESET} ${C_JIRA_UNSET}Jira Autopilot not set${RESET}${_ver_suffix}"
elif [ -f "$jira_session" ]; then
  jira_issue=$(jq -r '.currentIssue // empty' "$jira_session" 2>/dev/null)
  jira_autonomy=$(jq -r '.autonomyLevel // "C"' "$jira_session" 2>/dev/null)

  # Sum active issue time: tracked seconds + elapsed since startTime for current issue
  jira_minutes=""
  if [ -n "$jira_issue" ]; then
    jira_minutes=$(python3 - "$jira_session" "$jira_issue" <<'PYEOF'
import json, sys, time
path, issue = sys.argv[1], sys.argv[2]
s = json.load(open(path))
now = int(time.time())
total = 0
for key, data in s.get("activeIssues", {}).items():
    start = data.get("startTime", 0)
    if start > 0:
        total += now - start
# Convert to minutes
print(total // 60)
PYEOF
)
  fi

  # Pending worklogs count
  pending=$(jq '[.pendingWorklogs[]? | select(.status == "pending")] | length' "$jira_session" 2>/dev/null)

  # Planning mode active
  is_planning=$(jq -r '.activePlanning // empty | if . then "1" else "" end' "$jira_session" 2>/dev/null)

  # Build label: "PROJ-42 · 37m" or with pending "PROJ-42 · 37m · 2 pending"
  # Plugin version from plugin.json
  plugin_version=$(jq -r '.version // empty' "$jira_root/plugins/jira-autopilot/.claude-plugin/plugin.json" 2>/dev/null)

  if [ -n "$jira_issue" ]; then
    version_suffix=""
    [ -n "$plugin_version" ] && version_suffix=" ${C_ICON}v${plugin_version}${RESET}"
    jira_label="${C_ICON}⏱${RESET} ${C_JIRA}${jira_issue}${RESET}${version_suffix}"
    if [ -n "$jira_minutes" ] && [ "$jira_minutes" -gt 0 ] 2>/dev/null; then
      if [ "$jira_minutes" -ge 60 ]; then
        h=$((jira_minutes / 60)); m=$((jira_minutes % 60))
        time_str="${h}h${m}m"
      else
        time_str="${jira_minutes}m"
      fi
      jira_label="${jira_label} ${C_JIRA_TIME}${time_str}${RESET}"
    fi
    if [ -n "$pending" ] && [ "$pending" -gt 0 ] 2>/dev/null; then
      jira_label="${jira_label} ${C_JIRA_WARN}(${pending} pending)${RESET}"
    fi
  elif [ -n "$plugin_version" ]; then
    # No active issue but plugin is configured — show version only
    jira_label="${C_ICON}⏱${RESET} ${C_ICON}jira-autopilot v${plugin_version}${RESET}"
  fi
fi

# Cost formatting
cost_label=""
if [ -n "$total_cost" ] && [ "$total_cost" != "0" ]; then
  cost_label=$(printf "\$%.2f" "$total_cost")
fi

# Assemble
parts=()
parts+=("${C_ICON}▸${RESET} ${C_FOLDER}${folder_name}${RESET}")

if [ -n "$git_branch" ]; then
  parts+=("${C_ICON}⊕${RESET} ${C_REPO}${repo_name}${RESET}")
  parts+=("${C_ICON}⎇${RESET} ${C_BRANCH}${git_branch}${RESET}")
fi

if [ -n "$git_dirty" ]; then
  parts+=("${C_ICON}±${RESET}${C_DIRTY}${git_dirty}${RESET}")
fi

if [ -n "$git_unpushed" ]; then
  parts+=("${C_ICON}↑${RESET}${C_UNPUSHED}${git_unpushed}${RESET}")
fi

if [ -n "$jira_label" ]; then
  parts+=("$jira_label")
fi

if [ -n "$is_planning" ]; then
  parts+=("${C_ICON}~${RESET} ${C_PLANNING}planning${RESET}")
fi

parts+=("${C_ICON}◈${RESET} ${C_MODEL}${model_label}${RESET}")

if [ -n "$remaining_pct" ]; then
  parts+=("${C_ICON}⊙${RESET} ${ctx_color}${remaining_pct}% ctx${RESET}")
fi

if [ -n "$cost_label" ]; then
  parts+=("${C_ICON}★${RESET} ${C_COST}saved ${cost_label}${RESET}")
fi

# Print
result=""
for part in "${parts[@]}"; do
  [ -z "$result" ] && result="$part" || result="${result}${SEP}${part}"
done
echo -e "$result"
