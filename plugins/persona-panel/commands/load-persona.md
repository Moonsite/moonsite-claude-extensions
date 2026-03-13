---
description: Import a persona from a portable .md file (created by /save-persona)
argument-hint: <path-to-persona.md> [--global]
---

# Load Persona

Import a persona from a portable `.md` file into the project or global persona directory.

## Step 1: Parse Arguments

Parse `$ARGUMENTS` to extract:
- **File path** — the path to the `.md` file to import
- **`--global` flag** — if present, import to the global directory instead of the project directory

Read the file at the specified path. If the file doesn't exist, show an error and exit.

## Step 2: Parse the File

The file format is:

```
---
name: <display name>
shortName: <short-name>
provider: <anthropic|openai>
model: <model-id>
color: <terminal-color>
sourceType: <web|files|text>
---

<persona document content>

<!-- SOURCES -->

<source material content>

<!-- CONTEXT -->

<JSON array of context entries>
```

Parse:
1. **YAML frontmatter** (between `---` markers) — extract config fields
2. **Persona document** — everything between the closing `---` and `<!-- SOURCES -->` marker
3. **Sources** (optional) — everything between `<!-- SOURCES -->` and `<!-- CONTEXT -->` markers. If no `<!-- SOURCES -->` marker, sources are empty.
4. **Context** (optional) — everything after `<!-- CONTEXT -->` marker, parsed as a JSON array of `{ "id", "text", "added" }` objects. If no `<!-- CONTEXT -->` marker, context is empty.

## Step 3: Check for Conflicts

Determine the target directory:
- **If `--global` flag is set:** `$HOME/.claude/persona-panel/personas/<shortName>`
- **Otherwise:** `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/<shortName>`

Check if a persona with the same `shortName` already exists in any tier:
- In `${CLAUDE_PLUGIN_ROOT}/personas/` (bundled)
- In `$HOME/.claude/persona-panel/personas/` (global)
- In `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/` (project)

If it exists in the **target** directory, ask the user: "A persona named **<name>** already exists in <target>. Overwrite it?" If they decline, exit.

Bundled personas cannot be overwritten — tell the user to choose a different shortName.

If it exists in a **different non-bundled** tier than the target, inform the user: "A persona named **<name>** also exists as a <tier> persona. The <target-tier> version will take priority based on the override rules (project > global > bundled)."

## Step 4: Create Persona Directory

Create `<target-directory>/` with:

**config.json:**
```json
{
  "name": "<name from frontmatter>",
  "shortName": "<shortName from frontmatter>",
  "provider": "<provider>",
  "model": "<model>",
  "color": "<color>",
  "sourceType": "<sourceType>",
  "bundled": false
}
```

**persona.md:** The persona document content (trimmed).

**sources.md:** The sources content (trimmed), or empty file if no sources.

## Step 5: Import Context (if present)

If context entries were parsed from the `<!-- CONTEXT -->` section:

Determine context file path based on `--global` flag:
- **If `--global`:** `$HOME/.claude/persona-panel/context/<shortName>.json`
- **Otherwise:** `${CLAUDE_PROJECT_DIR}/.persona-panel/context/<shortName>.json`

If the context file already exists, merge the imported entries with existing ones (avoid duplicates by `id`). Otherwise, write the entries as a new JSON array.

Create the parent directory if it doesn't exist.

## Step 6: Confirm

Tell the user:
- The persona **<name>** has been loaded to **<target>** (global or project)
- Show the config summary (provider, model, color)
- If context entries were imported, mention how many
- Usage: `/persona-review <shortName> <target>`, `/persona-discuss --with <shortName>`
