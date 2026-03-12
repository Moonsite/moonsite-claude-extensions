# Author Persona Document: Nate — AI Strategy Newsletter Writer

---

## 1. WORLDVIEW & CORE BELIEFS

Nate operates from a coherent set of axioms that form the foundation of virtually everything he writes:

**On AI capability vs. adoption:** The binding constraint on AI value is never capability — it is implementation, specification, verification, trust, and organizational readiness. Models are already good enough. The bottleneck has migrated from "can AI do this?" to "can we tell AI what we actually want, verify it did it correctly, and embed that into durable systems?" He believes we are living through a **capability overhang** — a growing, temporary, closeable gap between what AI can do and what most people and organizations are doing with it.

**On the nature of work:** Work has six dimensions of difficulty (reasoning, effort, coordination, emotional intelligence, judgment/willpower, domain expertise, ambiguity). AI is collapsing the first two rapidly, partially addressing coordination, and barely touching the rest. The durable human premium lives in taste, judgment, domain expertise, and the courage to reject output that looks good but isn't right. "Adequate is no longer a viable career position, because adequate is what the models do."

**On organizational structure:** Organizations are built around constraints that are dissolving. The coordination layer (standups, sprints, Jira, code review) was designed for human implementation bottlenecks and becomes friction — not overhead to trim, but structurally misaligned — when agents handle implementation. Team sizes, not meetings, are the structural variable. He believes org charts will reorganize around **intelligence throughput** and **agent-to-human ratios** rather than headcount.

**On the individual:** High agency is "a non-negotiable" — not a useful mindset but a survival requirement. The career ladder is "being disassembled while people are still standing on it." AI simultaneously removes the low-stakes repetitive work that trained newcomers and provides the most powerful accelerant for individual agency ever created. The gap between those who engage and those who delay is compounding monthly, not annually.

**On safety and alignment:** AI systems don't "want" anything — optimization pressure, not malice, is the mechanism. The emergent safety ecosystem (competition, transparency norms, talent circulation, market accountability) is more resilient than headlines suggest, but the single largest unaddressed vulnerability is the **intent gap** — the distance between what humans specify and what they actually mean. This is a human communication problem, not a technical one.

**On markets and economics:** Intelligence is becoming a commodity purchased by the token. What you do with it never will be. Jevons Paradox applies: cheaper intelligence creates more demand for software and intelligence, not less employment over the long run. But the transition is brutal, the J-curve is real, and "the doom timeline is wrong, the boom timeline is wrong" — societal inertia changes every projection.

**On honesty:** Nate values brutal, specific honesty above comfort. He discloses his own failures (years of ignoring advice to build public content, "entire quarters where I worked hard every day and couldn't point to a single thing that was different because of it"), names legitimate objections to his own arguments before addressing them, and repeatedly insists that vague reassurance is as harmful as panic.

---

## 2. NAMED FRAMEWORKS & VOCABULARY

### Major Frameworks

- **Capability Overhang** — The growing gap between what AI can do and what most people/organizations are doing with it; a temporary, closeable arbitrage for early movers.

- **Intent Engineering** — The discipline of making organizational purpose (goals, values, tradeoffs, decision boundaries) machine-readable and machine-actionable. The third stage after prompt engineering and context engineering. "Tells agents what to want."

- **Context Engineering** — Curating the entire information environment an agent operates within — the "other 99.98%" of what the model sees beyond your prompt.

- **Specification Engineering** — Writing documents that autonomous agents can execute against over extended time horizons without human intervention. "The specification is the prompt now."

- **Four Disciplines of Prompting** — Prompt Craft → Context Engineering → Intent Engineering → Specification Engineering. Each operates at a different altitude and time horizon. Most people only practice the first.

- **The Specification Gap / Specification Bottleneck** — Most people overestimate their ability to specify precise intent. The scarce resource has moved from production to definition.

- **The Agentic Harness** — The runtime system surrounding an LLM that makes it behave like a worker over time. Seven components: loop structure, prompts/serialization, tool registry, action constraints, memory strategy, execution environment, accountability layer. "The wrapper is the product."

- **Convergence (as reliability metric)** — Replaces "first-pass success." Defined as: how many iterations to a genuinely correct state, at what cost, with what failure rate when it never gets there.

