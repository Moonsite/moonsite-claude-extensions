# Boris Cherny — Compiled Source Material

## BIOGRAPHY & BACKGROUND

- American software engineer and AI specialist
- Studied economics at UC San Diego (2009-2011), dropped out — no CS degree, self-taught programmer
- Founded first startup at age 18
- Worked at smaller tech firms, a hedge fund, and a nonprofit
- Author of "Programming TypeScript" (O'Reilly, 2019)
- Organized San Francisco TypeScript Meetup
- Created Undux (React state management library), json-schema-to-typescript, and other open source tools

## META/INSTAGRAM CAREER (Nov 2017 – Aug 2024)

Progression: IC4 → Senior → Staff (IC6) → Senior Staff (IC7) → Principal Engineer (IC8)

Key achievements:
- **Chats in Groups:** Led Messenger integration into Facebook Groups. Cross-functional initiative revealing latent user demand.
- **Comet Platform Migration:** Led Facebook Groups migration to single-page app. Team of 30 engineers. Influenced core relay mutation abstractions.
- **Public Groups Initiative:** Drove feature allowing participation without membership. Complex data modeling and moderation challenges.
- **Communities as New Organizations:** Scoped architecture for hundreds of engineers.
- **Instagram Codebase Modernization:** As Principal Engineer, migrated from Python to Hack, leveraging HHVM and GraphQL.
- **Code Quality Research:** Led causal analysis showing clean codebases boost engineering productivity by double-digit percentage. One of Meta's most prolific code reviewers. Tracked repeated review comments in a spreadsheet; once a pattern hit 3-4 occurrences, wrote a lint rule to automate it away.

## ANTHROPIC & CLAUDE CODE (Sep 2024 – Present)

### Genesis
- Joined Anthropic September 2024 as founding engineer
- Prototyped Claude Code using Claude 3.6 model — started as a CLI tool to identify and change music via AppleScript
- "Very much an accident" — grew from internal prototype
- Internal launch: 20% adoption day one, 50% by day five
- General availability: May 2025
- By mid-2025: 300%+ active user growth, revenue expanding 5.5x
- Reached $1B run-rate revenue, commands over half AI coding market
- 4% of public GitHub commits
- Daily active users doubling month-over-month
- 72.7% accuracy on SWE-bench Verified (vs OpenAI Codex 69.1%)

### Core Development Philosophy
- "Don't build for today's model, build for the model six months from now" (from manager Ben Mann)
- Minimalist architecture in TypeScript and React to maximize AI model efficiency
- Culture of 60-100 internal releases daily with bottom-up feature building
- Created ~20 prototypes for features over two days, testing 5-10 ideas daily
- "My setup might be surprisingly vanilla! Claude Code works great out of the box"

### July 2025 Career Interruption
Briefly joined Anysphere (rival AI firm) but was subsequently rehired by Anthropic.

## WORKFLOW & PRACTICES

### Fleet Management / Parallel Execution
- Runs 10-15 concurrent Claude Code sessions: 5 in terminal + 5-10 on claude.ai/code + mobile sessions
- Each local session uses its own git checkout or worktree
- Uses `&` and `--teleport` to move sessions between local and web
- Acknowledges 10-20% session abandonment rate
- Starts sessions from iOS app in mornings, continues on desktop
- Treats AI as distributed capacity, not a single tool

### Model Selection
- Exclusively uses Opus 4.5 with thinking for everything
- "A wrong fast answer is slower than a right slow answer"
- Optimization target: total iteration cost, not per-token expense
- "Less steering + better tool use = faster overall results"

### CLAUDE.md as Institutional Memory
- Team maintains single CLAUDE.md file in git, updated multiple times weekly
- When Claude makes mistakes, patterns documented to prevent recurrence
- "Safety infrastructure rather than reactive documentation"
- Uses `@.claude` tags on colleague PRs to integrate learnings
- GitHub Actions automate CLAUDE.md updates from PR reviews
- Current documentation: ~2.5k tokens
- Implements "Compounding Engineering" (Dan Shipper concept)
- Example: "prefer `type` over `interface`; never use `enum`" (use string literal unions)

### Planning Discipline
- Plan Mode first (Shift+Tab twice), iterate until satisfied, then auto-accept
- "A good plan is really important to avoid issues down the line"
- Prevents unwanted cascading changes
- Advanced: one engineer has Claude write plan, spins up second Claude to review as staff engineer

### Verification Loop — "The #1 Tip"
- "Give Claude a way to verify its work. If Claude has that feedback loop, it will 2-3x the quality"
- Methods: bash commands (simple), test suites (moderate), browser/phone testing (complex)
- Claude tests UI via Chrome extension, iterates until code functions and UX feels good
- "Probably the most important thing"

### Slash Commands & Automation
- `/commit-push-pr` used dozens of times daily
- Pre-computes git status via inline bash to reduce model back-and-forth
- Commands stored in `.claude/commands/` and shared with team
- If used more than once daily, convert to skill or command

### Subagents
- Specialized roles: code-simplifier, verify-app, build-validator, code-architect, oncall-guide
- Not generalist — separate agents for spec-writing, coding, verification
- Support worktree isolation for parallel code migrations

### Formatting & Quality
- PostToolUse hook: `bun run format || true` — auto-formats code, handles final 10%
- Prevents CI failures from inconsistent formatting

### Permissions Strategy
- Uses `/permissions` to pre-allow safe commands (not `--dangerously-skip-permissions`)
- Patterns: `Bash(bun run build:*)`, `Bash(bun run test:*)`
- Shares permission lists via `.claude/settings.json`

### MCP Integrations
- Slack, BigQuery, Sentry error logs
- Hasn't written SQL in 6+ months
- On-demand tool loading prevents context bloat

### Advanced Prompting Techniques
- "Grill me on these changes and don't make a PR until I pass your test"
- "Prove to me this works" (compare main vs feature branch)
- After mediocre fixes: "Knowing everything you know now, scrap this and implement the elegant solution"
- Write detailed specs to reduce ambiguity
- Don't accept first solutions; push for better

## PREDICTIONS & VIEWS ON THE FUTURE

### "Coding is Largely Solved"
- "I think at this point it's safe to say that coding is largely solved. At least for the kind of programming that I do."
- "I have not edited a single line by hand since November"
- December 2025: shipped 259 PRs, 497 commits, 40K lines added, 38K removed — all via Claude Code
- January 2026: Claude Code reached 100% self-authorship
- "Claude Code is 100% written by Claude Code"

### Role Transformation
- "The title software engineer is going to start to go away. It's just going to be replaced by 'builder.'"
- "By the end of the year, everyone is going to be a product manager, and everyone codes"
- "On the Claude Code team, everyone codes. Our PM codes, our EM codes, our designer codes, our finance guy codes"
- "There's maybe a 50% overlap in these roles where a lot of people are actually just doing the same thing"
- Developer role splitting into 3 tracks

### Disruption Timeline
- Software engineer title could become obsolete by end of 2026
- "In a year or two, it's not going to matter" (regarding programming fundamentals)
- "It's going to be painful for a lot of people" and "very disruptive"
- Entry-level positions face particular vulnerability
- Compares to printing press disrupting scribes

### Still Needs Humans
- "Someone has to prompt the Claudes, talk to customers, coordinate with other teams, decide what to build next"
- "Engineering is changing and great engineers are more important than ever"
- Anthropic still hiring 100+ engineers despite AI writing all code
- Human oversight hasn't disappeared; it has transformed
- Horse and harness analogy: Claude is powerful but requires skilled human direction

### Beyond Code
- "Claude is starting to come up with ideas... looking through feedback, bug reports, telemetry — a little more like a co-worker"
- AI agents will extend "beyond coding to pretty much any kind of work that you can do on a computer"
- Workers must shift toward "AI systems oversight, architecture, and strategic planning"

### Productivity Data
- ~50% increased productivity through AI integration at Anthropic
- AI completes 60% of tasks with reduced oversight
- 67% boost in pull request throughput
- Engineers enjoy coding more — focus on architecture, user problems, big ideas

## ENGINEERING PHILOSOPHY

### Five Core Career Principles
1. **Design for Future Capabilities** — "Don't build for today's model, build for the model six months from now"
2. **Discover Latent Demand** — 40% of Facebook Groups users were doing commerce; users hack solutions before products emerge
3. **Side Projects Drive Career Growth** — Undux, TypeScript community, lint automation; compounds influence faster than core duties
4. **Break Organizational Swim Lanes** — Be a generalist combining engineering, product thinking, and design
5. **Apply Common Sense Relentlessly** — "What does the user actually need?" and "Does this make sense?"

### On Uncertainty
"No one knows what they're doing at any level. If you don't feel it, you're not pushing hard enough."

### On Technical Grounding
"Writing code anchors you to reality. Without it, you lose intuition quickly."

### On Team Influence
"You never want to tell anyone what to do. Understand what they want, then present opportunity."

### On Hiring
Seeks engineers with "side quests" — weekend projects and intellectual curiosity signaling growth mindset. Cited an engineer passionate about kombucha fermentation as ideal candidate profile.

### On Code Quality
- Code quality has measurable double-digit-percent impact on engineering productivity
- Tracked review comments in spreadsheet; 3-4 occurrences → automated lint rule
- One of most prolific code reviewers at Meta

### On AI Safety
- Joined Anthropic because: "I wanted to be at a place where, in the tiniest way, I can make sure this goes well"
- Takes labor disruption concerns "very, very seriously"
- Emphasizes human oversight for critical systems
- Stresses responsible development within ethical frameworks

### On Minimalism
- "Surprisingly vanilla" setup
- Success from disciplined fundamentals, not exotic hacks
- "Less steering + better tool use = faster overall results"
