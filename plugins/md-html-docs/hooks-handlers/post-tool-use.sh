#!/bin/bash
# PostToolUse hook: auto-generate HTML when markdown files are created/updated in docs/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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

# Check if it's a .md file inside a docs/ folder
echo "$FILE_PATH" | grep -qE '/docs/.*\.md$' || exit 0

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
  # Create config as "pending" so we only ask once
  echo '{"enabled": "pending"}' > "$CONFIG_FILE"

  # Output message to user via stdout (hook feedback)
  cat <<'PROMPT'

---
**md-html-docs plugin detected a markdown file update in docs/.**

I can automatically generate HTML and update indexes whenever you create or edit markdown files in `docs/`.

To enable: run `/md-html-docs enable`
To disable: run `/md-html-docs disable`

Or edit `.claude/md-html-docs.json` and set `"enabled": true` or `"enabled": false`.

Until you decide, I won't run automatically.
---

PROMPT
  exit 0
fi

# If still pending (user hasn't decided), skip
ENABLED=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('enabled',''))" 2>/dev/null || true)
[[ "$ENABLED" != "true" && "$ENABLED" != "True" ]] && exit 0

# --- Auto-run: detect doc type and run converter ---

# Determine which docs subfolder this file belongs to
DOC_TYPE=$(echo "$FILE_PATH" | python3 -c "
import sys, re
path = sys.stdin.readline().strip()
m = re.search(r'/docs/([^/]+)/', path)
print(m.group(1) if m else '')
" 2>/dev/null || true)

[[ -z "$DOC_TYPE" ]] && exit 0

# Map doc type to converter script
CONVERTER=""
case "$DOC_TYPE" in
  spec)        CONVERTER="docs/spec/_convert.py" ;;
  guides)      CONVERTER="docs/guides/_convert.py" ;;
  code-review) CONVERTER="docs/code-review/_convert_report.py" ;;
  plans)       exit 0 ;; # Plans don't need HTML generation
  *)           exit 0 ;; # Unknown doc type, skip
esac

# Check converter exists
if [[ ! -f "$ROOT/$CONVERTER" ]]; then
  echo "md-html-docs: converter not found at $CONVERTER — skipping HTML generation."
  exit 0
fi

# Run the converter
cd "$ROOT"
python3 "$CONVERTER" 2>&1 | tail -3

echo "md-html-docs: HTML generated for $DOC_TYPE (from $(basename "$FILE_PATH"))."
