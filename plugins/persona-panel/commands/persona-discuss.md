---
description: Start a live multi-persona panel discussion in the terminal
argument-hint: "[topic]" --with name1,name2 --moderator name
---

# Persona Discussion

Start a live panel discussion with AI personas in the terminal.

## Step 1: Parse Arguments

Parse `$ARGUMENTS` for:
- **Topic** — any unquoted or quoted text that isn't a flag (e.g., `"Should we use microservices?"`)
- **--with <names>** — comma-separated list of persona short names to include
- **--file <path>** — file to discuss (all personas read it as context)
- **--moderator <name>** — persona to act as moderator

If no arguments provided, use all personas with a default topic.

## Step 2: Locate Personas

Load personas from both directories:
- Bundled: `${CLAUDE_PLUGIN_ROOT}/personas/`
- Project: `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/`

If `--with` specified, filter to only those personas. Verify all exist.

## Step 3: Moderator Setup (if --moderator specified)

If a moderator is specified, ask the user two questions before starting:

**Q1: Moderation style**
- `structured` — Opens with agenda, assigns speaking order, keeps on-topic, summarizes per round, drives toward conclusions
- `loose` — Sets opening question, only intervenes for tangents, conflicts, or quiet participants
- `devil` — Actively challenges every position, plays devil's advocate, demands evidence
- `custom` — User provides free-text description of moderator behavior

**Q2: Session duration**
- `quick` — 3-5 rounds (~5 minutes)
- `standard` — 8-12 rounds (~15 minutes)
- `deep` — 20-30 rounds (~30 minutes)
- `until-done` — Moderator decides when done (max 40 rounds)

## Step 4: Launch Discussion

Build the command:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/discuss.mjs \
  --personas-dir "${CLAUDE_PROJECT_DIR}/.persona-panel/personas" \
  --bundled-dir "${CLAUDE_PLUGIN_ROOT}/personas" \
  [--topic "..."] \
  [--with name1,name2] \
  [--moderator <name>] \
  [--style structured|loose|devil|"custom text"] \
  [--duration quick|standard|deep|until-done]
```

## Step 5: Discussion Controls

The discussion runs interactively. Available commands:
- `/ask <question>` — inject a question or comment into the discussion
- `/skip` — skip to the next speaker
- `/save` — save transcript so far
- `/quit` — end discussion and save transcript

Ctrl+C also saves the transcript before exiting.

Transcript is saved to `reviews/YYYY-MM-DD-panel-discussion.md`.