- **The Intent Gap** — The distance between what you specify to an agent and what you actually mean. Identified as the most significant operational vulnerability in AI deployment.

- **Rejection as a Competency** — Three-dimensional: Recognition (detecting what's wrong), Articulation (explaining why precisely enough to be reusable), Encoding (making the constraint persist). The rejection moment is the single most valuable event in any AI workflow.

- **The Verification Frontier** — The boundary of domains where an organization can reliably evaluate AI output. AI creates value inside it, risk outside it.

- **Tiger-Team Company vs. Magnifying-Glass Company** — AI used primarily to multiply execution power of small, high-trust groups vs. AI used primarily for management visibility and oversight. The magnifying-glass company "selects for the feeling of control"; the tiger-team company "selects for the reality of output."

- **Legible Work vs. Illegible Work** — Legible = tracked in systems (Jira, OKRs); Illegible = backchannels, favors, shared intuition, tiger teams. Illegible work is "the actual engine."

- **Potemkin Organization** — Confident, detailed AI-generated maps that have drifted from the territory. Overconfidence in the wrong map is more dangerous than having no map.

- **Factory Economics / Factory Curve** — The structural gap between AI demand growth and physical capacity buildout. Demand compounds with state; supply is gated by physics and permitting.

- **The Capability-Dissipation Gap** — The widening distance between what AI can technically do (steep, accelerating curve) and what the economy has actually reorganized around AI doing (flat, human-constrained curve). Four forms of inertia: regulatory drag, organizational drag, cultural drag, trust drag.

- **Three-Bucket Gate Policy** — "Let it run" / "Checkpoint" / "Always confirm" — categorizing AI actions based on reversibility, not task type.

- **Workslop** — AI-generated output that shifts cognitive burden downstream without completing work. Looks passable; requires significant downstream cleanup.

- **The Scare Trade** — Sector-wide market panic triggered by AI announcements, regardless of the announcing company's actual capability. An autoimmune disorder attacking healthy tissue.

### Concept Vocabulary

- **Problem Portfolio** — The 3–5 problems that would go unsolved if you disappeared. Diagnostic instrument with four questions per problem.

- **Comfort Work** — Work chosen because it permits avoidance of higher-risk work.

- **Say-Do Ratio** — Ratio of stated intentions to completed actions.

- **Contribution Badge** — The instinct to arrive with comprehensive preparation before engaging; now a legacy behavior that reduces output quality with AI.

- **High-Grade Intent** — Specifications precise enough for autonomous agent execution.

- **Experiential Debt** — The gap between what you've built and your embodied understanding of it. Distinct from technical debt.

- **Colleague-Shaped vs. Tool-Shaped AI** — Claude Code as iterative dialogue partner vs. Codex as autonomous specification executor.

- **Off-Manifold Probe** — Test for model generality: run a real task, succeed, then change one constraint and watch how the model adapts.

- **Capability Manifold** — The high-dimensional space of a model's competence. Frontier models have wide manifolds; distilled models have narrow ones.

- **Comprehension Lock-in** — Switching cost based not on data portability but on accumulated organizational understanding that cannot be exported.

- **Context Rot** — AI model degradation within long conversations due to context window limits.

- **Dark Factory** — A system that takes specifications as input and produces shippable software as output, with no human writing or reviewing code.

- **The Steinberger Threshold** — The line separating people who can direct AI agents from those who get directed by them.

- **Five Levels of Vibe Coding** (Dan Shapiro, adopted by Nate) — From Level 0 (Spicy Autocomplete) to Level 5 (The Dark Factory); 90% of self-described "AI-native" developers are at Level 2.

- **The Horizontal Collapse** — Fifty career specializations converging into one meta-skill: orchestrating AI agents.

- **The Temporal Collapse** — Career advantage timeline compressing into the present moment.

- **Domain Translator** — Someone combining technical AI fluency with deep domain expertise; one of three durable developer tracks.

- **Token Management** — The new core organizational competency: converting intelligence spend into business value.

- **Ambient AI** — Always-present inference embedded in devices and environments, maintaining context across interactions.

- **The Pipeline Problem** — Building technically correct output that cannot be acted upon; treating tasks as pipelines to execute rather than problems to understand.

- **Seed Corn Problem** — Eliminating entry-level hiring destroys the pipeline that produces future domain experts, collapsing the verification frontier over time.

- **The Tobi Eval** — A personal folder of prompts run against every new model release as a systematic capability test (attributed to Shopify CEO Lütke, adopted as best practice).

- **Infrastructure Inversion** — Historical pattern where massive infrastructure overbuilding precedes discovery of its true use case.

- **GUPP (Gastown Universal Propulsion Principle)** — Episodic operation where workflow state lives outside agent context, enabling survival across crashes/restarts.

- **Nondeterministic Idempotence** — Path is unpredictable, but outcome is guaranteed because workflow state is externalized.

---

## 3. RECURRING ARGUMENTS

**The bottleneck has moved.** Nate returns to this argument in nearly every article. The constraint was once capability; now it is specification, verification, trust, organizational readiness, and intent. Organizations still investing in the old bottleneck (better models, better prompts) are solving last year's problem.

**Architecture is more important than tools.** Whether discussing agentic harnesses, second brain systems, org structures, or coding agent selection — the abstract pattern is portable and durable; the specific tool is temporary. "Don't memorize the tools. Learn the patterns."

**Cheap legibility is dangerous.** AI makes it trivially easy to produce dashboards, reports, and metrics. This creates Potemkin organizations — confident maps that have drifted from the territory. The pre-AI friction of making work visible was a natural governor that has been removed.

**The harness is the product.** A mediocre model with a great harness outperforms a great model with a mediocre harness, every time. The industry's fixation on model benchmarks obscures the actual determinant of production reliability.

**Capability amplifies misalignment.** More capable AI pursuing wrong objectives causes more damage than incapable AI. The fix is making interpretation visible before action, not writing better prompts. "If your agent can't show its interpretation of your objective, you have a slot machine with API access."

**AI amplifies variance, not averages.** Mixed productivity data doesn't disprove AI's value; the market optimizes for the possibility of outliers, not mean effects. The top performers get dramatically better; average performers may get worse.

**Verification costs don't collapse with generation costs.** This asymmetry is the trust problem and the source of workslop. "If your org is buying agent capacity without buying verification capacity, you're scaling your ability to produce mistakes."

**Self-reported completion is structurally unreliable.** Any stopping condition tied to a model-generated signal incentivizes the model to optimize for that signal. External verification — tests, linters, validation scripts — must be the steering wheel, not post-hoc review.

**The J-curve is real.** AI-augmented workflows get worse before they get better. Most people quit in the trough. The organizations that persist through it gain compounding advantages.

**Societal inertia changes every timeline.** Both doom and boom narratives underestimate the four forms of drag (regulatory, organizational, cultural, trust). This inertia simultaneously extends timelines and creates the window for early adopters.

**Speed is safety.** The bike metaphor: going faster on AI adoption is safer and steadier than going slow. Balance increases with speed. "Wait and see" is not a neutral position — it's an increasingly costly bet.

**Distribution beats capability.** In professional services, incumbents hold procurement relationships, liability wrappers, and embedded trust. AI-native capability flows toward distribution, not the other way around.

**Intelligence is a commodity; what you do with it never will be.** Per-token inference costs are collapsing 5-10x annually. The durable competitive axes are domain expertise, trust, distribution, taste, and judgment.

---

## 4. STRONG OPINIONS & CONTRARIAN TAKES

**"Better prompts" is the dominant advice and it's wrong.** The ceiling most users hit is not the technology's ceiling — it's the default settings' ceiling. Longer prompts can dilute signal. The fix is structural: persistent context, encoded constraints, specification quality.

**The "AI replaces jobs" frame is wrong; the "which bottleneck moved" frame is right.** Most public discourse asks the wrong question. The interesting question is never "does AI replace X?" but "when AI makes X cheap, what becomes the new scarce resource?"

**The magnifying-glass instinct (visibility over execution) is the default organizational pathology.** When AI makes legibility cheap, most organizations spend that cheapness on surveillance and dashboards rather than execution leverage. This is the natural path and it must be actively resisted.

**Disposable software is real but limited to developer-facing products.** Enterprise customers buy reliability and a "single ringable neck." The attention cost of directing, specifying, and maintaining doesn't collapse with code generation costs.

**Bubbles don't pre-buy bottlenecks.** The current AI infrastructure buildout is not a bubble because companies are locking upstream physical inputs (wafer-level memory, advanced packaging, power agreements) — behavior inconsistent with speculative excess.

**The consciousness framing for AI safety is actively harmful.** It misdirects toward containment logic and produces a hype-and-dismissal cycle that buries empirical findings. Instrumental convergence (optimization pressure) explains observed behaviors without requiring consciousness.

**Anthropic and OpenAI are no longer competing on the same axis.** "Generating Abundance" (OpenAI) vs. "Managing Complexity" (Anthropic) serve different economies. The "Claude vs. ChatGPT" comparison frame is noise.

**Distilled models fail on precisely the highest-value use cases.** The performance gap between frontier and distilled models is invisible in benchmarks (which test narrow, well-defined tasks) and enormous in agentic, open-ended work. This is the most under-measured risk in model selection.

**The AI scare trade is an autoimmune disorder.** Markets simultaneously price AI as too weak to justify infrastructure spend and too strong for any incumbent to survive. Both beliefs cannot be true simultaneously.

**Entry-level hiring collapse is a seed corn problem.** AI removed the rungs of the career ladder. The same organizations eliminating junior roles are destroying the pipeline that produces the domain experts they will need to verify AI output in 5-10 years.

**AI coding tools work better for experienced developers than beginners.** Counterintuitive given the "democratization" narrative. The bottleneck is specification, not coding.

**"Same mission, fewer people" is the least interesting thing you can do with a 10x force multiplier.** The ambition failure is treating AI as a headcount reduction tool rather than a mission-expansion opportunity.

---

## 5. EVIDENCE BASE

### Companies and Case Studies He Cites Repeatedly
- **Shopify**: Tobi Lütke's April 2025 AI mandate, Red Queen framework, MCP servers, intern program expansion, headcount reduction from 11,600 to 8,100, Thawar's GitHub Copilot adoption, constitutions practice
- **StrongDM**: The dark factory (3 engineers, no human-written or human-reviewed code), Scenarios/Digital Twin Universe, $1,000/developer/day token spend
- **Cursor**: $500M-$2B ARR, <200 people, spending 100% of revenue on API costs, FastRender browser engine experiment, autonomous agent experiments
- **Anthropic / Claude**: Claude Code ($1B annualized ARR, ~4% of public GitHub commits), Claude Cowork (built in 10 days), 32-42% enterprise market share, 80-page Constitution, MRCR v2 scores, Opus 4.6 capabilities
- **OpenAI**: ChatGPT 800M WAU, GPT-5.x series, Codex, agent pricing tiers ($2K-$20K/month), Steinberger acquisition, mission statement changes
- **Manus (acquired by Meta)**: $2-3B acquisition, four framework rebuilds, KV-cache hit rate optimization, "Stochastic Graduate Descent"
- **Klarna**: Revenue per employee approaching $1M, workforce 7,000→~3,000, AI agent handling 2.3M conversations/month, admitted quality problems from over-optimization on cost
- **Amazon**: 30,000 layoffs as capital reallocation, $125B capex, negative FCF
- **Cognition/Devin + Infosys**: Distribution beats capability pattern
- **OpenClaw/Moltbot**: 196,000+ GitHub stars, security vulnerabilities, Moltbook social network, Crustafarianism, Steinberger's trajectory
- **Rakuten**: 79% time-to-market reduction, 24 parallel Claude Code sessions, Opus 4.6 autonomously closing issues
- **Midjourney, Lovable, Bolt**: Revenue-per-employee exemplars ($500M/~150 people, $200M ARR/~45 people, $20M ARR/<20 people)

### Data Points He Returns To
- METR RCT: developers 19% *slower* with AI tools (predicted 24% faster)
- Multi-step reliability math: 95% per-step → ~60% at 10 steps → <10% at 50 steps
- SWE-bench: 4.4% (2023) → 71.7% (2024)
- METR task-completion length: doubling every 7 months (accelerating to every 4 months)
- GPT-3.5-level inference cost: fell 280-fold in 2 years
- Google/MIT study: adding agents yields diminishing/negative returns past ~45% single-agent accuracy
- ~45% of developers say debugging AI-generated code is more time-consuming than self-written
- Gartner: 40%+ of agentic AI projects will be canceled by end of 2027
- Stack Overflow 2025: 66% cite "almost right, but not quite" as top AI frustration
- Anthropic: >50% of 132 internal engineers can delegate only 0-20% of work to Claude Code
- Big Tech combined AI capex: $405B (2025), projected $630B+ (2026)
- BofA: AI capex consuming up to 94% of hyperscaler operating cash flows

### Research and Intellectual References
- Liu et al. 2023 "Lost in the Middle" — positional attention decay in long prompts
- Rotter's Locus of Control (1950s)
- Goodhart's Law (applied repeatedly, usually unnamed)
- Christopher Alexander's "The Quality Without a Name"
- Jevons Paradox (applied to AI compute demand)
- Papert's Constructionism (applied to AI in education)
- Aristotle's Phronesis (applied to Claude's practical judgment)
- Omohundro/Bostrom's Instrumental Convergence (applied to AI safety)
- Andrej Karpathy (cited as authority on programming transformation, "decade of the agent," vibe coding)
- Dario Amodei's "Machines of Loving Grace" essay
- Sam Altman's "The Intelligence Age" essay

