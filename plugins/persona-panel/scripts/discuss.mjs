#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'fs';
import { join, resolve } from 'path';
import { createInterface } from 'readline';
import { CostTracker } from './costs.mjs';

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

// ─── ANSI colors ─────────────────────────────────────────────────────────────
const COLORS = {
  cyan: '\x1b[36m',
  yellow: '\x1b[33m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  magenta: '\x1b[35m',
  blue: '\x1b[34m',
  white: '\x1b[37m'
};
const BOLD = '\x1b[1m';
const DIM = '\x1b[2m';
const RESET = '\x1b[0m';

function colorize(text, color) {
  return `${COLORS[color] || ''}${text}${RESET}`;
}

// ─── CLI args ────────────────────────────────────────────────────────────────
function parseArgs(argv) {
  const args = { with: null, topic: null, moderator: null, style: null, duration: null, file: null, length: 'normal' };
  const positional = [];

  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === '--personas-dir') args.personasDir = argv[++i];
    else if (argv[i] === '--bundled-dir') args.bundledDir = argv[++i];
    else if (argv[i] === '--topic') args.topic = argv[++i];
    else if (argv[i] === '--with') args.with = argv[++i].split(',').map(s => s.trim().toLowerCase());
    else if (argv[i] === '--moderator') args.moderator = argv[++i].toLowerCase();
    else if (argv[i] === '--style') args.style = argv[++i];
    else if (argv[i] === '--duration') args.duration = argv[++i];
    else if (argv[i] === '--file') args.file = argv[++i];
    else if (argv[i] === '--length') args.length = argv[++i];
    else positional.push(argv[i]);
  }

  if (!args.topic && positional.length > 0) {
    args.topic = positional.join(' ');
  }

  return args;
}

const args = parseArgs(process.argv);

// ─── Load personas ───────────────────────────────────────────────────────────
function loadPersonasFromDir(dir, bundled = false) {
  const personas = [];
  if (!dir || !existsSync(dir)) return personas;

  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const configPath = join(dir, entry.name, 'config.json');
    const personaPath = join(dir, entry.name, 'persona.md');
    if (!existsSync(configPath) || !existsSync(personaPath)) continue;

    const config = JSON.parse(readFileSync(configPath, 'utf-8'));
    const personaDoc = readFileSync(personaPath, 'utf-8');
    personas.push({ ...config, personaDoc, dir: join(dir, entry.name), bundled });
  }
  return personas;
}

let allPersonas = [
  ...loadPersonasFromDir(args.bundledDir, true),
  ...loadPersonasFromDir(args.personasDir, false)
];

// Filter by --with
if (args.with) {
  allPersonas = allPersonas.filter(p =>
    args.with.includes(p.shortName.toLowerCase()) ||
    args.with.includes(p.name.toLowerCase())
  );
}

if (allPersonas.length === 0) {
  console.error('No personas found. Check --personas-dir and --bundled-dir paths.');
  process.exit(1);
}

// ─── File context ────────────────────────────────────────────────────────────
let fileContext = '';
if (args.file) {
  try {
    fileContext = readFileSync(args.file, 'utf-8');
    console.log(`${DIM}Loaded file context: ${args.file} (${fileContext.length} chars)${RESET}\n`);
  } catch (e) {
    console.error(`Failed to read file: ${e.message}`);
    process.exit(1);
  }
}

// ─── Moderator setup ─────────────────────────────────────────────────────────
let moderator = null;
let moderatorStyle = '';
let maxRounds = 20;

if (args.moderator) {
  moderator = allPersonas.find(p =>
    p.shortName.toLowerCase() === args.moderator ||
    p.name.toLowerCase() === args.moderator
  );
  if (!moderator) {
    console.error(`Moderator "${args.moderator}" not found among loaded personas.`);
    process.exit(1);
  }
}

// Duration → round limits
const DURATION_ROUNDS = {
  quick: { min: 3, max: 5 },
  standard: { min: 8, max: 12 },
  deep: { min: 20, max: 30 },
  'until-done': { min: 1, max: 40 }
};

