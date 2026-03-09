---
name: md-html-docs
description: Use PROACTIVELY whenever a markdown (.md) file is created or updated anywhere in the project. Automatically generates styled HTML with language-appropriate templates (RTL for Hebrew, LTR for English). Also use when the user asks to convert markdown to HTML, generate documentation, or create HTML from .md files.
version: 2.3.6
---

# md-html-docs

Convert any markdown file to styled, self-contained HTML. Auto-detects language and picks the right template.

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

Create this file in the project's `.claude/` directory for project-wide settings:

```json
{
  "projectName": "My Project",
  "orgName": "Acme Corp",
  "colorScheme": "blue",
  "documents": {
    "intro.md": { "title": "Getting Started", "icon": "🚀", "accent": "green" },
    "api.md": { "title": "API Reference", "description": "REST endpoints", "icon": "📡" }
  },
  "folders": {
    "guides": { "title": "User Guides", "icon": "📖", "accent": "purple" },
    "specs": { "title": "Technical Specs", "icon": "📐" }
  }
}
```

**Config fields:**
- `projectName` — shown in page header
- `orgName` — shown below project name
- `logoText` — 2-char text in header circle (auto-derived from projectName)
- `colorScheme` — preset: `blue`, `green`, `purple`, `orange`
- `accentColor`, `headerFrom`, `headerTo` — custom hex colors (override preset)
- `footerText` — custom footer text
- `documents` — per-file overrides keyed by filename (e.g. `"intro.md": {...}`)
- `folders` — per-folder overrides keyed by folder name (e.g. `"guides": {...}`)

**Priority chain:** config `documents`/`folders` override > frontmatter > auto-extracted from headings.

### Links Between Documents

Local `.md` links are automatically rewritten to `.html` during conversion:

```markdown
See [the API docs](api.md) or [setup guide](guides/setup.md#configuration)
```

Becomes: `<a href="api.html">` and `<a href="guides/setup.html#configuration">`.

## Key Rules

- **Never edit `.html` files directly** — always edit `.md` and let the converter regenerate
- **Commit `.md` and `.html` together** — never commit one without the other
- **Images**: reference with relative paths in markdown, e.g. `![alt](images/screenshot.png)`
- **Templates are auto-selected** — Hebrew content gets RTL, everything else gets LTR
- **Diagram blocks** (`mermaid`, `pintora`, `dot`, `graphviz`, `nomnoml`, `d2`) render as interactive SVGs via client-side libraries (d2 uses Kroki.io API)
- **Review notes**: heading 📝 buttons and text-selection notes are stored in localStorage per page; export to Markdown groups notes by section
