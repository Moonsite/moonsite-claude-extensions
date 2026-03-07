---
name: md-html-docs
description: Use PROACTIVELY whenever a markdown (.md) file is created or updated anywhere in the project. Automatically generates styled HTML with language-appropriate templates (RTL for Hebrew, LTR for English). Also use when the user asks to convert markdown to HTML, generate documentation, or create HTML from .md files.
version: 2.2.0
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

## Key Rules

- **Never edit `.html` files directly** — always edit `.md` and let the converter regenerate
- **Commit `.md` and `.html` together** — never commit one without the other
- **Images**: reference with relative paths in markdown, e.g. `![alt](images/screenshot.png)`
- **Templates are auto-selected** — Hebrew content gets RTL, everything else gets LTR
- **Diagram blocks** (`mermaid`, `pintora`, `dot`, `graphviz`, `nomnoml`) render as interactive SVGs via client-side libraries
