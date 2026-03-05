---
name: md-html-docs-regenerate-all
description: Regenerate all HTML files from markdown in the project
---

Regenerate all HTML files from every markdown file in the project.

Determine the project root:

```bash
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"
```

Run the converter in recursive mode:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/convert.py" --all "$PROJECT_ROOT"
```

Report the output to the user after running.
