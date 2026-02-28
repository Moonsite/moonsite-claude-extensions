# jira-autopilot Release Notes

Version 3.19.1:
• Fixed find_project_root() to trust CLAUDE_PROJECT_DIR directly (no .git required)
• Fixed auto-setup to work in non-git directories (empty projectKey, no branch/commit patterns)

Version 3.19.0:
• Auto-create project config when global Jira credentials exist
• Detect project key from git history (commits + branches)
• Use CLAUDE_PROJECT_DIR in find_project_root() for reliable hook execution

Version 3.18.0:
• /jira-stop now handles unattributed work — no longer bails when currentIssue is null
• New build-unattributed CLI command for orphaned work chunks

Version 3.17.0:
• AI-enriched worklogs: auto-posted worklogs get concise descriptions via Anthropic Haiku (periodic flushes, session-end, task/planning time). Requires anthropicApiKey in local config; graceful fallback without it
• API call logging: all Jira + Anthropic HTTP calls logged to ~/.claude/jira-autopilot-api.log (always-on, 1MB rotation)

Version 3.16.1:
• Fixed session corruption from concurrent hooks via atomic save_session (tempfile + os.replace)
• Fixed load_session crash on corrupt JSON — now returns {} instead of crashing
• Fixed inflated worklogs (e.g. 793min) by removing wallclock fallback in session-end
• Capped build_worklog at 4h (MAX_WORKLOG_SECONDS)
• Session-start now prunes stale issues older than 24h with zero work chunks

Version 3.16.0:
• Always-on work monitoring: all tool activity is captured even without an active Jira issue
• Retroactive work attribution: orphaned work is assigned when issues are created or detected from branch
• Session-end rescues unattributed work chunks
• Periodic flush handles unattributed work when no active issues
• Added unattributed work section in /jira-approve for handling orphaned worklogs
• Fixed stop.sh blocking — unattributed work now captured silently
• Fixed worklog description falling back to English instead of configured language

Version 3.15.5:
• Fixed build_worklog dropping null-issueKey chunks when sole active issue (orphaned work no longer lost)
• Fixed build_worklog hardcoded Hebrew fallback — now uses configured language
• Fixed empty task subjects: _handle_task_event caches subject from TaskCreate for TaskUpdate lookup
• Fixed statusline showing blank when configured but no session — now shows "ready"
• Fixed version detection picking non-semver files
• Fixed ghost paused issues surviving session-end
• Fixed logLanguage not being enforced in /jira-stop and /jira-approve summaries
• Fixed /jira-status Language field not reading global config fallback

Version 3.15.0:
• Fully autonomous Jira workflow for autonomy A/B: auto-create issues from user prompts with duplicate detection
• New auto-create-issue CLI command; seeds currentIssue from last commit on session start (autonomy A)
• Added [auto] tag and multi-issue count to statusline
• Autonomy A/B: blocking user-prompt-submit messages replaced with silent/notice auto-create
• Autonomy C behavior unchanged
• 32 new tests (180 total passing)

Version 3.14.0:
• Announce jira-autopilot status at every session start via systemMessage
• Plugin fires globally across all Claude Code terminals on the machine

Version 3.13.0:
• Rewrote /jira-status as single shell script — all computation in one python3 call, output printed directly. Zero terminal noise.

Version 3.12.0:
• Human-narrative worklog format: build_worklog produces clean file-list only; Claude replaces with full narrative in /jira-stop
• Explicit format rules in /jira-stop: natural language description, no code/commands, optional file list
• Issue titles in /jira-start now written in logLanguage

Version 3.11.0:
• Added logLanguage setting for worklog descriptions
• get_log_language() reads from project config with fallback to global config, defaults to English
• New /jira-setup step: language selection (English/Hebrew/Russian/Other) with global default option

Version 3.10.0:
• REST-first API with MCP fallback using urllib (no curl dependency)
• New create-issue, get-issue, add-worklog CLI commands in jira_core.py
• Changed API flow: jira_core.py → REST → MCP (was: jira-rest.sh curl → MCP)

Version 3.9.0:
• Fixed plugin version display for non-plugin projects — falls back to latest semver dir in global plugin cache
• Replaced emoji icons with universal Unicode characters (emoji rendered as [?] in some terminals)

Version 3.8.0:
• Fixed periodic flush blocked by empty buffer: _flush_periodic_worklogs was never reached during idle turns
• Added sub-issue enforcement: when an active issue exists and a new task/bug intent is detected, Claude creates a sub-issue via /jira-start before writing code

