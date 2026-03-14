#!/bin/bash
# jira-autopilot statusline script
#
# Setup: point Claude Code's statusLine command at this file via /jira-setup,
# or manually add to ~/.claude/settings.json:
#
#   "statusLine": {
#     "type": "command",
#     "command": "bash -c 'exec bash \"$(ls -d ~/.claude/plugins/cache/moonsite-claude-extensions/jira-autopilot/*/hooks-handlers/statusline-command.sh 2>/dev/null | sort -V | tail -1)\"'"
#   }
#
# Shows: folder · repo · branch · ±dirty · ↑unpushed · ⏱ ISSUE time · [auto] · (N pending) · model · ctx · cost
# Falls back to plain text if jq is not available.

# Do NOT use set -e — individual segment failures must not abort the entire statusline
set -uo pipefail

input=$(cat)

# ── jq availability check ────────────────────────────────
if ! command -v jq &>/dev/null; then
  # Plain fallback: extract what we can without jq
  cwd=$(echo "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null || echo "")
  folder_name="$(basename "${cwd:-$PWD}")"
  echo "$folder_name | statusline requires jq — brew install jq"
  exit 0
fi

# ── Colors ────────────────────────────────────────────────
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

# ── Parse stdin JSON ──────────────────────────────────────
cwd=$(echo "$input" | jq -r '.cwd // empty' 2>/dev/null)
model_name=$(echo "$input" | jq -r '.model.display_name // empty' 2>/dev/null)
output_style=$(echo "$input" | jq -r '.output_style.name // "default"' 2>/dev/null)
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty' 2>/dev/null)
remaining_pct=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty' 2>/dev/null)
total_cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty' 2>/dev/null)

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

# ── Git info ──────────────────────────────────────────────
project_dir="${cwd:-${CLAUDE_PROJECT_DIR:-$PWD}}"
folder_name="$(basename "$project_dir")"
cd "$project_dir" 2>/dev/null || true
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

# ── Context color ─────────────────────────────────────────
ctx_color="$C_CTX_OK"
if [ -n "$used_pct" ]; then
  if [ "$used_pct" -ge 80 ] 2>/dev/null; then
    ctx_color="$C_CTX_CRIT"
  elif [ "$used_pct" -ge 60 ] 2>/dev/null; then
    ctx_color="$C_CTX_WARN"
  fi
fi

# ── Jira autopilot ────────────────────────────────────────
# Walk up from project_dir to find session or config
jira_label=""
jira_root=""
jira_config_root=""
_dir="$project_dir"
while [[ "$_dir" != "/" ]]; do
  if [[ -f "$_dir/.claude/jira-session.json" ]]; then
    jira_root="$_dir"
    break
  fi
  if [[ -z "$jira_config_root" && -f "$_dir/.claude/jira-autopilot.json" ]]; then
    jira_config_root="$_dir"
  fi
  _dir="$(dirname "$_dir")"
done
jira_session="${jira_root:+$jira_root/.claude/jira-session.json}"

# Version helper: grep only semver directories
_plugin_version_from_cache() {
  local _cache="$HOME/.claude/plugins/cache/moonsite-claude-extensions/jira-autopilot"
  ls "$_cache" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1
}

if [ -z "$jira_session" ] || [ ! -f "$jira_session" ]; then
  # No session file found
  _plugin_ver=""
  if [ -n "$jira_root" ]; then
    _plugin_ver=$(jq -r '.version // empty' "$jira_root/plugins/jira-autopilot/.claude-plugin/plugin.json" 2>/dev/null)
  fi
  [ -z "$_plugin_ver" ] && _plugin_ver=$(_plugin_version_from_cache)
  _ver_suffix=""
  [ -n "$_plugin_ver" ] && _ver_suffix=" ${C_ICON}v${_plugin_ver}${RESET}"

  if [ -n "$jira_config_root" ]; then
    # Configured but no session yet
    _proj_key=$(jq -r '.projectKey // "?"' "$jira_config_root/.claude/jira-autopilot.json" 2>/dev/null)
    jira_label="${C_ICON}⏱${RESET} ${C_ICON}${_proj_key} ready${RESET}${_ver_suffix}"
  else
    jira_label="${C_ICON}⏱${RESET} ${C_JIRA_UNSET}Jira Autopilot not set${RESET}${_ver_suffix}"
  fi
elif [ -f "$jira_session" ]; then
  jira_issue=$(jq -r '.currentIssue // empty' "$jira_session" 2>/dev/null)
  jira_autonomy=$(jq -r '.autonomyLevel // "C"' "$jira_session" 2>/dev/null)

  # Calculate time using pure bash arithmetic (no python3)
  jira_minutes=""
  if [ -n "$jira_issue" ]; then
    start_time=$(jq -r ".activeIssues[\"$jira_issue\"].startTime // 0" "$jira_session" 2>/dev/null)
    now=$(date +%s 2>/dev/null)
    if [ -n "$start_time" ] && [ "$start_time" -gt 0 ] 2>/dev/null && [ -n "$now" ]; then
      jira_minutes=$(( (now - start_time) / 60 ))
    fi
  fi

  # Pending worklogs count
  pending=$(jq '[.pendingWorklogs[]? | select(.status == "pending")] | length' "$jira_session" 2>/dev/null)

  # Planning mode active
  is_planning=$(jq -r '.activePlanning // empty | if . then "1" else "" end' "$jira_session" 2>/dev/null)

  # Plugin version
  plugin_version=$(jq -r '.version // empty' "$jira_root/plugins/jira-autopilot/.claude-plugin/plugin.json" 2>/dev/null)
  [ -z "$plugin_version" ] && plugin_version=$(_plugin_version_from_cache)

  if [ -n "$jira_issue" ]; then
    version_suffix=""
    [ -n "$plugin_version" ] && version_suffix=" ${C_ICON}v${plugin_version}${RESET}"
    jira_label="${C_ICON}⏱${RESET} ${C_JIRA}${jira_issue}${RESET}${version_suffix}"

    # Time tracked
    if [ -n "$jira_minutes" ] && [ "$jira_minutes" -gt 0 ] 2>/dev/null; then
      if [ "$jira_minutes" -ge 60 ]; then
        h=$((jira_minutes / 60)); m=$((jira_minutes % 60))
        time_str="${h}h${m}m"
      else
        time_str="${jira_minutes}m"
      fi
      jira_label="${jira_label} ${C_JIRA_TIME}${time_str}${RESET}"
    fi

    # Autonomy mode indicator
    if [ "$jira_autonomy" = "A" ]; then
      jira_label="${jira_label} ${C_ICON}[auto]${RESET}"
    fi

    # Issue count when > 1 active
    issue_count=$(jq '.activeIssues | length' "$jira_session" 2>/dev/null)
    if [ -n "$issue_count" ] && [ "$issue_count" -gt 1 ] 2>/dev/null; then
      jira_label="${jira_label} ${C_ICON}(${issue_count})${RESET}"
    fi

    # Pending worklogs
    if [ -n "$pending" ] && [ "$pending" -gt 0 ] 2>/dev/null; then
      jira_label="${jira_label} ${C_JIRA_WARN}(${pending} pending)${RESET}"
    fi
  elif [ -n "$plugin_version" ]; then
    jira_label="${C_ICON}⏱${RESET} ${C_ICON}jira-autopilot v${plugin_version}${RESET}"
  fi
fi

# ── Cost formatting ───────────────────────────────────────
cost_label=""
if [ -n "$total_cost" ] && [ "$total_cost" != "0" ]; then
  cost_label=$(printf "\$%.2f" "$total_cost" 2>/dev/null)
fi

# ── Assemble segments ────────────────────────────────────
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

if [ -n "${is_planning:-}" ]; then
  parts+=("${C_ICON}~${RESET} ${C_PLANNING}planning${RESET}")
fi

parts+=("${C_ICON}◈${RESET} ${C_MODEL}${model_label}${RESET}")

if [ -n "$remaining_pct" ]; then
  parts+=("${C_ICON}⊙${RESET} ${ctx_color}${remaining_pct}% ctx${RESET}")
fi

if [ -n "$cost_label" ]; then
  parts+=("${C_ICON}★${RESET} ${C_COST}${cost_label}${RESET}")
fi

# ── Output ────────────────────────────────────────────────
result=""
for part in "${parts[@]}"; do
  [ -z "$result" ] && result="$part" || result="${result}${SEP}${part}"
done
echo -e "$result"
