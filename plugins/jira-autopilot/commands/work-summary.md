---
name: work-summary
description: Show today's work summary across all sessions and Jira issues
allowed-tools: Bash, Read, ToolSearch
---

# /work-summary — Today's Work Summary

Aggregate and display a summary of all work done today, across the current session and all archived sessions from today.

## Path Resolution

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
CLI="python3 $PLUGIN_ROOT/hooks-handlers/jira_core.py"
```

---

## Step 1: Gather Session Data

### Current Session

```bash
$CLI get-session "$PROJECT_ROOT"
```

### Archived Sessions from Today

Read all files in `$PROJECT_ROOT/.claude/jira-sessions/` and filter for today's date.

Session files are named `<sessionId>.json` where sessionId typically starts with the date (e.g. `20260301-123456.json`).

```bash
TODAY=$(date +%Y%m%d)
for f in "$PROJECT_ROOT/.claude/jira-sessions/"${TODAY}*.json; do
  [ -f "$f" ] && cat "$f"
done
```

Alternatively, use the CLI if available:

```bash
$CLI daily-summary "$PROJECT_ROOT"
```

## Step 2: Aggregate Data

Across all sessions (current + archived), aggregate:

- **Issues worked on:** unique issue keys with summaries.
- **Time per issue:** sum of `totalSeconds` from each session's `activeIssues`, plus time from posted worklogs.
- **Files per issue:** union of files from work chunks attributed to each issue.
- **Activities per issue:** count of activities from work chunks.
- **Pending worklogs:** worklogs with status `"pending"` or `"deferred"` across all sessions.
- **Unattributed work:** worklogs with null `issueKey` across all sessions.
- **Total time:** sum of all issue times.

## Step 3: Display Summary

Present a formatted summary report:

```
Today's Work Summary ({date})
{'=' * 40}

Total time tracked: {total_time}
Issues worked on:   {issue_count}
Sessions:           {session_count}

Issues:
  KEY-42 — Fix login crash
    Time:       1h 30m
    Files:      src/auth.ts, src/login.tsx, tests/auth.test.ts
    Activities: 24 tool calls
    Worklogs:   1 posted (30m), 1 pending (1h)

  KEY-43 — Add user dashboard
    Time:       45m
    Files:      src/dashboard.tsx, src/api/users.ts
    Activities: 12 tool calls
    Worklogs:   1 posted (45m)

  (unattributed)
    Time:       15m
    Files:      README.md, package.json
    Activities: 5 tool calls

{'=' * 40}
Pending:  2 worklogs need review (/approve-work)
Deferred: 1 worklog saved for later
```

### Time Formatting

- Under 1 hour: `Xm` (e.g. "45m")
- 1 hour or more: `Xh Ym` (e.g. "1h 30m")
- Zero time: `0m`

### File Lists

Show up to 8 file names per issue. If more than 8, show the first 7 and "+N more":
```
Files: src/a.ts, src/b.ts, src/c.ts, +5 more
```

## Step 4: Offer to Post Summary to Jira

Ask the user: "Post this summary as a comment to each Jira issue?"

If yes, for each issue that has a valid key:

```bash
$CLI add-comment "$PROJECT_ROOT" "ISSUE_KEY" "COMMENT_TEXT"
```

The comment should contain:
- Date
- Time worked on this specific issue
- Files changed
- Activity count
- Written in the configured `logLanguage`

Format as a concise Jira comment (not the full daily report — just the portion relevant to that issue).

If posting fails for any issue, inform the user but continue with other issues.

If the user declines, skip posting.

---

## Error Handling

- If no config exists: tell the user to run `/jira-setup` first.
- If no session and no archives exist: "No work tracked today. Start with `/start-work`."
- If archived session files are corrupt: skip them, log a warning, continue with valid data.
- If Jira API fails during comment posting: inform the user, continue with other issues.
