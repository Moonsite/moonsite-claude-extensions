#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
ROOT="$(find_project_root)"
is_enabled "$ROOT" || exit 0
python3 "$SCRIPT_DIR/jira_core.py" pre-tool-use "$ROOT"
