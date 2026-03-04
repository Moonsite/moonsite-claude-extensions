---
name: work-status
description: Show all active Jira tasks with time breakdown
allowed-tools: Bash
---

# /work-status — Show Active Tasks

Display the current Jira Autopilot tracking status, including all active issues, time breakdown, and pending items.

## Path Resolution

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
CLI="python3 $PLUGIN_ROOT/hooks-handlers/jira_core.py"
```

---

## Step 1: Read Configuration

```bash
cat "$PROJECT_ROOT/.claude/jira-autopilot.json" 2>/dev/null
```

If no config exists, display:
```
Jira Autopilot is not configured. Run /jira-setup to get started.
```
And exit.

## Step 2: Read Session State

```bash
$CLI get-session "$PROJECT_ROOT"
```

If no session exists, display:
```
Jira Autopilot configured but no active session.
Project: {projectKey}
Autonomy: {autonomyLevel}

Run /start-work to begin tracking a task.
```
And exit.

## Step 3: Display Full Status

Run the status display command:

```bash
$CLI status "$PROJECT_ROOT"
```

If the CLI command is not available, build the display manually from the session JSON. Present a formatted status report with the following sections:

### Configuration

```
Project:   {projectKey} (or "Monitoring mode" if empty)
Autonomy:  {autonomyLevel} — {description}
Accuracy:  {accuracy}/10
Language:  {logLanguage}
Debug:     {debugLog ? "on" : "off"}
```

### Current Issue

```
Current:   {currentIssue} — {summary}
           Elapsed: {elapsed_time}
```

Where `elapsed_time` is calculated as: `totalSeconds + (now - startTime)` for unpaused issues.

Format time as `Xh Ym` (e.g. "1h 23m") or just `Ym` if under an hour.

### Active Issues Tree

If multiple issues are active, show all of them:

```
Active Issues:
  * KEY-42 — Fix login crash          [1h 23m] (current)
    KEY-43 — Add user dashboard       [0h 15m] (paused)
    KEY-44 — Update API docs          [0h 08m]
```

Mark the current issue with `*`. Show `(paused)` for paused issues.

### Work Chunks

```
Work Chunks:
  KEY-42: 3 chunks, 15 tool calls
  KEY-43: 1 chunk, 5 tool calls
  Unattributed: 2 chunks, 8 tool calls
```

### Pending Items

```
Pending:
  Worklogs: 2 pending, 1 deferred
  Issues:   1 awaiting approval
  Buffer:   12 activities
```

### Usage Tips

```
Commands:
  /start-work KEY-42     Link to existing issue
  /start-work "summary"  Create new issue
  /stop-work             Stop current task and log time
  /approve-work          Review pending worklogs and issues
  /work-summary          Today's work across all sessions
  /report-work           Generate a work report
```

---

## Error Handling

- If config file is corrupt: show an error and suggest running `/jira-setup`.
- If session file is corrupt: show config info only, note that session data is unavailable.
- Never fail silently — always show at least the configuration status.
