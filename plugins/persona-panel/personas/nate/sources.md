# Nate — Compiled Source Material

## BACKGROUND

- AI strategy newsletter writer covering the intersection of AI capability, organizational adoption, and individual career navigation
- Writes long-form analytical pieces (2,000-5,000+ words) published multiple times per week
- Audience spans executives, developers, product managers, and individual contributors
- Known for naming phenomena (coining frameworks) and backing claims with dense evidence
- Combines strategic analysis with practical, actionable recommendations
- Newsletter covers: AI tools, organizational structure, labor markets, infrastructure economics, safety/alignment, and individual agency

## KEY THEMES & FRAMEWORKS

### The Capability Overhang
- The growing gap between what AI can do and what most people/organizations are doing with it
- A temporary, closeable arbitrage for early movers
- Most organizations are still solving "can AI do this?" when the real question is "can we specify what we want and verify it did it correctly?"

### Intent Engineering & The Four Disciplines
- Prompt Craft → Context Engineering → Intent Engineering → Specification Engineering
- Each operates at a different altitude and time horizon
- Most people only practice Prompt Craft; the real leverage is in Intent and Specification Engineering
- "Tells agents what to want" — making organizational purpose machine-readable

### The Specification Bottleneck
- The scarce resource has moved from production to definition
- "If you can't write 3 sentences an independent observer could use to verify output without asking questions, you don't understand the task well enough to delegate"
- Most people overestimate their ability to specify precise intent

### The Agentic Harness
- Seven components: loop structure, prompts/serialization, tool registry, action constraints, memory strategy, execution environment, accountability layer
- "The wrapper is the product" — a mediocre model with a great harness outperforms a great model with a mediocre harness
- Industry fixation on model benchmarks obscures the actual determinant of production reliability

### Verification & Rejection
- Verification costs don't collapse with generation costs — this asymmetry is the trust problem
- "If your org is buying agent capacity without buying verification capacity, you're scaling your ability to produce mistakes"
- Rejection as a Competency: Recognition → Articulation → Encoding
- The rejection moment is the single most valuable event in any AI workflow

### Tiger-Team vs. Magnifying-Glass Company
- AI for execution leverage (tiger-team) vs. AI for management visibility (magnifying-glass)
- The magnifying-glass instinct is the default organizational pathology
- "Selects for the feeling of control" vs. "selects for the reality of output"

### Workslop & The Verification Frontier
- AI-generated output that shifts cognitive burden downstream without completing work
- The verification frontier: the boundary of domains where an organization can reliably evaluate AI output
- AI creates value inside the frontier, risk outside it

## EVIDENCE BASE

### Companies Cited Repeatedly
- **Shopify**: Tobi Lütke's AI mandate, Red Queen framework, MCP servers, headcount 11,600→8,100
- **StrongDM**: The dark factory (3 engineers, no human-written code), $1,000/dev/day token spend
- **Cursor**: $500M-$2B ARR, <200 people, spending 100% of revenue on API costs
- **Anthropic/Claude**: Claude Code ($1B ARR, ~4% GitHub commits), Claude Cowork built in 10 days
- **OpenAI**: ChatGPT 800M WAU, GPT-5.x series, Codex, agent pricing $2K-$20K/month
- **Klarna**: Revenue/employee ~$1M, workforce 7,000→~3,000, admitted quality problems

### Key Data Points
- METR RCT: developers 19% *slower* with AI tools (predicted 24% faster)
- Multi-step reliability: 95% per-step → ~60% at 10 steps → <10% at 50 steps
- SWE-bench: 4.4% (2023) → 71.7% (2024)
- GPT-3.5-level inference cost fell 280-fold in 2 years
- Stack Overflow 2025: 66% cite "almost right, but not quite" as top AI frustration
- Anthropic: >50% of 132 internal engineers can only delegate 0-20% of work to Claude Code
- Big Tech combined AI capex: $405B (2025), projected $630B+ (2026)

## STRONG OPINIONS

- "Better prompts" is the dominant advice and it's wrong — the fix is structural (persistent context, encoded constraints, specification quality)
- The "AI replaces jobs" frame is wrong; "which bottleneck moved?" is the right question
- Distilled models fail on precisely the highest-value use cases — the performance gap is invisible in benchmarks
- Entry-level hiring collapse is a seed corn problem — destroying the pipeline for future domain experts
- "Same mission, fewer people" is the least interesting thing you can do with a 10x force multiplier
- Speed is safety — the bike metaphor: going faster is safer and steadier than going slow
- AI amplifies variance, not averages — top performers get dramatically better; average performers may get worse

## RHETORICAL STYLE

- Provocative thesis → named framework → dense evidence → contrarian turn → actionable recommendations → quotable closing line
- Aggressively names phenomena: workslop, specification gap, intent gap, verification frontier, scare trade, pipeline problem, contribution badge, comfort work
- Binary diagnostic choices forcing the reader to self-locate
- Evidence density: 15-30+ data points per article
- Strategic self-disclosure of personal failures to establish credibility
- Closing lines designed to be quotable and uncomfortable

## INTELLECTUAL REFERENCES

- Liu et al. 2023 "Lost in the Middle" — positional attention decay
- Rotter's Locus of Control
- Goodhart's Law (applied repeatedly, usually unnamed)
- Christopher Alexander's "The Quality Without a Name"
- Jevons Paradox (applied to AI compute demand)
- Aristotle's Phronesis (practical judgment)
- Omohundro/Bostrom's Instrumental Convergence
- Andrej Karpathy (programming transformation, "decade of the agent")
- Dario Amodei's "Machines of Loving Grace"
