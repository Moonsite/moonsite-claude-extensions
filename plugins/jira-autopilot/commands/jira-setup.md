---
name: jira-setup
description: Configure Jira tracking for this project
allowed-tools: Bash, Write, Edit, Read, AskUserQuestion, Glob
---

# /jira-setup — Configure Jira Tracking

You are the Jira Autopilot setup wizard. Walk the user through configuring their Jira connection step by step. Be concise but friendly.

**IMPORTANT:** Use `AskUserQuestion` for every user-facing question. Never assume answers.

## Path Resolution

Set `PLUGIN_ROOT` to the directory containing this plugin. All Python CLI calls use:

```
python3 "$PLUGIN_ROOT/hooks-handlers/jira_core.py" <command> <args>
```

where `PLUGIN_ROOT` is resolved from `$CLAUDE_PLUGIN_ROOT` if available, or by finding the `jira_core.py` file relative to the commands directory.

Determine the project root:
```bash
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
```

---

## Step 1: Check for Saved Global Credentials

Read `~/.claude/jira-autopilot.global.json`. If it exists and contains `baseUrl`, `email`, and `apiToken`:

- Show the saved email and URL (NOT the token).
- Ask: "Found saved Jira credentials for **{email}** at **{baseUrl}**. Use these?"
- If yes: reuse saved values, skip Steps 2-3.
- If no: continue to Steps 2-3 for fresh entry.

If no global file exists, continue to Step 2.

## Step 2: Ask for Jira Base URL

Ask the user for their Jira instance URL (e.g. `https://company.atlassian.net`).

- Validate it starts with `https://`
- Auto-fetch Cloud ID:

```bash
curl -s "${BASE_URL}/_edge/tenant_info" | python3 -c "import json,sys; print(json.load(sys.stdin).get('cloudId',''))"
```

- If Cloud ID fetch fails, ask the user to provide it manually (or skip — it can be empty).
- Store `baseUrl` and `cloudId`.

## Step 3: Ask for Credentials

Ask for:
1. **Email address** — their Atlassian account email.
2. **API token** — provide the link: `https://id.atlassian.com/manage-profile/security/api-tokens`

Tell the user: "Your API token will be stored locally and never committed to git."

## Step 4: Test Connectivity

Test the connection:

```bash
python3 "$PLUGIN_ROOT/hooks-handlers/jira_core.py" test-connection "$PROJECT_ROOT" "$BASE_URL" "$EMAIL" "$API_TOKEN"
```

If no `test-connection` CLI command exists, test directly:

```bash
curl -s -u "$EMAIL:$API_TOKEN" "${BASE_URL}/rest/api/3/myself"
```

- Extract `accountId` and `displayName` from the response.
- Show: "Connected as **{displayName}**"
- If the test fails, show the error and ask the user to re-enter credentials. Do NOT proceed until connectivity is confirmed.

## Step 5: Select Project Key

Fetch available Jira projects:

```bash
python3 "$PLUGIN_ROOT/hooks-handlers/jira_core.py" get-projects "$PROJECT_ROOT"
```

Also detect keys from git history:

```bash
git log --oneline -100 2>/dev/null | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | sed 's/-[0-9]*//' | sort -u
git branch -a 2>/dev/null | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | sed 's/-[0-9]*//' | sort -u
```

Present the options via `AskUserQuestion`:
- Sort git-detected matches first (they are most likely relevant).
- Format: "KEY — Project Name"
- Include a "Skip for now" option (sets `projectKey` to empty string — monitoring mode).
- Include an "Other" option for manual key entry.

If the API returns no projects, fall back to text input with a "Skip for now" option.

## Step 6: Autonomy Level

Ask the user to choose their autonomy level via `AskUserQuestion`:

- **C (Cautious)** — Default. Ask before every action (issue creation, worklog posting).
- **B (Balanced)** — Show summaries, then auto-proceed. Enables `autoCreate: true`.
- **A (Autonomous)** — Act silently. Enables `autoCreate: true`. Auto-creates at confidence >= 0.65.

Default to C if the user is unsure.

## Step 7: Accuracy (1-10)

Ask for an accuracy level from 1 to 10 (default: 5):

- **Low (1-3):** Coarser time entries, longer idle thresholds, fewer issues/day.
- **Medium (4-7):** Balanced defaults.
- **High (8-10):** Fine-grained entries, shorter idle thresholds, more issues/day.

## Step 8: Worklog Language

