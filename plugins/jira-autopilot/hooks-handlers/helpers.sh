#!/usr/bin/env bash
# helpers.sh — minimal shell utilities for hook entry points

find_project_root() {
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
    echo "$CLAUDE_PROJECT_DIR"
    return
  fi
  local dir="$PWD"
  while [[ "$dir" != "/" ]]; do
    [[ -d "$dir/.git" ]] && { echo "$dir"; return; }
    dir="$(dirname "$dir")"
  done
  echo "$PWD"
}

json_get() {
  python3 -c "import json,sys; print(json.load(open('$1')).get('$2',''))" 2>/dev/null || echo ""
}

is_enabled() {
  local root="$1"
  local cfg="$root/.claude/jira-autopilot.json"
  [[ -f "$cfg" ]] && [[ "$(json_get "$cfg" enabled)" != "false" ]]
}
