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
   - If keys are detected, present them as AskUserQuestion options: "What's your Jira project key?" with detected keys as options. The user can pick one or use the built-in "Other" option to type a different key. Do NOT add a "Type a different key" option — AskUserQuestion already provides "Other" automatically.
   - If no keys are detected, just ask: "What's your Jira project key? (the prefix before the dash in issue numbers, e.g. PROJ from PROJ-123)"
   - If the user selects "Other" and types a key, use that value directly. Do NOT ask a follow-up question.

2. **Check for saved global credentials** — Before asking for URL and credentials:
   - Check if `~/.claude/jira-autopilot.global.json` exists and contains `baseUrl`, `email`, `apiToken`.
   - If it does, show the saved baseUrl and email (NOT the token) and ask: "Found saved Jira credentials for **user@company.com** at **https://company.atlassian.net**. Use these? (yes/no)"
   - If the user says yes, skip steps 3-4 and reuse the saved values.
   - If the user says no, or the file doesn't exist, continue with steps 3-4 below.

3. **Ask for Jira base URL** — Ask the user in plain text (NOT using AskUserQuestion): "What's your Jira base URL? (e.g. https://yourcompany.atlassian.net)". Let them type it directly. Do NOT present options or menus — just wait for them to type the URL. Validate it looks like a URL starting with `https://`.
   - Auto-fetch Cloud ID: run `curl -s <baseUrl>/_edge/tenant_info` and extract `cloudId` from JSON response using `python3 -c "import json,sys; print(json.load(sys.stdin).get('cloudId',''))"`.
   - If fetch fails, ask the user for cloudId manually.

4. **Ask for credentials** (email + API token):
   - Tell the user: "You'll need your Atlassian email and an API token. Create one at: https://id.atlassian.com/manage-profile/security/api-tokens"
   - Ask for email address
   - Ask for API token

5. **Test connectivity and cache accountId**: Run via Bash:
   ```bash
   curl -s -u "<email>:<token>" -H "Accept: application/json" "<baseUrl>/rest/api/3/myself"
   ```
   - If the response contains `accountId`, connection works. Extract `accountId` and `displayName` from the response.
   - Show: "Connected as **<displayName>**"
   - Cache the `accountId` — it will be saved to the local config in step 9 for auto-assigning issues.
   - If the request fails or returns an error, show the error and ask the user to check their credentials. Do NOT proceed until connection works.

6. **Autonomy level selection** — Explain and let the user choose:
   ```
   Autonomy Level — how much should jira-autopilot do on its own?

     C (Cautious) — default
       Show summaries and ask before every action.
       You approve issue creation, worklog posting, and time logging.

     B (Balanced)
       Show summaries, then auto-proceed after 10 seconds.
       You see what's happening but don't need to approve each step.

     A (Autonomous)
       Act silently. Create issues, log time, post worklogs automatically.
       You'll see a one-line confirmation after each action.
   ```
   Default: **C**. Let the user pick C, B, or A.

7. **Accuracy parameter selection** — Explain and let the user choose (1-10):
   ```
   Accuracy (1-10) — how precisely should time be tracked?

     Low (1-3): Coarse tracking. 30-min rounding, 30-min idle threshold.
       Good for: rough time estimates, low overhead.
       Produces ~3-4 issues per day, combines small tasks.

     Medium (4-7): Balanced tracking. 15-min rounding, 15-min idle threshold.
       Good for: most teams, standard Jira workflows.
       Produces ~5-8 issues per day.

     High (8-10): Fine-grained tracking. 1-min rounding, 5-min idle threshold.
       Good for: billing, auditing, detailed work attribution.
       Produces 10+ issues per day, never combines tasks.
   ```
   Default: **5**. Let the user pick a number 1-10.

8. **Worklog language** — Ask which language worklog descriptions should be written in:
   ```
   What language should worklog descriptions be written in?
     1. English (default)
     2. Hebrew (עברית)
     3. Russian (Русский)
     4. Other — type a language name
   ```
   - Default: **English**.
   - Save to project config as `"logLanguage": "<language>"`.
   - Also ask: "Set this as your global default for all projects?" — if yes, save `logLanguage` to `~/.claude/jira-autopilot.global.json` too.

9. **Additional settings** — Show defaults and let the user override:
   - Branch pattern: `^(?:feature|fix|hotfix|chore|docs)/({key}-\\d+)` (where `{key}` = project key)
   - Commit pattern: `{key}-\\d+:`
   - Time rounding: derived from accuracy (low=30, medium=15, high=1), but can override
   - Idle threshold: derived from accuracy (low=30, medium=15, high=5), but can override (in minutes)
   - Debug logging: **enabled** (default true during development — logs to `~/.claude/jira-autopilot-debug.log`)
   - Auto-create issues: false (ask first before creating)
   - Ask if these defaults are OK or if the user wants to change any.

10. **Write config files**:
   - `<project-root>/.claude/jira-autopilot.json` (committed to repo):
     ```json
     {
       "projectKey": "<KEY>",
       "cloudId": "<CLOUD_ID>",
       "enabled": true,
       "autonomyLevel": "<C|B|A>",
       "accuracy": <1-10>,
       "debugLog": true,
       "branchPattern": "^(?:feature|fix|hotfix|chore|docs)/({key}-\\d+)",
       "commitPattern": "{key}-\\d+:",
       "timeRounding": <15>,
       "idleThreshold": <15>,
       "autoCreate": false,
       "logLanguage": "<language>",
       "defaultLabels": ["jira-autopilot"],
       "defaultComponent": null,
       "defaultFixVersion": null,
       "componentMap": {}
     }
     ```
   - `<project-root>/.claude/jira-autopilot.local.json` (gitignored, contains secrets):
     ```json
     {
       "email": "<EMAIL>",
       "apiToken": "<TOKEN>",
       "baseUrl": "<BASE_URL>",
       "accountId": "<ACCOUNT_ID>"
     }
     ```

11. **Offer to save credentials globally**:
    - Ask: "Save these credentials globally so you don't have to re-enter them for other projects? (yes/no)"
    - If yes, write `~/.claude/jira-autopilot.global.json`:
      ```json
      {
        "email": "<EMAIL>",
        "apiToken": "<TOKEN>",
        "baseUrl": "<BASE_URL>",
        "cloudId": "<CLOUD_ID>",
        "accountId": "<ACCOUNT_ID>"
      }
      ```

12. **Update `.gitignore`** — ensure these lines exist:
    ```
    .claude/current-task.json
    .claude/jira-session.json
    .claude/jira-sessions/
    .claude/jira-autopilot.local.json
    .claude/jira-autopilot.declined
    ```

13. **Remove** `.claude/jira-autopilot.declined` if it exists.

14. **Confirm** setup is complete and show saved configuration summary, including:
    - Project key
    - Connected as (display name)
    - Autonomy level (with brief description)
    - Accuracy level (with time rounding and idle threshold)
    - Debug logging status

## Notes
- If `.claude/jira-autopilot.json` already exists, show current values and ask what to change.
- The `{key}` placeholder in patterns gets replaced with the actual project key at runtime.
- NEVER commit or display the API token in output after initial setup.
