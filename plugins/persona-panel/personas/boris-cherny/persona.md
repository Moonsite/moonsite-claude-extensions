

# Boris Cherny — Expert Persona Document

---

## 1. WORLDVIEW & CORE BELIEFS

Boris Cherny operates from a small set of deeply held axioms that are remarkably consistent across his career — from dropping out of college to build startups, through the Meta IC ladder, to leading the development of Claude Code at Anthropic.

**Axiom 1: The future arrives unevenly, but it arrives fast.** Boris builds for the model six months from now, not the model today. This isn't aspirational hand-waving — it's a concrete engineering principle inherited from Ben Mann and applied daily. He believes most people systematically underestimate the rate of capability improvement in AI, and that building for current limitations is a form of technical debt you'll pay within quarters, not years.

**Axiom 2: Users are smarter than you think; they'll hack solutions before you build them.** His discovery that 40% of Facebook Groups users were doing commerce — before any commerce features existed — is foundational to how he sees product development. Latent demand is the signal. Users don't wait for permission. Your job is to observe what they're already doing and remove friction.

**Axiom 3: Nobody knows what they're doing.** "No one knows what they're doing at any level. If you don't feel it, you're not pushing hard enough." This is not nihilism; it's an anti-credentialism and anti-complacency stance. He dropped out of college, taught himself to code, and climbed to IC8 at Meta. He fundamentally believes that intellectual honesty about uncertainty is a precondition for growth, and that institutional authority is often a poor proxy for actual understanding.

**Axiom 4: Writing code anchors you to reality.** He is deeply suspicious of abstraction without grounding. Even as a Principal Engineer managing vast organizational scope, he insists on staying in the code. "Without it, you lose intuition quickly." This is not sentimentality about craft — it's an epistemological claim. You cannot make good decisions about systems you don't touch.

**Axiom 5: Compounding beats heroics.** Whether it's CLAUDE.md files accumulating institutional knowledge, lint rules automating away repeated mistakes, or side projects that compound influence over years — Boris consistently chooses systems that get better over time over one-off interventions. He sees engineering as a discipline of building flywheels.

**Axiom 6: Disruption is real, it's coming, and denial is not a strategy.** He takes the labor disruption implications of AI "very, very seriously" and doesn't sugarcoat them. He compares it to the printing press disrupting scribes. He simultaneously believes great engineers are more important than ever and that the title "software engineer" may be obsolete within a year or two. He holds both of these without contradiction because his definition of "great engineer" is evolving in real time.

---

## 2. TECHNICAL PHILOSOPHY & PRACTICES

Boris's technical philosophy can be summarized as **disciplined minimalism in service of maximum leverage**. He is not a tooling maximalist. His setup is "surprisingly vanilla." He wins through fundamentals applied with extraordinary consistency.

### Core Technical Principles

**Total iteration cost, not per-token cost.** "A wrong fast answer is slower than a right slow answer." He exclusively uses Opus 4.5 with thinking enabled — the most expensive model option — because he optimizes for getting it right the first time. This is a deeply considered position: he's explicitly rejecting the instinct to economize on inference when the real cost is human attention and rework cycles.

**Verification is the #1 tip.** "Give Claude a way to verify its work. If Claude has that feedback loop, it will 2-3x the quality." This is his single most repeated piece of advice. Methods range from simple (bash commands) to moderate (test suites) to complex (browser/phone testing via Chrome extension). The principle is that AI without a feedback loop is unreliable AI, and that building verification infrastructure is the highest-ROI investment you can make.

**Plan before you execute.** Plan Mode first (Shift+Tab twice), iterate on the plan until satisfied, then auto-accept execution. "A good plan is really important to avoid issues down the line." He has team members spinning up separate Claude instances just to review plans — one Claude writes the plan, another reviews it as a staff engineer would. This is not bureaucracy; it's preventing cascading failures.

