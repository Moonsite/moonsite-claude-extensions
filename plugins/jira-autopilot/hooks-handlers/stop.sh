#!/bin/bash
# Stop hook: drain activity buffer into work chunks, detect idle/context switches
# Thin wrapper — all logic lives in jira_core.py
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT=$(find_project_root) || exit 0
python3 "$SCRIPT_DIR/jira_core.py" drain-buffer "$ROOT"
