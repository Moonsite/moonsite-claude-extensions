# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Claude Code **plugin** called **jira-autopilot**. It provides automatic Jira issue tracking, work documentation, and time logging via hooks and slash commands. Every task done in Claude Code is tracked, documented, and logged to Jira with minimal manual intervention.

## Architecture

The plugin has four layers:

1. **Plugin manifest** (`.claude-plugin/marketplace.json` + `plugins/jira-autopilot/.claude-plugin/plugin.json`) — registers the plugin with Claude Code.

2. **Slash commands** (`plugins/jira-autopilot/commands/*.md`) — markdown files with YAML frontmatter:
   - `/jira-setup` — configure Jira connection with guided UX
   - `/jira-start` — start tracking a Jira task (create new or link existing)
   - `/jira-stop` — stop tracking and log time to Jira
   - `/jira-status` — show all active issues with time breakdown
   - `/jira-approve` — review and approve pending work items as Jira issues
   - `/jira-summary` — show today's work summary across all sessions

3. **Hook handlers** (`plugins/jira-autopilot/hooks-handlers/`) — shell scripts triggered by Claude Code lifecycle events:
   - `session-start-check.sh` (SessionStart) — init session, detect issue from branch, migrate old state
   - `post-tool-use.sh` (PostToolUse, async) — log each tool call to activity buffer
   - `pre-tool-use.sh` (PreToolUse) — suggest issue key in git commit messages
   - `stop.sh` (Stop) — drain activity buffer into work chunks, suggest issue creation
   - `session-end.sh` (SessionEnd) — log time + post work summary to Jira, archive session

4. **REST API client** (`plugins/jira-autopilot/hooks-handlers/jira-rest.sh`) — curl-based Jira Cloud API functions as fallback when MCP tools are unavailable.

## Hook lifecycle

```
SessionStart → init session, detect branch, load config
     ↓
PostToolUse (async) → log each tool call to activity buffer
     ↓
Stop → drain buffer into work chunk, suggest issue creation if none active
     ↓
PreToolUse → inject issue key into git commit messages
     ↓
SessionEnd → log time + post work summary to each Jira issue
```

## State files

- **`.claude/jira-autopilot.json`** — project config (committed): projectKey, cloudId, branchPattern, etc.
- **`.claude/jira-autopilot.local.json`** — credentials (gitignored): email, apiToken, baseUrl
- **`.claude/jira-session.json`** — runtime session state (gitignored): active issues, work chunks, activity buffer
- **`.claude/jira-sessions/`** — archived sessions (gitignored)

## Key design decisions

- **No npm/node dependencies.** Shell scripts use `python3 -c` (available on macOS) for JSON parsing via the `json_get()` helper.
- **MCP-first, REST-fallback.** Commands try Atlassian MCP tools first, fall back to `jira-rest.sh` curl-based API calls.
- **Multi-issue tracking.** Session state supports multiple active issues with time tracking on each.
- **Automatic work documentation.** PostToolUse hook logs activities; Stop hook creates work chunks; SessionEnd posts summaries to Jira.

## Working on this code

- Edit markdown command files to change slash command behavior (prompt, allowed tools, steps).
- Edit shell scripts in `hooks-handlers/` to change hook logic.
- Test hook scripts manually: `bash plugins/jira-autopilot/hooks-handlers/session-start-check.sh` from a git repo with `.claude/jira-autopilot.json` configured.
- Test REST client: `source plugins/jira-autopilot/hooks-handlers/jira-rest.sh && jira_load_creds . && jira_test_connection`
- The `{key}` placeholder in `branchPattern`/`commitPattern` config fields is replaced with the actual `projectKey` at runtime by the command prompts.