Version 3.7.0:
• Fixed empty worklog descriptions in Jira: _text_to_adf() emitted empty paragraph nodes for blank lines
• Fixed task and planning worklogs posted with empty subject string — now substitutes readable fallback

Version 3.6.0:
• Intercept time-logging shortcuts (1h, 30m, 2h30m, "log time", etc.) and redirect to /jira-stop
• Prevents Claude from bypassing jira-autopilot workflow when user provides bare time durations

Version 3.5.0:
• Added statusline integration: statusline-command.sh shows current issue, elapsed time, and tracking status in Claude Code's status bar

Version 3.4.0:
• Branch-per-task enforcement: UserPromptSubmit hook detects feature/fix intent and instructs Claude to run /jira-start first
• /jira-start always creates feature/<KEY>-<slug> branch; blocks implementation on main/master/develop
• /jira-stop step 10: PR + branch cleanup prompt (open PR / keep working / switch to main)
• Upgraded pre-tool-use git commit enforcement from plain stdout to structured JSON systemMessage

Version 3.3.0:
• Periodic worklog flushing every worklogInterval minutes (default 15)
• Triggered from Stop hook after each Claude response
• lastWorklogTime tracked in session state

Version 3.2.1:
• Improved debug logging coverage: silent code paths now emit debug logs (branch detection, read-only tool skips, planning triggers, drain-buffer split reasons, API error details)

Version 3.2.0:
• Log planning time to Jira: track time in plan mode and planning-related skills
• EnterPlanMode starts planning timer; ExitPlanMode or first edit ends it
• accuracy >= 8: create Jira sub-issue for planning time
• accuracy < 8: log directly to current/parent issue
• Micro-sessions < 60s are skipped

Version 3.1.1:
• Fixed session-end double-posting: workChunks cleared after posting, startTime reset as fresh watermark
• Long-running sessions no longer create duplicate Jira worklog entries

Version 3.1.0:
• Task-level Jira worklogging: track TaskCreate/TaskUpdate events to time individual tasks
• accuracy >= 8: create Jira sub-issue per task, log worklog to it
• accuracy < 8: log to parent issue with task name as comment
• Micro-tasks < 60s skipped
• Added TaskList, TaskGet, ToolSearch, Skill, Task, and more to READ_ONLY_TOOLS
• Fixed sessionId not assigned on resume (sessions created by /jira-start lacked one)
• Fixed 42-hour phantom worklog: wallclock fallback now guarded against issues with no actual activity

Version 3.0.1:
• **Security**: Sanitize API tokens/credentials from activity buffer — raw tokens were stored in jira-session.json
• Retroactively sanitize credentials in existing sessions on resume
• Skip .claude/ internal files from activity log (noise + security)
• Fixed SessionEnd not posting worklogs to Jira — time was silently dropped with autonomy A/B
• Added post_worklog_to_jira() using urllib.request (stdlib, no deps)
• Fixed migration running on every hook call (moved to session-start only)
• Fixed jira-rest.sh source path resolution for helpers.sh
• Fixed autonomyLevel/accuracy not syncing from config on session resume

Version 3.0.0:
• Complete rewrite as jira-autopilot with autonomous work tracking
• Three autonomy levels: C (conservative), B (balanced), A (fully autonomous)
• Accuracy parameter (1-10) controlling time granularity and sub-issue creation
• New jira_core.py central Python module replacing most shell logic
• Automatic issue type classification (Bug vs Task) with confidence scoring
• Parent issue suggestion with session defaults and recent history
• Idle detection and context-switch detection in drain-buffer
• Work chunk model with needsAttribution flags
• Session archival to .claude/jira-sessions/
• Bug-story linking and component mapping
• Hook scripts converted to thin shell wrappers delegating to jira_core.py
• 45 tests with full coverage

Version 2.0.0:
• Multi-issue tracking with jira-session.json replacing single-issue current-task.json
• REST API client (jira-rest.sh) as fallback when MCP unavailable
• PostToolUse hook (async) to log tool activity to session buffer
• Stop hook to drain buffer into work chunks with pending issue suggestions
• PreToolUse hook to suggest issue key in git commit messages
• SessionEnd hook to log time and post work summaries to Jira
• New /jira-approve command to review and create issues from pending work
• New /jira-summary command for daily aggregated work reporting
• Guided /jira-setup with auto cloud ID fetch and connectivity test
• Renamed from jira-tracker to jira-auto-issue

Version 1.0.0:
• Initial release: Jira tracker plugin for Claude Code
• Automatic Jira issue tracking and time logging via SessionStart hooks
• /jira-setup, /jira-start, /jira-stop, /jira-status slash commands
