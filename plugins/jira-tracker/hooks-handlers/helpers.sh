#!/bin/bash
# Shared utilities for jira-tracker hooks

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

# Get current task file path
task_file() {
  echo "$1/.claude/current-task.json"
}
