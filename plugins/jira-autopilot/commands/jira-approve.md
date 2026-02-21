---
name: jira-approve
description: Review and approve pending work items as Jira issues
allowed-tools: Bash, Write, Read, ToolSearch, mcp__atlassian__createJiraIssue, mcp__atlassian__getJiraIssue
---

# Approve Pending Work Items

Review unattributed work chunks and deferred worklogs, then create or link Jira issues for them.

## Steps

1. **Read** `<project-root>/.claude/jira-session.json`
   - Check for `pendingIssues` with status `awaiting_approval` AND `pendingWorklogs` with status `deferred` or `unattributed`.
   - If none exist, tell user "No pending work items to review."

2. **For each pending issue**, show:
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

7. **For each pending/deferred worklog** (`status == "pending"` or `status == "deferred"`):

   First, get the configured worklog language:
   ```bash
   python3 <plugin-root>/hooks-handlers/jira_core.py build-worklog "<project-root>" "<issueKey>"
   ```
   Read the `logLanguage` field from the output.

   If the existing `summary` is a raw file list (e.g. `"auth.ts, middleware.ts +2"`) rather than a human-readable sentence, **enrich it** — write a 1-3 sentence description of the work in `logLanguage` before presenting it to the user. Use the `rawFacts` from the pending worklog entry if available.

   Then show:
   ```
   Worklog #<n>
   Issue: <issueKey>
   Time: <rounded time>
   Summary: "<enriched summary in logLanguage>"
   ```
   Ask: Approve (post now) / Edit / Redirect to different issue / Drop

   On Approve — post using REST:
   ```bash
   python3 <plugin-root>/hooks-handlers/jira_core.py add-worklog \
     "<project-root>" "<issueKey>" <seconds> "<enriched_summary>"
   ```
   Mark entry status as `posted`.

8. **Unattributed Work**

   For `pendingWorklogs` entries with `status: "unattributed"` (issueKey is null):

   Show:
   ```
   Unattributed Work #<n>
   Time: <rounded time>  
   Files: <list from rawFacts.files, if any>
   Activities: <rawFacts.activityCount> tool calls
   ```

   Ask the user:
   ```
   What should I do with this time?
     1. Create a new Jira issue for this work
     2. Log to existing issue (you provide key)
     3. Drop entirely
   ```

   **On "Create new issue"**:
   - Run: `python3 <plugin-root>/hooks-handlers/jira_core.py auto-create-issue "<project-root>" "<summary_hint_from_files>"`
   - Extract the new key from the result
   - Post worklog to the new key using:
     ```bash
     python3 <plugin-root>/hooks-handlers/jira_core.py add-worklog \
       "<project-root>" "<newKey>" <seconds> "<summary from rawFacts>"
     ```
   - Update entry status to `"posted"`

   **On "Log to existing"**:
   - Ask user for the issue key
   - Verify it exists (via MCP or REST)
   - Post worklog to that key
   - Update entry status to `"posted"`

   **On "Drop"**:
   - Remove the entry or set status to `"dropped"`

9. **Update** `jira-session.json` with all changes.

10. **Show summary** of actions taken.
