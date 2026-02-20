#!/bin/bash
# jira-status: print session status in one shot, no Claude tool calls needed.
# Usage: bash jira-status.sh [project-root]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

ROOT="${1:-$(find_project_root 2>/dev/null || echo ".")}"
SESSION_FILE="$ROOT/.claude/jira-session.json"
CONFIG_FILE="$ROOT/.claude/jira-autopilot.json"

if [[ ! -f "$SESSION_FILE" ]]; then
  echo "No active session. Use /jira-start to begin tracking."
  exit 0
fi

python3 - "$SESSION_FILE" "$CONFIG_FILE" <<'PYEOF'
import json, sys, time, os

sf, cf = sys.argv[1], sys.argv[2]
now = int(time.time())

with open(sf) as f:
    s = json.load(f)

cfg = {}
if os.path.exists(cf):
    with open(cf) as f:
        cfg = json.load(f)

autonomy_desc = {
    "C": "Cautious — asks before every action",
    "B": "Balanced — shows summaries, auto-proceeds",
    "A": "Autonomous — acts silently",
}

autonomy = s.get("autonomyLevel", cfg.get("autonomyLevel", "C"))
accuracy = s.get("accuracy", cfg.get("accuracy", 5))
current = s.get("currentIssue") or "none"

print("Jira Autopilot Status")
print("════════════════════════════════════════")
print(f"Project:  {cfg.get('projectKey', '—')}")
print(f"Autonomy: {autonomy} ({autonomy_desc.get(autonomy, '—')})")
print(f"Accuracy: {accuracy}/10  rounding={cfg.get('timeRounding', 15)}m  idle={cfg.get('idleThreshold', 15)}m")
print(f"Language: {cfg.get('logLanguage', '—')}")
print(f"Debug:    {'enabled' if cfg.get('debugLog') else 'disabled'}")
print(f"\nCurrent issue: {current}")

# Per-issue elapsed
active = s.get("activeIssues", {})
if active:
    print("\nActive Issues:")
    items = list(active.items())
    for i, (key, data) in enumerate(items):
        connector = "└─" if i == len(items) - 1 else "├─"
        sub       = "   " if i == len(items) - 1 else "│  "
        start = data.get("startTime", 0)
        total = data.get("totalSeconds", 0)
        elapsed = total + (now - start) if start and not data.get("paused") else total
        h, m = elapsed // 3600, (elapsed % 3600) // 60
        label = " (current)" if key == current else (" (paused)" if data.get("paused") else "")
        print(f"{connector} {key}{label}")
        print(f"{sub}├─ Summary:  {data.get('summary', '—')}")
        print(f"{sub}└─ Elapsed:  {h}h {m}m")

# Work chunks
chunks_by_issue = {}
total_acts = {}
for c in s.get("workChunks", []):
    k = c.get("issueKey") or "unlinked"
    chunks_by_issue[k] = chunks_by_issue.get(k, 0) + 1
    total_acts[k] = total_acts.get(k, 0) + len(c.get("activities", []))

if chunks_by_issue:
    print("\nWork chunks:")
    for k, n in chunks_by_issue.items():
        acts = total_acts.get(k, 0)
        print(f"  {k}: {n} chunk(s), {acts} tool calls")

# Pending worklogs
pending = [w for w in s.get("pendingWorklogs", []) if w.get("status") == "pending"]
print(f"\nPending worklogs: {len(pending)}", end="")
if pending:
    print("  ← use /jira-approve to review")
else:
    print()

print(f"Activity buffer:  {len(s.get('activityBuffer', []))} items")
print("\nTips:")
print("  /jira-start <KEY>  switch issue    /jira-stop    log & stop")
print("  /jira-approve      review pending  /jira-summary today's summary")
PYEOF
