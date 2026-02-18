---
name: jira-summary
description: Show today's work summary across all sessions and Jira issues
allowed-tools: Bash, Read, ToolSearch, mcp__atlassian__addCommentToJiraIssue
---

# Jira Work Summary

Aggregate today's session data and display a formatted summary.

## Steps

1. **Read current session** from `<project-root>/.claude/jira-session.json`

2. **Read archived sessions** from `<project-root>/.claude/jira-sessions/` — filter for today's date (files starting with today's YYYYMMDD)

3. **Aggregate data** across all sessions:
   - Issues worked on (with total time per issue)
   - Files changed per issue
   - Total activities per issue
   - Pending/unattributed work chunks
   - Deferred worklogs

4. **Display formatted table**:
   ```
   Today's Work Summary
   ════════════════════════════════════════

   Issue        Time      Files   Activities
   ─────────────────────────────────────────
   PROJ-42      45m       5       23
   PROJ-43      30m       3       12
   (unlinked)   15m       2       8
   ─────────────────────────────────────────
   Total        1h 30m    10      43

   Details:
   ├─ PROJ-42: <summary>
   │  Files: file1.ts, file2.ts, ...
   ├─ PROJ-43: <summary>
   │  Files: file3.ts, ...
   └─ Unlinked work: 2 chunks awaiting /jira-approve
   ```

5. **Optionally post to Jira**: Ask the user if they want to post this summary as a comment on each issue. If yes:
   - Try MCP `mcp__atlassian__addCommentToJiraIssue` first (load via ToolSearch)
   - Fall back to REST:
     ```bash
     source <plugin-root>/hooks-handlers/jira-rest.sh
     jira_load_creds "<project-root>"
     jira_add_comment "<ISSUE_KEY>" "<summary_text>"
     ```
