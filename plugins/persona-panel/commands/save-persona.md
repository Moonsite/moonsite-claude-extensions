---
description: Export a persona to a portable .md file (frontmatter config + persona doc + sources)
argument-hint: <persona-name> [output-path]
---

# Save Persona

Export a persona to a single portable `.md` file that can be shared, version-controlled, or later imported with `/load-persona`.

## Step 1: Parse Arguments

Parse `$ARGUMENTS`:
- **First word** = persona short name (e.g., "cherny", "nate")
- **Second word** (optional) = output file path. Default: `<shortName>.persona.md` in current directory.

## Step 2: Locate Persona

Search for the persona by short name (case-insensitive):
1. Check `${CLAUDE_PLUGIN_ROOT}/personas/` — read each subdirectory's `config.json`, match on `shortName`
2. Check `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/` — same process

If not found, show available personas and exit.

## Step 3: Read Persona Files

Read from the persona directory:
- `config.json` — persona configuration
- `persona.md` — the persona document
- `sources.md` — source material (may not exist)

## Step 4: Write Portable File

Create a single `.md` file with this structure:

```markdown
---
name: <config.name>
shortName: <config.shortName>
provider: <config.provider>
model: <config.model>
color: <config.color>
sourceType: <config.sourceType>
---

<contents of persona.md>

<!-- SOURCES -->

<contents of sources.md, if it exists>
```

The YAML frontmatter contains the config fields (excluding `bundled` — saved personas are always non-bundled when loaded).

The `<!-- SOURCES -->` HTML comment is a separator marker. Everything after it is the source material.

## Step 5: Confirm

Tell the user:
- The file was saved to `<output-path>`
- They can import it later with `/load-persona <path>`
- They can share it with others or commit it to version control
