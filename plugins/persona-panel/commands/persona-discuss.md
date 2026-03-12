---
description: Start a multi-persona panel discussion orchestrated natively in Claude Code
argument-hint: "[topic]" --with name1,name2 --moderator name --rounds 12 --max-cost 5 --final-summary --context --verbose --file path
---

# Persona Panel Discussion Engine

You are the orchestrator of a multi-persona panel discussion. You will manage the entire discussion loop, making API calls via `call-llm.mjs`, displaying results, tracking costs, and saving state.

**IMPORTANT:** Run the discussion autonomously. Do NOT prompt the user between rounds. Just run all rounds continuously. If the user wants to intervene, they will interrupt (Escape).

## Step 1: Parse Arguments

Parse `$ARGUMENTS` for:

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| topic | positional text | "Share your perspectives on the current state of AI and software development." | The discussion topic (unquoted or quoted) |
| `--with <names>` | comma-separated | all personas | Filter to specific personas by short name |
| `--file <path>` | file path | none | File context shared with all personas |
| `--moderator <name>` | persona short name | none | Designate a moderator persona |
| `--rounds <n>` | integer | 12 | Maximum number of rounds |
| `--max-cost <n>` | float | none | Stop if total cost exceeds $n |
| `--final-summary` | flag | off | Each persona summarizes independently at end |
| `--context` | flag | off | Add rich metadata header to transcript |
| `--verbose` | flag | off | Include prompts and technical data in transcript |

## Step 2: Check for Existing State (Resume Support)

Check if `${CLAUDE_PROJECT_DIR}/.persona-panel/discuss-state.json` exists.

If it exists, read it and tell the user:
> Found an interrupted discussion from [startTime] on topic "[topic]" (round [round] of [maxRounds], $[totalCost] spent). Resume or start fresh?

- If user says resume: load the state and skip to Step 5, continuing from the saved round.
- If user says fresh: delete the state file and continue normally.
- If no state file: continue normally.

## Step 3: Load Personas

Load personas from both directories:
- **Bundled:** `${CLAUDE_PLUGIN_ROOT}/personas/` — read each subdirectory's `config.json` and `persona.md`
- **Project:** `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/` — same structure

If `--with` is specified, filter to only those personas (match on `shortName` or `name`, case-insensitive). Verify all requested personas exist.

If `--moderator` is specified, identify the moderator persona from the loaded set. The moderator participates AND moderates.

## Step 4: Moderator Setup (if --moderator specified)

Ask the user two questions:

**Q1: Moderation style** — present these options:
- `structured` — Opens with agenda, assigns speaking order, keeps on-topic, summarizes per round, drives toward conclusions
- `loose` — Sets opening question, only intervenes for tangents, conflicts, or quiet participants
- `devil` — Actively challenges every position, plays devil's advocate, demands evidence
- `custom` — User provides free-text description of moderator behavior

**Q2: Session duration** — present these options:
- `quick` — 3-5 rounds
- `standard` — 8-12 rounds (default)
- `deep` — 20-30 rounds
- `until-done` — Moderator decides when done (max 40 rounds)

Update `--rounds` based on duration choice (use the max of the range).

## Step 5: Initialize or Load State

### If starting fresh, create this state object:

```json
{
  "version": 1,
  "round": 0,
  "maxRounds": <from args>,
  "topic": "<parsed topic>",
  "startTime": "<current ISO timestamp>",
  "personas": ["<shortName1>", "<shortName2>"],
  "moderator": "<shortName or null>",
  "moderatorStyle": "<style text or null>",
  "histories": {
    "<shortName>": []
  },
  "transcript": [],
  "metaInstructions": [],
  "totalCost": 0,
  "fileContext": "<file contents or empty string>"
}
```

### If resuming, the state is already loaded from Step 2.

Save the state file to `${CLAUDE_PROJECT_DIR}/.persona-panel/discuss-state.json` (create `.persona-panel/` directory if needed).

## Step 6: Run the Discussion

### Moderator Opening (if moderator is set)

Build a request for the moderator's opening statement and make an API call (see "Making an API Call" below). Display the response. Add it to all participants' histories as context.

### Main Loop

For each round (starting from `state.round` to `state.maxRounds - 1`):

1. Display: `--- Round {n} of {maxRounds} ---`

