---
name: start
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

1. Use `mcp__atlassian__getJiraIssue` to fetch the issue details (load tool via ToolSearch first)
2. Record start time: run `date +%s`
3. Write `<project-root>/.claude/current-task.json`:
```json
{
  "issueKey": "<KEY>",
  "summary": "<issue summary from Jira>",
  "startTime": <unix_timestamp>,
  "branch": "<current_branch>"
}
```
4. If not on a matching feature branch, create one:
   ```bash
   git checkout -b feature/<KEY>-<slug>
   ```
5. Display: "Started tracking **<KEY>**: <summary>. Timer running."

## Create New Issue

1. Use `mcp__atlassian__createJiraIssue` to create a Task with the given summary (load tool via ToolSearch first)
   - Use `cloudId` and `projectKey` from config
   - `issueTypeName`: "Task"
   - `summary`: the argument text
2. Follow steps 2-5 from "Link to Existing Issue" above with the newly created key

## If a task is already active

Check if `<project-root>/.claude/current-task.json` exists. If so, warn the user and ask if they want to stop the current task first (log time) before starting a new one.
