---
name: start-work
description: Start tracking a Jira task (create new or link existing)
allowed-tools: Bash, Write, Read, ToolSearch
---

# /start-work — Start Tracking a Jira Task

You are starting work on a Jira issue. The user may provide an issue key (e.g. `PROJ-42`) or a summary text for a new issue.

## Path Resolution

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
CLI="python3 $PLUGIN_ROOT/hooks-handlers/jira_core.py"
```

---

## Pre-check: Active Task Conflict

Read the session state:

```bash
$CLI get-session "$PROJECT_ROOT"
```

If there is already a `currentIssue` set:
- Show the active issue key and summary.
- Ask the user: "You are currently tracking **{currentIssue}**. Would you like to:"
  - **Switch** — pause the current issue and start the new one.
  - **Stop current first** — run the stop-work flow for the current issue, then start new.
  - **Cancel** — keep working on the current issue.

If the user chooses Switch, the current issue stays in `activeIssues` but is no longer `currentIssue`.

## Parse the Argument

The user's argument (everything after `/start-work`) determines the flow:

- If it matches `[A-Z][A-Z0-9]+-\d+` (e.g. `PROJ-42`): **Link to Existing Issue**.
- Otherwise: **Create New Issue** using the text as the summary.
- If no argument provided: ask the user what they want to do (link existing or create new).

---

## Flow A: Link to Existing Issue

### Step 1: Fetch Issue from Jira

```bash
$CLI get-issue "$PROJECT_ROOT" "ISSUE_KEY"
```

If the issue is not found, inform the user and ask them to verify the key.

### Step 2: Update Session State

```bash
$CLI start-tracking "$PROJECT_ROOT" "ISSUE_KEY" "ISSUE_SUMMARY"
```

This should:
- Add the issue to `activeIssues` with `{summary, startTime: now, totalSeconds: 0, paused: false, autoApproveWorklogs: false}`.
- Set `currentIssue` to the issue key.
- Retroactively claim any unattributed (null) work chunks to this issue.

### Step 3: Create or Switch to Feature Branch

**IMPORTANT:** Never work directly on `main`, `master`, or `develop` branches.

Check the current branch:

```bash
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
```

If on `main`, `master`, or `develop`:
- Create a feature branch: `git checkout -b feature/ISSUE_KEY-slug`
- The slug is the issue summary, lowercased, spaces replaced with hyphens, truncated to 40 chars.

If already on a feature branch containing the issue key, stay on it.

### Step 4: Confirm

Display:
```
Tracking ISSUE_KEY: {summary}
Branch: {branch_name}
Time tracking started.
```

---

## Flow B: Create New Issue

### Step 0: Language

Read `logLanguage` from the project config. If the summary is not in the target language, keep it as-is (translation happens at worklog time, not issue creation time).

### Step 1: Classify Issue Type

```bash
$CLI classify-issue "$PROJECT_ROOT" "SUMMARY_TEXT"
```

Returns `{type, confidence, signals}`.

Read the current autonomy level from session/config:

- **Autonomy C:** Present options via the conversation:
  - "Based on the summary, this looks like a **{type}** (confidence: {confidence}). Choose:"
  - Task
  - Bug
  - Story
  - Let the user pick.

- **Autonomy B/A:** Auto-use the classified type. Show a brief notice: "Creating {type}: {summary}"

### Step 2: Parent Issue Selection

```bash
$CLI suggest-parent "$PROJECT_ROOT"
```

Returns `{sessionDefault, contextual, recent}`.

- **Autonomy C:** Present parent options:
  - Session default (if set): "{key} — {summary}"
  - Contextual matches (if any)
  - Recent parents (last used)
  - "Create new parent"
  - "No parent"
  - Let the user choose.

- **Autonomy B/A:** Auto-select `sessionDefault` if available, otherwise best contextual match, otherwise no parent.

### Step 3: Bug-Story Linking

If the issue type is Bug:
- **Autonomy C:** Ask: "Link this bug to a Story? (Relates link)" — show active stories or let user enter a key.
- **Autonomy B/A:** Auto-link to `currentIssue` if it's a Story, or skip.

### Step 4: Gather Fields

Prepare the issue creation payload:
- `summary`: the user-provided summary text.
- `issuetype`: from Step 1.
- `project`: project key from config.
- `assignee`: `accountId` from local/global credentials.
- `labels`: always include `jira-autopilot` plus any `defaultLabels` from config.
- `parent`: from Step 2 (if selected).
- `components`: from `componentMap` config (match file paths in work chunks) or `defaultComponent`.
- `fixVersions`: from `defaultFixVersion` config.

### Step 5: Create the Issue

```bash
$CLI create-issue "$PROJECT_ROOT" '{"summary":"...","issuetype":"...","parent":"...","labels":[...]}'
```

Returns `{key, id}`.

If creation fails, show the error and suggest checking credentials or project permissions.

### Step 6: Post-Creation

1. If Bug-Story link was requested in Step 3, create the link:
   ```bash
   $CLI link-issues "$PROJECT_ROOT" "NEW_KEY" "STORY_KEY" "Relates"
   ```

2. Follow the **Link to Existing Issue** flow (Steps 2-4) with the newly created key.

3. Update `recentParents` in local config (keep last 10 entries).

### Step 7: Confirm

Display:
```
Created ISSUE_KEY: {summary}
Type: {type}
Parent: {parent_key} (or "None")
Branch: {branch_name}
Time tracking started.
```

---

## Error Handling

- If no config exists (`jira-autopilot.json` missing): tell the user to run `/jira-setup` first.
- If credentials are missing: tell the user to run `/jira-setup` first.
- If Jira API call fails: show the error, suggest checking network/credentials.
- If git operations fail: continue without branching, warn the user.