if (args.duration && DURATION_ROUNDS[args.duration]) {
  maxRounds = DURATION_ROUNDS[args.duration].max;
}

// Moderator style instructions
const STYLE_INSTRUCTIONS = {
  structured: `You are the MODERATOR of this discussion. Your role:
- Open with a clear agenda and the key questions to address
- Assign speaking order and keep participants on-topic
- After each round of responses, provide a brief summary of key points
- Drive the conversation toward concrete conclusions and action items
- If participants drift off-topic, redirect firmly but respectfully
- Close with a comprehensive summary of agreements, disagreements, and next steps`,

  loose: `You are the MODERATOR of this discussion. Your role:
- Set an opening question to frame the discussion
- Let participants speak freely — only intervene when:
  - Someone goes significantly off-topic
  - A conflict needs mediation
  - A quiet participant should be drawn in
- Keep interventions minimal and natural
- Close with a brief summary when the topic feels exhausted`,

  devil: `You are the MODERATOR of this discussion. Your role:
- Challenge every position that participants take
- Play devil's advocate — push people to defend their views with specific evidence
- Question assumptions, probe weak points, and stress-test arguments
- If everyone agrees, find the strongest counterargument
- Your job is not to be disagreeable but to ensure no idea survives unchallenged
- Close with which arguments held up under scrutiny and which didn't`
};

if (args.style) {
  moderatorStyle = STYLE_INSTRUCTIONS[args.style] || `You are the MODERATOR of this discussion. ${args.style}`;
}

// ─── Response length control ─────────────────────────────────────────────────
const LENGTH_PRESETS = {
  brief:    { instruction: 'Keep responses to 1-3 sentences. Be extremely concise — a single word or short phrase is fine if that\'s the honest answer. No filler.', maxTokens: 512 },
  normal:   { instruction: 'Keep responses focused and concise — aim for 2-4 paragraphs per turn.', maxTokens: 4096 },
  detailed: { instruction: 'Provide thorough, detailed responses with examples and evidence. 4-8 paragraphs per turn is fine.', maxTokens: 8192 }
};

let currentLength = LENGTH_PRESETS[args.length] ? args.length : 'normal';

// ─── Build system prompts ────────────────────────────────────────────────────
function buildSystemPrompt(persona, isModerator = false) {
  const lengthInstruction = LENGTH_PRESETS[currentLength].instruction;

  let prompt = `You ARE ${persona.name}. Your worldview, practices, and opinions are described below.

PERSONA DOCUMENT:
${persona.personaDoc}

${'─'.repeat(60)}

You are participating in a panel discussion with other experts. Speak in first person as ${persona.name}. Use your actual frameworks, language, and perspective. Be direct and specific.

${lengthInstruction} You can reference what other participants said, agree, disagree, or build on their points. Don't repeat what's already been said.`;

  if (fileContext) {
    prompt += `\n\nCONTEXT — The following file has been shared for discussion:\n\n${fileContext}`;
  }

  if (isModerator && moderatorStyle) {
    prompt += `\n\n${'═'.repeat(60)}\nMODERATOR ROLE:\n${moderatorStyle}\n\nSession duration: up to ${maxRounds} rounds. You will be told the current round number. When approaching the limit, begin wrapping up.`;
  }

  return prompt;
}

