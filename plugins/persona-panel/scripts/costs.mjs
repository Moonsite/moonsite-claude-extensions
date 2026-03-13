import { appendFileSync, mkdirSync, existsSync } from 'fs';
import { join, basename } from 'path';
import { execSync } from 'child_process';

// ─── Token cost monitoring ───────────────────────────────────────────────────
// Pricing: [input $/1M tokens, output $/1M tokens]
// Update as providers change pricing.
const MODEL_PRICING = {
  // Anthropic
  'claude-opus-4-6':            [15.00, 75.00],
  'claude-opus-4-20250514':     [15.00, 75.00],
  'claude-sonnet-4-6':          [3.00,  15.00],
  'claude-sonnet-4-20250514':   [3.00,  15.00],
  'claude-haiku-4-5-20251001':  [0.80,   4.00],
  // OpenAI
  'gpt-4o':                     [2.50,  10.00],
  'gpt-4o-mini':                [0.15,   0.60],
  'gpt-4.1':                    [2.00,   8.00],
  'gpt-4.1-mini':               [0.40,   1.60],
  'gpt-4.1-nano':               [0.10,   0.40],
  'o3':                         [10.00,  40.00],
  'o3-mini':                    [1.10,   4.40],
  'o4-mini':                    [1.10,   4.40],
  // Google Gemini
  'gemini-2.5-pro':             [1.25,  10.00],
  'gemini-2.5-flash':           [0.15,   0.60],
  'gemini-2.0-flash':           [0.10,   0.40],
};

function findPricing(model) {
  if (MODEL_PRICING[model]) return MODEL_PRICING[model];
  // Prefix match: "claude-opus-4-6-20260301" → "claude-opus-4-6"
  for (const key of Object.keys(MODEL_PRICING)) {
    if (model.startsWith(key)) return MODEL_PRICING[key];
  }
  return null;
}

function calcCost(model, inputTokens, outputTokens) {
  const pricing = findPricing(model);
  if (!pricing) return null;
  return (inputTokens * pricing[0] + outputTokens * pricing[1]) / 1_000_000;
}

// Normalize usage from either provider's response format
export function normalizeUsage(usage) {
  if (!usage) return { input: 0, output: 0 };
  return {
    input: usage.input_tokens ?? usage.prompt_tokens ?? 0,
    output: usage.output_tokens ?? usage.completion_tokens ?? 0
  };
}

export class CostTracker {
  constructor() {
    this.entries = [];
    this.totals = {};
  }

  add(model, inputTokens, outputTokens, label) {
    const cost = calcCost(model, inputTokens, outputTokens);
    this.entries.push({ model, inputTokens, outputTokens, cost, label });

    if (!this.totals[model]) this.totals[model] = { input: 0, output: 0 };
    this.totals[model].input += inputTokens;
    this.totals[model].output += outputTokens;

    return cost;
  }

  // One-line summary for inline display after an API call
  formatEntry(model, inputTokens, outputTokens) {
    const cost = calcCost(model, inputTokens, outputTokens);
    const tokens = `${inputTokens.toLocaleString()} in / ${outputTokens.toLocaleString()} out`;
    return cost !== null ? `${tokens} · $${cost.toFixed(4)}` : tokens;
  }

  get totalCost() {
    let total = 0;
    let hasUnknown = false;
    for (const [model, t] of Object.entries(this.totals)) {
      const cost = calcCost(model, t.input, t.output);
      if (cost !== null) total += cost;
      else hasUnknown = true;
    }
    return { total, hasUnknown };
  }

  get totalTokens() {
    let input = 0, output = 0;
    for (const t of Object.values(this.totals)) {
      input += t.input;
      output += t.output;
    }
    return { input, output };
  }

  // Running total one-liner
  formatRunningTotal() {
    const { input, output } = this.totalTokens;
    const { total, hasUnknown } = this.totalCost;
    const costStr = total > 0 ? `$${total.toFixed(4)}` : '';
    const warn = hasUnknown ? ' (partial)' : '';
    return `${input.toLocaleString()} in / ${output.toLocaleString()} out${costStr ? ' · ' + costStr + warn : ''}`;
  }

  // Full summary table for end of session
  summary() {
    const lines = [];
    lines.push('═══ Token Usage & Cost ═══');

    for (const [model, t] of Object.entries(this.totals)) {
      const cost = calcCost(model, t.input, t.output);
      const costStr = cost !== null ? `$${cost.toFixed(4)}` : 'pricing N/A';
      lines.push(`  ${model}: ${t.input.toLocaleString()} in / ${t.output.toLocaleString()} out → ${costStr}`);
    }

    const { input, output } = this.totalTokens;
    const { total, hasUnknown } = this.totalCost;
    lines.push('  ─────────────────────────────');
    lines.push(`  Total: ${input.toLocaleString()} in / ${output.toLocaleString()} out → $${total.toFixed(4)}${hasUnknown ? ' (some models have unknown pricing)' : ''}`);

    return lines.join('\n');
  }

  // Markdown summary for embedding in review/transcript files
  summaryMarkdown() {
    const lines = [];
    lines.push('## Token Usage & Cost\n');
    lines.push('| Model | Input | Output | Cost |');
    lines.push('|-------|------:|-------:|-----:|');

    for (const [model, t] of Object.entries(this.totals)) {
      const cost = calcCost(model, t.input, t.output);
      const costStr = cost !== null ? `$${cost.toFixed(4)}` : 'N/A';
      lines.push(`| ${model} | ${t.input.toLocaleString()} | ${t.output.toLocaleString()} | ${costStr} |`);
    }

    const { input, output } = this.totalTokens;
    const { total, hasUnknown } = this.totalCost;
    lines.push(`| **Total** | **${input.toLocaleString()}** | **${output.toLocaleString()}** | **$${total.toFixed(4)}**${hasUnknown ? '*' : ''} |`);
    if (hasUnknown) lines.push('\n*Some models have unknown pricing');

    return lines.join('\n');
  }
}

// ─── Persistent cost logging ────────────────────────────────────────────────

function detectProject() {
  try {
    const root = execSync('git rev-parse --show-toplevel', { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
    return basename(root);
  } catch {
    return basename(process.cwd());
  }
}

/**
 * Append a cost entry to both global (~/.persona-panel/cost-log.jsonl)
 * and project (.claude/persona-panel-costs.jsonl) logs.
 */
export function logCost({ model, provider, inputTokens, outputTokens, cost, action, persona }) {
  const home = process.env.HOME || process.env.USERPROFILE || '';
  const entry = JSON.stringify({
    ts: new Date().toISOString(),
    project: detectProject(),
    action: action || 'call',
    persona: persona || '',
    provider: provider || '',
    model,
    in: inputTokens,
    out: outputTokens,
    cost: cost !== null && cost !== undefined ? +cost.toFixed(6) : null
  }) + '\n';

  // Global log
  const globalDir = join(home, '.persona-panel');
  try { mkdirSync(globalDir, { recursive: true }); appendFileSync(join(globalDir, 'cost-log.jsonl'), entry); } catch {}

  // Project log
  try {
    if (!existsSync('.claude')) mkdirSync('.claude', { recursive: true });
    appendFileSync(join('.claude', 'persona-panel-costs.jsonl'), entry);
  } catch {}
}
