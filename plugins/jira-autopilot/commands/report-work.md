---
name: report-work
description: Generate a periodic work report for Jira issues
allowed-tools: Bash, Read, Write, ToolSearch
---

# /report-work — Generate Periodic Work Report

Generate a detailed work report spanning a configurable time period. Unlike `/work-summary` (today only), this command can produce reports across multiple days, suitable for weekly standups, sprint reviews, or manager reports.

## Path Resolution

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
CLI="python3 $PLUGIN_ROOT/hooks-handlers/jira_core.py"
```

---

## Step 1: Determine Report Period

Check if the user provided a time range argument. Common patterns:
- `/report-work` — defaults to today
- `/report-work today` — today only
- `/report-work week` or `/report-work this week` — current week (Monday to today)
- `/report-work yesterday` — yesterday only
- `/report-work 2026-02-28` — specific date
- `/report-work 2026-02-24 2026-03-01` — date range

If no argument or ambiguous, ask the user:
```
What period should the report cover?
- Today
- This week (Mon-today)
- Last 7 days
- Custom date range
```

Calculate the start and end dates as `YYYY-MM-DD` strings.

## Step 2: Gather Session Data

### Current Session

```bash
$CLI get-session "$PROJECT_ROOT"
```

Include only if today falls within the report period.

### Archived Sessions

Scan all files in `$PROJECT_ROOT/.claude/jira-sessions/`:

```bash
ls "$PROJECT_ROOT/.claude/jira-sessions/"*.json 2>/dev/null
```

Filter sessions whose `sessionId` date prefix falls within the report period. Session IDs are formatted as `YYYYMMDD-HHMMSS`.

```bash
python3 -c "
import json, os, sys
sessions_dir = '$PROJECT_ROOT/.claude/jira-sessions'
start_date = '$START_DATE'.replace('-', '')
end_date = '$END_DATE'.replace('-', '')
results = []
if os.path.isdir(sessions_dir):
    for f in sorted(os.listdir(sessions_dir)):
        if f.endswith('.json'):
            date_part = f[:8]
            if start_date <= date_part <= end_date:
                try:
                    data = json.load(open(os.path.join(sessions_dir, f)))
                    results.append(data)
                except: pass
print(json.dumps(results))
"
```

## Step 3: Aggregate Across Sessions

For each session in the report period, aggregate:

- **Issues worked on:** unique issue keys with summaries.
- **Time per issue per day:** daily breakdown of time spent.
- **Total time per issue:** sum across all days.
- **Files per issue:** union of all files from work chunks.
- **Activities per issue:** total tool call count.
- **Worklogs posted:** count and total time of posted worklogs.
- **Pending/failed worklogs:** items that still need attention.

Also compute:
- **Total sessions:** count of sessions in period.
- **Total time:** sum of all issue times.
- **Busiest day:** day with most tracked time.
- **Most active issue:** issue with most time.

## Step 4: Build the Report

Generate a structured report:

```
Work Report: {start_date} to {end_date}
{'=' * 50}

Overview:
  Period:     {start_date} — {end_date} ({N} days)
  Sessions:   {session_count}
  Total time: {total_time}
  Issues:     {issue_count}

Daily Breakdown:
  Mon 2026-02-24:  2h 15m  (3 issues)
  Tue 2026-02-25:  4h 30m  (5 issues)
  Wed 2026-02-26:  1h 45m  (2 issues)
  ...

Issues Detail:
  KEY-42 — Fix login crash
    Total time: 3h 15m across 4 sessions
    Days active: Mon, Tue, Wed
    Files: src/auth.ts, src/login.tsx, +3 more
    Worklogs: 3 posted (3h), 1 pending (15m)

  KEY-43 — Add user dashboard
    Total time: 1h 30m across 2 sessions
    Days active: Tue, Wed
    Files: src/dashboard.tsx, src/api/users.ts
    Worklogs: 2 posted (1h 30m)

Pending Items:
  1 pending worklog (KEY-42, 15m)
  2 unattributed work entries (30m total)

{'=' * 50}
```

### Time Formatting

- Under 1 hour: `Xm`
- 1 hour or more: `Xh Ym`

### File Lists

Show up to 8 files per issue, "+N more" for overflow.

## Step 5: Offer Export Options

Ask the user what to do with the report:

1. **Display only** — just show the report (already done).
2. **Post to Jira** — post a summary comment to each issue listed in the report.
3. **Save to file** — write the report to a file (e.g. `work-report-{date}.md`).

### If Post to Jira:

For each issue in the report:

```bash
$CLI add-comment "$PROJECT_ROOT" "ISSUE_KEY" "REPORT_COMMENT"
```

The comment should include only the portion of the report relevant to that issue:
- Time worked in the report period.
- Files changed.
- Sessions count.
- Written in the configured `logLanguage`.

### If Save to File:

```bash
REPORT_FILE="$PROJECT_ROOT/work-report-${END_DATE}.md"
```

Write the full report as a markdown file.

---

## Error Handling

- If no config exists: tell the user to run `/jira-setup` first.
- If no sessions exist for the period: "No work tracked for this period."
- If archived session files are corrupt: skip them, continue with valid data.
- If Jira API fails during comment posting: inform the user, continue with other issues.
- If no `jira-sessions` directory exists: only use the current session (if within period).