// ─── Streaming API wrappers ──────────────────────────────────────────────────
async function streamAnthropic(system, messages, model, onChunk) {
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': process.env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model,
      max_tokens: LENGTH_PRESETS[currentLength].maxTokens,
      stream: true,
      system,
      messages
    })
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Anthropic API ${resp.status}: ${err}`);
  }

  let fullText = '';
  const usage = { input: 0, output: 0 };
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6);
      if (data === '[DONE]') continue;

      try {
        const event = JSON.parse(data);
        if (event.type === 'message_start' && event.message?.usage) {
          usage.input = event.message.usage.input_tokens || 0;
        }
        if (event.type === 'content_block_delta' && event.delta?.text) {
          fullText += event.delta.text;
          onChunk(event.delta.text);
        }
        if (event.type === 'message_delta' && event.usage) {
          usage.output = event.usage.output_tokens || 0;
        }
      } catch {}
    }
  }

  return { text: fullText, usage };
}

async function streamOpenAI(system, messages, model, onChunk) {
  const oaiMessages = [
    { role: 'system', content: system },
    ...messages
  ];

  const resp = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`
    },
    body: JSON.stringify({
      model,
      max_completion_tokens: LENGTH_PRESETS[currentLength].maxTokens,
      stream: true,
      stream_options: { include_usage: true },
      messages: oaiMessages
    })
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`OpenAI API ${resp.status}: ${err}`);
  }

  let fullText = '';
  const usage = { input: 0, output: 0 };
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6).trim();
      if (data === '[DONE]') continue;

      try {
        const event = JSON.parse(data);
        const content = event.choices?.[0]?.delta?.content;
        if (content) {
          fullText += content;
          onChunk(content);
        }
        if (event.usage) {
          usage.input = event.usage.prompt_tokens || 0;
          usage.output = event.usage.completion_tokens || 0;
        }
      } catch {}
    }
  }

  return { text: fullText, usage };
}

// ─── Conversation history ────────────────────────────────────────────────────
// Each persona maintains their own conversation history.
// Anthropic requires strictly alternating user/assistant roles.
const MAX_EXCHANGES = 30;

class ConversationManager {
  constructor() {
    // Per-persona message histories
    this.histories = new Map();
  }

  init(persona) {
    this.histories.set(persona.shortName, []);
  }

  addUserMessage(personaName, content) {
    const history = this.histories.get(personaName);
    if (!history) return;

    // Merge consecutive user messages
    if (history.length > 0 && history[history.length - 1].role === 'user') {
      history[history.length - 1].content += '\n\n' + content;
    } else {
      history.push({ role: 'user', content });
    }

    // Trim if too long
    while (history.length > MAX_EXCHANGES * 2) {
      history.shift();
      history.shift();
    }
  }

  addAssistantMessage(personaName, content) {
    const history = this.histories.get(personaName);
    if (!history) return;
    history.push({ role: 'assistant', content });
  }

  getHistory(personaName) {
    return this.histories.get(personaName) || [];
  }
}

// ─── Discussion engine ───────────────────────────────────────────────────────
const conversation = new ConversationManager();
const tracker = new CostTracker();
const transcript = [];
let currentRound = 0;

// Initialize per-persona histories
for (const p of allPersonas) {
  conversation.init(p);
}

// Build speaking order
function getSpeakers() {
  if (!moderator) {
    // Round-robin, all personas
    return allPersonas;
  }

  // Moderator-led: participants (excluding moderator) in order
  return allPersonas.filter(p => p.shortName !== moderator.shortName);
}

const participants = getSpeakers();

async function speakAs(persona, prompt, isModerator = false) {
  const system = buildSystemPrompt(persona, isModerator);

  // Add the prompt as a user message
  conversation.addUserMessage(persona.shortName, prompt);
  const messages = conversation.getHistory(persona.shortName);

  const color = persona.color || 'white';
  const header = `\n${BOLD}${colorize(`┌─ ${persona.name}`, color)} ${DIM}(${persona.provider}/${persona.model})${RESET}${BOLD}${colorize(' ─', color)}${RESET}`;
  process.stdout.write(header + '\n');
  process.stdout.write(colorize('│ ', color));

  let fullResponse = '';
  let turnUsage = { input: 0, output: 0 };
  const streamFn = persona.provider === 'openai' ? streamOpenAI : streamAnthropic;

  try {
    const result = await streamFn(system, messages, persona.model, (chunk) => {
      // Handle newlines for box drawing
      const formatted = chunk.replace(/\n/g, `\n${colorize('│ ', color)}`);
      process.stdout.write(colorize(formatted, color));
    });
    fullResponse = result.text;
    turnUsage = result.usage;
  } catch (e) {
    process.stdout.write(`\n${colorize('│ ', color)}${BOLD}\x1b[31m[Error: ${e.message}]${RESET}`);
    fullResponse = `[Error: ${e.message}]`;
  }

  // Track cost
  tracker.add(persona.model, turnUsage.input, turnUsage.output, persona.shortName);
  const costLine = tracker.formatEntry(persona.model, turnUsage.input, turnUsage.output);
  process.stdout.write(`\n${colorize('└─', color)} ${DIM}${costLine} · running: ${tracker.formatRunningTotal()}${RESET}\n`);

  // Save to histories
  conversation.addAssistantMessage(persona.shortName, fullResponse);

  // Add this persona's response as context for other personas
  const contextMsg = `[${persona.name}]: ${fullResponse}`;
  for (const other of allPersonas) {
    if (other.shortName !== persona.shortName) {
      conversation.addUserMessage(other.shortName, contextMsg);
    }
  }

  // Add to transcript
  transcript.push({ speaker: persona.name, text: fullResponse, round: currentRound });

  return fullResponse;
}

