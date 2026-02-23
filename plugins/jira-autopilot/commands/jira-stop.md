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
   - If session doesn't exist → bail: "No session found. Use /jira-start to begin tracking."
   - If `currentIssue` is set → proceed to step 2 (existing flow).
   - If `currentIssue` is null → check for unattributed work (step 1b).

### Step 1b — Unattributed work flow

Run the unattributed worklog builder:
```bash
python3 <plugin-root>/hooks-handlers/jira_core.py build-unattributed "<project-root>"
```
This returns JSON: `{ "seconds": N, "summary": "...", "rawFacts": {...}, "chunkCount": N, "logLanguage": "..." }`

- If `seconds == 0` → bail: "No active task and no captured work. Use /jira-start to begin tracking."
- If `seconds > 0` → present options based on autonomy level:

**Autonomy C** (default):
```
[jira-autopilot] No active issue, but <formatted_time> of work was captured:
  Files: <file list from rawFacts>

  1. Create new issue and log time  → enter /jira-start create flow, then post worklog
  2. Log to existing issue          → ask for issue key, post worklog
  3. Keep for later (/jira-approve) → save as deferred pendingWorklog
  4. Drop entirely                  → discard
```

Handle each choice:
- **1. Create new issue** — Run the `/jira-start` create flow to create an issue, then post the unattributed worklog to the newly created issue using step 6.
- **2. Log to existing issue** — Ask the user for an issue key, then post the worklog to that issue using step 6.
- **3. Keep for later** — Add to `pendingWorklogs` in session state with `status: "deferred"` and `issueKey: null`. The user can review later with `/jira-approve`.
- **4. Drop entirely** — Discard the unattributed work chunks and exit.

**Autonomy B**: Show summary, auto-create issue via:
```bash
python3 <plugin-root>/hooks-handlers/jira_core.py auto-create-issue "<project-root>" "<summary>"
```
Then post the worklog to the created issue.

**Autonomy A**: Silent — auto-create issue, log time, print one-liner:
```
[jira-autopilot] Auto-created <KEY> and logged <time>
```

After handling the unattributed work, skip to step 8 (update session state) — steps 2-5 are only for the attributed (currentIssue) flow.

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
     "rawFacts": {"files": [...], "commands": [...], "activityCount": 3},
     "logLanguage": "Hebrew"
   }
   ```

3. **Enrich summary** — Write a human-readable description of what was accomplished. **Always read the `logLanguage` field** from the build-worklog JSON output and write the summary in that language.

   **Format rules:**
   - **Write in `logLanguage`** — this is mandatory. If `logLanguage` is `"Hebrew"`, the entire summary must be in Hebrew. If `"Russian"`, in Russian. If `"English"`, in English.
   - Never default to English if `logLanguage` says otherwise
   - Describe the *work done* in natural language — what was the goal, what was changed, what was the outcome
   - Do NOT include raw commands, git hashes, test output, or code snippets
   - Optionally list relevant files/components/pipelines as a short bullet list at the end
   - Keep it concise — 2-4 sentences max + optional file list

   **Good example (Hebrew):**
   > יישמתי לוגיקת פרסום תקופתי של worklogs — כל X דקות מוגדרות מתפרסם worklog אוטומטי ל-Jira.
   > תוקן באג שבו הבאפר הריק גרם לדילוג על הפרסום.
   > קבצים: jira_core.py, test_jira_core.py

   **Good example (English):**
   > Implemented periodic worklog flushing so time is posted automatically every N minutes.
   > Fixed a bug where an empty activity buffer bypassed the flush.
   > Files: jira_core.py, test_jira_core.py

   **Bad example (do NOT do this):**
   > Ran: cd /Users/… && python3 -m pytest tests/ -q 2>&1 | tail -20. 143 tool calls.

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

6. **Post worklog to Jira** — Try REST first:
   ```bash
   python3 <plugin-root>/hooks-handlers/jira_core.py add-worklog \
     "<project-root>" "<ISSUE_KEY>" <total_seconds> "<enriched_summary>"
   ```
   If REST fails (no credentials), fall back to MCP: `mcp__atlassian__addWorklogToJiraIssue` (load via ToolSearch).

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
