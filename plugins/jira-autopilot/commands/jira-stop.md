---
name: jira-stop
description: Stop tracking current task and log time to Jira
allowed-tools: Bash, Read, Write, ToolSearch, mcp__atlassian__addWorklogToJiraIssue
---

# Stop Jira Task

You are stopping work on the current Jira task and logging time with a worklog approval flow.

## Steps

1. **Read session and config**:
   - Read `<project-root>/.claude/jira-session.json`
   - Read `<project-root>/.claude/jira-autopilot.json` for config (timeRounding, accuracy, autonomyLevel)
   - If session doesn't exist or `currentIssue` is null, tell the user "No active task. Use /jira-start to begin tracking."

2. **Build worklog** — Run the worklog builder to gather raw facts:
   ```bash
   python3 <plugin-root>/hooks-handlers/jira_core.py build-worklog "<project-root>" "<currentIssue>"
   ```
   This returns JSON:
   ```json
   {
     "issueKey": "PROJ-1",
     "seconds": 900,
     "summary": "Edited auth.ts, middleware.ts. Ran tests (npm test). 3 tool calls.",
     "rawFacts": {"files": [...], "commands": [...], "activityCount": 3}
   }
   ```

3. **Enrich summary** — Use the `rawFacts` from the worklog builder along with your conversation context to write a 1-3 line human-readable work summary. This should describe *what was accomplished*, not just list files. Example:
   - Raw: `files: [auth.ts, middleware.ts], commands: [npm test]`
   - Enriched: "Refactored auth middleware to support SSO tokens. Updated middleware chain. All tests passing."

4. **Calculate display time** — Convert seconds to a human-readable format:
   - Round up to nearest increment from `timeRounding` in config (default 15 min)
   - Show both actual and rounded time

5. **Present worklog for approval** — Behavior depends on autonomy level:

### Autonomy C (default) — Full approval flow

If `autoApproveWorklogs` is true for this issue (set by a previous "Approve + silent" choice), skip to posting directly.

Otherwise, present the 5-option approval flow:
```
[jira-autopilot] Worklog for <KEY> (<rounded time>):
  "<enriched summary>"

  Actual: <actual_minutes>m → logged as: <rounded_time>

  1. Approve
  2. Approve + go silent for this issue
  3. Edit summary
  4. Log to different issue
  5. Reject
```

Handle each choice:

**1. Approve** — Post the worklog with the enriched summary to Jira (step 6).

**2. Approve + go silent** — Post the worklog, then set `autoApproveWorklogs: true` for this issue in session state. Future worklogs for this issue will be auto-approved without prompting.

**3. Edit summary** — Ask the user to type a replacement summary, then post with the edited text.

**4. Log to different issue** — Show a selection of available targets:
```
Log this time to a different issue:
  Active:
    1. <KEY>: <summary> (currently tracking)
  Recent:
    2. <KEY>: <summary>
  Other:
    3. Enter issue key
```
After selection, re-attribute the worklog to the chosen issue and post.

**5. Reject** — Ask the user what to do with the rejected worklog:
```
What should I do with this worklog?
  1. Keep for later (save as deferred — can review with /jira-approve)
  2. Drop entirely (discard time and summary)
```
- **Keep**: Add to `pendingWorklogs` in session state with status `deferred`
- **Drop**: Discard the worklog entirely

### Autonomy B — Show and auto-approve

Display the worklog summary, then auto-approve after a brief pause:
```
[jira-autopilot] Worklog for <KEY> (<rounded time>):
  "<enriched summary>"
  Auto-approving...
```
Post the worklog (step 6).

### Autonomy A — Silent posting

Post the worklog silently and print a one-liner:
```
[jira-autopilot] Logged <rounded time> to <KEY>
```

6. **Post worklog to Jira** — Try MCP first (`mcp__atlassian__addWorklogToJiraIssue` via ToolSearch), providing:
   - Issue key
   - Time spent in seconds (rounded value)
   - Comment/description: the enriched summary

   If MCP fails, fall back to REST:
   ```bash
   source <plugin-root>/hooks-handlers/jira-rest.sh
   jira_load_creds "<project-root>"
   jira_log_time "<ISSUE_KEY>" <total_seconds>
   jira_add_comment "<ISSUE_KEY>" "<enriched_summary>"
   ```

7. **Post work summary as comment** — If work chunks exist for this issue and the worklog was approved, post a detailed comment to the issue summarizing files changed and activities performed.

8. **Update session state**:
   - Remove issue from `activeIssues`
   - Set `currentIssue` to null (or to the next active issue if one exists)
   - Clear work chunks associated with this issue (unless deferred)

9. **Display final summary**:
   ```
   Logged <rounded_time> to <KEY>: <summary>
   Total elapsed: <actual_minutes>m → logged as <rounded_time>
   ```

10. **PR and branch cleanup prompt** — Check the current git branch:
    ```bash
    git rev-parse --abbrev-ref HEAD
    ```
    If the current branch is a feature branch (contains the issue key or starts with `feature/`), prompt:
    ```
    Work on <KEY> is logged. Would you like to:
      1. Open a PR now  — push branch and run: gh pr create --title "<KEY>: <summary>" --body "..."
      2. Keep working   — stay on this branch (more commits coming)
      3. Switch to main — git checkout main (no PR yet)
    ```
    **Autonomy A/B**: Auto-suggest option 1 and execute if on a feature branch with unpushed commits.
    **Autonomy C**: Always present the 3-option prompt above.

    If option 1 is chosen, create the PR with:
    - Title: `<KEY>: <enriched summary>`
    - Body: bullet list of files changed + commands run from `rawFacts`
    - Then switch to main: `git checkout main`
