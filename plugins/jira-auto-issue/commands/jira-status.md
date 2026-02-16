---
name: jira-status
description: Show all active Jira tasks with time breakdown
allowed-tools: Bash, Read
---

# Jira Task Status

Show the current session tracking status across all active issues.

## Steps

1. **Read** `<project-root>/.claude/jira-session.json`
   - If it doesn't exist, say "No active session. Use /jira-start to begin tracking."

2. **For each issue in `activeIssues`**, calculate elapsed time:
   - `totalSeconds + (now - startTime)` if not paused
   - `totalSeconds` if paused

3. **Count work chunks and activities** per issue from `workChunks` array.

4. **Display**:
   ```
   Jira Session Status
   ════════════════════════════════════════

   Current issue: <currentIssue or "none">

   Active Issues:
   ├─ <KEY> (current)
   │  ├─ Summary: <summary>
   │  ├─ Elapsed: <X>h <Y>m
   │  ├─ Activities: <N> tool calls
   │  └─ Files: <file list>
   ├─ <KEY2> (paused)
   │  ├─ Summary: <summary>
   │  └─ Elapsed: <X>h <Y>m
   └─ Total tracked: <total time>

   Pending (unlinked): <N> work chunks
   Activity buffer: <N> items
   ```

5. **Read config** from `<project-root>/.claude/jira-tracker.json` and show project key + time rounding setting.

6. **Show tips**:
   - `/jira-start <KEY>` to switch to a different issue
   - `/jira-stop` to log time and stop tracking
   - `/jira-approve` to review pending work
   - `/jira-summary` for today's full summary
