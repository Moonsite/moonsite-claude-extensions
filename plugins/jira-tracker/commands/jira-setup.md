---
name: setup
description: Configure Jira tracking for this project
allowed-tools: Bash, Write, Edit, Read, AskUserQuestion, Glob
---

# Jira Tracker Setup

You are configuring the jira-tracker plugin for this project.

## Steps

1. **Ask the user** for these settings (provide defaults where possible):
   - Jira project key (e.g., `MYPROJ`)
   - Atlassian Cloud ID (check existing CLAUDE.md for hints)
   - Branch naming pattern (default: `^(?:feature|fix|hotfix|chore|docs)/({key}-\\d+)`)
   - Time rounding in minutes (default: `15`)
   - Enable tracking? (default: `true`)

2. **Create config file** at `<project-root>/.claude/jira-tracker.json`:
```json
{
  "projectKey": "<KEY>",
  "cloudId": "<CLOUD_ID>",
  "enabled": true,
  "branchPattern": "^(?:feature|fix|hotfix|chore|docs)/({key}-\\d+)",
  "commitPattern": "{key}-\\d+:",
  "timeRounding": 15
}
```

3. **Update `.gitignore`** — ensure these lines exist:
```
.claude/current-task.json
.claude/jira-tracker.local.json
.claude/jira-tracker.declined
```

4. **Confirm** setup is complete and show the saved configuration.

## Notes
- If `.claude/jira-tracker.json` already exists, show current values and ask what to change.
- The `{key}` placeholder in patterns gets replaced with the actual project key at runtime.
- Remove `.claude/jira-tracker.declined` if it exists (user is now configuring).
