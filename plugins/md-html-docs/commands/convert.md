---
name: md-html-docs-convert
description: Manually convert markdown files to HTML
arguments:
  - name: target
    description: "File path, folder path, glob pattern, or --all <root>"
    required: true
---

Convert markdown files to styled HTML using the bundled converter.

Run the converter with the provided arguments:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/convert.py" $ARGUMENTS
```

The converter supports:
- **Single file**: `python3 convert.py path/to/file.md`
- **Folder** (non-recursive): `python3 convert.py path/to/folder/`
- **Glob pattern**: `python3 convert.py 'docs/**/*.md'`
- **Index only**: `python3 convert.py --index path/to/folder/`
- **Recursive all**: `python3 convert.py --all path/to/root/`

Features:
- Auto-detects Hebrew content and uses RTL template (Heebo font)
- English/other content uses LTR template (Inter font)
- Generates TOC from h2/h3 headings
- Generates `index.html` for folders listing all documents and subfolders
- Supports tables, code blocks, checkboxes, blockquotes, images, links
- Renders diagram code blocks (mermaid, dot/graphviz, nomnoml) as interactive SVGs

Report the output to the user after running.
