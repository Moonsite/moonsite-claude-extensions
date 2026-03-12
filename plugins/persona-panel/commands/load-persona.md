---
description: Import a persona from a portable .md file (created by /save-persona)
argument-hint: <path-to-persona.md>
---

# Load Persona

Import a persona from a portable `.md` file into the project's persona directory.

## Step 1: Read the File

Read the file at the path specified in `$ARGUMENTS`.

If the file doesn't exist, show an error and exit.

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
```

Parse:
1. **YAML frontmatter** (between `---` markers) — extract config fields
2. **Persona document** — everything between the closing `---` and `<!-- SOURCES -->` marker
3. **Sources** (optional) — everything after `<!-- SOURCES -->` marker. If no marker, sources are empty.

## Step 3: Check for Conflicts

Check if a persona with the same `shortName` already exists:
- In `${CLAUDE_PLUGIN_ROOT}/personas/` (bundled)
- In `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/` (project)

If it exists, ask the user: "A persona named **<name>** already exists. Overwrite it?" If they decline, exit.

Bundled personas cannot be overwritten — tell the user to choose a different shortName.

## Step 4: Create Persona Directory

Create `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/<shortName>/` with:

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

## Step 5: Confirm

Tell the user:
- The persona **<name>** has been loaded
- Show the config summary (provider, model, color)
- Usage: `/persona-review <shortName> <target>`, `/persona-discuss --with <shortName>`
