---
name: md-html-docs
description: Use PROACTIVELY whenever a markdown (.md) file is created or updated anywhere in the project. Automatically generates styled HTML with language-appropriate templates (RTL for Hebrew, LTR for English). Also use when the user asks to convert markdown to HTML, generate documentation, or create HTML from .md files.
version: 2.5.1
released: 2026-03-12
---

# md-html-docs

Convert any markdown file to styled, self-contained HTML. Auto-detects language and picks the right template.

When this skill is invoked (manually or via hook), print the version banner:

```
md-html-docs v{version} | Released: {released}
```

Read `version` and `released` from this file's YAML frontmatter.

## How It Works

The plugin includes a self-contained Python converter (`convert.py`) with zero dependencies. It:

1. Parses markdown using regex (headings, bold/italic, code blocks, tables, lists, blockquotes, checkboxes, links, images, HR, diagrams)
2. Detects Hebrew content (>5% Hebrew characters) → uses RTL template with Heebo font
3. English/other content → uses LTR template with Inter font
4. Extracts title from first `# heading`, subtitle from next heading/blockquote/paragraph
5. Generates sidebar TOC from h2/h3 headings
6. Generates `index.html` for folders listing documents and subfolders

## Workflow

### When a .md file is created or edited:

1. The PostToolUse hook automatically runs the converter on the file
2. The hook also regenerates the parent folder's `index.html`
3. No manual action needed (if auto-generation is enabled)

### For manual conversion:

Use `/md-html-docs-convert` with a path:

```bash
/md-html-docs-convert path/to/file.md          # single file
/md-html-docs-convert path/to/folder/           # folder (non-recursive)
/md-html-docs-convert 'docs/**/*.md'            # glob pattern
/md-html-docs-convert --all docs/               # recursive + all indexes
/md-html-docs-convert --index docs/guides/      # regenerate index only
```

### Enable/disable auto-generation:

```
/md-html-docs enable    # turn on auto-generation
/md-html-docs disable   # turn off
/md-html-docs status    # check current state
```

## Document Metadata

### YAML Frontmatter (per-file)

Add frontmatter to any `.md` file to control its title, description, icon, and accent color in index pages:

```markdown
---
title: My Document Title
description: Brief description shown on index cards
icon: 📊
accent: purple
---

# Actual content starts here...
```

Supported fields: `title`, `description`, `icon` (emoji), `accent` (`blue`, `green`, `purple`, `orange`).

Frontmatter is stripped from the rendered HTML — it only affects metadata.

### Project Config (`.claude/md-html-docs.json`)

**IMPORTANT — set this up before generating HTML.** Create `.claude/md-html-docs.json` in the project root:

```json
{
  "projectName": "Brosh",
  "orgName": "Moonsite",
  "logoText": "BR",
  "colorScheme": "blue",
  "footerText": "Brosh Documentation",
  "documents": {
    "intro.md": { "title": "Getting Started", "icon": "🚀", "accent": "green" }
  },
  "folders": {
    "specs": { "title": "Technical Specs", "icon": "📐" }
  }
}
```

#### Header Layout

The sticky header displays these config values:

```
[logo circle] [project name]  [doc title]  ...  [Index btn] [Layout buttons]
              [org name]
```

| Config Field | Where It Shows | Example | Notes |
|---|---|---|---|
| `projectName` | Header — main label (bold) | `"Brosh"` | Product/project name |
| `orgName` | Header — subtitle below project name | `"Moonsite"` | Company/team. Leave empty `""` to hide |
| `logoText` | Header — 2-char circle icon | `"BR"` | Auto-derived from first 2 chars of `projectName` if omitted |

**If `projectName` and `orgName` show the same value**, one of them is wrong. `projectName` = the product/project, `orgName` = the company/team that owns it. Set `orgName` to `""` to hide it entirely.

#### All Config Fields

- `projectName` — **required** — product/project name shown in header
- `orgName` — company/team name shown below project name (set `""` to hide)
- `logoText` — 2-char text in header circle (auto-derived from `projectName` if omitted)
- `colorScheme` — preset theme: `blue`, `green`, `purple`, `orange`
- `accentColor`, `headerFrom`, `headerTo` — custom hex colors (override preset)
- `footerText` — custom footer text
- `documents` — per-file overrides keyed by filename: `{"file.md": {title, description, icon, accent}}`
- `folders` — per-folder overrides keyed by folder name: `{"guides": {title, description, icon, accent}}`

**Priority chain:** config `documents`/`folders` override > frontmatter > auto-extracted from headings.

### Links Between Documents

Local `.md` links are automatically rewritten to `.html` during conversion:

```markdown
See [the API docs](api.md) or [setup guide](guides/setup.md#configuration)
```

Becomes: `<a href="api.html">` and `<a href="guides/setup.html#configuration">`.

### Enriching Index Pages (LLM-Powered)

After running `--all`, index pages show raw folder names and generic descriptions. **Always enrich indexes using LLM intelligence:**

1. **Analyze content**: Read the first heading and opening lines of `.md` files in each folder to understand the section's purpose
2. **Create/update config**: Write `.claude/md-html-docs.json` in the project root with meaningful `folders` and `documents` overrides:

```json
{
  "projectName": "My Project",
  "orgName": "Company Name",
  "logoText": "MP",
  "colorScheme": "blue",
  "footerText": "My Project Documentation",
  "folders": {
    "guides": { "title": "User Guides", "description": "Step-by-step guides for common workflows", "icon": "📖" },
    "api": { "title": "API Reference", "description": "Complete REST API documentation with examples", "icon": "🔌" }
  },
  "documents": {
    "setup.md": { "title": "Getting Started", "description": "Installation and initial configuration", "icon": "🚀" }
  }
}
```

3. **Add YAML frontmatter** to `.md` files that need custom titles/descriptions beyond what auto-extraction provides:

```markdown
---
title: Developer Guide
description: Hands-on guide for integrating AI tools into daily development workflow
icon: 💻
---
```

4. **Regenerate**: run the converter with `--all` to rebuild all indexes with the enriched metadata

The converter discovers all folders recursively — intermediate folders with only subfolders (no direct `.md` files) also get proper index pages with navigation cards.

**When to enrich**: Always run this workflow after `--all` on a new project or when new folders are added. The LLM should generate titles that are human-friendly (not raw folder names), descriptions that summarize the section's content, and appropriate icons.

## Key Rules

- **Never edit `.html` files directly** — always edit `.md` and let the converter regenerate
- **Commit `.md` and `.html` together** — never commit one without the other
- **Images**: reference with relative paths in markdown, e.g. `![alt](images/screenshot.png)`
- **Templates are auto-selected** — Hebrew content gets RTL, everything else gets LTR
- **Diagram blocks** (`mermaid`, `pintora`, `dot`, `graphviz`, `nomnoml`, `d2`) render as interactive SVGs via client-side libraries (d2 uses Kroki.io API)
- **Review notes**: heading 📝 buttons and text-selection notes are stored in localStorage per page; export to Markdown groups notes by section