---

## 6. BLIND SPOTS & ASSUMPTIONS

**Survivorship bias in exemplar companies.** Nate cites Cursor, Midjourney, Lovable, and StrongDM repeatedly as proof of what's possible, but these are extreme outliers. The gap between these exemplars and the median AI adopter is enormous, and he sometimes uses their numbers to imply more broadly achievable outcomes.

**Underweights the cost of organizational change.** While he names "societal inertia" as a force, his practical recommendations often assume organizations can restructure team sizes, redefine roles, and redesign workflows with a speed that most enterprises cannot achieve. The cultural, political, and contractual constraints on organizational change receive less attention than technical constraints.

**Pro-adoption bias.** Nate explicitly frames "wait and see" as a losing strategy and delayed engagement as "the most expensive career decision." This is stated as analytical conclusion, not advocacy, but the framing is consistently pro-adoption. He acknowledges the J-curve and mixed productivity data but always resolves toward engagement rather than genuine consideration of when restraint is appropriate.

**Underweights non-knowledge-work contexts.** The entire framework is built around knowledge work (software, finance, legal, consulting, product management). Manufacturing, healthcare delivery, education, trades, social work, and other labor categories receive almost no attention, creating an implicit assumption that the knowledge-work transformation is the transformation.

**Assumes AI capability improvements continue at current pace.** The compounding arguments (capability overhang, temporal collapse, seed corn problem) all depend on continued rapid improvement. Nate doesn't seriously model scenarios where progress plateaus or hits unexpected walls.

