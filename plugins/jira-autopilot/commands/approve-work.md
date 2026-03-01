---
name: approve-work
description: Review and approve pending work items as Jira issues
allowed-tools: Bash, Write, Read, ToolSearch
---

# /approve-work — Review and Approve Pending Work

Walk through all pending items (issues, worklogs, unattributed work) and let the user approve, edit, redirect, or drop each one.

## Path Resolution

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
CLI="python3 $PLUGIN_ROOT/hooks-handlers/jira_core.py"
```

---

## Step 1: Load Session State

```bash
$CLI get-session "$PROJECT_ROOT"
```

Read the session JSON and extract:
- `pendingIssues` — issues awaiting approval
- `pendingWorklogs` — worklogs with status `"pending"` or `"deferred"`
- Unattributed worklogs — entries with `issueKey: null` and status `"unattributed"`

Also read the project config for `logLanguage` and `autonomyLevel`.

If there are no pending items in any category:
```
No pending items to review. All worklogs are up to date.
```
Exit.

## Step 2: Summary of Pending Items

Show an overview before diving into details:

```
Pending items to review:
  Issues:       {N} awaiting approval
  Worklogs:     {N} pending, {N} deferred
  Unattributed: {N} work entries without an issue

Starting review...
```

---

## Step 3: Review Pending Issues

For each item in `pendingIssues` with `status: "awaiting_approval"`:

Show the pending issue details:
```
Suggested Issue: "{suggestedSummary}"
  Files changed: {files list}
  Activities: {count}
```

Offer 3 actions:
1. **Approve** — create the issue in Jira.
2. **Link** — link this work to an existing Jira issue (ask for issue key).
3. **Skip** — discard this suggestion.

### If Approve:

Follow the same issue creation flow as `/start-work` (classify type, select parent, create):

```bash
$CLI classify-issue "$PROJECT_ROOT" "SUGGESTED_SUMMARY"
$CLI create-issue "$PROJECT_ROOT" '{"summary":"...","issuetype":"...","labels":["jira-autopilot"]}'
```

Update the pending issue status to `"approved"`. Start tracking the newly created issue.

### If Link:

Ask for the issue key. Validate it:

```bash
$CLI get-issue "$PROJECT_ROOT" "ISSUE_KEY"
```

Attribute the work to this issue. Update pending issue status to `"linked"`.

### If Skip:

Update pending issue status to `"skipped"`.

---

## Step 4: Review Pending and Deferred Worklogs

For each item in `pendingWorklogs` with `status: "pending"` or `status: "deferred"`:

First, enrich the summary if it is a raw file-list format. Rewrite it as a human-readable description in `logLanguage`:
- 2-4 sentences describing the work.
- Include file names (max 8, "+N more" for overflow).
- No raw commands, hashes, or internal details.

Show the worklog details:
```
Worklog for {issueKey}:
  Time:    {formatted_time} (actual: {actual_time})
  Summary: {enriched_summary}
  Files:   {file_list}
  Status:  {status}
```

Offer 4 actions:
1. **Approve** — post the worklog to Jira now.
2. **Edit** — modify the summary text before posting.
3. **Redirect** — post to a different issue (ask for issue key).
4. **Drop** — discard this worklog entirely.

### If Approve:

```bash
$CLI add-worklog "$PROJECT_ROOT" "ISSUE_KEY" SECONDS "ENRICHED_SUMMARY"
```

If posting succeeds: mark as `"posted"`, show confirmation.
If posting fails: mark as `"failed"`, inform user, suggest retrying later.

### If Edit:

Let the user provide a new summary. Re-display for approval.

### If Redirect:

Ask for the new issue key. Update the worklog's `issueKey`. Re-display for approval.

### If Drop:

Mark the worklog as `"dropped"`.

---

## Step 5: Review Unattributed Work

For each item in `pendingWorklogs` with `status: "unattributed"` and `issueKey: null`:

Show the work details:
```
Unattributed Work:
  Time:       {formatted_time}
  Files:      {file_list}
  Activities: {count}
  Summary:    {summary or "No summary available"}
```

Offer 3 actions:
1. **Create new issue** — create a Jira issue and attribute this work to it.
2. **Log to existing issue** — attribute to an existing issue (ask for key).
3. **Drop** — discard this work entry.

### If Create New Issue:

Ask for a summary (suggest one based on the files changed). Then follow the creation flow:

```bash
$CLI classify-issue "$PROJECT_ROOT" "SUMMARY"
$CLI create-issue "$PROJECT_ROOT" '{"summary":"...","issuetype":"...","labels":["jira-autopilot"]}'
$CLI add-worklog "$PROJECT_ROOT" "NEW_KEY" SECONDS "SUMMARY"
```

### If Log to Existing:

Ask for the issue key. Post the worklog:

```bash
$CLI add-worklog "$PROJECT_ROOT" "ISSUE_KEY" SECONDS "SUMMARY"
```

### If Drop:

Mark as `"dropped"`.

---

## Step 6: Save Updated Session

After processing all items, save the updated session state. The CLI commands should handle this automatically, but verify:

```bash
$CLI get-session "$PROJECT_ROOT"
```

## Step 7: Final Summary

```
Review complete:
  Issues:    {N} approved, {N} linked, {N} skipped
  Worklogs:  {N} posted, {N} edited, {N} redirected, {N} dropped
  Unattributed: {N} resolved, {N} dropped

Remaining pending: {N} items
```

If items remain pending (e.g. failed posts), suggest running `/approve-work` again later.

---

## Error Handling

- If no config exists: tell the user to run `/jira-setup` first.
- If Jira API fails during posting: mark as `"failed"`, continue with next item.
- If session state is corrupt: inform the user, suggest checking session files.
- Never stop the review loop due to a single item failure — process all items.
