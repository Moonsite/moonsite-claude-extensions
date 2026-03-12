---
description: Have ALL personas review a target in parallel using subagents
argument-hint: <target>
---

# Persona Review All

Run all available personas against the same target in parallel, each producing their own independent review.

## Step 1: Locate All Personas

Scan both directories for personas:
1. **Bundled:** `${CLAUDE_PLUGIN_ROOT}/personas/` — read each subdirectory's `config.json`
2. **Project:** `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/` — read each subdirectory's `config.json`

List all found personas and confirm with the user:
"Found N personas: <name1>, <name2>, ... — Running all reviews in parallel against: `$ARGUMENTS`"

## Step 2: Resolve Target

Determine what `$ARGUMENTS` points to:
- **File or directory path** — verify it exists
- **Glob pattern** (contains `*`) — note the pattern
- **URL** (starts with `http`) — note the URL
- **Quoted text** — treat as inline idea/topic

## Step 3: Dispatch Parallel Reviews

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
  --output "reviews/<YYYY-MM-DD>-<shortName>-persona-review.md"

After the script completes, read the output file and return its contents.
```

**IMPORTANT:** Launch ALL agents in a single message to maximize parallelism. Do NOT wait for one to finish before starting another.

## Step 4: Collect Results

As each agent completes, collect the review output. Once all are done, present a summary:

```
## Persona Reviews Complete

| Persona | File | Status |
|---------|------|--------|
| Boris Cherny | reviews/YYYY-MM-DD-cherny-persona-review.md | Done |
| Nate | reviews/YYYY-MM-DD-nate-persona-review.md | Done |
| ... | ... | ... |
```

## Step 5: Optional Synthesis

Ask the user: "Would you like me to synthesize the reviews into a combined summary highlighting agreements, disagreements, and key themes across all personas?"

If yes, read all review files and produce a synthesis document saved to `reviews/YYYY-MM-DD-combined-persona-review.md`.
