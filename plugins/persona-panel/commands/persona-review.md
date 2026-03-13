---
description: Have a persona review a document, source code, idea, or URL
argument-hint: <persona-name> <target>
---

# Persona Review

The user's arguments are in `$ARGUMENTS`. Parse them to extract:
- **First word** = persona short name (e.g., "cherny", "nate")
- **Rest** = target to review (file path, glob, URL, or quoted text)

## Step 1: Locate Persona

Search for the persona by short name (case-insensitive), in priority order (first match wins):
1. Check `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/` — read each subdirectory's `config.json`, match on `shortName`
2. Check `$HOME/.claude/persona-panel/personas/` — same process
3. Check `${CLAUDE_PLUGIN_ROOT}/personas/` — same process

If not found, show available personas and exit.

## Step 2: Load Context

Load context notes for this persona from both locations (merge into a single list):
- `$HOME/.claude/persona-panel/context/<shortName>.json` (global context)
- `${CLAUDE_PROJECT_DIR}/.persona-panel/context/<shortName>.json` (project context)

Each file is a JSON array of `{ "id", "text", "added" }` objects. If a file doesn't exist, treat as empty array. Combine both arrays into one list.

## Step 3: Resolve Target

The target can be:
- **File or directory path** — if it exists on disk, read the file(s)
- **Glob pattern** (contains `*` or `**`) — expand and read matching files
- **URL** (starts with `http`) — fetch the web content
- **Quoted text / inline text** — treat as an idea, question, or topic to review

## Step 4: Generate Review

Run the review script. If context notes exist, pass them via the `--context` flag as a JSON string:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/review.mjs \
  --persona <persona-directory-path> \
  --target "<target>" \
  --output "reviews/$(date +%Y-%m-%d)-<persona-shortname>-persona-review.md" \
  --context '<JSON array of context entries, or omit flag if empty>'
```

Only include the `--context` flag when there are context entries.

The script auto-detects review type:
- `.md` files → `doc` type (clarity, completeness, strategy)
- Source code files → `code` type (architecture, quality, patterns, bugs)
- Inline text → `idea` type (feasibility, tradeoffs, alternatives)

## Step 5: Display Results

Show the review output to the user and confirm the file was saved to the `reviews/` directory.