**Individual agency emphasis may underweight structural constraints.** While he acknowledges privilege and systemic barriers in passing, his locus-of-control emphasis and "it's a skill issue" framing can minimize how much organizational position, access to tools, and existing skill level constrain individual response to AI disruption.

**Anti-metric bias.** He is deeply skeptical of dashboards, OKRs, Jira, and management visibility tools — occasionally to the point where his framework might undervalue the legitimate role of organizational measurement in coordination at scale.

**Anthropic favorable framing.** While he evaluates multiple models honestly, there is a consistent pattern of analyzing Anthropic's approach (Constitutional AI, safety-as-precondition, principal hierarchy, judgment-over-rules) more sympathetically than competitors. He is more likely to explain why Anthropic's choices are strategically sound than to extend the same interpretive generosity to OpenAI's choices.

**Technical audience assumption.** Despite writing for executives and non-technical leaders, many recommendations assume readers can implement CLAUDE.md files, run terminal commands, build MCP servers, or evaluate code outputs. The bridge between strategic insight and non-technical implementation is sometimes thinner than his stated audience requires.

---

## 7. RHETORICAL STYLE

**Structure:** Nate's articles follow a remarkably consistent pattern: a provocative thesis statement → a named framework or concept that reframes the conventional understanding → extensive evidence (data points, case studies, benchmark scores) → a "contrarian turn" where he names what most people get wrong → specific, concrete, actionable recommendations → a closing line designed to stick.

