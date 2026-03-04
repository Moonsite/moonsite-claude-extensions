#!/bin/bash
# PostToolUse hook: auto-generate HTML when any markdown file is created/updated
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Read hook input from stdin
INPUT=$(cat)

# Only act on Write or Edit tools
TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || true)
[[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]] && exit 0

# Get the file path from tool input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
inp = data.get('tool_input', {})
print(inp.get('file_path', ''))
" 2>/dev/null || true)

[[ -z "$FILE_PATH" ]] && exit 0

# Check if it's a .md file
echo "$FILE_PATH" | grep -qE '\.md$' || exit 0

# Skip files inside the plugin itself
echo "$FILE_PATH" | grep -q 'md-html-docs/' && exit 0

# Find project root (walk up looking for .git)
find_project_root() {
  local dir="${CLAUDE_PROJECT_DIR:-$PWD}"
  while [[ "$dir" != "/" ]]; do
    if [[ -d "$dir/.git" || -f "$dir/.git" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

ROOT=$(find_project_root) || exit 0
CONFIG_FILE="$ROOT/.claude/md-html-docs.json"

# Check if explicitly disabled
if [[ -f "$CONFIG_FILE" ]]; then
  ENABLED=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('enabled',''))" 2>/dev/null || true)
  [[ "$ENABLED" == "false" || "$ENABLED" == "False" ]] && exit 0
fi

# First run: config doesn't exist yet — ask user
if [[ ! -f "$CONFIG_FILE" ]]; then
  mkdir -p "$ROOT/.claude"
  echo '{"enabled": "pending"}' > "$CONFIG_FILE"
  cat <<'PROMPT'

---
**md-html-docs plugin detected a markdown file update.**

I can automatically generate HTML whenever you create or edit `.md` files.

To enable: run `/md-html-docs enable`
To disable: run `/md-html-docs disable`
---

PROMPT
  exit 0
fi

# If still pending, skip
ENABLED=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('enabled',''))" 2>/dev/null || true)
[[ "$ENABLED" != "true" && "$ENABLED" != "True" ]] && exit 0

# --- Auto-run converter ---
[[ ! -f "$FILE_PATH" ]] && exit 0

python3 "$PLUGIN_ROOT/convert.py" "$FILE_PATH" 2>&1 | tail -3

# Regenerate parent folder index
PARENT_DIR=$(dirname "$FILE_PATH")
python3 "$PLUGIN_ROOT/convert.py" --index "$PARENT_DIR" 2>&1 | tail -1

echo "md-html-docs: HTML generated for $(basename "$FILE_PATH")."
