---
description: List all available personas (bundled + global + project)
---

# List Personas

List all available personas from bundled, global, and project directories.

## Instructions

1. **Scan bundled personas** at `${CLAUDE_PLUGIN_ROOT}/personas/`. For each subdirectory, read `config.json`.

2. **Scan global personas** at `$HOME/.claude/persona-panel/personas/`. For each subdirectory, read `config.json`. If the directory doesn't exist, skip (no global personas yet).

3. **Scan project personas** at `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/`. For each subdirectory, read `config.json`. If the directory doesn't exist, skip (no project personas yet).

4. **Deduplicate by shortName.** If a persona appears in multiple tiers, the highest-priority tier wins: project > global > bundled.

5. **Count context notes** for each persona. For each shortName, count entries in:
   - `$HOME/.claude/persona-panel/context/<shortName>.json` (global context)
   - `${CLAUDE_PROJECT_DIR}/.persona-panel/context/<shortName>.json` (project context)

   Each file contains a JSON array of entries. Total = sum of both arrays' lengths. If a file doesn't exist, count is 0.

6. **Display as a formatted table:**

```
  Name             Provider    Model              Color    Source    Context
  -------------------------------------------------------------------------
  Boris Cherny     anthropic   claude-opus-4-6    cyan     bundled   2 notes
  Nate             openai      gpt-5.4            yellow   global
  <project personas listed here>
```

Use the `name` field from config.json for the Name column. Use "bundled", "global", or "project" for the Source column based on where the persona was found (after dedup). Show context count as "N notes" if > 0, or leave blank if 0.

7. **Show usage hints** after the table:
   - `/persona-review <shortName> <target>` — have a persona review something
   - `/persona-discuss --with <name1>,<name2>` — start a discussion
   - `/add-persona <name>` — create a new persona
   - `/persona-context add <name> "note"` — add context to a persona
