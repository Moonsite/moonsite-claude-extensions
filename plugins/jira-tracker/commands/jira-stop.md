---
name: stop
description: Stop tracking current task and log time to Jira
allowed-tools: Bash, Read, Write, ToolSearch, mcp__atlassian__addWorklogToJiraIssue
---

# Stop Jira Task

You are stopping work on the current Jira task and logging time.

## Steps

1. **Read** `<project-root>/.claude/current-task.json`
   - If it doesn't exist, tell the user "No active task. Use /jira:start to begin tracking."

2. **Calculate elapsed time**:
   - Run `date +%s` to get current timestamp
   - Subtract `startTime` from current time
   - Convert to minutes

3. **Round up** to nearest 15 minutes (or whatever `timeRounding` is in config):
   | Elapsed | Log as |
   |---------|--------|
   | 1-15m   | `15m`  |
   | 16-30m  | `30m`  |
   | 31-45m  | `45m`  |
   | 46-60m  | `1h`   |
   | 61-90m  | `1h 30m` |
   | 91-120m | `2h`   |

4. **Log time** via `mcp__atlassian__addWorklogToJiraIssue` (load via ToolSearch first):
   - `cloudId`: from config
   - `issueIdOrKey`: from current-task.json
   - `timeSpent`: rounded value in Jira format

5. **Delete** `<project-root>/.claude/current-task.json`

6. **Display summary**:
   ```
   ✅ Logged <time> to <ISSUE_KEY>: <summary>
   Total elapsed: <actual_minutes>m → logged as <rounded_time>
   ```
