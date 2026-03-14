# Changelog — jira-autopilot

All notable changes to **jira-autopilot** are documented here.

---

## [4.1.1] — 2026-03-14

- Add per-plugin CHANGELOG.md with full version history backfill

## [4.1.0] — 2026-03-14

- Add statusLine command script for rich Claude Code status bar with git, Jira, context, and cost segments
- Add setup step for status bar configuration

## [4.0.4] — 2026-03-09

- Fix hooks.json schema: use record-by-event format instead of flat array

## [4.0.3] — 2026-03-08

- Fix session-start branch auto-detection

## [4.0.2] — 2026-03-05

- Add `/dashboard` command for cross-project Jira autopilot status
- Show issue summary alongside key in active task conflict dialog

## [4.0.1] — 2026-03-05

- Bug fixes post-v4 release

## [4.0.0] — 2026-03-01

- Full rewrite: Python + shell scripts, MCP-first with REST fallback
- Multi-issue tracking with time per issue
- Automatic work documentation via PostToolUse hook
- Slash commands: `/jira-setup`, `/jira-start`, `/jira-stop`, `/jira-status`, `/jira-approve`, `/jira-summary`, `/jira-report`
- Core Python module: config, sessions, atomic writes, logging
- REST API client, session-end handler, auto-create, pre-tool-use hook
- TDD test suite for core logic and API client

## Pre-4.0 — v3.x (2026-02-16 to 2026-02-28)

### 3.20.0 (2026-02-28)
- Validate project keys against Jira API
- Auto-setup validates git-detected keys; phantom keys become empty

### 3.19.1 (2026-02-26)
- Fix auto-setup for non-git directories

### 3.19.0 (2026-02-26)
- Auto-create project config when global Jira credentials exist
- Detect project key from git history (commits + branches)

### 3.17.0 (2026-02-22)
- AI-enriched worklogs via Anthropic Haiku
- API call logging to `~/.claude/jira-autopilot-api.log`

### 3.16.1 (2026-02-22)
- Fix session corruption via atomic save with tempfile + os.replace
- Cap worklogs at 4h to prevent inflated entries
- Prune stale issues older than 24h with zero work chunks

### 3.16.0 (2026-02-21)
- Always-on work monitoring
- Unattributed work handling in jira-approve
- Retroactive work attribution via `_claim_null_chunks`
- Session-end rescues unattributed null-issueKey work chunks
- Periodic flush handles unattributed work when no active issues
- Stop hook captures unattributed work silently (never blocks)

### 3.15.5 (2026-02-21)
- Fix build_worklog to include null-issueKey chunks when sole active issue
- Language-aware fallback worklog summary
- Cache task subject from TaskCreate for TaskUpdate lookup

### 3.15.0 (2026-02-20)
- Fully autonomous Jira workflow (autonomy A/B auto-create)
- Auto-create issues from commit context
- Statusline shows `[auto]` tag and multi-issue count
- Fix statusline for configured-but-no-session state
- Fix ghost paused issues at session-end
- Enforce logLanguage in jira-stop and jira-approve summaries

### 3.14.0 (2026-02-20)
- Announce jira-autopilot status at every session start via systemMessage

### 3.13.0 (2026-02-20)
- Rewrite jira-status as single shell script (zero terminal noise)

### 3.12.0 (2026-02-20)
- Human-narrative worklog format in configured language
- Clean file-list summaries (basename, up to 8 files)

### 3.11.0 (2026-02-19)
- logLanguage setting for worklog descriptions
- Language selection in jira-setup (English/Hebrew/Russian/Other)

### 3.10.0 (2026-02-19)
- REST-first API with MCP fallback
- Add create-issue, get-issue, add-worklog CLI commands

### 3.9.0 (2026-02-19)
- Fix plugin version display from global cache for non-plugin projects
- Replace emoji icons with universal Unicode characters

### 3.8.0 (2026-02-19)
- Fix periodic flush blocked by empty buffer
- Enforce sub-issue creation when active issue exists and new task detected

### 3.7.0 (2026-02-19)
- Fix empty worklog descriptions (skip blank ADF paragraph nodes)
- Fallback worklog comment when description is empty

### 3.6.0 (2026-02-19)
- Intercept time-logging shortcuts and redirect to `/jira-stop`

### 3.5.0 (2026-02-19)
- Enforce branch-per-task and ticket discipline
- UserPromptSubmit hook detects feature/fix intent
- Unconditional branch creation in jira-start
- PR + branch cleanup prompt in jira-stop

### 3.4.0 (2026-02-19)
- Enforce branch-per-task discipline with pre-tool-use systemMessage

### 3.3.0 (2026-02-19)
- Periodic worklog flushing every worklogInterval minutes

### 3.2.1 (2026-02-19)
- Improve debug logging coverage in jira_core

### 3.2.0 (2026-02-19)
- Log planning time to Jira (plan mode + planning skills)

### 3.1.1 (2026-02-19)
- Fix session-end double-posting Jira worklogs

### 3.1.0 (2026-02-18)
- Task-level worklogging
- Add Task tool to READ_ONLY_TOOLS
- Fix 7 bugs found during plugin testing
- Fix 4 bugs found during plugin testing
- Fix jira-start: always show 'Create new parent' option
- Fix jira-setup: ask base URL as plain text, not menu
- Fix jira-setup double-prompt on project key selection
- Fix hooks.json schema: add nested hooks arrays

### 3.0.0 (2026-02-18)
- Rewrite as jira-autopilot v3 with autonomous logging

### 2.0.0 (2026-02-16)
- Rewrite as jira-auto-issue with automatic work tracking

### 1.0.0 (2026-02-16)
- Initial release: Jira tracker plugin for Claude Code
