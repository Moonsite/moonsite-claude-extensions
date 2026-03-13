---
description: Create a new AI persona from source material (URLs, files, or pasted text)
argument-hint: <persona-name> [--global]
---

# Add Persona

The user wants to create a new persona. The persona name is provided in `$ARGUMENTS` (e.g., "boris-sigalov" or "boris-sigalov --global").

Parse `$ARGUMENTS` to extract:
- **Persona name** — the first word (everything before any flags)
- **`--global` flag** — if present, the persona will be saved to the global directory instead of the project directory

You are creating a new AI persona called **<persona-name>** for the persona-panel plugin.

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

## Step 3: Determine Output Directory

- **If `--global` flag is set:** Use `$HOME/.claude/persona-panel/personas/<persona-name>`
- **Otherwise:** Use `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/<persona-name>`

Create the directory if it doesn't exist.

## Step 4: Synthesize Persona

Run the synthesis pipeline:

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/synthesize.mjs \
  --name "<persona-name>" \
  --sources <source-file-path> \
  --output "<output-directory>" \
  --model <chosen-model> \
  --provider <chosen-provider>
```

## Step 5: Save Config

Write the config.json to `<output-directory>/config.json`:

```json
{
  "name": "<display name>",
  "shortName": "<persona-name>",
  "provider": "<chosen provider>",
  "model": "<chosen model>",
  "color": "<chosen color>",
  "sourceType": "<urls|files|text>",
  "bundled": false
}
```

Also save the source material as `sources.md` in the same directory.

## Step 6: Confirm

Tell the user the persona has been created and where it was saved:
- **Global:** `$HOME/.claude/persona-panel/personas/<persona-name>` — available in all projects
- **Project:** `${CLAUDE_PROJECT_DIR}/.persona-panel/personas/<persona-name>` — available only in this project

Show them how to use it:
- `/persona-review <persona-name> <target>` — to generate a review
- `/persona-discuss --with <persona-name>` — to include in a discussion
- `/personas` — to see all available personas
