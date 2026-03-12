#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync, readdirSync } from 'fs';
import { join, basename, extname, resolve, dirname } from 'path';
import { CostTracker, normalizeUsage } from './costs.mjs';

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
    if (argv[i] === '--persona') args.persona = argv[++i];
    else if (argv[i] === '--target') args.target = argv[++i];
    else if (argv[i] === '--output') args.output = argv[++i];
    else if (argv[i] === '--type') args.type = argv[++i];
  }
  return args;
}

const args = parseArgs(process.argv);
if (!args.persona || !args.target) {
  console.error('Usage: review.mjs --persona <dir> --target <path-or-text> [--output <path>] [--type code|doc|idea]');
  process.exit(1);
}

// ─── Load persona ────────────────────────────────────────────────────────────
const personaDir = resolve(args.persona);
const config = JSON.parse(readFileSync(join(personaDir, 'config.json'), 'utf-8'));
const personaDoc = readFileSync(join(personaDir, 'persona.md'), 'utf-8');

console.log(`\x1b[1mPersona:\x1b[0m ${config.name} (${config.provider}/${config.model})`);

// ─── Simple glob expansion (no shell) ────────────────────────────────────────
function matchGlob(pattern) {
  // Convert glob to regex: ** → any path, * → any segment
  const parts = pattern.split('/');
  const files = [];

  function walk(dir, patternParts, depth) {
    if (patternParts.length === 0) return;

    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch { return; }

    const current = patternParts[0];
    const remaining = patternParts.slice(1);

    if (current === '**') {
      // Match zero or more directories
      // Try matching remaining pattern at this level
      walk(dir, remaining, depth + 1);
      // Also recurse into subdirectories with same pattern
      for (const entry of entries) {
        if (entry.isDirectory() && !entry.name.startsWith('.')) {
          walk(join(dir, entry.name), patternParts, depth + 1);
        }
      }
    } else {
      // Convert glob wildcards to regex
      const regex = new RegExp(
        '^' + current.replace(/\./g, '\\.').replace(/\*/g, '[^/]*') + '$'
      );

      for (const entry of entries) {
        if (!regex.test(entry.name)) continue;

        const fullPath = join(dir, entry.name);
        if (remaining.length === 0) {
          if (entry.isFile()) files.push(fullPath);
        } else if (entry.isDirectory()) {
          walk(fullPath, remaining, depth + 1);
        }
      }
    }
  }

  const startDir = pattern.startsWith('/') ? '/' : '.';
  walk(startDir, parts, 0);
  return files.sort();
}

// ─── Resolve target ──────────────────────────────────────────────────────────
function resolveTarget(target) {
  // URL
  if (target.startsWith('http://') || target.startsWith('https://')) {
    return { type: 'url', content: null, path: target };
  }

  // Glob pattern
  if (target.includes('*')) {
    const files = matchGlob(target);
    if (files.length === 0) {
      console.error(`No files matched pattern: ${target}`);
      process.exit(1);
    }
    const content = files
      .map(f => `# FILE: ${f}\n\n${readFileSync(f, 'utf-8')}`)
      .join('\n\n' + '='.repeat(80) + '\n\n');
    console.log(`Matched ${files.length} files`);
    return { type: 'glob', content, files };
  }

  // File or directory
  try {
    const stat = statSync(target);
    if (stat.isDirectory()) {
      const files = [];
      function walk(dir) {
        for (const entry of readdirSync(dir, { withFileTypes: true })) {
          const full = join(dir, entry.name);
          if (entry.isDirectory()) walk(full);
          else files.push(full);
        }
      }
      walk(target);
      const contents = files
        .sort()
        .map(f => `# FILE: ${f}\n\n${readFileSync(f, 'utf-8')}`)
        .join('\n\n' + '='.repeat(80) + '\n\n');
      return { type: 'files', content: contents, files };
    } else {
      return { type: 'file', content: readFileSync(target, 'utf-8'), path: target };
    }
  } catch {}

  // Inline text (no file match)
  return { type: 'text', content: target };
}

const resolved = resolveTarget(args.target);

