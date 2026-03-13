---
description: Manage context notes for personas (add, list, remove)
argument-hint: add|list|remove <persona-name> ["text"] [--global]
---

# Persona Context

Manage ephemeral context notes that augment a persona's knowledge. Context notes are injected into the persona's system prompt during reviews and discussions, providing up-to-date information without modifying the persona document itself.

Parse `$ARGUMENTS` to extract the subcommand and its arguments.

## Subcommand: `add <name> "<text>"` [--global]

Add a new context note for a persona.

### Steps:

1. **Parse arguments:**
   - `<name>` — persona shortName
   - `<text>` — the context note text (may be quoted or unquoted, everything after the name and before --global)
   - `--global` flag — if present, store in global context; otherwise store in project context

2. **Verify persona exists** — check all three tiers (project → global → bundled). The persona itself doesn't need to be in the same tier as the context. If the persona doesn't exist anywhere, show an error and exit.

3. **Determine context file path:**
   - **If `--global`:** `$HOME/.claude/persona-panel/context/<name>.json`
   - **Otherwise:** `${CLAUDE_PROJECT_DIR}/.persona-panel/context/<name>.json`

4. **Read existing context** — if the file exists, parse the JSON array. Otherwise, start with an empty array.

5. **Create new entry:**
   ```json
   {
     "id": "<generate a UUID>",
     "text": "<the context note text>",
     "added": "<today's date in YYYY-MM-DD format>"
   }
   ```
   Generate the UUID using: `node -e "console.log(crypto.randomUUID())"`

6. **Append and save** — add the entry to the array and write back to the file. Create the parent directory if needed.

7. **Confirm** — tell the user the context note was added, show the entry, and mention which scope (global/project) it was saved to.

## Subcommand: `list <name>`

List all context notes for a persona, merging global and project entries.

### Steps:

1. **Parse arguments:** `<name>` — persona shortName.

2. **Load context from both locations:**
   - `$HOME/.claude/persona-panel/context/<name>.json` (global)
   - `${CLAUDE_PROJECT_DIR}/.persona-panel/context/<name>.json` (project)

   Each file is a JSON array. If a file doesn't exist, treat as empty array.

3. **Display as a numbered table:**

   ```
   # Context notes for <name>

     #   Scope     Added        Text
     ─────────────────────────────────────────────────────────
     1   global    2026-03-13   Quit Anthropic, joined OpenAI
     2   global    2026-02-20   Published book on type systems
     3   project   2026-03-10   Working on persona-panel plugin
   ```

   Number entries sequentially (1-based). Show global entries first, then project entries. Include the scope column so the user knows where each note lives.

4. If no context notes exist, say so and show how to add one:
   `/persona-context add <name> "your note here"`

## Subcommand: `remove <name> <number>`

Remove a context note by its display number.

### Steps:

1. **Parse arguments:**
   - `<name>` — persona shortName
   - `<number>` — the display number from `list` output (1-based)

2. **Load context from both locations** (same as `list`), maintaining the same ordering: global entries first, then project entries.

3. **Resolve the entry** — find the entry at the given display number. Determine which file (global or project) it belongs to.

4. **Remove the entry** from the appropriate file. Write the updated array back to the file. If the array is now empty, delete the file.

5. **Confirm** — show which note was removed and from which scope.
