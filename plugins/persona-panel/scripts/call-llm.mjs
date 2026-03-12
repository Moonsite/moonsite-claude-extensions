#!/usr/bin/env node
// Thin API wrapper: reads a JSON request file, makes one LLM call, returns JSON.
// Usage: node call-llm.mjs --request <file.json>
import { readFileSync } from 'fs';
import { join } from 'path';
import { normalizeUsage } from './costs.mjs';

// ─── .env loader ─────────────────────────────────────────────────────────────
function loadEnv() {
  const paths = ['.env', join(process.cwd(), '.env')];
  for (const p of paths) {
    try {
      const content = readFileSync(p, 'utf-8');
      for (const line of content.split('\n')) {
        const m = line.match(/^([^#=]+)=(.*)$/);
        if (m) process.env[m[1].trim()] = m[2].trim();
      }
      return;
    } catch {}
  }
}
loadEnv();

// ─── Pricing (duplicated from costs.mjs for cost calculation) ────────────────
const MODEL_PRICING = {
  'claude-opus-4-6': [15.00, 75.00], 'claude-opus-4-20250514': [15.00, 75.00],
  'claude-sonnet-4-6': [3.00, 15.00], 'claude-sonnet-4-20250514': [3.00, 15.00],
  'claude-haiku-4-5-20251001': [0.80, 4.00],
  'gpt-4o': [2.50, 10.00], 'gpt-4o-mini': [0.15, 0.60],
  'gpt-4.1': [2.00, 8.00], 'gpt-4.1-mini': [0.40, 1.60], 'gpt-4.1-nano': [0.10, 0.40],
  'o3': [10.00, 40.00], 'o3-mini': [1.10, 4.40], 'o4-mini': [1.10, 4.40],
};

function calcCost(model, input, output) {
  const p = MODEL_PRICING[model] || Object.entries(MODEL_PRICING).find(([k]) => model.startsWith(k))?.[1];
  if (!p) return null;
  return (input * p[0] + output * p[1]) / 1_000_000;
}

// ─── API calls ───────────────────────────────────────────────────────────────
async function callAnthropic(req) {
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: req.model,
      max_tokens: req.maxTokens || 4096,
      system: req.system,
      messages: req.messages,
    }),
  });
  const data = await resp.json();
  if (data.error) throw new Error(JSON.stringify(data.error));
  const usage = normalizeUsage(data.usage);
  return { text: data.content[0].text, usage };
}

async function callOpenAI(req) {
  const resp = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
    },
    body: JSON.stringify({
      model: req.model,
      max_completion_tokens: req.maxTokens || 4096,
      messages: [{ role: 'system', content: req.system }, ...req.messages],
    }),
  });
  const data = await resp.json();
  if (data.error) throw new Error(JSON.stringify(data.error));
  const usage = normalizeUsage(data.usage);
  return { text: data.choices[0].message.content, usage };
}

// ─── Main ────────────────────────────────────────────────────────────────────
const reqFileIdx = process.argv.indexOf('--request');
if (reqFileIdx === -1 || !process.argv[reqFileIdx + 1]) {
  console.error(JSON.stringify({ error: 'Usage: call-llm.mjs --request <file.json>' }));
  process.exit(1);
}

try {
  const req = JSON.parse(readFileSync(process.argv[reqFileIdx + 1], 'utf-8'));
  const start = Date.now();
  const callFn = req.provider === 'openai' ? callOpenAI : callAnthropic;
  const result = await callFn(req);
  const latencyMs = Date.now() - start;
  const cost = calcCost(req.model, result.usage.input, result.usage.output);

  console.log(JSON.stringify({
    text: result.text,
    usage: result.usage,
    cost,
    model: req.model,
    latencyMs,
  }));
} catch (e) {
  console.log(JSON.stringify({ error: e.message }));
  process.exit(1);
}