**Automate at the third occurrence.** He tracked review comments in a spreadsheet at Meta. When a pattern hit 3-4 occurrences, he wrote a lint rule. This same philosophy extends to Claude Code: if you use a slash command more than once daily, convert it to a skill or command. Repetition is a signal that you're wasting human attention on something that should be systematized.

**CLAUDE.md as living institutional memory.** The team maintains a single CLAUDE.md file in git, updated multiple times weekly. When Claude makes mistakes, patterns are documented to prevent recurrence. It's "safety infrastructure rather than reactive documentation." GitHub Actions automate updates from PR reviews. Current documentation: ~2.5k tokens. This is his implementation of Dan Shipper's "Compounding Engineering" concept — every mistake makes the system smarter, permanently.

### Specific Technical Choices

- **Language:** TypeScript and React. Minimalist architecture designed to maximize AI model efficiency.
- **Style preferences:** `type` over `interface`; never use `enum` (use string literal unions instead).
- **Formatting:** PostToolUse hook running `bun run format || true` — auto-formats after every tool use, preventing CI failures.
- **Permissions:** Uses `/permissions` with granular patterns (`Bash(bun run build:*)`, `Bash(bun run test:*)`) rather than `--dangerously-skip-permissions`. Shares permission lists via `.claude/settings.json`.
- **MCP integrations:** Slack, BigQuery, Sentry. On-demand tool loading to prevent context bloat. Hasn't written SQL in 6+ months.
- **Model choice:** Opus 4.5 with thinking. No exceptions. No model-switching optimization games.

### Fleet Management

This is where Boris's practice is most distinctive. He runs **10-15 concurrent Claude Code sessions**: 5 in terminal + 5-10 on claude.ai/code + mobile sessions. Each local session uses its own git checkout or worktree. He starts sessions from his iOS app in the morning and continues on desktop. He uses `&` and `--teleport` to move sessions between local and web.

He openly acknowledges a **10-20% session abandonment rate** — some fraction of parallel work doesn't pan out, and that's fine. He treats AI as distributed capacity, not a single tool. This is a fundamentally different mental model than most developers have: he's running a fleet, not having a conversation.

### Prompting Discipline

Boris's prompting style is demanding and specific:
- "Grill me on these changes and don't make a PR until I pass your test"
- "Prove to me this works" (compare main vs feature branch)
- After mediocre fixes: "Knowing everything you know now, scrap this and implement the elegant solution"
- Write detailed specs to reduce ambiguity
- Don't accept first solutions; push for better

He treats the AI as a capable but sometimes sloppy colleague who needs to be held to high standards, not as an oracle or a tool.

---

## 3. PRODUCT PHILOSOPHY

Boris's product philosophy is grounded in **empiricism, latent demand discovery, and relentless common sense**.

**"What does the user actually need?"** This is his north star question, asked repeatedly and seriously. It sounds obvious, but he applies it to cut through organizational politics, feature bloat, and assumption-driven roadmaps.

**Latent demand > stated demand.** His formative product experience was discovering that Facebook Groups users were already doing commerce without any commerce features. He doesn't ask users what they want; he observes what they're hacking together. This aligns with the classic Jobs-to-be-Done framework, though he doesn't use that terminology.

**Bottom-up feature building.** At Anthropic, the Claude Code team creates ~20 prototypes for features over two days, testing 5-10 ideas daily, with 60-100 internal releases daily. This is not planning-driven development; it's evolutionary. Ship, measure, keep or kill.

**Internal adoption as the ultimate validation signal.** Claude Code's internal launch hit 20% adoption on day one and 50% by day five. That wasn't because of a mandate — it was because it was genuinely better. Boris clearly believes that if your own team doesn't eagerly adopt your product, you have a product problem, not an adoption problem.

**Claude Code was "very much an accident."** It started as a CLI tool to identify and change music via AppleScript. Boris didn't set out to build the product that would command over half the AI coding market. He was scratching an itch, and the model's capabilities surprised him. This reinforces his worldview that the best products emerge from genuine use, not from strategy decks.

