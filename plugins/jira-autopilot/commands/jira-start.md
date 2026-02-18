---
name: jira-start
description: Start tracking a Jira task (create new or link existing)
argument: Issue key (e.g. PROJ-42) or summary text to create a new issue
allowed-tools: Bash, Write, Read, ToolSearch, mcp__atlassian__createJiraIssue, mcp__atlassian__getJiraIssue
---

# Start Jira Task

You are starting work on a Jira task. Read the project config from `<project-root>/.claude/jira-autopilot.json` and session state from `<project-root>/.claude/jira-session.json` first. Also read `<project-root>/.claude/jira-autopilot.local.json` for cached `accountId`.

## If a task is already active

Check `currentIssue` in session state. If set, ask the user if they want to:
- **Switch** to the new issue (pause timer on current, keep it in activeIssues)
- **Stop** the current task first (log time via /jira-stop flow) before starting new one

## Parse the argument

- If argument matches `<PROJECT_KEY>-\d+` pattern → **link to existing issue** (jump to "Link to Existing Issue")
- Otherwise → **create a new issue** with the argument as summary (jump to "Create New Issue")

---

## Link to Existing Issue

1. **Fetch issue details** — Try `mcp__atlassian__getJiraIssue` first (load tool via ToolSearch). If MCP fails, fall back to REST:
   ```bash
   source <plugin-root>/hooks-handlers/jira-rest.sh
   jira_load_creds "<project-root>"
   jira_get_issue "<ISSUE_KEY>"
   ```
2. **Record start time**: run `date +%s`
3. **Update session state** in `<project-root>/.claude/jira-session.json`:
   - Add issue to `activeIssues` with summary, startTime, totalSeconds: 0, paused: false, autoApproveWorklogs: false
   - Set `currentIssue` to this key
4. **Create feature branch** if not on a matching branch:
   ```bash
   git checkout -b feature/<KEY>-<slug>
   ```
5. Display: "Started tracking **<KEY>**: <summary>. Timer running."

---

## Create New Issue

### Step 1: Classify issue type

Run the type classifier:
```bash
python3 <plugin-root>/hooks-handlers/jira_core.py classify-issue "<summary>"
```
This returns JSON: `{"type": "Task"|"Bug", "confidence": <0-1>, "signals": [...]}`

**Autonomy C** (default): Show the classification and let the user approve or change:
```
Suggested type: Task (confidence: 0.80)
  Signals: "add", "implement"

  1. Task (recommended)
  2. Bug
  3. Story
```

**Autonomy B/A**: Use the auto-classified type silently.

### Step 2: Parent issue selection

Run the parent suggester:
```bash
python3 <plugin-root>/hooks-handlers/jira_core.py suggest-parent "<project-root>" "<summary>"
```
This returns JSON with `sessionDefault`, `contextual`, and `recent` arrays.

**Autonomy C**: Present the parent selection. Always include "Create new parent" and "No parent" options, even when there are no suggestions:
- If there are contextual or recent suggestions, show them as numbered options followed by "Enter a key/URL", "Create new parent", and "No parent".
- If there are NO suggestions (empty results), show just three options:
  1. Enter a parent key
  2. Create new parent (create an Epic first, then link)
  3. No parent (standalone task)

Example with suggestions:
```
Parent for "<summary>":
  Suggested (by context):
    1. <KEY>: <summary> (recommended)
    2. <KEY>: <summary>
  Recent:
    3. <KEY>: <summary> (last used)
  Other:
    4. Enter a key/URL
    5. Create new parent
    6. No parent
```

**Autonomy B/A**: Auto-select `sessionDefault` (lastParentKey) if available, otherwise the best contextual match. If neither exists, skip parent.

After selection, store the chosen parent key as `lastParentKey` in session state.

### Step 3: Bug → Story linking (if type is Bug)

If the classified type is **Bug**, trigger story linking flow:

**Autonomy C**: Present story selection:
```
Bugs should be linked to a Story. Choose a Story to link:
  Suggested:
    1. <KEY>: <story summary> (contextual match)
  Recent:
    2. <KEY>: <story summary>
  Other:
    3. Create new Story
    4. Enter story key/URL
    5. Skip — no Story link
```

**Autonomy B/A**: Auto-link to best contextual match or skip if none found.

If a Story is selected/created, create an issue link (type: "Relates") between the Bug and the Story after issue creation.

### Step 4: Determine additional fields

- **Assignee**: Use cached `accountId` from `<project-root>/.claude/jira-autopilot.local.json`. Always auto-assign to current user.
- **Labels**: Always include `jira-autopilot`. Merge with any `defaultLabels` from config.
- **Component**: Check `componentMap` in config. If any file paths from the current working context match a key in the map, use that component. Otherwise use `defaultComponent` if set.
- **Fix Version**: Use `defaultFixVersion` from config if set. Otherwise, optionally query Jira for the latest unreleased version and suggest it (skip if no versions configured).

### Step 5: Create the issue

Try `mcp__atlassian__createJiraIssue` first (load via ToolSearch), providing:
- project key, summary, issue type (from step 1)
- parent key (from step 2, if selected)
- assignee accountId
- labels
- component (if determined)
- fix version (if determined)

If MCP fails, fall back to REST:
```bash
source <plugin-root>/hooks-handlers/jira-rest.sh
jira_load_creds "<project-root>"
jira_create_issue "<PROJECT_KEY>" "<summary>" "<type>" "<parent_key>" "<assignee_id>"
```

### Step 6: Post-creation

1. If Bug → Story link was selected in step 3, create the issue link now.
2. Follow steps 2-5 from "Link to Existing Issue" above with the newly created key.
3. Update `recentParents` in local config if a parent was selected (keep last 10).
