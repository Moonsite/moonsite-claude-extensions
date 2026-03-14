# Changelog

All notable changes to **moonsite-claude-extensions** are documented here.

Format: each release groups changes by plugin. Versions follow [SemVer](https://semver.org/).

---

## [1.3.5] — 2026-03-14

### md-html-docs 2.5.1
- Fix TOC sidebar showing raw markdown formatting instead of clean text

## [1.3.4] — 2026-03-14

### md-html-docs 2.5.0
- Add document settings panel with slide-out UI (Typography, Density, Colors, More tabs)
- Dark mode support with full element restyling
- Font presets (Noto, IBM Plex, Inter/Heebo, Serif, Monospace) with dynamic Google Fonts loading
- Density presets (compact, comfortable, spacious) with live preview
- Per-document and global default settings via localStorage persistence
- CSS variables for all typography, spacing, and color values
- Responsive bottom-sheet on mobile, RTL-aware layout
- Configurable via `enableSettings` in `.claude/md-html-docs.json`

### moonsite-skills 1.0.4
- Add per-plugin CHANGELOG.md generation to `/publish` skill (Step 5.5)
- Update `/bump-release` skill to maintain per-plugin changelogs

### jira-autopilot 4.1.1
- Add per-plugin CHANGELOG.md with full version history backfill

### persona-panel 1.2.3
- Add per-plugin CHANGELOG.md with full version history backfill

## [1.3.3] — 2026-03-14

### jira-autopilot 4.1.0
- Add statusLine command script for rich Claude Code status bar (git, Jira, context, cost segments)
- Add setup step for status bar configuration

## [1.3.2] — 2026-03-13

### persona-panel 1.2.2
- Add Gemini provider support (review, synthesize, call-llm)
- Add persistent cost logging to `~/.persona-panel/cost-log.jsonl`
- Add `/persona-costs` command for cost breakdown
- Fix HTML-instead-of-JSON API error handling
- `loadEnv()` now cascades: project `.env` -> cwd `.env` -> `~/.env`

### moonsite-skills 1.0.3
- Add `/publish` skill for marketplace-wide releases
- Sync plugin.json version field

## [1.3.1] — 2026-03-12

### persona-panel 1.0.1
- Add save/load persona commands for reusable persona sets
- Add review-all command for batch document review
- Fix OpenAI max_tokens parameter for GPT-5.4
- Handle non-interactive mode in discuss.mjs for Claude Code Bash tool

## [1.3.0] — 2026-03-12

### persona-panel 1.0.0
- Initial release: AI persona panel plugin
- Synthesize expert personas from sources (URLs, files, topics)
- Multi-persona document/code review with scoring
- Live multi-persona discussions with moderator support

## [1.2.16] — 2026-03-12

### md-html-docs 2.3.15
- Add `released` field to SKILL.md frontmatter
- Display skill version and release date banner on invocation

## [1.2.15] — 2026-03-12

### md-html-docs 2.3.14
- Merge LTR/RTL templates into unified template with live direction toggle
- Direction toggle button in header toolbar (persists to localStorage)
- Bilingual UI labels (Back to Index, Narrow/Wide/Full, Contents) switch with direction
- Both font families (Inter + Heebo/Rubik/Assistant) and hljs themes loaded upfront
- `[dir="rtl"]` CSS overrides for all directional properties (sidebar, TOC arrows, blockquotes, code, tables)
- Header toolbar redesign: "Back to Index" with SVG arrow, pill-shaped layout switcher

## [1.2.14] — 2026-03-11

### md-html-docs 2.3.13
- Fix LTR sidebar arrow position: move from right side (::after) to left side (::before)

## [1.2.13] — 2026-03-11

### md-html-docs 2.3.12
- Redesign sidebar TOC: CSS triangle arrows, flexbox alignment, tighter spacing
- Strip "Table of Contents" / "תוכן עניינים" headings from body and TOC
- Consistent h2/h3 indentation in both LTR and RTL templates

## [1.2.12] — 2026-03-11

### md-html-docs 2.3.11
- No code changes (version alignment)

### moonsite-skills 1.0.2
- Add CHANGELOG.md auto-update step to bump-release skill
- Backfill full CHANGELOG.md from project history

## [1.2.11] — 2026-03-10

### md-html-docs 2.3.10
- Fix duplicate H1 title in doc pages (template header + content body)
- Strip markdown formatting (`**bold**`, `*italic*`) from index card descriptions
- Recursive index generation for intermediate folders with only subfolders
- Checklist rendering: `- [ ]` → HTML checkboxes without bullet markers
- LLM-powered index enrichment workflow documented in SKILL.md
- No-config fallback: use folder name instead of doc title for `projectName`

## [1.2.10] — 2026-03-09

### md-html-docs 2.3.9
- Clickable logo + project name linking to index page
- Doc title in header only visible when body H1 scrolls out of view (IntersectionObserver)
- RTL fix: layout buttons and index link on left side (margin-right:auto)
- Document `projectName` vs `orgName` config in SKILL.md

## [1.2.9] — 2026-03-09

### md-html-docs 2.3.8
- Fix page freeze when adding multiple text-selection notes (two-phase DOM annotation)
- Bigger doc title, rounded-square frosted-glass logo in header

## [1.2.8] — 2026-03-09

### md-html-docs 2.3.7
- Sticky header with doc title, layout switcher, and index link
- MD source line:col references in exported notes

## [1.2.7] — 2026-03-09

### md-html-docs 2.3.6
- Section context for text-selection notes (nearest heading)
- Notes grouped by section in export and panel
- Heading button note states synced with stored notes

## [1.2.6] — 2026-03-09

### md-html-docs 2.3.5
- Document metadata: YAML frontmatter and project config documentation in SKILL.md
- Per-file/folder overrides via `.claude/md-html-docs.json`

## [1.2.5] — 2026-03-09

### jira-autopilot 4.0.4
- Fix hooks.json schema: migrate from flat array to record-by-event-name format

## [1.2.4] — 2026-03-09

### md-html-docs 2.3.4
- Rewrite local `.md` links to `.html` during conversion

## [1.2.3] — 2026-03-08

### md-html-docs 2.3.3
- Add D2 diagram language support via Kroki.io rendering API

## [1.2.2] — 2026-03-08

### md-html-docs 2.3.2
- Redesign index page: list-row layout with colored stripes, language/folder badges, description truncation

## [1.2.1] — 2026-03-08

### md-html-docs 2.3.1
- Fix `e.target.closest` guard for synthetic events in notes JS
- Fix index page URL paths: add trailing-slash redirect script

## [1.2.0] — 2026-03-08

### md-html-docs 2.3.0
- Text-selection inline sticky notes with localStorage persistence
- Notes panel with export to markdown
- Scroll-spy sidebar (active heading tracking via IntersectionObserver)

### jira-autopilot 4.0.3
- Fix session-start hook initialization

## [1.1.2] — 2026-03-07

### md-html-docs 2.2.2
- Fix layout switcher CSS selectors (compound vs descendant selectors)
- Fluid mode display fix for large screens

## [1.1.1] — 2026-03-07

### md-html-docs 2.2.1
- Fluid mode: sidebar pinned to window edge with `position:fixed`
- Wide mode: bumped from 1100px to 1200px content width
- RTL fluid: sidebar correctly pinned to right edge

## [1.1.0] — 2026-03-07

### md-html-docs 2.2.0
- Color presets (blue/green/purple/orange) and config-driven accent colors
- RTL index template for Hebrew-majority folders
- Preserve custom index files marked with `<!-- custom-index -->`
- Support `subtitle` config for index header

## [1.0.8] — 2026-03-07

### md-html-docs 2.1.3
- Layout switcher moved into site header
- Full width mode: 100% screen width
- Rich index cards with accent bars, icons, and metadata

## [1.0.7] — 2026-03-05

### md-html-docs 2.1.2
- Fix RTL sidebar appearing on wrong side
- Add index page link in sidebar
- Rewrite index template with gradient header
- Fix header defaults: use doc title when no config

## [1.0.6] — 2026-03-05

### md-html-docs 2.1.1
- Post-update patch after Mermaid v11 switch

## [1.0.5] — 2026-03-05

### md-html-docs 2.1.0
- Switch diagrams to Mermaid v11 Neo + ELK layout + Ocean Blue palette
- Rich templates: gradient header, logo circle, highlight.js, card-style sidebar
- `load_config()` for project branding via `.claude/md-html-docs.json`
- Dark code blocks (vs2015) for LTR, light (vs) for RTL
- Client-side diagram rendering for mermaid, dot, nomnoml
- Regenerate-all command

## [1.0.3] — 2026-03-05

### jira-autopilot 4.0.2
- Add `/dashboard` command for cross-project status
- Show issue summary in start-work conflict prompt

## [1.0.2] — 2026-03-05

### jira-autopilot 4.0.1
- Bug fixes post-v4 release

### md-html-docs 2.0.1
- Generalize plugin: auto language detection, zero-dependency converter

### moonsite-skills 1.0.1
- Add merge step to bump-release skill

## [1.0.1] — 2026-03-04

### jira-autopilot 4.0.0
- Full rewrite: Python → shell scripts, MCP-first with REST fallback
- Multi-issue tracking with time per issue
- Automatic work documentation via PostToolUse hook
- Commands: `/jira-setup`, `/jira-start`, `/jira-stop`, `/jira-status`, `/jira-approve`, `/jira-summary`

### md-html-docs 2.0.0
- Generalize from Hebrew-only to universal markdown-to-HTML converter
- Auto-detect Hebrew (RTL) vs English (LTR) content
- Zero-dependency Python converter with embedded templates

### moonsite-skills 1.0.0
- Initial release: `/bump-release` and `/moonsite-spec` skills

## Pre-1.0 — jira-autopilot v3.x (2026-02-16 → 2026-02-28)

### 3.20.0 (2026-02-28)
- Validate project keys against Jira API

### 3.19.0–3.19.1 (2026-02-25)
- Auto-setup from global credentials
- Fix auto-setup for non-git directories

### 3.14.0 (2026-02-20)
- Fully autonomous Jira workflow (auto-create issues)

### 3.10.0–3.13.0 (2026-02-19–20)
- logLanguage setting for worklog descriptions
- Multiple minor improvements and fixes

### 3.1.0–3.9.0 (2026-02-18–19)
- Task-level worklogging
- Plan mode time logging
- Fix session-end double-posting worklogs
- 14+ bug fixes from plugin testing

### 3.0.0 (2026-02-18)
- Rewrite as jira-autopilot v3 with autonomous logging

### 2.0.0 (2026-02-16)
- Rewrite as jira-auto-issue with automatic work tracking

### 1.0.0 (2026-02-16)
- Initial release: Jira tracker plugin for Claude Code
