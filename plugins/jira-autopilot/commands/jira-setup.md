---
name: jira-setup
description: Configure Jira tracking for this project
allowed-tools: Bash, Write, Edit, Read, AskUserQuestion, Glob
---

# Jira Autopilot Setup

You are configuring the jira-autopilot plugin for this project.

## Steps

1. **Auto-detect project key from git history** — Before asking the user, try to detect the project key automatically:
   - Run: `bash plugins/jira-autopilot/hooks-handlers/helpers.sh detect_project_key` (or inline the logic: scan `git log --oneline -100` and `git branch -a` for patterns matching `[A-Z]+-\d+`, extract the most common prefixes)
   - If keys are detected, present them as choices: "I found these project keys in your git history:" and list them. Let the user pick one or type a different key.
   - If no keys are detected, ask normally: "What's your Jira project key? (the prefix before the dash in issue numbers, e.g. PROJ from PROJ-123)"

2. **Check for saved global credentials** — Before asking for URL and credentials:
   - Check if `~/.claude/jira-autopilot.global.json` exists and contains `baseUrl`, `email`, `apiToken`.
   - If it does, show the saved baseUrl and email (NOT the token) and ask: "Found saved Jira credentials for **user@company.com** at **https://company.atlassian.net**. Use these? (yes/no)"
   - If the user says yes, skip steps 3-4 and reuse the saved values.
   - If the user says no, or the file doesn't exist, continue with steps 3-4 below.

3. **Ask for Jira base URL** — Ask the user to type their Jira base URL. Do NOT suggest specific URLs or provide example domain names — just ask for the URL as free text. Validate it looks like a URL starting with `https://`.
   - Auto-fetch Cloud ID: run `curl -s <baseUrl>/_edge/tenant_info` and extract `cloudId` from JSON response using `python3 -c "import json,sys; print(json.load(sys.stdin).get('cloudId',''))"`.
   - If fetch fails, ask the user for cloudId manually.

4. **Ask for credentials** (email + API token):
   - Tell the user: "You'll need your Atlassian email and an API token. Create one at: https://id.atlassian.com/manage-profile/security/api-tokens"
   - Ask for email address
   - Ask for API token

5. **Test connectivity**: Run via Bash:
   ```bash
   curl -s -w "%{http_code}" -u "<email>:<token>" -H "Accept: application/json" "<baseUrl>/rest/api/3/myself"
   ```
   - If the HTTP code is 200, show the display name from the response and confirm connection works.
   - If it fails, show the error and ask the user to check their credentials. Do NOT proceed until connection works.

6. **Show defaults and confirm**:
   - Branch pattern: `^(?:feature|fix|hotfix|chore|docs)/({key}-\\d+)` (where `{key}` = project key)
   - Commit pattern: `{key}-\\d+:`
   - Time rounding: 15 minutes
   - Auto-create issues: false (ask first before creating)
   - Ask if these defaults are OK or if the user wants to change any.

7. **Write config files**:
   - `<project-root>/.claude/jira-autopilot.json` (committed to repo):
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
   - `<project-root>/.claude/jira-autopilot.local.json` (gitignored, contains secrets):
     ```json
     {
       "email": "<EMAIL>",
       "apiToken": "<TOKEN>",
       "baseUrl": "<BASE_URL>"
     }
     ```

8. **Offer to save credentials globally**:
   - Ask: "Save these credentials globally so you don't have to re-enter them for other projects? (yes/no)"
   - If yes, write `~/.claude/jira-autopilot.global.json`:
     ```json
     {
       "email": "<EMAIL>",
       "apiToken": "<TOKEN>",
       "baseUrl": "<BASE_URL>",
       "cloudId": "<CLOUD_ID>"
     }
     ```

9. **Update `.gitignore`** — ensure these lines exist:
   ```
   .claude/current-task.json
   .claude/jira-session.json
   .claude/jira-sessions/
   .claude/jira-autopilot.local.json
   .claude/jira-autopilot.declined
   ```

10. **Remove** `.claude/jira-autopilot.declined` if it exists.

11. **Confirm** setup is complete and show saved configuration summary.

## Notes
- If `.claude/jira-autopilot.json` already exists, show current values and ask what to change.
- The `{key}` placeholder in patterns gets replaced with the actual project key at runtime.
- NEVER commit or display the API token in output after initial setup.