// ─── Transcript saving ───────────────────────────────────────────────────────
function saveTranscript() {
  mkdirSync('reviews', { recursive: true });
  const date = new Date().toISOString().substring(0, 10);
  const time = new Date().toISOString().substring(11, 16).replace(':', '');
  const path = `reviews/${date}-${time}-panel-discussion.md`;

  const topic = args.topic || 'General discussion';
  const personaNames = allPersonas.map(p => p.name).join(', ');

  let content = `# Panel Discussion Transcript

**Date:** ${date}
**Participants:** ${personaNames}
**Topic:** ${topic}
${moderator ? `**Moderator:** ${moderator.name}` : ''}
${args.file ? `**File context:** ${args.file}` : ''}

---

`;

  let lastRound = -1;
  for (const entry of transcript) {
    if (entry.round !== lastRound) {
      content += `\n## Round ${entry.round + 1}\n\n`;
      lastRound = entry.round;
    }
    content += `### ${entry.speaker}\n\n${entry.text}\n\n`;
  }

  content += `\n---\n\n${tracker.summaryMarkdown()}\n`;

  writeFileSync(path, content);
  console.log(`\n${tracker.summary()}`);
  console.log(`${DIM}Transcript saved to: ${path}${RESET}`);
  return path;
}

// ─── User input ──────────────────────────────────────────────────────────────
const isInteractive = process.stdin.isTTY === true;

let rl;
if (isInteractive) {
  rl = createInterface({
    input: process.stdin,
    output: process.stdout
  });
} else {
  console.log(`${DIM}Non-interactive mode — auto-continuing all rounds${RESET}`);
}

function prompt(question) {
  if (!isInteractive) return Promise.resolve('');
  return new Promise((resolve) => {
    rl.question(question, resolve);
  });
}

// ─── Ctrl+C handler ──────────────────────────────────────────────────────────
let exiting = false;
process.on('SIGINT', () => {
  if (exiting) process.exit(0);
  exiting = true;
  console.log(`\n\n${DIM}Saving transcript...${RESET}`);
  saveTranscript();
  if (rl) rl.close();
  process.exit(0);
});

// ─── Main loop ───────────────────────────────────────────────────────────────
console.log(`\n${BOLD}${'═'.repeat(60)}${RESET}`);
console.log(`${BOLD}  PERSONA PANEL DISCUSSION${RESET}`);
console.log(`${BOLD}${'═'.repeat(60)}${RESET}`);
console.log(`${DIM}  Participants: ${allPersonas.map(p => colorize(p.name, p.color)).join(', ')}${RESET}`);
if (moderator) {
  console.log(`${DIM}  Moderator: ${colorize(moderator.name, moderator.color)}${RESET}`);
  console.log(`${DIM}  Style: ${args.style || 'default'} | Duration: ${args.duration || 'standard'} (max ${maxRounds} rounds)${RESET}`);
}
if (args.topic) {
  console.log(`${DIM}  Topic: ${args.topic}${RESET}`);
}
console.log(`${DIM}  Length: ${currentLength} (max ${LENGTH_PRESETS[currentLength].maxTokens} tokens)${RESET}`);
console.log(`${DIM}  Commands: /ask <question>  /brief  /normal  /detailed  /skip  /save  /quit${RESET}`);
console.log(`${BOLD}${'═'.repeat(60)}${RESET}\n`);

