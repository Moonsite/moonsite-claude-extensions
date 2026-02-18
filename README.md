# jira-autopilot

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin that automatically tracks, documents, and logs your work to Jira. Every task done in Claude Code gets captured — files changed, time spent, work summaries — and posted to your Jira board with minimal manual intervention.

## Why

Adding Jira instructions to `CLAUDE.md` works until Claude forgets them. This plugin uses **hooks** and **commands** to make the workflow fully automatic:

- **5 lifecycle hooks** track your work in real-time (tool activity, time, file changes)
- **6 slash commands** for setup, tracking, approvals, and daily summaries
- **REST API fallback** when Atlassian MCP tools aren't available
- **Multi-issue tracking** with automatic time allocation
- At session end, time is logged and work summaries are posted to Jira automatically

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed
- A Jira Cloud project
- Jira API token ([create one here](https://id.atlassian.com/manage-profile/security/api-tokens))
- Optional: [Atlassian MCP server](https://www.npmjs.com/package/@anthropic/mcp-atlassian) for enhanced functionality (the plugin falls back to REST API if unavailable)

## Installation

### Option 1: Clone to local plugins directory

```bash
git clone https://github.com/Moonsite/claude-code-jira-tracker.git ~/.claude/plugins/local/jira-autopilot
```

### Option 2: Manual download

```bash
mkdir -p ~/.claude/plugins/local/jira-autopilot
cd ~/.claude/plugins/local/jira-autopilot
# Copy plugin files here
```

### Register the plugin

Add to `~/.claude/plugins/installed_plugins.json` inside the `"plugins"` object:

```json
"jira-autopilot@local": [
  {
    "scope": "user",
    "installPath": "/Users/<you>/.claude/plugins/local/jira-autopilot",
    "version": "2.0.0",
    "installedAt": "2026-01-01T00:00:00.000Z",
    "lastUpdated": "2026-01-01T00:00:00.000Z"
  }
]
```

Add to `~/.claude/settings.json` inside `"enabledPlugins"`:

```json
"jira-autopilot@local": true
```

## Quick Start

### 1. Configure your project

Open Claude Code in your project directory and run:

```
/jira-setup
```

The setup wizard will:
1. Ask for your Jira project key (e.g., `PROJ` from `PROJ-123`)
2. Ask for your Jira base URL and auto-fetch the Cloud ID
3. Ask for your email and API token
4. Test the connection to verify credentials
5. Save config files with sensible defaults

### 2. Start working on a task

**Link to an existing Jira issue:**
```
/jira-start MYPROJ-42
```

**Create a new issue and start tracking:**
```
/jira-start Add user export feature
```

This will:
- Create/fetch the Jira issue
- Start a timer
- Create a feature branch if needed (e.g., `feature/MYPROJ-42-add-user-export`)

### 3. Work normally

The plugin works in the background:
- **PostToolUse hook** (async) logs every meaningful tool call — file edits, bash commands, agent spawns
- **PreToolUse hook** reminds you to include the issue key in git commit messages
- **Stop hook** bundles your activity into work chunks when Claude pauses

### 4. Check your progress

```
/jira-status
```

Shows all active issues with per-issue time breakdown, activity counts, and files changed.

### 5. Review untracked work

If you've been working without an active issue, the plugin detects it:

```
/jira-approve
```

Review pending work items and either create new Jira issues, link to existing ones, or skip.

### 6. Finish and log time

```
/jira-stop
```

Calculates elapsed time, rounds up to the nearest increment, logs a worklog to Jira, and posts a work summary comment.

### 7. Daily summary

```
/jira-summary
```

Aggregates all sessions from today, showing time per issue, files changed, and activity counts. Optionally posts the summary to each Jira issue.

## Automatic Behavior

### Session Start
When you start a Claude Code session, the hook automatically:
1. Initializes the session state
2. Detects the active issue from the git branch name
3. Starts the timer
4. Migrates from old `current-task.json` format if found

### Session End
When the session ends, the hook automatically:
1. Calculates time for each active issue
2. Logs time to Jira via REST API
3. Posts a work summary comment with files changed
4. Archives the session data

### During Work
- **PostToolUse** (async, non-blocking): Records file edits, bash commands, and agent spawns
- **Stop**: Bundles the activity buffer into work chunks; suggests creating an issue if work is untracked
- **PreToolUse**: Suggests including the issue key in git commit messages

## Commands Reference

| Command | Description |
|---------|-------------|
| `/jira-setup` | Configure Jira tracking with guided setup wizard |
| `/jira-start <KEY-123>` | Link to existing issue and start timer |
| `/jira-start <summary>` | Create new Jira issue and start timer |
| `/jira-stop` | Log elapsed time and work summary to Jira |
| `/jira-status` | Show all active issues with time breakdown |
| `/jira-approve` | Review untracked work and create/link Jira issues |
| `/jira-summary` | Show today's aggregated work summary |

## Configuration

### Project config (committed, shared with team)

`<project-root>/.claude/jira-autopilot.json`:

```json
{
  "projectKey": "MYPROJ",
  "cloudId": "your-atlassian-cloud-id",
  "enabled": true,
  "branchPattern": "^(?:feature|fix|hotfix|chore|docs)/({key}-\\d+)",
  "commitPattern": "{key}-\\d+:",
  "timeRounding": 15,
  "autoCreate": false
}
```

| Field | Description |
|-------|-------------|
| `projectKey` | Jira project key (e.g., `MYPROJ`) |
| `cloudId` | Atlassian Cloud ID (auto-fetched during setup) |
| `enabled` | Enable/disable tracking for this project |
| `branchPattern` | Regex to extract issue key from branch name. `{key}` → `projectKey` |
| `commitPattern` | Expected pattern in commit messages. `{key}` → `projectKey` |
| `timeRounding` | Round logged time up to nearest N minutes (default: 15) |
| `autoCreate` | Auto-create Jira issues without asking (default: false) |

### Credentials (gitignored, per-developer)

`<project-root>/.claude/jira-autopilot.local.json`:

```json
{
  "email": "you@company.com",
  "apiToken": "your-api-token",
  "baseUrl": "https://company.atlassian.net"
}
```

### Session state (gitignored, auto-managed)

`<project-root>/.claude/jira-session.json` — tracks active issues, work chunks, activity buffer, and pending issues. Managed entirely by hooks. Archived to `.claude/jira-sessions/` on session end.

## Time Rounding

Logged time is always rounded **up** to the nearest increment (default 15 minutes):

| Actual elapsed | Logged as |
|---------------|-----------|
| 1–15 min | `15m` |
| 16–30 min | `30m` |
| 31–45 min | `45m` |
| 46–60 min | `1h` |
| 61–90 min | `1h 30m` |
| 91–120 min | `2h` |

## Plugin Structure

```
jira-autopilot/
├── .claude-plugin/
│   └── plugin.json                 # Plugin metadata
├── commands/
│   ├── jira-setup.md               # /jira-setup — guided configuration
│   ├── jira-start.md               # /jira-start — begin tracking
│   ├── jira-stop.md                # /jira-stop — stop and log time
│   ├── jira-status.md              # /jira-status — multi-issue dashboard
│   ├── jira-approve.md             # /jira-approve — review pending work
│   └── jira-summary.md             # /jira-summary — daily report
├── hooks/
│   └── hooks.json                  # All 5 hook registrations
└── hooks-handlers/
    ├── helpers.sh                  # Shared shell utilities
    ├── jira-rest.sh                # REST API client (curl + Basic auth)
    ├── session-start-check.sh      # SessionStart — init + detect
    ├── post-tool-use.sh            # PostToolUse (async) — log activity
    ├── pre-tool-use.sh             # PreToolUse — commit message hint
    ├── stop.sh                     # Stop — bundle work chunks
    └── session-end.sh              # SessionEnd — log time + archive
```

## Troubleshooting

**"Not configured"** — Run `/jira-setup` in your project directory.

**Hook doesn't fire** — Verify the plugin is registered in both `installed_plugins.json` and `settings.json`. Restart Claude Code.

**"No active Jira task"** — Either run `/jira-start` manually, or name your branch with the issue key: `feature/MYPROJ-42-description`.

**Time not logging at session end** — Ensure `.claude/jira-autopilot.local.json` exists with valid email, apiToken, and baseUrl. Test with: `source hooks-handlers/jira-rest.sh && jira_load_creds . && jira_test_connection`

**MCP tools not available** — The plugin falls back to REST API automatically. Ensure credentials are configured via `/jira-setup`.

## License

MIT