// Fetch URL content if needed
if (resolved.type === 'url') {
  console.log(`Fetching: ${resolved.path}`);
  try {
    const resp = await fetch(resolved.path);
    resolved.content = await resp.text();
    // Strip HTML tags for basic extraction
    resolved.content = resolved.content
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  } catch (e) {
    console.error(`Failed to fetch URL: ${e.message}`);
    process.exit(1);
  }
}

// ─── Detect review type ──────────────────────────────────────────────────────
function detectType(resolved, explicitType) {
  if (explicitType) return explicitType;

  if (resolved.type === 'text') return 'idea';
  if (resolved.type === 'url') return 'doc';

  const path = resolved.path || (resolved.files && resolved.files[0]) || '';
  const ext = extname(path).toLowerCase();

  const codeExts = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.py', '.go', '.rs', '.java', '.cs', '.rb', '.swift', '.kt', '.c', '.cpp', '.h'];
  const docExts = ['.md', '.txt', '.rst', '.adoc', '.html', '.pdf'];

  if (codeExts.includes(ext)) return 'code';
  if (docExts.includes(ext)) return 'doc';
  return 'doc';
}

const reviewType = detectType(resolved, args.type);
console.log(`Review type: ${reviewType}`);
console.log(`Content: ${resolved.content.length} chars (~${Math.round(resolved.content.length / 4)} tokens)\n`);

// ─── Build review prompt ─────────────────────────────────────────────────────
const TYPE_INSTRUCTIONS = {
  doc: `Focus your review on:
- Clarity and completeness of the document
- Strategic coherence and internal consistency
- What's missing or underspecified
- Where claims lack evidence or reasoning
- Practical actionability of recommendations
- What the document gets right and should double down on`,

  code: `Focus your review on:
- Architecture and design patterns — are they appropriate?
- Code quality — readability, maintainability, naming
- Potential bugs, edge cases, or error handling gaps
- Security considerations
- Performance implications
- What's done well and what patterns to replicate`,

  idea: `Focus your review on:
- Feasibility — is this realistic given current technology and constraints?
- Key tradeoffs the person should consider
- Alternative approaches they may not have considered
- Risks and potential failure modes
- What excites you about this and what concerns you
- Concrete next steps you'd recommend`
};

const REVIEW_SYSTEM = `You ARE ${config.name}. Your worldview, practices, and opinions are described in the persona document below.

PERSONA DOCUMENT:
${personaDoc}

${'─'.repeat(60)}

Now review the following content AS ${config.name}. Write in first person. Use your actual experience, frameworks, and language. Be specific, not generic.

${TYPE_INSTRUCTIONS[reviewType]}

Structure your review with clear sections. Be direct and practical — give your honest assessment based on your specific expertise and perspective.`;

// ─── API call ────────────────────────────────────────────────────────────────
async function callAnthropic(system, userContent, model, maxTokens = 16384) {
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

async function callOpenAI(system, userContent, model, maxTokens = 16384) {
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

// ─── Generate review ─────────────────────────────────────────────────────────
const tracker = new CostTracker();
console.log(`Generating review as ${config.name}...\n`);

const callFn = config.provider === 'openai' ? callOpenAI : callAnthropic;
const result = await callFn(REVIEW_SYSTEM, resolved.content, config.model);

const usage = normalizeUsage(result.usage);
tracker.add(config.model, usage.input, usage.output, 'review');
console.log(`Done: ${tracker.formatEntry(config.model, usage.input, usage.output)}\n`);

// ─── Save output ─────────────────────────────────────────────────────────────
const date = new Date().toISOString().substring(0, 10);
const outputPath = args.output || `reviews/${date}-${config.shortName}-persona-review.md`;
const outputDir = dirname(outputPath);

mkdirSync(outputDir, { recursive: true });

const targetLabel = resolved.type === 'text'
  ? `"${args.target.substring(0, 100)}${args.target.length > 100 ? '...' : ''}"`
  : args.target;

writeFileSync(outputPath, `# ${config.name} — Persona Review

**Date:** ${date}
**Persona:** ${config.name} (${config.provider}/${config.model})
**Target:** ${targetLabel}
**Review type:** ${reviewType}

---

${result.text}

---

${tracker.summaryMarkdown()}
`);

console.log(`Review saved to: ${outputPath}`);
console.log(`\n${tracker.summary()}`);
