---
name: dashboard
description: Cross-project Jira autopilot dashboard — scans all repos and shows aggregated status
allowed-tools: Bash, Read
---

# /dashboard — Cross-Project Jira Autopilot Dashboard

Scan all repos under `~/Source` that have jira-autopilot data and produce an aggregated status report for a given time window.

## Step 1: Parse Time Window

Check if the user provided a time range argument. Common patterns:
- `/dashboard` — defaults to today from 06:00
- `/dashboard today` — today from 06:00
- `/dashboard yesterday` — yesterday 06:00 to today 06:00
- `/dashboard week` or `/dashboard this week` — Monday 06:00 to now
- `/dashboard 2026-03-05` — specific date 06:00 to 23:59
- `/dashboard 2026-03-01 2026-03-05` — date range

Calculate `START_DATE` and `END_DATE` as `YYYY-MM-DD` strings and `START_TS` / `END_TS` as Unix timestamps. For "today", use today's date at 06:00 local time as start, now as end.

```bash
# Example for "today" default:
START_DATE=$(date +%Y-%m-%d)
END_DATE=$(date +%Y-%m-%d)
START_TS=$(date -j -f "%Y-%m-%d %H:%M:%S" "$START_DATE 06:00:00" +%s 2>/dev/null || date -d "$START_DATE 06:00:00" +%s)
END_TS=$(date +%s)
```

## Step 2: Discover Repos

Find all repos under `~/Source` that have jira-autopilot config or session archives:

```bash
python3 -c "
import os, json, glob

source_dir = os.path.expanduser('~/Source')
repos = {}

# Find repos with jira-autopilot.json config
for config_path in glob.glob(os.path.join(source_dir, '*/.claude/jira-autopilot.json')) + \
                   glob.glob(os.path.join(source_dir, '*/*/.claude/jira-autopilot.json')) + \
                   glob.glob(os.path.join(source_dir, '*/*/*/.claude/jira-autopilot.json')):
    repo_root = config_path.rsplit('/.claude/', 1)[0]
    repo_name = os.path.basename(repo_root)
    repos[repo_root] = {'name': repo_name, 'has_config': True}

# Find repos with jira-sessions dir (catches repos without config but with archives)
for sessions_dir in glob.glob(os.path.join(source_dir, '*/.claude/jira-sessions')) + \
                    glob.glob(os.path.join(source_dir, '*/*/.claude/jira-sessions')) + \
                    glob.glob(os.path.join(source_dir, '*/*/*/.claude/jira-sessions')):
    repo_root = sessions_dir.rsplit('/.claude/', 1)[0]
    repo_name = os.path.basename(repo_root)
    if repo_root not in repos:
        repos[repo_root] = {'name': repo_name, 'has_config': False}

print(json.dumps(repos, indent=2))
"
```

Record the list of discovered repo paths.

## Step 3: Gather Data From Each Repo

For each discovered repo, run a single Python script that collects all data:

```bash
python3 -c "
import json, os, sys, time

repo_root = sys.argv[1]
start_date = sys.argv[2].replace('-', '')  # YYYYMMDD
end_date = sys.argv[3].replace('-', '')
start_ts = int(sys.argv[4])
end_ts = int(sys.argv[5])

result = {
    'repo': os.path.basename(repo_root),
    'repo_path': repo_root,
    'project_key': None,
    'autonomy': None,
    'current_session': None,
    'archived_sessions': [],
    'issues': {},
    'total_seconds': 0,
    'session_count': 0,
    'pending_worklogs': [],
    'unattributed_chunks': 0
}

# Read config
config_path = os.path.join(repo_root, '.claude', 'jira-autopilot.json')
if os.path.isfile(config_path):
    try:
        cfg = json.load(open(config_path))
        result['project_key'] = cfg.get('projectKey')
        result['autonomy'] = cfg.get('autonomyLevel')
    except: pass

# Read current session
session_path = os.path.join(repo_root, '.claude', 'jira-session.json')
if os.path.isfile(session_path):
    try:
        sess = json.load(open(session_path))
        now = int(time.time())
        for iss in sess.get('activeIssues', []):
            key = iss.get('issueKey', 'unattributed')
            secs = iss.get('totalSeconds', 0)
            if not iss.get('paused') and iss.get('startTime'):
                secs += now - iss['startTime']
            summary = iss.get('summary', '')
            if key not in result['issues']:
                result['issues'][key] = {'summary': summary, 'seconds': 0, 'sessions': 0, 'files': set()}
            result['issues'][key]['seconds'] += secs
            result['issues'][key]['sessions'] += 1
            result['total_seconds'] += secs
        result['current_session'] = {
            'active_issues': [i.get('issueKey') for i in sess.get('activeIssues', [])],
            'buffer_count': len(sess.get('activityBuffer', [])),
            'pending_count': len([w for w in sess.get('worklogs', []) if w.get('status') == 'pending'])
        }
        result['session_count'] += 1
        # Pending worklogs from current session
        for wl in sess.get('worklogs', []):
            if wl.get('status') in ('pending', 'deferred'):
                result['pending_worklogs'].append({
                    'issueKey': wl.get('issueKey'),
                    'seconds': wl.get('timeSpentSeconds', 0)
                })
        # Work chunks for files
        for chunk in sess.get('workChunks', []):
            key = chunk.get('issueKey', 'unattributed')
            files = chunk.get('files', [])
            if key and key in result['issues']:
                result['issues'][key]['files'].update(files)
            elif not key:
                result['unattributed_chunks'] += 1
    except: pass

# Scan archived sessions
sessions_dir = os.path.join(repo_root, '.claude', 'jira-sessions')
if os.path.isdir(sessions_dir):
    for f in sorted(os.listdir(sessions_dir)):
        if not f.endswith('.json'):
            continue
        date_part = f[:8]
        if not (start_date <= date_part <= end_date):
            continue
        try:
            data = json.load(open(os.path.join(sessions_dir, f)))
            result['session_count'] += 1
            for iss in data.get('activeIssues', []):
                key = iss.get('issueKey', 'unattributed')
                secs = iss.get('totalSeconds', 0)
                summary = iss.get('summary', '')
                if key not in result['issues']:
                    result['issues'][key] = {'summary': summary, 'seconds': 0, 'sessions': 0, 'files': set()}
                result['issues'][key]['seconds'] += secs
                result['issues'][key]['sessions'] += 1
                result['total_seconds'] += secs
            for chunk in data.get('workChunks', []):
                key = chunk.get('issueKey', 'unattributed')
                files = chunk.get('files', [])
                if key and key in result['issues']:
                    result['issues'][key]['files'].update(files)
                elif not key:
                    result['unattributed_chunks'] += 1
            for wl in data.get('worklogs', []):
                if wl.get('status') in ('pending', 'deferred'):
                    result['pending_worklogs'].append({
                        'issueKey': wl.get('issueKey'),
                        'seconds': wl.get('timeSpentSeconds', 0)
                    })
        except: pass

# Convert sets to lists for JSON serialization
for k in result['issues']:
    result['issues'][k]['files'] = list(result['issues'][k]['files'])

print(json.dumps(result))
" "$REPO_PATH" "$START_DATE" "$END_DATE" "$START_TS" "$END_TS"
```

