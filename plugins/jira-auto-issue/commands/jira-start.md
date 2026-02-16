---
name: jira-start
description: Start tracking a Jira task (create new or link existing)
argument: Issue key (e.g. PROJ-42) or summary text to create a new issue
allowed-tools: Bash, Write, Read, ToolSearch, mcp__atlassian__createJiraIssue, mcp__atlassian__getJiraIssue
---

# Start Jira Task

You are starting work on a Jira task. Read the project config from `<project-root>/.claude/jira-tracker.json` first.

## Parse the argument

- If argument matches `<PROJECT_KEY>-\d+` pattern → **link to existing issue**
- Otherwise → **create a new issue** with the argument as summary

## Link to Existing Issue

1. Try `mcp__atlassian__getJiraIssue` first (load tool via ToolSearch). If MCP fails, fall back to REST:
   ```bash
   source <plugin-root>/hooks-handlers/jira-rest.sh
   jira_load_creds "<project-root>"
   jira_get_issue "<ISSUE_KEY>"
   ```
2. Record start time: run `date +%s`
3. Update session state in `<project-root>/.claude/jira-session.json`:
   - Add issue to `activeIssues` with summary, startTime, totalSeconds: 0
   - Set `currentIssue` to this key
4. If not on a matching feature branch, create one:
   ```bash
   git checkout -b feature/<KEY>-<slug>
   ```
5. Display: "Started tracking **<KEY>**: <summary>. Timer running."

## Create New Issue

1. Try `mcp__atlassian__createJiraIssue` first (load via ToolSearch). If MCP fails, fall back to REST:
   ```bash
   source <plugin-root>/hooks-handlers/jira-rest.sh
   jira_load_creds "<project-root>"
   jira_create_issue "<PROJECT_KEY>" "<summary>"
   ```
2. Follow steps 2-5 from "Link to Existing Issue" above with the newly created key

## If a task is already active

Check `currentIssue` in `<project-root>/.claude/jira-session.json`. If set, ask the user if they want to:
- Switch to the new issue (pause timer on current)
- Stop the current task first (log time) before starting new one
