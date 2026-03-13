---
description: Remove a project or global persona (cannot remove bundled personas)
argument-hint: <persona-name>
---

# Remove Persona

The persona name to remove is in `$ARGUMENTS`.

## Step 1: Locate Persona

Search for the persona by short name:
1. Check bundled personas at `${CLAUDE_PLUGIN_ROOT}/personas/` — if found there **only** (not overridden by global or project), tell the user **bundled personas cannot be removed** and exit.
2. Check global personas at `$HOME/.claude/persona-panel/personas/` — if found, note it as removable (global).
3. Check project personas at `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/` — if found, note it as removable (project).
4. If not found anywhere, list available personas and exit.

If the persona exists in multiple tiers (e.g., both global and project), tell the user which tiers it exists in and ask which one to remove.

## Step 2: Confirm

Show the user the persona's config and ask for confirmation:
"Are you sure you want to remove **$ARGUMENTS** from <tier>? This will delete the persona directory and all its files (config.json, persona.md, sources.md)."

Also ask if they want to remove associated context notes:
- `$HOME/.claude/persona-panel/context/$ARGUMENTS.json` (global context, if exists)
- `${CLAUDE_PROJECT_DIR}/.persona-panel/context/$ARGUMENTS.json` (project context, if exists)

## Step 3: Remove

Delete the persona directory from the chosen tier:
- **Global:** `rm -rf "$HOME/.claude/persona-panel/personas/$ARGUMENTS"`
- **Project:** `rm -rf "${CLAUDE_PROJECT_DIR}/.persona-panel/personas/$ARGUMENTS"`

If the user confirmed context removal, also delete the context files.

## Step 4: Confirm Removal

Tell the user the persona has been removed and show the remaining personas with `/personas`.
