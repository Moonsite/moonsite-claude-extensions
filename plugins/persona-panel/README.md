# Persona Panel

AI persona panel for Claude Code — synthesize expert personas from source materials and have them review documents, code, and ideas. Run multi-persona panel discussions with moderator support.

## Installation

Install as a Claude Code plugin:

```bash
claude plugin add /path/to/persona-panel
```

Or symlink into your plugins directory.

## Commands

### `/personas`
List all available personas (bundled and project-local).

### `/persona-discuss`
Start a multi-persona panel discussion.

```bash
# Basic discussion with all personas
/persona-discuss "Should we use microservices?"

# Specific personas only
/persona-discuss --with cherny,nate "Monolith vs microservices for a 10-person team"

# With a moderator
/persona-discuss --with cherny,nate --moderator cherny "API design philosophy"

# With file context
/persona-discuss --with cherny,nate --file src/api/routes.ts "Review this API design"

# Full options
/persona-discuss --with cherny,nate --rounds 8 --max-cost 2.00 --final-summary --context --verbose "Topic"
```

**Flags:**

| Flag | Description |
|------|-------------|
| `--with <names>` | Comma-separated persona short names |
| `--file <path>` | File to share as context with all personas |
| `--moderator <name>` | Persona to act as moderator |
| `--rounds <n>` | Maximum rounds (default: 12) |
| `--max-cost <n>` | Stop if total cost exceeds $n |
| `--final-summary` | Each persona writes an independent closing summary |
| `--context` | Add rich metadata header to transcript |
| `--verbose` | Include system prompts and technical data in transcript |

**During a discussion:**
- The discussion runs autonomously — no input needed between rounds
- Press **Escape** to interrupt and give instructions ("be more concise", "wrap up", "stop")
- Say "continue" or run `/persona-discuss` again to resume from where you left off
- State is checkpointed after every persona turn

### `/persona-review`
Get a single persona's review of a file, URL, or idea.

```bash
/persona-review --with cherny src/auth/middleware.ts
/persona-review --with nate "Should we pivot to B2B?"
```

### `/persona-review-all`
Get reviews from all personas on the same target.

### `/add-persona`
Add a new persona to your project.

### `/remove-persona`
Remove a persona from your project.

### `/save-persona`
Save a project persona for sharing.

### `/load-persona`
Load a shared persona into your project.

## Persona Structure

Each persona lives in a directory with two files:

```
personas/
  my-persona/
    config.json    # Name, provider, model, metadata
    persona.md     # Full persona document
```

### config.json

```json
{
  "name": "Display Name",
  "shortName": "lowercase-id",
  "provider": "anthropic",
  "model": "claude-opus-4-6",
  "color": "cyan",
  "sourceType": "web",
  "bundled": false
}
```

**Providers:** `anthropic` or `openai`

**Models:** Any model from the supported list — `claude-opus-4-6`, `claude-sonnet-4-6`, `gpt-4o`, `gpt-4.1`, `o3`, etc.

### persona.md

A detailed document describing the persona's worldview, frameworks, opinions, rhetorical style, and blind spots. The richer and more specific this document is, the better the persona performs.

Use `/add-persona` to synthesize a persona from web sources automatically.

## Persona Locations

- **Bundled personas** ship with the plugin: `<plugin-root>/personas/`
- **Project personas** are per-project: `.persona-panel/personas/` in your project root

Project personas override bundled ones with the same `shortName`.

## Cost Monitoring

Every API call shows token usage and cost inline:

```
*1,234 in / 456 out · $0.0523 · 8.2s — Running: $0.42*
```

Use `--max-cost` to set a hard limit. The discussion stops gracefully when the limit is reached.

Transcripts always include a cost summary table at the end.

## Transcripts

Discussions and reviews are saved to `reviews/` in your project directory:

```
reviews/2026-03-12-1430-panel-discussion.md
reviews/2026-03-12-cherny-persona-review.md
```

Use `--context` for rich metadata headers and `--verbose` for full technical details (prompts, latency, token counts per turn).

## Environment

Requires API keys in `.env` at your project root:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
```

Only the keys for providers you use are required.

## Architecture

```
commands/persona-discuss.md  → Claude Code orchestrates the discussion loop
scripts/call-llm.mjs        → Thin API wrapper (JSON in → JSON out)
scripts/review.mjs           → Single-persona review generator
scripts/synthesize.mjs       → Persona builder from source materials
scripts/costs.mjs            → Token pricing and cost tracking
```

The discussion engine runs natively inside Claude Code. `call-llm.mjs` handles only the authenticated API calls that Claude Code can't make directly.
