---
description: Show persona panel cost breakdown — today, by project, by persona, or all time
argument-hint: [today|project|all]
---

# Persona Costs

Show cost breakdown from the persona panel cost logs.

The user's arguments are in `$ARGUMENTS`. If empty, default to `today`.

## Step 1: Read Cost Logs

Two log files exist (both are JSONL — one JSON object per line):

- **Global log**: `$HOME/.persona-panel/cost-log.jsonl` — all costs across all projects
- **Project log**: `.claude/persona-panel-costs.jsonl` — costs for current project only

Read the appropriate log based on the argument:
- `today` → read global log, filter to today's date
- `project` → read project log (all time)
- `all` → read global log (all time)

If the log file doesn't exist, inform the user that no costs have been recorded yet.

Each line is a JSON object with these fields:
```json
{"ts":"2026-03-13T14:22:00.000Z","project":"my-repo","action":"review","persona":"nate","provider":"openai","model":"gpt-4.1","in":1200,"out":850,"cost":0.0092}
```

## Step 2: Aggregate and Display

Parse all lines and compute aggregates. Display a report with these sections:

### Summary
Show total cost, total calls, total tokens (in/out).

### By Day (if `all` or `project`)
Table showing date, number of calls, and total cost per day. Most recent first. Limit to last 30 days.

### By Project (if `today` or `all`)
Table showing project name, number of calls, and total cost.

### By Persona
Table showing persona name, provider/model, number of calls, and total cost.

### By Action
Table showing action type (review/synthesize/discuss), number of calls, and total cost.

### Recent Calls (last 10)
Table showing timestamp, persona, action, model, tokens, and cost for the 10 most recent entries.

## Formatting

- Use markdown tables for all breakdowns
- Format costs as `$X.XXXX`
- Format token counts with locale separators (e.g., `1,200`)
- If total cost is $0, mention that pricing may be unavailable for some models
