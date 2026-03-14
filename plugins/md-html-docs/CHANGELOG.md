# Changelog — md-html-docs

All notable changes to **md-html-docs** are documented here.

---

## [2.5.1] — 2026-03-14

- Fix TOC sidebar showing raw markdown formatting (`**`, `_`, etc.) instead of clean text

## [2.5.0] — 2026-03-14

- Add document settings panel with slide-out UI (gear icon in header)
- Four settings tabs: Typography, Density, Colors, More
- Dark mode with full element restyling (header, sidebar, tables, code blocks, blockquotes)
- Font presets: Noto Clean, IBM Technical, Inter/Heebo, Serif Editorial, Monospace
- Dynamic Google Fonts loading for all preset fonts
- Density presets: compact, comfortable, spacious with live preview
- Per-document and global default settings persistence via localStorage
- CSS variables for typography, spacing, and color values (`--body-font`, `--base-size`, `--line-height`, etc.)
- Refactored hardcoded CSS to use CSS variables throughout
- Responsive bottom-sheet panel on mobile (<768px)
- RTL-aware panel layout
- Configurable via `enableSettings` in `.claude/md-html-docs.json` (default: true)

## [2.4.0] — 2026-03-13

- Add configurable fonts for LTR and RTL templates
- Sentence-based RTL detection for improved language detection accuracy
- Per-document direction persistence
- Updated footer label

## [2.3.15] — 2026-03-12

- Add `released` field to SKILL.md frontmatter
- Display skill version and release date banner on invocation

## [2.3.14] — 2026-03-12

- Merge LTR/RTL templates into unified template with live direction toggle
- Direction toggle button in header toolbar (persists to localStorage)
- Bilingual UI labels switch with direction
- Both font families (Inter + Heebo/Rubik/Assistant) and hljs themes loaded upfront
- `[dir="rtl"]` CSS overrides for all directional properties
- Header toolbar redesign: "Back to Index" with SVG arrow, pill-shaped layout switcher

## [2.3.13] — 2026-03-11

- Fix LTR sidebar arrow position: move from right side (::after) to left side (::before)

## [2.3.12] — 2026-03-11

- Redesign sidebar TOC: CSS triangle arrows, flexbox alignment, tighter spacing
- Strip "Table of Contents" headings from body and TOC
- Consistent h2/h3 indentation in both LTR and RTL templates

## [2.3.11] — 2026-03-11

- No code changes (version alignment)

## [2.3.10] — 2026-03-10

- Fix duplicate H1 title in doc pages (template header + content body)
- Strip markdown formatting from index card descriptions
- Recursive index generation for intermediate folders with only subfolders
- Checklist rendering: `- [ ]` renders as HTML checkboxes
- LLM-powered index enrichment workflow documented in SKILL.md
- No-config fallback: use folder name for `projectName`

## [2.3.9] — 2026-03-09

- Clickable logo + project name linking to index page
- Doc title in header only visible when body H1 scrolls out of view (IntersectionObserver)
- RTL fix: layout buttons and index link on left side
- Document `projectName` vs `orgName` config in SKILL.md

## [2.3.8] — 2026-03-09

- Fix page freeze when adding multiple text-selection notes (two-phase DOM annotation)
- Bigger doc title, rounded-square frosted-glass logo in header

## [2.3.7] — 2026-03-09

- Sticky header with doc title, layout switcher, and index link
- MD source line:col references in exported notes

## [2.3.6] — 2026-03-09

- Section context for text-selection notes (nearest heading)
- Notes grouped by section in export and panel
- Heading button note states synced with stored notes

## [2.3.5] — 2026-03-09

- Document metadata: YAML frontmatter and project config documentation in SKILL.md
- Per-file/folder overrides via `.claude/md-html-docs.json`

## [2.3.4] — 2026-03-09

- Rewrite local `.md` links to `.html` during conversion

## [2.3.3] — 2026-03-08

- Add D2 diagram language support via Kroki.io rendering API

## [2.3.2] — 2026-03-08

- Redesign index page: list-row layout with colored stripes, language/folder badges, description truncation

## [2.3.1] — 2026-03-08

- Fix `e.target.closest` guard for synthetic events in notes JS
- Fix index page URL paths: add trailing-slash redirect script

## [2.3.0] — 2026-03-08

- Text-selection inline sticky notes with localStorage persistence
- Notes panel with export to markdown
- Scroll-spy sidebar (active heading tracking via IntersectionObserver)

## [2.2.2] — 2026-03-07

- Fix layout switcher CSS selectors (compound vs descendant selectors)
- Fluid mode display fix for large screens

## [2.2.1] — 2026-03-07

- Fluid mode: sidebar pinned to window edge with `position:fixed`
- Wide mode: bumped from 1100px to 1200px content width
- RTL fluid: sidebar correctly pinned to right edge

## [2.2.0] — 2026-03-07

- Color presets (blue/green/purple/orange) and config-driven accent colors
- RTL index template for Hebrew-majority folders
- Preserve custom index files marked with `<!-- custom-index -->`
- Support `subtitle` config for index header

## [2.1.3] — 2026-03-07

- Layout switcher moved into site header
- Full width mode: 100% screen width
- Rich index cards with accent bars, icons, and metadata

## [2.1.2] — 2026-03-05

- Fix RTL sidebar appearing on wrong side
- Add index page link in sidebar
- Rewrite index template with gradient header
- Fix header defaults: use doc title when no config

## [2.1.1] — 2026-03-05

- Post-update patch after Mermaid v11 switch

## [2.1.0] — 2026-03-05

- Switch diagrams to Mermaid v11 Neo + ELK layout + Ocean Blue palette
- Rich templates: gradient header, logo circle, highlight.js, card-style sidebar
- `load_config()` for project branding via `.claude/md-html-docs.json`
- Dark code blocks (vs2015) for LTR, light (vs) for RTL
- Client-side diagram rendering for mermaid, dot, nomnoml
- Regenerate-all command

## [2.0.1] — 2026-03-05

- Generalize plugin: auto language detection, zero-dependency converter

## [2.0.0] — 2026-03-04

- Generalize from Hebrew-only to universal markdown-to-HTML converter
- Auto-detect Hebrew (RTL) vs English (LTR) content
- Zero-dependency Python converter with embedded templates
- File/folder/glob/recursive conversion with index generation

## [1.0.0] — 2026-02-26

- Initial release: hook-based plugin for auto-generating HTML from markdown
- First-run opt-in prompt, enable/disable command
- Doc authoring skill with templates
