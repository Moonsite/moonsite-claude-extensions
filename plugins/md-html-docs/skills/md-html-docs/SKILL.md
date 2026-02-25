---
name: md-html-docs
description: Use PROACTIVELY whenever a markdown (.md) file is created or updated in the project's docs/ folder. This skill should fire automatically to generate/update the corresponding HTML and maintain indexes — unless the user has explicitly opted out for the current project. Also use when the user asks to "write a spec", "create a guide", "add a doc", "create a report", "write a decision doc", or any documentation task that produces markdown in docs/.
version: 1.0.0
---

# md-html-docs

Author documentation in the project's `docs/` system: write structured markdown, capture images from Figma or the live app, generate HTML, and keep indexes up to date.

## Routing Table

Determine doc type first, then use this table to set every parameter:

| Doc type | Folder | Converter | Language | Notes |
|---|---|---|---|---|
| **spec** | `docs/spec/` | `python3 docs/spec/_convert.py` | LTR English | subtitle + priority badge |
| **guide** | `docs/guides/` | `python3 docs/guides/_convert.py` | RTL Hebrew | role name, prev/next nav |
| **report** | `docs/code-review/` | `python3 docs/code-review/_convert_report.py` | LTR English | checkbox `[ ]` / `[x]` support |
| **plan** | `docs/plans/` | None | English | plain markdown only, no HTML |

## Workflow

### 1. Detect project structure

Confirm `docs/` exists in the project root. Identify which subfolders exist (`spec/`, `guides/`, `code-review/`, `plans/`). If `docs/` is missing, ask the user whether to create it or adapt to their structure.

### 2. Determine doc type

Ask the user if not clear from context:
- Feature/domain documentation → **spec**
- Role-based how-to for end users → **guide** (Hebrew RTL)
- Code review findings or product analysis → **report**
- Design decision, migration plan, ADR → **plan**

### 3. Assign filename and metadata

- **spec**: next available number, e.g. `19-FEATURE-NAME.md`. Requires title, subtitle, priority (P0/P1/P2).
- **guide**: next number in sequence, e.g. `08-role-name.md`. Requires Hebrew title and role name.
- **report**: descriptive name, e.g. `FEATURE_ANALYSIS.md`. Requires title.
- **plan**: date-prefixed, e.g. `2026-02-20-topic.md`. No HTML needed.

### 4. Create `images/` subdirectory (if needed)

```bash
mkdir -p docs/<type>/images
```

Skip for plans.

### 5. Write the markdown file

Use the appropriate template from `references/`:
- `references/spec-template.md`
- `references/guide-template.md`
- `references/report-template.md`
- `references/plan-template.md`

Populate all sections with real content. Use `[SCREENSHOT: name]` as placeholders for images that will be captured in step 6.

### 6. Capture images

**From Figma** (use when documenting UI designs or mockups):
1. Get the Figma fileKey and nodeId from the user or from a Figma URL (`https://figma.com/design/<fileKey>/...?node-id=<nodeId>`)
2. Call `mcp__claude_ai_Figma__get_screenshot` with `fileKey` and `nodeId`
3. Save the returned image to `docs/<type>/images/<name>.png`
4. Replace `[SCREENSHOT: name]` in the markdown with `![description](images/<name>.png)`

**From Playwright** (use when documenting the live running app):
1. Use `mcp__plugin_playwright_playwright__browser_navigate` to go to the relevant page
2. Call `mcp__plugin_playwright_playwright__browser_take_screenshot` with `filename: "docs/<type>/images/<name>.png"`
3. Replace `[SCREENSHOT: name]` in the markdown with `![description](images/<name>.png)`

If no images are needed, skip this step.

### 7. Run the converter

From the project root:

```bash
python3 docs/<type>/_convert.py
```

Verify the `.html` file was created or updated alongside the `.md` file.

Plans skip this step — no HTML generation needed.

### 8. Update index files

See `references/index-update-guide.md` for the exact HTML snippets to add to each index file.

- **spec**: add card to `docs/spec/index.html`; update doc count in `docs/index.html`
- **guide**: add card to `docs/guides/index.html`; update prev/next navigation links in adjacent guide HTML files; update doc count in `docs/index.html`
- **report**: add card to `docs/code-review/index.html`
- **plan**: no index update

### 9. Commit

Stage and commit both `.md` and `.html` files together:

```bash
git add docs/<type>/<filename>.md docs/<type>/<filename>.html docs/<type>/index.html docs/<type>/images/
git commit -m "TAAMATCL-XX: docs: add <title>"
```

## Key Rules

- **Never edit `.html` files directly** — always edit `.md` and re-run the converter
- **Guides are Hebrew RTL** — all content, headings, and TOC in Hebrew
- **Do not modify templates** — `_report-template.html` and `_template.html` are shared across all docs
- **Images go in `docs/<type>/images/`** — never inline base64 or reference external URLs
- **Commit `.md` and `.html` together** — never commit one without the other

## Additional Resources

- **`references/spec-template.md`** — Full spec markdown template with all sections
- **`references/guide-template.md`** — Hebrew RTL guide template with TOC and screenshot placeholders
- **`references/report-template.md`** — Report template with checkbox support
- **`references/plan-template.md`** — Plan/decision doc template
- **`references/index-update-guide.md`** — Exact HTML snippets for updating index files and converter registration
