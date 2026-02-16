---
name: status
description: Show current Jira task and elapsed time
allowed-tools: Bash, Read
---

# Jira Task Status

Show the current task tracking status.

## Steps

1. **Read** `<project-root>/.claude/current-task.json`
   - If it doesn't exist, say "No active task. Use /jira:start to begin tracking."

2. **Calculate elapsed time**: run `date +%s`, subtract `startTime`

3. **Display**:
   ```
   🎯 Current Task
   ├─ Issue:   <issueKey>
   ├─ Summary: <summary>
   ├─ Branch:  <branch>
   ├─ Started: <human readable time>
   └─ Elapsed: <X>h <Y>m
   ```

4. **Read config** from `<project-root>/.claude/jira-tracker.json` and show project key.
