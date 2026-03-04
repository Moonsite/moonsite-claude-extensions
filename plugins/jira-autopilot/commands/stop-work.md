---
name: stop-work
description: Stop tracking current task and log time to Jira
allowed-tools: Bash, Read, Write, ToolSearch
---

# /stop-work — Stop Tracking and Log Time

You are stopping work on the current Jira issue, building a worklog, and posting it to Jira.

## Path Resolution

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
CLI="python3 $PLUGIN_ROOT/hooks-handlers/jira_core.py"
```

---

## Step 1: Read Session and Config

```bash
$CLI get-session "$PROJECT_ROOT"
```

Read the config:

```bash
cat "$PROJECT_ROOT/.claude/jira-autopilot.json"
```

If there is no active task (`currentIssue` is null or empty):
- Inform the user: "No active task being tracked. Run `/start-work` to begin tracking."
- If there are pending worklogs or unattributed work, suggest running `/approve-work`.
- Exit.

Get the current issue key and autonomy level.

## Step 2: Build Worklog

```bash
$CLI build-worklog "$PROJECT_ROOT" "ISSUE_KEY"
```

Returns:
```json
{
  "issueKey": "KEY-42",
  "seconds": 1800,
  "summary": "Edited auth.ts, login.tsx",
  "rawFacts": {
    "files": ["src/auth.ts", "src/login.tsx"],
    "commands": ["npm test"],
    "activityCount": 12
  },
  "logLanguage": "English"
}
```

If no work was tracked (seconds == 0 and no activities), inform the user and ask if they still want to stop tracking the issue.

## Step 3: Enrich Summary

Write a human-readable worklog description in the configured `logLanguage`:
- 2-4 sentences describing what was accomplished.
- Include file names (max 8, with "+N more" if overflow).
- No raw commands, hashes, or internal details.
- Use the `rawFacts` (files, commands, activityCount) to compose the description.

If an Anthropic API key is configured, the CLI can enrich the summary via AI:

```bash
$CLI enrich-summary "$PROJECT_ROOT" '{"files":["..."],"commands":["..."],"activityCount":N}'
```

Otherwise, compose it yourself from the raw facts.

## Step 4: Calculate Display Time

Read `timeRounding` and `accuracy` from config.

Time rounding rules:
- **High accuracy (8-10):** granularity = max(timeRounding / 15, 1) minutes
- **Low accuracy (1-3):** granularity = timeRounding * 2
- **Medium (4-7):** granularity = timeRounding

Always round UP. Minimum one rounding increment (never zero).

Show both actual and rounded time:
```
Actual time: 27 minutes
Rounded time: 30 minutes (rounded up to 15-min increments)
```

If the time exceeds 4 hours (14400 seconds), cap it and inform the user:
```
Time capped at 4 hours (actual: 5h 12m). This is the maximum for a single worklog.
```

## Step 5: Approval Flow

### Autonomy C (Cautious) — 5-Option Approval

Present the worklog summary and time to the user, then offer 5 options:

```
Worklog for KEY-42: {summary}
Time: {rounded_time}
Files: {file_list}

Options:
1. Approve — post this worklog to Jira
2. Approve + go silent — approve this and auto-approve future worklogs for this issue
3. Edit summary — modify the worklog description before posting
4. Log to different issue — redirect this worklog to another issue
5. Reject — keep for later (deferred) or drop entirely
```

Handle each option:
1. **Approve:** proceed to Step 6.
2. **Approve + silent:** set `autoApproveWorklogs: true` for this issue in session, then proceed to Step 6.
3. **Edit summary:** let the user provide a new summary, then re-present for approval.
4. **Log to different issue:** ask which issue key to use, re-attribute the worklog, then re-present.
5. **Reject:** ask "Keep for later (can approve via /approve-work) or drop entirely?"
   - Keep: save worklog with `status: "deferred"`.
   - Drop: save worklog with `status: "dropped"`.

### Autonomy B (Balanced)

Show the worklog summary and time, then auto-approve after a brief display:
```
Posting worklog for KEY-42: {summary} ({rounded_time})
```

### Autonomy A (Autonomous)

Silent post with one-line confirmation:
```
Logged {rounded_time} to KEY-42.
```

## Step 6: Post Worklog to Jira

```bash
$CLI add-worklog "$PROJECT_ROOT" "ISSUE_KEY" SECONDS "SUMMARY_TEXT"
```

If posting fails:
- Mark the worklog as `status: "failed"`.
- Inform the user: "Failed to post worklog. It has been saved and can be retried via `/approve-work`."

If posting succeeds:
- Mark the worklog as `status: "posted"`.

## Step 7: Post Work Summary Comment

If there were work chunks for this issue, post a summary comment to the Jira issue:

```bash
$CLI add-comment "$PROJECT_ROOT" "ISSUE_KEY" "COMMENT_TEXT"
```

The comment should summarize what was done (files changed, key actions) in the configured language.

## Step 8: Update Session State

```bash
$CLI stop-tracking "$PROJECT_ROOT" "ISSUE_KEY"
```

This should:
- Remove the issue from `activeIssues`.
- Set `currentIssue` to null (or the next active issue if multiple are being tracked).
- Clear processed work chunks for this issue.

## Step 9: Display Final Summary

```
Stopped tracking KEY-42: {summary}
Time logged: {rounded_time}
Worklog: {status}
```

## Step 10: Branch Cleanup

Check if on a feature branch:

```bash
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
```

If the branch contains the issue key:

### Autonomy C:
Offer 3 options:
1. **Open PR** — push branch and create a pull request.
2. **Keep working** — stay on this branch.
3. **Switch to main** — `git checkout main` (or `master`/`develop`).

### Autonomy B/A:
If there are unpushed commits, auto-suggest opening a PR:
```
You have unpushed commits on {branch}. Consider opening a PR.
```

---

## Error Handling

- If no config exists: tell the user to run `/jira-setup` first.
- If no session exists: tell the user no work has been tracked.
- If Jira API fails: save the worklog as `"failed"` and inform the user it can be retried.
- If git operations fail: continue without branch cleanup, inform the user.
