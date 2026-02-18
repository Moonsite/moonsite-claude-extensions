---
name: jira-stop
description: Stop tracking current task and log time to Jira
allowed-tools: Bash, Read, Write, ToolSearch, mcp__atlassian__addWorklogToJiraIssue
---

# Stop Jira Task

You are stopping work on the current Jira task and logging time.

## Steps

1. **Read** `<project-root>/.claude/jira-session.json`
   - If it doesn't exist or `currentIssue` is null, tell the user "No active task. Use /jira-start to begin tracking."

2. **Calculate elapsed time** for the current issue:
   - Get current issue from `activeIssues[currentIssue]`
   - Run `date +%s` to get current timestamp
   - Calculate: `totalSeconds + (now - startTime)`
   - Convert to minutes

3. **Round up** to nearest increment from `timeRounding` in config (default 15):
   | Elapsed | Log as |
   |---------|--------|
   | 1-15m   | `15m`  |
   | 16-30m  | `30m`  |
   | 31-45m  | `45m`  |
   | 46-60m  | `1h`   |
   | 61-90m  | `1h 30m` |
   | 91-120m | `2h`   |

4. **Log time** — try MCP first (`mcp__atlassian__addWorklogToJiraIssue` via ToolSearch), fall back to REST:
   ```bash
   source <plugin-root>/hooks-handlers/jira-rest.sh
   jira_load_creds "<project-root>"
   jira_log_time "<ISSUE_KEY>" <total_seconds>
   ```

5. **Post work summary** as comment if work chunks exist for this issue:
   - Gather `workChunks` associated with this issue from session state
   - Build a summary of files changed and activities performed
   - Post via REST: `jira_add_comment "<ISSUE_KEY>" "<summary>"`

6. **Update session state**: remove issue from `activeIssues`, set `currentIssue` to null

7. **Display summary**:
   ```
   Logged <time> to <ISSUE_KEY>: <summary>
   Total elapsed: <actual_minutes>m → logged as <rounded_time>
   ```
