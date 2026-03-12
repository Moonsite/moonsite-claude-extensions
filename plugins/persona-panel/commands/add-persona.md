---
description: Create a new AI persona from source material (URLs, files, or pasted text)
argument-hint: <persona-name>
---

# Add Persona

The user wants to create a new persona. The persona name is provided in `$ARGUMENTS` (e.g., "boris-sigalov").

You are creating a new AI persona called **$ARGUMENTS** for the persona-panel plugin.

## Step 1: Gather Information

Ask the user the following questions one at a time:

### Source Type
"What source material should I use to build this persona?"
- **URLs** — I'll fetch web pages and extract the person's ideas, style, and frameworks
- **Files** — Point me to local files (articles, transcripts, emails, writing samples)
- **Text** — Paste text directly that captures this person's voice and thinking

### Model & Provider
"Which LLM should this persona use when generating reviews and participating in discussions?"
- **anthropic / claude-opus-4-6** — Best for nuanced, thorough analysis
- **anthropic / claude-sonnet-4-6** — Faster, good balance of quality and speed
- **openai / gpt-5.4** — OpenAI's flagship model
- Or specify any other provider/model combination

### Terminal Color
"Pick a terminal color for this persona's output in discussions:"
- cyan, yellow, green, red, magenta, blue, white

## Step 2: Load Sources

Based on the source type:

**If URLs:** Ask the user for the URLs. Use WebFetch to download each page. Concatenate the extracted text.

**If Files:** Ask the user for file paths or glob patterns. Read all matching files and concatenate.

**If Text:** Ask the user to paste the text.

Save the raw source material to a temporary file.

## Step 3: Synthesize Persona

Run the synthesis pipeline:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/synthesize.mjs \
  --name "$ARGUMENTS" \
  --sources <source-file-path> \
  --output "${CLAUDE_PROJECT_DIR}/.persona-panel/personas/$ARGUMENTS" \
  --model <chosen-model> \
  --provider <chosen-provider>
```

## Step 4: Save Config

Write the config.json to `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/$ARGUMENTS/config.json`:

```json
{
  "name": "<display name>",
  "shortName": "$ARGUMENTS",
  "provider": "<chosen provider>",
  "model": "<chosen model>",
  "color": "<chosen color>",
  "sourceType": "<urls|files|text>",
  "bundled": false
}
```

Also save the source material as `sources.md` in the same directory.

## Step 5: Confirm

Tell the user the persona has been created and show them how to use it:
- `/persona-review $ARGUMENTS <target>` — to generate a review
- `/persona-discuss --with $ARGUMENTS` — to include in a discussion
- `/personas` — to see all available personas