Run this for each discovered repo and collect results into a list.

## Step 4: Parse Global Logs

Extract errors from global logs within the time window:

```bash
python3 -c "
import os, re, json, sys

start_date = sys.argv[1]
end_date = sys.argv[2]
errors = []

for log_file in [
    os.path.expanduser('~/.claude/jira-autopilot-debug.log'),
    os.path.expanduser('~/.claude/jira-autopilot-api.log')
]:
    if not os.path.isfile(log_file):
        continue
    log_name = os.path.basename(log_file)
    try:
        with open(log_file) as f:
            for line in f:
                # Format: [YYYY-MM-DD HH:MM:SS] message
                m = re.match(r'\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\] (.*)', line.strip())
                if not m:
                    continue
                date_str, time_str, msg = m.groups()
                if not (start_date <= date_str <= end_date):
                    continue
                lower = msg.lower()
                if any(kw in lower for kw in ['error', 'fail', 'exception', '401', '403', '404', '500', 'timeout']):
                    errors.append({'time': time_str, 'message': msg, 'source': log_name})
    except: pass

print(json.dumps(errors))
" "$START_DATE" "$END_DATE"
```

## Step 5: Render the Report

Using all collected data, render a formatted report:

```
Cross-Project Dashboard: {start_date} {start_time} — {end_label}
══════════════════════════════════════════════════

Overview:
  Repos scanned:    {repo_count}
  Active sessions:  {active_count}
  Total time:       {total_time}
  Issues touched:   {issue_count}

Per-Project Breakdown:
┌─────────────────────┬────────┬──────────┬─────────────────────────────┐
│ Project             │ Time   │ Sessions │ Current Issue               │
├─────────────────────┼────────┼──────────┼─────────────────────────────┤
│ repo-name (KEY)     │ 2h 15m │ 3        │ KEY-42 — Fix sidebar        │
│ other-repo (OTHER)  │ 1h 30m │ 2        │ (none)                      │
└─────────────────────┴────────┴──────────┴─────────────────────────────┘

Issues Detail:
  KEY-42 — Fix sidebar               2h 15m  (3 sessions, 12 files)
  KEY-43 — Add dashboard             1h 30m  (2 sessions, 8 files)

Errors & Exceptions (from logs):
  [10:23:15] API 401 Unauthorized (debug.log)
  [11:45:02] Worklog post failed: KEY-42 (api.log)
  Total: {error_count} errors

Pending Items:
  {pending_count} pending worklogs ({details})
  {unattributed_count} unattributed work chunks
══════════════════════════════════════════════════
```

### Time Formatting

- Under 1 hour: `Xm`
- 1 hour or more: `Xh Ym`
- Zero time: `0m`

### Sorting

- Per-Project table: sorted by time descending
- Issues Detail: sorted by time descending
- Errors: sorted by time ascending

### Empty Sections

- If no errors: omit the "Errors & Exceptions" section
- If no pending items: omit the "Pending Items" section
- If a repo has 0 sessions and 0 time in the window: omit it from the table

## Error Handling

- If no repos found: "No jira-autopilot repos found under ~/Source."
- If no sessions exist for any repo in the period: "No work tracked for this period across any repo."
- If a repo's session files are corrupt: skip them, continue with valid data.
- If global log files don't exist: skip log parsing, omit errors section.
