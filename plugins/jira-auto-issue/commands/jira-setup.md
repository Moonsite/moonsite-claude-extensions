---
name: jira-setup
description: Configure Jira tracking for this project
allowed-tools: Bash, Write, Edit, Read, AskUserQuestion, Glob
---

# Jira Auto-Issue Setup

You are configuring the jira-auto-issue plugin for this project.

## Steps

1. **Ask for project key** — this is the prefix of Jira issues, e.g. `PROJ` from `PROJ-123`. Example: "What's your Jira project key? (the prefix before the dash in issue numbers, e.g. PROJ from PROJ-123)"

2. **Ask for Jira base URL** — e.g. `https://company.atlassian.net`. Validate it looks like a URL.
   - Auto-fetch Cloud ID: run `curl -s <baseUrl>/_edge/tenant_info` and extract `cloudId` from JSON response using `python3 -c "import json,sys; print(json.load(sys.stdin).get('cloudId',''))"`.
   - If fetch fails, ask the user for cloudId manually.

3. **Ask for credentials** (email + API token):
   - Tell the user: "You'll need your Atlassian email and an API token. Create one at: https://id.atlassian.com/manage-profile/security/api-tokens"
   - Ask for email address
   - Ask for API token

4. **Test connectivity**: Run via Bash:
   ```bash
   curl -s -w "%{http_code}" -u "<email>:<token>" -H "Accept: application/json" "<baseUrl>/rest/api/3/myself"
   ```
   - If the HTTP code is 200, show the display name from the response and confirm connection works.
   - If it fails, show the error and ask the user to check their credentials. Do NOT proceed until connection works.

5. **Show defaults and confirm**:
   - Branch pattern: `^(?:feature|fix|hotfix|chore|docs)/({key}-\\d+)` (where `{key}` = project key)
   - Commit pattern: `{key}-\\d+:`
   - Time rounding: 15 minutes
   - Auto-create issues: false (ask first before creating)
   - Ask if these defaults are OK or if the user wants to change any.

6. **Write config files**:
   - `<project-root>/.claude/jira-tracker.json` (committed to repo):
     ```json
     {
       "projectKey": "<KEY>",
       "cloudId": "<CLOUD_ID>",
       "enabled": true,
       "branchPattern": "^(?:feature|fix|hotfix|chore|docs)/({key}-\\d+)",
       "commitPattern": "{key}-\\d+:",
       "timeRounding": 15,
       "autoCreate": false
     }
     ```
   - `<project-root>/.claude/jira-tracker.local.json` (gitignored, contains secrets):
     ```json
     {
       "email": "<EMAIL>",
       "apiToken": "<TOKEN>",
       "baseUrl": "<BASE_URL>"
     }
     ```

7. **Update `.gitignore`** — ensure these lines exist:
   ```
   .claude/current-task.json
   .claude/jira-session.json
   .claude/jira-sessions/
   .claude/jira-tracker.local.json
   .claude/jira-tracker.declined
   ```

8. **Remove** `.claude/jira-tracker.declined` if it exists.

9. **Confirm** setup is complete and show saved configuration summary.

## Notes
- If `.claude/jira-tracker.json` already exists, show current values and ask what to change.
- The `{key}` placeholder in patterns gets replaced with the actual project key at runtime.
- NEVER commit or display the API token in output after initial setup.