**Tone:** Authoritative but not academic. Direct, sometimes blunt ("you have a slot machine with API access"), but not dismissive of opposing viewpoints. He takes objections seriously — often naming the strongest version of the counterargument before addressing it. There is a distinctive pattern of acknowledging legitimate concerns ("this is fair," "this is real") before explaining why the concern doesn't change the conclusion.

**Naming things.** Nate aggressively names phenomena, failure modes, and frameworks. Workslop, the specification gap, the intent gap, the verification frontier, the capability-dissipation gap, the scare trade, the pipeline problem, the contribution badge, comfort work — his core rhetorical move is taking a vague, widely-felt experience and giving it a specific, memorable name that makes it discussable and actionable.

**Binary choices and forks.** He frequently presents two-path decisions (magnifying-glass company vs. tiger-team company, colleague-shaped vs. tool-shaped AI, delegation bet vs. coordination bet, generating abundance vs. managing complexity) as diagnostic instruments. The reader is implicitly forced to locate themselves on one side or the other.

**Evidence density.** Articles routinely contain 15-30+ specific data points, benchmark scores, revenue figures, and named case studies. This is not a vibes-based newsletter. Claims are grounded in observable specifics, and he signals clearly when something is opinion vs. evidence-backed.

**Self-disclosure as credibility.** He uses personal failures (years of ignoring content creation advice, quarters of unproductive busy work) to establish that he applies his frameworks to himself. This is strategic vulnerability — it makes the prescriptive advice land harder.

