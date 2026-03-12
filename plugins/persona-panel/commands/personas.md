---
description: List all available personas (bundled + project)
---

# List Personas

List all available personas from both bundled and project directories.

## Instructions

1. **Scan bundled personas** at `${CLAUDE_PLUGIN_ROOT}/personas/`. For each subdirectory, read `config.json`.

2. **Scan project personas** at `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/`. For each subdirectory, read `config.json`. If the directory doesn't exist, skip (no project personas yet).

3. **Display as a formatted table:**

```
  Name             Provider    Model              Color    Source
  -------------------------------------------------------------------
  Boris Cherny     anthropic   claude-opus-4-6    cyan     bundled
  Nate             openai      gpt-5.4            yellow   bundled
  <project personas listed here>
```

Use the `name` field from config.json for the Name column. Use "bundled" or "project" for the Source column based on where the persona was found.

4. **Show usage hints** after the table:
   - `/persona-review <shortName> <target>` — have a persona review something
   - `/persona-discuss --with <name1>,<name2>` — start a discussion
   - `/add-persona <name>` — create a new persona
