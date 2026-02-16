---
name: jira-approve
description: Review and approve pending work items as Jira issues
allowed-tools: Bash, Write, Read, ToolSearch, mcp__atlassian__createJiraIssue, mcp__atlassian__getJiraIssue
---

# Approve Pending Work Items

Review unattributed work chunks and create or link Jira issues for them.

## Steps

1. **Read** `<project-root>/.claude/jira-session.json`
   - If no `pendingIssues` with status `awaiting_approval`, tell user "No pending work items to review."

2. **For each pending item**, show:
   ```
   Pending Work #<n>
   Suggested summary: <suggestedSummary>
   Files changed: <list from associated chunks>
   Activities: <count> tool calls
   ```

3. **Ask the user** for each item — what to do:
   - **Approve** — create a new Jira issue with the suggested (or edited) summary
   - **Link** — associate with an existing issue key (user provides key)
   - **Skip** — discard this pending item

4. **On Approve**:
   - Read config for `projectKey` and `cloudId`
   - Try MCP `mcp__atlassian__createJiraIssue` first (load via ToolSearch). If MCP fails, fall back to REST:
     ```bash
     source <plugin-root>/hooks-handlers/jira-rest.sh
     jira_load_creds "<project-root>"
     jira_create_issue "<PROJECT_KEY>" "<summary>" "<description>"
     ```
   - Move associated chunks to the new issue key
   - Set as `currentIssue` if user confirms
   - Update pending item status to `approved`

5. **On Link**:
   - Verify the issue exists (via MCP or REST `jira_get_issue`)
   - Move associated chunks to that issue key
   - Update pending item status to `linked`

6. **On Skip**:
   - Update pending item status to `skipped`

7. **Update** `jira-session.json` with all changes.

8. **Show summary** of actions taken.
