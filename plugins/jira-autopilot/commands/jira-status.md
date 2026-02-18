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

2. **Read config** from `<project-root>/.claude/jira-autopilot.json`.

3. **For each issue in `activeIssues`**, calculate elapsed time:
   - `totalSeconds + (now - startTime)` if not paused
   - `totalSeconds` if paused

4. **Count work chunks and activities** per issue from `workChunks` array.

5. **Display**:
   ```
   Jira Autopilot Status
   ════════════════════════════════════════

   Project: <projectKey>
   Autonomy: <level> (<description>)
   Accuracy: <value>/10 (rounding: <timeRounding>m, idle: <idleThreshold>m)
   Debug log: <enabled|disabled>

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

   Pending worklogs: <N> (use /jira-stop or /jira-approve to review)
   Pending (unlinked): <N> work chunks
   Activity buffer: <N> items
   ```

6. **Autonomy level descriptions** for the display:
   - C: "Cautious — asks before every action"
   - B: "Balanced — shows summaries, auto-proceeds"
   - A: "Autonomous — acts silently"

7. **Show tips**:
   - `/jira-start <KEY>` to switch to a different issue
   - `/jira-stop` to log time and stop tracking
   - `/jira-approve` to review pending work
   - `/jira-summary` for today's full summary
