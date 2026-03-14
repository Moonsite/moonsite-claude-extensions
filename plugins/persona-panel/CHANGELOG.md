# Changelog — persona-panel

All notable changes to **persona-panel** are documented here.

---

## [1.2.3] — 2026-03-14

- Add per-plugin CHANGELOG.md with full version history backfill

## [1.2.2] — 2026-03-13

- Add Gemini provider support (review, synthesize, call-llm)
- Add persistent cost logging to `~/.persona-panel/cost-log.jsonl`
- Add `/persona-costs` command for cost breakdown
- Fix HTML-instead-of-JSON API error handling
- `loadEnv()` now cascades: project `.env` -> cwd `.env` -> `~/.env`

## [1.2.1] — 2026-03-12

- Rewrite persona-discuss to inline orchestration engine
- Replace discuss.mjs with call-llm.mjs for direct API calls
- Add README, resume support, cost tracking, verbose mode

## [1.1.1] — 2026-03-12

- Version alignment bump (no functional changes)

## [1.1.0] — 2026-03-12

- Native Claude Code discussion engine replacing discuss.mjs
- New features: `--final-summary`, `--context`, `--verbose`, `--max-cost`
- Pause/resume via Escape, meta-instructions, state checkpointing
- Let personas decide their own response length (adaptive brevity)
- Add `--length` flag and `/brief` `/normal` `/detailed` runtime commands
- Add token cost monitoring across all persona-panel scripts

## [1.0.1] — 2026-03-12

- Add `/save-persona`, `/load-persona`, `/persona-review-all` commands
- Fix OpenAI `max_tokens` parameter for GPT-5.4 (`max_completion_tokens`)
- Handle non-interactive mode in discuss.mjs for Claude Code Bash tool

## [1.0.0] — 2026-03-12

- Initial release: AI persona panel plugin
- Synthesize expert personas from sources (URLs, files, topics)
- Multi-persona document/code review with scoring
- Live multi-persona discussions with moderator support
- Bundled personas: Boris Cherny (Anthropic), Nate (AI strategy)
- Commands: `/personas`, `/persona-review`, `/persona-discuss`, `/add-persona`, `/remove-persona`
