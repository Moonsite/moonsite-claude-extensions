#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'fs';
import { join, resolve } from 'path';

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

// ─── CLI args ────────────────────────────────────────────────────────────────
function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === '--name') args.name = argv[++i];
    else if (argv[i] === '--sources') args.sources = argv[++i];
    else if (argv[i] === '--output') args.output = argv[++i];
    else if (argv[i] === '--model') args.model = argv[++i];
    else if (argv[i] === '--provider') args.provider = argv[++i];
  }
  return args;
}

const args = parseArgs(process.argv);
if (!args.name || !args.sources || !args.output) {
  console.error('Usage: synthesize.mjs --name <name> --sources <path> --output <dir> --model <model> --provider <provider>');
  process.exit(1);
}

const model = args.model || 'claude-opus-4-6';
const provider = args.provider || 'anthropic';

// ─── Load sources ────────────────────────────────────────────────────────────
let sourceContent;

try {
  const stat = (await import('fs')).statSync(args.sources);
  if (stat.isDirectory()) {
    const files = [];
    function walk(dir) {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else files.push(full);
      }
    }
    walk(args.sources);
    sourceContent = files
      .sort()
      .map(f => `# FILE: ${f}\n\n${readFileSync(f, 'utf-8')}`)
      .join('\n\n' + '='.repeat(80) + '\n\n');
    console.log(`Loaded ${files.length} source files`);
  } else {
    sourceContent = readFileSync(args.sources, 'utf-8');
    console.log(`Loaded source file: ${args.sources}`);
  }
} catch {
  // Treat as inline text
  sourceContent = args.sources;
  console.log('Using inline text as source');
}

console.log(`Source: ${sourceContent.length} chars (~${Math.round(sourceContent.length / 4)} tokens)\n`);

// ─── API calls ───────────────────────────────────────────────────────────────
async function callAnthropic(system, userContent, maxTokens = 16384) {
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      system,
      messages: [{ role: 'user', content: userContent }]
    })
  });
  const data = await resp.json();
  if (data.error) throw new Error(`Anthropic API error: ${JSON.stringify(data.error)}`);
  return { text: data.content[0].text, usage: data.usage };
}

async function callOpenAI(system, userContent, maxTokens = 16384) {
  const resp = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`
    },
    body: JSON.stringify({
      model,
      max_completion_tokens: maxTokens,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: userContent }
      ]
    })
  });
  const data = await resp.json();
  if (data.error) throw new Error(`OpenAI API error: ${JSON.stringify(data.error)}`);
  return { text: data.choices[0].message.content, usage: data.usage };
}

const callLLM = provider === 'openai' ? callOpenAI : callAnthropic;

// ─── Pass 1: Batch extraction (if large source) ─────────────────────────────
const WORD_THRESHOLD = 10000;
const wordCount = sourceContent.split(/\s+/).length;
let extractedContent = sourceContent;

if (wordCount > WORD_THRESHOLD) {
  console.log(`Source is ${wordCount} words — running Pass 1 extraction\n`);
  console.log('═══ PASS 1: Extracting key ideas ═══\n');

  const EXTRACTION_SYSTEM = `You are extracting key ideas from source material about a person named ${args.name}.

For each section of content, extract:
1. **Core thesis and key arguments** — what is this person's main point?
2. **Named frameworks and concepts** — any mental models, named patterns, or vocabulary they use
3. **Concrete evidence** — specific data points, metrics, case studies, examples
4. **Contrarian or surprising claims** — where do they disagree with mainstream thinking?
5. **Actionable recommendations** — specific advice they give
6. **Strong opinions and value judgments** — what they feel strongly about and why

Be thorough. Preserve specific quotes, numbers, and named concepts. This extraction will be used to synthesize a persona document.`;

  // Split into chunks if very large (>50k chars)
  const CHUNK_SIZE = 50000;
  const chunks = [];
  for (let i = 0; i < sourceContent.length; i += CHUNK_SIZE) {
    chunks.push(sourceContent.slice(i, i + CHUNK_SIZE));
  }

  const extractions = [];
  for (let i = 0; i < chunks.length; i++) {
    console.log(`  Extracting chunk ${i + 1}/${chunks.length}...`);
    const result = await callLLM(EXTRACTION_SYSTEM, chunks[i], 8000);
    console.log(`  Done: ${JSON.stringify(result.usage)}`);
    extractions.push(result.text);
  }

  extractedContent = extractions.join('\n\n' + '─'.repeat(80) + '\n\n');
  console.log(`\nPass 1 complete: ${extractions.length} chunks extracted\n`);
}

// ─── Pass 2: Synthesize persona ──────────────────────────────────────────────
console.log('═══ PASS 2: Synthesizing persona document ═══\n');

const PERSONA_SYSTEM = `You are building a comprehensive expert persona document from compiled research material.

You will receive aggregated content about ${args.name}.

Create a detailed **Expert Persona Document** that captures:

## 1. WORLDVIEW & CORE BELIEFS
What does ${args.name} fundamentally believe? What are their axioms — the non-negotiable principles that drive everything else?

## 2. TECHNICAL PHILOSOPHY & PRACTICES
Their specific methods, tools, workflow principles, and technical opinions. Include actual choices and the reasoning behind them. If not applicable, cover their domain-specific methodology.

## 3. PRODUCT / DOMAIN PHILOSOPHY
How do they think about building things, making decisions, and creating value in their domain?

## 4. STRONG OPINIONS & CONTRARIAN TAKES
Where do they explicitly disagree with mainstream thinking? What do they think most people get wrong?

## 5. LEADERSHIP & TEAM PHILOSOPHY
How do they think about teams, hiring, influence, collaboration, and organizational design? If not applicable, cover their approach to working with others.

## 6. PREDICTIONS & FUTURE VISION
What do they believe is coming? What timeline do they give? How confident are they?

## 7. EVIDENCE BASE
What specific metrics, case studies, data, and examples do they cite? What is their empirical foundation?

## 8. BLIND SPOTS & ASSUMPTIONS
What do they take for granted? What perspectives might they underweight? What biases can you detect?

## 9. RHETORICAL STYLE
How do they communicate? What is their tone, structure, and approach to building arguments? What are their favorite rhetorical moves?

## 10. EVALUATION CRITERIA
Based on everything above, what specific things would ${args.name} focus on, praise, or criticize when reviewing work in their area of expertise? What would their rubric look like?

Be extremely specific. Use their actual language and frameworks. This document will be used to generate reviews and discussion contributions in their voice.`;

const pass2 = await callLLM(PERSONA_SYSTEM, extractedContent, 12000);
console.log(`Pass 2 done: ${JSON.stringify(pass2.usage)}`);

// ─── Save output ─────────────────────────────────────────────────────────────
const outputDir = resolve(args.output);
mkdirSync(outputDir, { recursive: true });

writeFileSync(join(outputDir, 'persona.md'), pass2.text);
writeFileSync(join(outputDir, 'sources.md'), sourceContent);

console.log(`\n${'═'.repeat(60)}`);
console.log(`Persona synthesized for: ${args.name}`);
console.log(`  persona.md: ${pass2.text.length} chars`);
console.log(`  sources.md: ${sourceContent.length} chars`);
console.log(`  Output: ${outputDir}`);
console.log('═'.repeat(60));