Ask the user to choose their worklog language via `AskUserQuestion`:

- **English** (default)
- **Hebrew**
- **Russian**
- **Other** (let the user type a custom language name)

Offer to save this as the global default.

## Step 9: Additional Settings (Optional)

Show the defaults for these settings and ask if the user wants to override any:

| Setting | Default | Description |
|---------|---------|-------------|
| `branchPattern` | `^(?:feature\|fix\|hotfix\|chore\|docs)/({key}-\\d+)` | Regex for extracting issue key from branch name |
| `commitPattern` | `{key}-\\d+:` | Regex for detecting issue key in commits |
| `timeRounding` | `15` | Minutes to round worklogs up to |
| `idleThreshold` | `15` | Minutes of inactivity before splitting chunks |
| `debugLog` | `true` | Enable debug logging |
| `autoCreate` | `false` (C) / `true` (B/A) | Auto-create issues on work intent detection |

If the user wants defaults, skip ahead. Otherwise, ask for each override individually.

## Step 10: Write Config Files

Write the project config:

```bash
python3 -c "
import json
config = {
    'projectKey': '$PROJECT_KEY',
    'cloudId': '$CLOUD_ID',
    'enabled': True,
    'autonomyLevel': '$AUTONOMY',
    'accuracy': $ACCURACY,
    'debugLog': True,
    'branchPattern': '$BRANCH_PATTERN',
    'commitPattern': '$COMMIT_PATTERN',
    'timeRounding': $TIME_ROUNDING,
    'idleThreshold': $IDLE_THRESHOLD,
    'autoCreate': $AUTO_CREATE,
    'logLanguage': '$LOG_LANGUAGE',
    'defaultLabels': ['jira-autopilot'],
    'defaultComponent': None,
    'defaultFixVersion': None,
    'componentMap': {},
    'worklogInterval': 15
}
with open('$PROJECT_ROOT/.claude/jira-autopilot.json', 'w') as f:
    json.dump(config, f, indent=2)
print('Project config saved.')
"
```

Write the local credentials file:

```bash
python3 -c "
import json
local = {
    'email': '$EMAIL',
    'apiToken': '$API_TOKEN',
    'baseUrl': '$BASE_URL',
    'accountId': '$ACCOUNT_ID',
    'anthropicApiKey': '',
    'recentParents': []
}
with open('$PROJECT_ROOT/.claude/jira-autopilot.local.json', 'w') as f:
    json.dump(local, f, indent=2)
print('Local credentials saved.')
"
```

## Step 11: Offer Global Save

Ask: "Save these credentials globally for use in other projects?"

If yes, write to `~/.claude/jira-autopilot.global.json`:

```bash
python3 -c "
import json, os
path = os.path.expanduser('~/.claude/jira-autopilot.global.json')
os.makedirs(os.path.dirname(path), exist_ok=True)
data = {
    'email': '$EMAIL',
    'apiToken': '$API_TOKEN',
    'baseUrl': '$BASE_URL',
    'cloudId': '$CLOUD_ID',
    'accountId': '$ACCOUNT_ID',
    'logLanguage': '$LOG_LANGUAGE'
}
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
print('Global credentials saved.')
"
```

## Step 12: Update .gitignore

Ensure these lines exist in `$PROJECT_ROOT/.gitignore`:

```
.claude/current-task.json
.claude/jira-session.json
.claude/jira-sessions/
.claude/jira-autopilot.local.json
.claude/jira-autopilot.declined
```

Read the existing `.gitignore` and append only missing lines. Create the file if it does not exist.

## Step 13: Remove Declined Marker

If `.claude/jira-autopilot.declined` exists, delete it:

```bash
rm -f "$PROJECT_ROOT/.claude/jira-autopilot.declined"
```

## Step 14: Confirm Setup

Display a summary of the saved configuration:

```
Jira Autopilot configured:
  Project:   {projectKey} (or "Monitoring mode" if empty)
  Connected: {displayName} ({email})
  Autonomy:  {autonomyLevel} ({description})
  Accuracy:  {accuracy}
  Language:  {logLanguage}
  Debug:     {debugLog}

Run /start-work to begin tracking a Jira task.
```

## Re-configuration

If `.claude/jira-autopilot.json` already exists when this command runs:
- Show current configuration values.
- Ask: "What would you like to change?" with options for each setting category.
- Only update the fields the user wants to change.
- Re-test connectivity if credentials change.
