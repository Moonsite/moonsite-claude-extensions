---
description: Remove a project persona (cannot remove bundled personas)
argument-hint: <persona-name>
---

# Remove Persona

The persona name to remove is in `$ARGUMENTS`.

## Step 1: Locate Persona

Search for the persona by short name:
1. Check bundled personas at `${CLAUDE_PLUGIN_ROOT}/personas/` — if found there, tell the user **bundled personas cannot be removed** and exit.
2. Check project personas at `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/` — if found, proceed.
3. If not found anywhere, list available personas and exit.

## Step 2: Confirm

Show the user the persona's config and ask for confirmation:
"Are you sure you want to remove **$ARGUMENTS**? This will delete the persona directory and all its files (config.json, persona.md, sources.md)."

## Step 3: Remove

Delete the persona directory:
```bash
rm -rf "${CLAUDE_PROJECT_DIR}/.persona-panel/personas/$ARGUMENTS"
```

## Step 4: Confirm Removal

Tell the user the persona has been removed and show the remaining personas with `/personas`.