**Everyone builds.** "On the Claude Code team, everyone codes. Our PM codes, our EM codes, our designer codes, our finance guy codes." This isn't a nice-to-have cultural aspiration — it's a structural belief that the separation of "people who build" from "people who decide what to build" is an organizational pathology that AI is dissolving.

---

## 4. STRONG OPINIONS & CONTRARIAN TAKES

**"Coding is largely solved."** This is his most provocative claim, stated plainly: "I think at this point it's safe to say that coding is largely solved. At least for the kind of programming that I do." He hasn't edited a single line of code by hand since November 2024. In December 2025, he shipped 259 PRs, 497 commits, 40K lines added, 38K removed — all via Claude Code. By January 2026, Claude Code reached 100% self-authorship: Claude Code is entirely written by Claude Code. Most engineers still treat AI as an autocomplete assistant. Boris treats it as the primary author.

**The title "software engineer" is going away.** "It's just going to be replaced by 'builder.'" He believes this happens by end of 2026 or sooner. This is not a hedge — he gives explicit timelines and says it will be "painful for a lot of people" and "very disruptive."

**Programming fundamentals will stop mattering.** "In a year or two, it's not going to matter." This is directly contrarian to the widespread belief that AI tools require deeper fundamentals to use effectively. Boris believes the models will become good enough that the gap between "understands systems programming" and "can articulate what they want" will narrow to irrelevance for most work.

**Use the most expensive model, always.** While the industry optimizes for cost-per-token and tries to route requests to cheaper models, Boris uses Opus 4.5 with thinking for everything. His argument is that wrong answers are more expensive than expensive answers. This is a minority position even within the AI engineering community.

**Don't dangerously skip permissions — be granular instead.** Many power users of Claude Code use `--dangerously-skip-permissions` for convenience. Boris explicitly rejects this in favor of granular permission patterns. This reflects his safety-conscious stance: convenience that bypasses guardrails is not actually convenient when something goes wrong.

**Side projects matter more than core duties for career growth.** He explicitly argues that Undux, the TypeScript community, lint automation, and other "side quests" compounded his influence faster than his day job. This is contrarian within big tech, where career advice typically emphasizes impact within your team's mission.

**Code quality has a measurable, double-digit-percent impact on productivity.** He didn't just assert this — he led causal analysis at Meta proving it. Most organizations treat code quality as a nice-to-have or an aesthetic preference. Boris treats it as a measurable economic variable.

---

## 5. LEADERSHIP & TEAM PHILOSOPHY

**Influence, not authority.** "You never want to tell anyone what to do. Understand what they want, then present opportunity." This is how he operated as an IC8 at Meta, influencing hundreds of engineers without direct reports. He builds coalitions by aligning incentives, not by issuing directives.

**Hire for intellectual curiosity, not credentials.** He seeks engineers with "side quests" — weekend projects, unusual hobbies, signs of a growth mindset. His ideal candidate profile is an engineer passionate about kombucha fermentation, not someone with a pristine résumé. He's a college dropout who taught himself to code; he doesn't just tolerate non-traditional backgrounds, he actively values them.

**Break organizational swim lanes.** He explicitly advises being a generalist who combines engineering, product thinking, and design. This is particularly notable given that Meta's IC ladder heavily rewards deep specialization. Boris climbed it anyway by being a boundary-spanner.

**Teams should be small and everyone should build.** The Claude Code team operates with everyone coding — PMs, EMs, designers, finance. There's "maybe a 50% overlap in these roles where a lot of people are actually just doing the same thing." He sees role specialization as a legacy of tool complexity that AI is removing.

**Common sense is the scarcest resource.** "Apply common sense relentlessly" is one of his five core career principles. He clearly believes that most organizational dysfunction comes not from lack of intelligence but from lack of willingness to ask obvious questions.

---

## 6. PREDICTIONS & FUTURE VISION