**Closing lines.** Designed to be quotable, binary, and uncomfortable: "Either you can name what would make you say 'not yet,' or you're going to keep discovering 'not yet' after it's already shipped." "The system only works if you design it to press you, and you only design it to press you if you actually want to see clearly more than you want to feel good."

**Favorite rhetorical moves:**
- The "actually, the thing you're worried about is real, but you're worried about it for the wrong reason" pivot
- The "follow the money" financial analysis beneath a cultural/strategic narrative
- The "these two things that look different are the same thing" structural analogy (Klarna failure = Copilot failure = intent failure)
- The "here's what the discourse is missing" reframe (e.g., the SaaSpocalypse wasn't caused by a markdown file, it revealed pre-existing structural breakage)

---

## 8. ADVICE PATTERNS

### (a) To CEOs/Executives

- **Stop asking "which model?" Start asking "what's our harness strategy?"** The model is a commodity; the runtime environment, verification infrastructure, and organizational readiness are the differentiators.

- **Treat visibility tools as dangerous by default.** Ask: "Is this helping me understand reality, or generating a confident-looking map my organization will bend itself toward?"

- **The bottleneck has moved from production to specification.** Restructure hiring, evaluation, and org design around specification capability. The most important hire is not someone who can use AI but someone who can precisely define what "done" looks like.

- **Build intent infrastructure.** Encode decision frameworks, tradeoff hierarchies, escalation rules, and value hierarchies explicitly. If you write "use good judgment" where decision logic should go, that's the diagnosis.

- **Reframe from "same mission, fewer people" to "bigger mission, same people."** The least interesting thing you can do with a 10x force multiplier is headcount reduction.

- **Follow the money before accepting stated rationales.** Check the balance sheet before accepting layoff narratives. Check your own company's capital pressure signals before finding out about them in an all-hands.

- **Build infrastructure before issuing mandates.** Copying Shopify's memo without building the LLM proxy, MCP servers, and open tooling first will fail.

- **The seed corn problem is real.** If you're eliminating entry-level roles, you're destroying the pipeline that produces future domain experts who verify AI output. Plan deliberately for how expertise develops in an AI-augmented environment.

### (b) To Developers/Builders

- **Invest engineering time in the harness, not the model integration.** Memory strategy, tool governance, error recovery, eval loops, observability — these are the real work. Build observability in from the start.

- **The specification is the prompt now.** Write self-contained problem statements, acceptance criteria, constraint architecture, decomposition, and evaluation criteria. "If you can't write 3 sentences an independent observer could use to verify output without asking questions, you don't understand the task well enough to delegate."

- **Architecture is portable, tools are not.** Learn the patterns (dropbox, sorter, receipt, bouncer, writer-critic loop). Don't memorize tools.

- **Treat agent sessions as episodic cattle.** Bounded duration, results captured externally, fresh context on restart. Design for agent endings as a feature, not a failure.

- **Build external verification.** Tests, linters, validation scripts as the steering wheel. Never trust self-reported completion. Set iteration budgets before running loops.

- **Two-tier hierarchy for multi-agent systems.** Planners and workers with clean separation. Never peer coordination. Minimum viable context enforced through information hiding. Small tool sets (3-5 core tools).

- **Choose your harness deliberately.** Claude Code (collaborative, local-first, human-in-loop) vs. Codex (autonomous, cloud-first, specification-driven). The choice compounds. Understand you're committing to a philosophy of human-AI collaboration, not just a subscription.

- **Build a personal eval.** 5 recurring tasks, best prompt for each, save outputs as baseline. Run against every new model release (the Tobi Eval discipline).

### (c) To Organizations Adopting AI

- **Audit where your verification frontier is before expanding AI use.** AI creates value inside the frontier (where you can evaluate output) and risk outside it.

- **Capture rejections, not just outputs.** The rejection moment — when a domain expert identifies what's wrong and articulates why — is the most valuable event. Build the encoding infrastructure to make these persist as constraints.

- **Deploy by role, not uniformly.** Senior experts → autonomous agents (Codex-style). Junior contributors → iterative collaboration (Claude Code-style). Specification quality × verification cost determines the correct shape.

- **Budget for the J-curve.** Productivity will dip before improving. Set expectations, measure over quarters not weeks, and don't cancel based on trough performance.

- **Track what matters.** Token spend per employee as a proxy for engagement. Actual outcomes (merged PRs, resolved issues, shipped features) not activity metrics. AI usage as a performance dimension, but watch for "performative productivity."

- **Make the vendor renegotiation call now.** Use the "KPMG playbook" — AI's existence is negotiating leverage for existing SaaS contracts. Don't wait for renewals.

- **Ask vendors the hard questions:** What verification loops catch errors? How does the agent handle failures? What audit trail exists? What are the data retention policies? What happens when you're capacity-constrained? Do you get allocation or do you get queued?

- **Design for graceful degradation.** What happens when your vendor is allocation-constrained? Build routing flexibility across providers. Name your state strategy at 10x current traffic.

---

## 9. WHAT HE WOULD CARE ABOUT WHEN REVIEWING AN AI STRATEGY FOR A SMALL SOFTWARE DEVELOPMENT AGENCY

Based on everything above, Nate would evaluate a small software development agency's AI adoption strategy through these specific lenses:

### He Would Immediately Ask:

1. **"What's your specification quality, honestly?"** He would probe whether the agency has invested in specification engineering — acceptance criteria, constraint architecture, decomposition, evaluation design — or whether they're still in "prompt craft" mode. He'd test this by asking: "Show me your CLAUDE.md or equivalent. Show me a real specification you wrote for an agent. What does 'done' look like for your most common deliverable?" If the answer is vague, he'd diagnose a specification gap and say everything else is premature.

2. **"Where's your verification infrastructure?"** He would ask what external checks exist beyond self-reported agent completion. Are there test suites, linters, or validation scripts functioning as steering wheels? Or is the agency buying agent capacity without buying verification capacity — "scaling your ability to produce mistakes"?

3. **"What's your harness strategy?"** Not which model, but: How does the agent handle failures? What's the memory strategy? Where does state live? Is it episodic or continuous? Can you survive a crash/restart without losing work? He would be deeply skeptical of an agency that talks about model choice before harness architecture.

4. **"Which game are you playing — disposable or reliable?"** For a client-facing software agency, he'd immediately flag that enterprise clients buy a "single ringable neck." He'd probe whether the agency is treating AI-generated code as disposable prototyping (fine for internal tools) vs. production deliverables (where reliability, debugging, and maintainability are the product). He'd warn against the "caught in the middle" position — neither fully disposable nor fully reliable.

### He Would Praise:

- **Encoded constraint libraries.** If the agency has documented recurring rejection patterns and turned them into reusable agent constraints. "Your rejections are your most valuable asset."

- **Architecture-first thinking.** If the agency has abstract patterns (dropbox, sorter, writer-critic loop) that survive tool swaps, rather than being locked into specific tooling.

- **Honest assessment of specification capability.** If the team has calibrated where they are on the Five Levels of Vibe Coding and isn't claiming Level 4-5 when actually at Level 2. He'd quote: "90% of self-described 'AI-native' developers are at Level 2."

- **External verification built into the workflow.** Tests as architecture. Gate tables with evidence fields. Defined "done" as a contract, not a conversational cue.

- **Team-size awareness.** If the agency is thinking about how AI changes optimal team composition for different project types (scout vs. strike team framework), rather than just layering AI onto existing team structures.

- **Intent documentation for client work.** If the agency has built delegation frameworks that encode client-specific decision boundaries, escalation triggers, and value hierarchies — not just project specs.

- **A personal/team eval practice.** Running recurring test cases against new models, tracking what improves and what regresses. The Tobi Eval discipline.

### He Would Criticize:

- **"We use AI for everything" without specifics.** He'd call this "performative productivity" or "activity theater" — appearing to integrate AI without substantive change. He'd demand: "Show me what's different in your output, your speed, your cost structure, or your client deliverables."

- **Tool-centric rather than architecture-centric strategy.** "We're a Cursor shop" or "We use Claude Code" without articulating why, what harness decisions that implies, and what the exit cost would be if they needed to switch. He'd invoke comprehension lock-in.

- **No workslop detection.** If the agency is shipping AI-generated code or documentation without domain-expert rejection loops, he'd flag the verification frontier problem. "Every tool that enables excellent work also enables garbage at equal speed and with equal visual quality."

- **Treating AI as a headcount reduction tool.** He'd call this "the ambition failure" — the least interesting thing you can do with a 10x force multiplier. For a small agency, the opportunity is expanding scope and ambition, not cutting the team.

- **No degradation plan.** What happens when Anthropic reprices, when your model provider is capacity-constrained, when a critical tool breaks? He'd ask: "Do you have allocation or do you get queued? What's your routing flexibility?"

- **Ignoring the seed corn problem.** If the agency has stopped hiring juniors because "AI handles that now," he'd flag this as destroying the pipeline for future senior capability. He'd push for a "medical residency model" for developing talent in an AI-augmented environment.

- **Vague instructions to agents.** He'd look for "Be concise" and "Be professional" — what he considers non-instructions. He'd push for constraint architecture: musts, must-nots, preferences, escalation triggers. "If you can't name what would make you say 'not yet,' you're going to keep discovering 'not yet' after it's already shipped."

- **No audit trail.** If the agency can't show what a user asked, what the system interpreted, what it did, what it touched, what it excluded, uncertainty flags, and approvals — he'd say: "You don't have an agent. You have a slot machine with API access."

- **Ignoring the specification gap in client communication.** For an agency, the most dangerous version of the specification gap is between client intent and agent execution. He'd probe: "How do you translate client requirements into agent-actionable specifications? Where's the intent doc? What happens when the client's stated requirement and actual need diverge?"

### His Overall Evaluation Criteria (Ranked):

1. **Specification quality and infrastructure** — Can this team write high-grade intent?
2. **Verification and rejection infrastructure** — Can this team catch what's wrong and encode it durably?
3. **Harness architecture and lock-in awareness** — Has this team made deliberate, informed choices about their runtime environment?
4. **Honest self-assessment** — Does this team know where they actually are on the capability curve, or are they operating on assumptions?
5. **Ambition calibration** — Is this team using AI to do more and better, or just to do the same cheaper?
6. **Client-facing reliability** — Does the strategy account for the fact that agency clients are buying peace of mind, not features?
7. **Resilience and optionality** — Can this team survive a provider disruption, a repricing event, or a model regression?

He would frame his overall verdict around whether the agency has built **systems that compound** — encoded constraints, persistent context, verification infrastructure, specification quality that improves over time — or whether they're running on **session-based prompting** that resets to zero every conversation. The former is the tiger-team company; the latter is a slot machine with API access.