const topic = args.topic || 'Share your perspectives on the current state of AI and software development.';

async function runDiscussion() {
  // Opening
  if (moderator) {
    const openingPrompt = `You are opening a panel discussion. The topic is: "${topic}"\n\nCurrent round: 1 of ${maxRounds}.\n\nOpen the discussion — set the framing, key questions, and invite the first participant to share their perspective.`;
    await speakAs(moderator, openingPrompt, true);
  }

  // Main discussion loop
  for (currentRound = 0; currentRound < maxRounds; currentRound++) {
    // Each participant speaks
    for (const participant of participants) {
      const roundInfo = moderator ? `\n[Round ${currentRound + 1} of ${maxRounds}]` : '';
      const turnPrompt = currentRound === 0 && !moderator
        ? `The topic for discussion is: "${topic}"\n\nShare your perspective.${roundInfo}`
        : `Continue the discussion. Respond to what's been said, add your own perspective, challenge points you disagree with.${roundInfo}`;

      await speakAs(participant, turnPrompt);
    }

    // Moderator interjection (after every round in moderated mode)
    if (moderator) {
      const isLastRound = currentRound >= maxRounds - 2;
      const modPrompt = isLastRound
        ? `[Round ${currentRound + 2} of ${maxRounds} — FINAL ROUND]\n\nThis is the final round. Provide a comprehensive closing summary:\n- Key agreements and disagreements\n- Most compelling arguments from each participant\n- Action items or recommendations\n- What remains unresolved`
        : `[Round ${currentRound + 2} of ${maxRounds}]\n\nProvide a brief moderator interjection — summarize key points, redirect if needed, pose the next question or angle to explore.`;

      await speakAs(moderator, modPrompt, true);

      if (isLastRound) {
        console.log(`\n${DIM}Discussion complete (${maxRounds} rounds).${RESET}`);
        break;
      }
    }

    // User input opportunity
    const userInput = await prompt(`\n${DIM}[Round ${currentRound + 2}] Press Enter to continue, or type a command: ${RESET}`);
    const trimmed = userInput.trim();

    if (trimmed === '/quit') {
      break;
    } else if (trimmed === '/save') {
      saveTranscript();
    } else if (trimmed === '/skip') {
      continue;
    } else if (trimmed === '/brief' || trimmed === '/normal' || trimmed === '/detailed') {
      currentLength = trimmed.slice(1);
      console.log(`${DIM}Response length set to: ${currentLength} (max ${LENGTH_PRESETS[currentLength].maxTokens} tokens)${RESET}`);
    } else if (trimmed.startsWith('/ask ')) {
      const question = trimmed.slice(5);
      transcript.push({ speaker: 'User', text: question, round: currentRound + 1 });
      // Add user question as context for all personas
      for (const p of allPersonas) {
        conversation.addUserMessage(p.shortName, `[User question]: ${question}`);
      }
      console.log(`\n${BOLD}You:${RESET} ${question}\n`);
    } else if (trimmed.length > 0) {
      // Treat any input as a question
      transcript.push({ speaker: 'User', text: trimmed, round: currentRound + 1 });
      for (const p of allPersonas) {
        conversation.addUserMessage(p.shortName, `[User comment]: ${trimmed}`);
      }
      console.log(`\n${BOLD}You:${RESET} ${trimmed}\n`);
    }
  }

  // Save transcript
  saveTranscript();
  if (rl) rl.close();
}

runDiscussion().catch(e => {
  console.error(`\nFatal error: ${e.message}`);
  saveTranscript();
  if (rl) rl.close();
  process.exit(1);
});