2. **For each participant** (excluding moderator if one is set):
   a. Build the system prompt (see "Building System Prompts")
   b. Build the messages array from `state.histories[shortName]`
   c. Add the turn prompt as a user message:
      - Round 1 (no moderator): `The topic for discussion is: "{topic}"\n\nShare your perspective.`
      - All other rounds: `Continue the discussion. Respond to what's been said, add your own perspective, challenge points you disagree with.\n\n[Round {n} of {maxRounds}]`
   d. Make the API call (see "Making an API Call")
   e. Display the persona's response (see "Display Format")
   f. Add the response as an assistant message in this persona's history
   g. Broadcast the response to all OTHER personas' histories as a user message: `[{Persona Name}]: {response text}` (merge with previous user message if the last message in their history is already a user message)
   h. Add to `state.transcript`
   i. Update `state.totalCost`
   j. **Save state checkpoint** — write `state` to the state file after EVERY persona turn
   k. **Check cost limit** — if `--max-cost` is set and `state.totalCost >= maxCost`, display a warning and jump to Step 7

3. **Moderator interjection** (if moderator is set):
   - If this is the last round or second-to-last: prompt for comprehensive closing summary
   - Otherwise: prompt for brief interjection (summarize key points, redirect, pose next question)
   - Make API call, display, broadcast to all participants, save checkpoint

4. Increment `state.round` and continue to next round.

### Making an API Call

For each persona turn:

1. Build the request JSON:
```json
{
  "provider": "<from persona config>",
  "model": "<from persona config>",
  "system": "<built system prompt>",
  "messages": <messages array from persona's history>,
  "maxTokens": 4096
}
```

2. Write the request JSON to a temp file:
```bash
cat > /tmp/persona-panel-req.json << 'REQEOF'
<request JSON>
REQEOF
```

3. Run the API call:
```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/call-llm.mjs --request /tmp/persona-panel-req.json
```

4. Parse the JSON response. If it contains `"error"`, display the error and skip this turn.

5. Extract: `text`, `usage.input`, `usage.output`, `cost`, `model`, `latencyMs`

### Building System Prompts

For each persona, build the system prompt as:

```
You ARE {persona.name}. Your worldview, practices, and opinions are described below.

PERSONA DOCUMENT:
{contents of persona.md}

────────────────────────────────────────────────────────────

You are participating in a panel discussion with other experts. Speak in first person as {persona.name}. Use your actual frameworks, language, and perspective. Be direct and specific.

CRITICAL — Response length: Match your response length to what the conversation actually needs. A single word ("Yes."), one sentence, or several paragraphs — whatever fits. If you agree, just say so. If someone asked a yes/no question, answer it. Only elaborate when the point genuinely requires it. Never pad a response with extra context, caveats, or restated points just to fill space. Shorter is almost always better.

You can reference what other participants said, agree, disagree, or build on their points. Don't repeat what's already been said.
```

If `state.fileContext` is non-empty, append:
```
CONTEXT — The following file has been shared for discussion:

{fileContext}
```

If `state.moderatorStyle` and this persona IS the moderator, append:
```
════════════════════════════════════════════════════════════
MODERATOR ROLE:
{moderatorStyle}

Session duration: up to {maxRounds} rounds. You will be told the current round number. When approaching the limit, begin wrapping up.
```

If `state.metaInstructions` is non-empty, append:
```
────────────────────────────────────────────────────────────
META-INSTRUCTIONS FROM SESSION DIRECTOR:
{join metaInstructions with newline, prefixed with "- "}
```

### Managing Conversation History

- Each persona has their own `histories[shortName]` array of `{role, content}` messages.
- When adding a user message: if the last message in history is already `role: "user"`, append to its content with `\n\n` separator (Anthropic requires strictly alternating roles).
- When adding an assistant message: just push `{role: "assistant", content}`.
- Trim history if it exceeds 60 messages (30 exchanges): remove the oldest 2 messages at a time from the front.

### Display Format

Show each persona's response as:

```markdown
**{Persona Name}** *({model})*

> {response text — as a blockquote}

*{input tokens} in / {output tokens} out · ${cost} · {latency}s — Running: ${totalCost}*
```

Between rounds, show:
```markdown
--- Round {n} of {maxRounds} ---
```

## Step 7: Final Summary (if --final-summary)

After the main loop completes (or cost limit hit), run a closing summary phase:

For each participant (NOT the moderator):
1. Build a special prompt: `Provide your final summary of this discussion: your top 3-5 takeaways, what was agreed upon, what remains unresolved, and your strongest recommendation.`
2. Make the API call (do NOT broadcast responses to other personas — these are independent summaries)
3. Display each summary
4. Add to transcript under a "Closing Summaries" section

## Step 8: Save Transcript

Create the transcript markdown file at `${CLAUDE_PROJECT_DIR}/reviews/YYYY-MM-DD-HHMM-panel-discussion.md`.

### Transcript Structure

```markdown
# Panel Discussion Transcript

**Date:** {date}
**Participants:** {comma-separated names}
**Topic:** {topic}
**Moderator:** {name or "None"}
**File context:** {path or "None"}
```

### If --context flag is set, add:

```markdown
## Context

**Topic:** {topic}
**Date:** {date}
**Duration:** {duration from startTime to now}
**Rounds:** {completed rounds} of {maxRounds}

### Participants

| Name | Provider | Model | Description |
|------|----------|-------|-------------|
| {Name} | {provider} | {model} | {first ~100 words of persona.md} |

### Settings
- Moderator: {name or "None"}
- Style: {style or "N/A"}
- Max cost: {limit or "None"}
- Final summary: {Yes/No}
```

### Discussion content:

For each round, output:
```markdown
## Round {n}

### {Speaker Name}

{response text}
```

### If --verbose flag is set, add after each speaker's response:

```markdown
<details><summary>Technical: {Speaker Name} — Round {n}</summary>

**System prompt** ({char count} chars):
> {first 500 chars of system prompt}...

**User message** ({char count} chars):
> {the prompt sent}

**Response metadata:**
- Latency: {latency}s
- Input tokens: {input}
- Output tokens: {output}
- Cost: ${cost}
- Model: {model}

</details>
```

### If --final-summary was used, add:

```markdown
## Closing Summaries

### {Speaker Name}

{summary text}
```

### Always end with cost summary:

Use the token usage data accumulated across all turns to build a summary table:

```markdown
---

## Token Usage & Cost

| Model | Input | Output | Cost |
|-------|------:|-------:|-----:|
| {model} | {input} | {output} | ${cost} |
| **Total** | **{input}** | **{output}** | **${total}** |
```

### After saving, display:
```
Transcript saved to: {path}
```

## Step 9: Cleanup

Delete the state file (`discuss-state.json`) since the discussion completed normally.

Display a final cost summary line:
```
Discussion complete. {rounds} rounds, {total tokens} tokens, ${total cost}.
```

## Handling User Interruption

If the user interrupts (Escape) at any point during the discussion:
- State is already saved (checkpointed after every turn).
- The user may provide natural language instructions like "be more concise", "focus on practical trade-offs", "wrap up in 2 more rounds".
- If the user provides meta-instructions: add them to `state.metaInstructions` array, save state, and tell the user they can say "continue" or run `/persona-discuss` again to resume.
- If the user says "stop" or "end": jump to Step 8 (save transcript) and Step 9 (cleanup).
- If the user says "continue": resume from the saved state (go to Step 5 with resume path).

## Moderator Style Definitions

Use these exact style instructions when building the moderator's system prompt:

**structured:**
```
You are the MODERATOR of this discussion. Your role:
- Open with a clear agenda and the key questions to address
- Assign speaking order and keep participants on-topic
- After each round of responses, provide a brief summary of key points
- Drive the conversation toward concrete conclusions and action items
- If participants drift off-topic, redirect firmly but respectfully
- Close with a comprehensive summary of agreements, disagreements, and next steps
```

**loose:**
```
You are the MODERATOR of this discussion. Your role:
- Set an opening question to frame the discussion
- Let participants speak freely — only intervene when:
  - Someone goes significantly off-topic
  - A conflict needs mediation
  - A quiet participant should be drawn in
- Keep interventions minimal and natural
- Close with a brief summary when the topic feels exhausted
```

**devil:**
```
You are the MODERATOR of this discussion. Your role:
- Challenge every position that participants take
- Play devil's advocate — push people to defend their views with specific evidence
- Question assumptions, probe weak points, and stress-test arguments
- If everyone agrees, find the strongest counterargument
- Your job is not to be disagreeable but to ensure no idea survives unchallenged
- Close with which arguments held up under scrutiny and which didn't
```