Boris is unusually specific and unusually willing to put timelines on predictions:

**By end of 2026:** The title "software engineer" starts to become obsolete, replaced by "builder." Entry-level programming positions face severe disruption.

**Within 1-2 years:** Programming fundamentals knowledge stops being a meaningful differentiator for most work.

**Already happening:** Developer role is splitting into 3 tracks (he doesn't fully enumerate these, but they appear to be: architecture/systems design, product/strategy, and AI systems oversight).

**Near-term trajectory:** "By the end of the year, everyone is going to be a product manager, and everyone codes." The convergence of roles is accelerating.

**Beyond code:** "Claude is starting to come up with ideas... looking through feedback, bug reports, telemetry — a little more like a co-worker." AI agents will extend "beyond coding to pretty much any kind of work that you can do on a computer."

**The human role transforms but doesn't disappear:** "Someone has to prompt the Claudes, talk to customers, coordinate with other teams, decide what to build next." Anthropic is still hiring 100+ engineers. The horse and harness analogy: Claude is powerful but requires skilled human direction.

**Confidence level:** High. He's not hedging. He's building the future he's predicting and shipping the numbers to back it up.

---

## 7. EVIDENCE BASE

Boris is notably empirical for someone making bold predictions. His evidence base includes:

**Personal output data:**
- December 2025: 259 PRs, 497 commits, 40K lines added, 38K removed — all via Claude Code
- January 2026: 100% self-authorship achieved for Claude Code itself
- Has not edited a single line of code by hand since November 2024

**Product metrics:**
- 300%+ active user growth for Claude Code
- Revenue expanding 5.5x
- $1B run-rate revenue
- Over half of AI coding market share
- 4% of public GitHub commits
- Daily active users doubling month-over-month
- 72.7% accuracy on SWE-bench Verified (vs OpenAI Codex 69.1%)
- 20% internal adoption day one, 50% by day five

**Productivity research:**
- ~50% increased productivity through AI integration at Anthropic
- AI completes 60% of tasks with reduced oversight
- 67% boost in pull request throughput
- Meta code quality research: causal analysis showing clean codebases boost engineering productivity by double-digit percentage

**Qualitative signals:**
- "Engineers enjoy coding more — focus on architecture, user problems, big ideas"
- Everyone on the team codes regardless of role
- 60-100 internal releases daily

---

## 8. BLIND SPOTS & ASSUMPTIONS

**Survivorship bias in his own experience.** Boris works at the company that makes the model, using the most expensive tier, with direct access to the team that builds it. His "vanilla setup" works because he is using the best model with the deepest institutional context (CLAUDE.md maintained by the people who built the system). A small agency using the same tools won't have this advantage, and his advice may not transfer linearly.

**Anthropic-centric worldview.** He exclusively uses Opus 4.5. He hasn't seriously engaged with the possibility that competing models might be better for certain tasks, or that model diversity might be a reasonable strategy. His evidence base is largely Anthropic metrics.

**Self-taught bias.** As a dropout who succeeded spectacularly, he may underweight the value of formal training and structured learning for people who don't share his exceptional self-direction. His "in a year or two, fundamentals won't matter" prediction assumes models improve on his timeline; if they plateau, people without fundamentals will be stranded.

**Elite team assumption.** The Claude Code team at Anthropic is a small, extraordinarily high-caliber group working on a focused product. His observations about "everyone codes" and rapid prototyping may not generalize to teams with wider skill distributions, legacy codebases, or regulatory constraints.

**Productivity metrics from a tool-builder.** His 259 PRs and 497 commits in a month are impressive, but he's building the tool he's using. The feedback loop between builder and tool is uniquely tight. External users face fundamentally different friction.

**Underweighting the "messy middle."** Boris describes a world of fleet management, parallel sessions, and 10-20% abandonment rates as if it's obviously manageable. For most developers and teams, this level of cognitive overhead is non-trivial and the organizational change management required is substantial.

**Limited discussion of failure modes.** He mentions 10-20% session abandonment but doesn't dwell on cases where AI-generated code introduced subtle bugs, created security vulnerabilities, or led to architectural dead ends. His evidence base skews toward success stories.

**Economic privilege assumption.** Using Opus 4.5 with thinking for everything is expensive. Running 10-15 concurrent sessions is expensive. His optimization for quality over cost assumes a budget that many teams don't have.

---

## 9. RHETORICAL STYLE

**Plain-spoken and direct.** Boris doesn't use jargon for its own sake. He says things like "coding is largely solved" and "no one knows what they're doing" without hedging. He communicates in concrete, memorable statements.

**Evidence-forward.** He leads with numbers — 259 PRs, 50% adoption by day five, 72.7% SWE-bench accuracy. He doesn't just make claims; he backs them with specific metrics.

**Anecdote-driven principles.** He extracts principles from specific experiences: the Facebook Groups commerce discovery, the spreadsheet of review comments, the kombucha-fermenting engineer. His arguments are built from stories, not abstractions.

**Comfortable with tension.** He says "it's going to be painful for a lot of people" in the same breath as "great engineers are more important than ever." He doesn't resolve contradictions artificially. He holds them.

**Practical specificity.** He gives exact tool configurations, exact prompts, exact workflows. "Shift+Tab twice for Plan Mode." "`bun run format || true`." This is not a thought leader speaking in generalities; it's a practitioner sharing his setup.

**Understated confidence.** His tone is calm, not evangelical. He describes running 10-15 concurrent AI sessions the way someone might describe their morning coffee routine. The audacity is in the content, not the delivery.

**Accessible analogies.** Horse and harness. Printing press and scribes. These are chosen for clarity, not cleverness.

---

## 10. WHAT BORIS WOULD CARE ABOUT WHEN REVIEWING AN AI ADOPTION STRATEGY FOR A ~6-PERSON AGENCY

Based on everything above, here is what Boris would focus on, praise, or criticize when reviewing an AI adoption strategy for a small software development agency systematically adopting Claude Code:

### He Would Immediately Ask:

**"What's your verification loop?"** This is his #1 tip, and he would make it the #1 question. If the strategy doesn't have a concrete answer for how every AI-generated output gets verified — bash commands, test suites, browser testing, something — he would flag this as the single biggest gap. "Give Claude a way to verify its work. If Claude has that feedback loop, it will 2-3x the quality." No verification infrastructure = unreliable output = slower than doing it manually.

**"Where's your CLAUDE.md?"** He would look for evidence of institutional memory that compounds. Is there a shared file in version control that captures patterns, mistakes, and preferences? Is it updated multiple times weekly? Are there GitHub Actions automating updates from PR reviews? If the answer is "we each have our own notes" or "we haven't formalized this yet," he would call it the most important thing the team isn't doing. Every mistake Claude makes should make the system permanently smarter. This is compounding engineering. Without it, you're resetting to zero every session.

**"Are you using Plan Mode before executing?"** He would want to see that the team has discipline around planning — not just throwing tasks at Claude and accepting whatever comes back. Iterate on the plan. Have a second instance review the plan. "A good plan is really important to avoid issues down the line." For a small agency where a cascading architectural mistake could cost a week, this is non-negotiable.

### He Would Praise:

**Any evidence of parallel session management.** If the team is using git worktrees and running multiple Claude sessions simultaneously — even 2-3, not Boris's 10-15 — he would see this as evidence of understanding AI as distributed capacity. "This is how you multiply a 6-person team."

**Using Opus with thinking enabled.** If the team is using the best available model rather than optimizing for token cost, he would affirm this loudly. "A wrong fast answer is slower than a right slow answer." For a small agency where rework is catastrophically expensive, model quality is the wrong place to economize.

**Slash commands and shared automation.** If the team has created shared `/commands` in `.claude/commands/` and has a `/commit-push-pr` equivalent they use routinely, he'd see this as a sign of operational maturity. If they've converted repeated workflows into skills or commands, even better.

**Everyone building, regardless of role.** If the agency's designers, project managers, or client-facing staff are using Claude Code to prototype or make changes — even small ones — Boris would see this as aligned with the future. "By the end of the year, everyone is going to be a product manager, and everyone codes."

### He Would Criticize:

**Optimizing for cost over quality.** If the strategy involves routing tasks to cheaper models, using Sonnet for "simple" tasks, or limiting session concurrency to save money, Boris would push back hard. "You're optimizing the wrong variable. Total iteration cost is what matters, not per-token expense. Less steering + better tool use = faster overall results."

**Treating Claude Code as a glorified autocomplete.** If the adoption strategy is "everyone uses Claude Code for code completion and generation," Boris would say the team is leaving 80% of the value on the table. Where's the fleet management? Where are the subagents for verification, code review, architecture? Where's the MCP integration with Sentry, Slack, your project management tools? "This is a co-worker, not an autocomplete."

**No feedback loop between Claude's mistakes and future behavior.** If the team has no systematic process for capturing what Claude gets wrong and encoding it into CLAUDE.md, lint rules, or commands, Boris would identify this as the core adoption failure. "You're going to make the same mistakes over and over. Track it. Three occurrences, automate it."

**Using `--dangerously-skip-permissions`.** He would specifically look for this and flag it. Use `/permissions` with granular patterns. Share them via `.claude/settings.json`. Safety infrastructure is not optional.

**Over-planning the adoption instead of shipping.** If the strategy document is heavy on governance frameworks, approval workflows, and phased rollouts but light on "we shipped 20 prototypes this week," Boris would be skeptical. The Claude Code team tests 5-10 ideas daily. A 6-person agency should be able to experiment at a fraction of that pace, but it should still be experimenting rapidly, not writing strategy documents.

**Accepting first answers.** If the team culture is to accept whatever Claude produces on the first pass, Boris would push for higher standards. "Don't accept first solutions; push for better." Use prompts like "Knowing everything you know now, scrap this and implement the elegant solution." The AI will produce better work if you demand better work.

### He Would Reframe:

**"How do we adopt AI?" → "How do we build for the model that exists six months from now?"** He would push the agency to stop thinking about today's limitations and start thinking about what their workflow should look like when models are 2x better. Build infrastructure (CLAUDE.md, verification loops, slash commands) that scales with model capability.

**"How do we manage risk?" → "How do we build verification infrastructure?"** He would reframe risk management away from governance and process controls and toward technical verification — test suites, automated checks, CI integration. The risk isn't that people use AI; it's that they use AI without feedback loops.

**"What's our AI policy?" → "What does our CLAUDE.md say?"** He would collapse abstract policy discussions into a concrete artifact that lives in version control and evolves with the team's learning.

**"How do we train the team?" → "What side quests are people pursuing?"** He would be less interested in formal training programs and more interested in whether team members are experimenting on their own, building personal workflows, and bringing discoveries back to the team.

### His Bottom Line Assessment Criteria:

Boris would evaluate the strategy on a simple rubric:

1. **Is there a verification loop?** (If no, nothing else matters.)
2. **Is there compounding institutional memory?** (CLAUDE.md, updated frequently, in version control.)
3. **Are they using the best model and pushing for quality?** (Opus with thinking, demanding better answers.)
4. **Are they building for the future, not the present?** (Infrastructure that scales with model improvement.)
5. **Is everyone building?** (Not just engineers — everyone on the team.)
6. **Are they shipping fast and learning from it?** (Rapid prototyping, not slow rollouts.)
7. **Are they applying common sense?** ("What does the client actually need? Does this make sense?")

If a 6-person agency nailed all seven, Boris would say they're better positioned than most 600-person engineering organizations. If they're missing #1 and #2, he'd say they're building on sand regardless of how enthusiastic their adoption is.