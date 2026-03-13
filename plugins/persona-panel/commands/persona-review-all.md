---
description: Have ALL personas review a target in parallel using subagents
argument-hint: <target>
---

# Persona Review All

Run all available personas against the same target in parallel, each producing their own independent review.

## Step 1: Locate All Personas

Scan all three directories for personas:
1. **Bundled:** `${CLAUDE_PLUGIN_ROOT}/personas/` — read each subdirectory's `config.json`
2. **Global:** `$HOME/.claude/persona-panel/personas/` — read each subdirectory's `config.json` (skip if directory doesn't exist)
3. **Project:** `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/` — read each subdirectory's `config.json` (skip if directory doesn't exist)

**Deduplicate by shortName.** If a persona appears in multiple tiers, the highest-priority tier wins: project > global > bundled.

List all found personas and confirm with the user:
"Found N personas: <name1>, <name2>, ... — Running all reviews in parallel against: `$ARGUMENTS`"

## Step 2: Resolve Target

Determine what `$ARGUMENTS` points to:
- **File or directory path** — verify it exists
- **Glob pattern** (contains `*`) — note the pattern
- **URL** (starts with `http`) — note the URL
- **Quoted text** — treat as inline idea/topic

## Step 3: Load Context for Each Persona

For each persona, load context notes from both locations:
- `$HOME/.claude/persona-panel/context/<shortName>.json` (global context)
- `${CLAUDE_PROJECT_DIR}/.persona-panel/context/<shortName>.json` (project context)

Combine both arrays into one list per persona.

## Step 4: Dispatch Parallel Reviews

Launch one **Agent** per persona using the Agent tool. All agents run in parallel (send all Agent tool calls in a single message).

For each persona, launch an agent with this prompt:

```
Run a persona review using the persona-panel plugin.

Persona directory: <full path to persona directory>
Target: $ARGUMENTS

Execute this command:
node ${CLAUDE_PLUGIN_ROOT}/scripts/review.mjs \
  --persona "<persona-directory-path>" \
  --target "$ARGUMENTS" \
  --output "reviews/<YYYY-MM-DD>-<shortName>-persona-review.md" \
  --context '<JSON array of context entries, or omit flag if no context>'

After the script completes, read the output file and return its contents.
```

Only include the `--context` flag when there are context entries for that persona.

**IMPORTANT:** Launch ALL agents in a single message to maximize parallelism. Do NOT wait for one to finish before starting another.

## Step 5: Collect Results

As each agent completes, collect the review output. Once all are done, present a summary:

```
## Persona Reviews Complete

| Persona | File | Status |
|---------|------|--------|
| Boris Cherny | reviews/YYYY-MM-DD-cherny-persona-review.md | Done |
| Nate | reviews/YYYY-MM-DD-nate-persona-review.md | Done |
| ... | ... | ... |
```

## Step 6: Optional Synthesis

Ask the user: "Would you like me to synthesize the reviews into a combined summary highlighting agreements, disagreements, and key themes across all personas?"

If yes, read all review files and produce a synthesis document saved to `reviews/YYYY-MM-DD-combined-persona-review.md`.
