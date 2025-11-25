# 5 Things I Learned Building Production Software with Claude Code

*Draft notes for potential Medium article - based on building dfo DevFinOps CLI*

---

## 1. **Architecture Constraints Enable AI Velocity**

**The Insight:** Clear architectural boundaries are MORE important when working with AI, not less.

**What happened:** We established strict layer responsibilities upfront (documented in CODE_STYLE.md):
- `providers/` calls Azure SDKs only, never touches database
- `discover/` writes to DuckDB, never runs analysis
- `analyze/` pure logic, no cloud calls
- `cli/` orchestrates only, no business logic

**Why it mattered:** Because AI can generate code quickly, it's tempting to take shortcuts. But these constraints prevented a tangled mess. When adding progress display, the callback pattern emerged naturally because discovery layer couldn't know about Rich/terminal UI.

**Key Quote:** "Fast code generation × poor architecture = fast technical debt"

---

## 2. **The Tight Feedback Loop is Your Superpower**

**The Insight:** Test immediately, report precisely, iterate fast.

**What happened:**
- Built enhanced progress display → tested → found "Using rule: Idle VM Detection" was confusing during discovery
- Changed message same session
- Deployed idle-vms rule with "period: 3d" → tested → got 14 days instead
- Found the bug in rule engine forcing defaults
- Fixed in two iterations (shell env, then .env file)

**Why it mattered:** Each issue was caught and fixed within minutes because of immediate testing. Traditional dev cycle would have been: code → commit → deploy → QA finds bug days later → context switching cost.

**Key Quote:** "The best thing about AI pair programming isn't the code generation - it's the zero-cost iteration speed"

---

## 3. **Specification Precision > Implementation Details**

**The Insight:** Be specific about WHAT you want, not HOW to build it.

**What happened:** User said: "can we make the spinner during discover process fancier?"

I provided 4 options with tradeoffs. User responded:
- "Option 4" (hybrid progressive enhancement)
- "100 columns" (specific threshold)
- "keep simple" (no timing stats)
- "show failed VMs inline" (not in summary)

**Result:** Got exactly what was needed, first try. No back-and-forth on implementation details.

**Why it mattered:** AI can generate many solutions. Your job is choosing the RIGHT one by specifying constraints, not implementation.

**Key Quote:** "Tell me the threshold is 100 columns and why. I'll figure out shutil.get_terminal_size()."

---

## 4. **Living Documentation is Your Second Brain**

**The Insight:** Documentation isn't overhead - it's how you scale AI collaboration.

**What happened:** Created CLAUDE.md with:
- Architecture patterns (rules-driven CLI, progress callbacks)
- Layer responsibilities (what each module must/must not do)
- Implementation examples (how to add progress to long operations)

**Impact:** When adding Right-Sizing overrides, I followed the exact pattern from Idle VM Detection without being told. The documentation was the specification.

**Why it mattered:** Documentation captures decisions. AI reads it every session. You document once, AI applies everywhere.

**Key Quote:** "CLAUDE.md isn't instructions for the AI - it's your team's institutional memory that never forgets"

---

## 5. **Real Users Find Real Bugs (Tests Don't)**

**The Insight:** Comprehensive tests passed. Production usage found the critical bug immediately.

**What happened:**
- 341 tests passing ✓
- User sets `DFO_IDLE_DAYS=7` in .env
- Runs discover → gets 14 days from default, not 7 from .env
- Bug: pydantic loads .env into Settings, doesn't populate `os.environ`
- Fix: Check both `"DFO_IDLE_DAYS" in os.environ` AND `settings.dfo_idle_days != 14`

**Why it mattered:** Tests verified the code worked. User verified it solved the actual problem. The .env use case wasn't in our test scenarios.

**Key Quote:** "Testing proves your code works. Users prove your code is useful. Don't confuse the two."

---

## Bonus Insight: **Progressive Enhancement > Feature Flags**

The terminal detection that auto-switches between simple/rich mode is better UX than:
```bash
./dfo azure discover --display=rich  # Explicit flag
```

Let the system adapt to the environment. Users want it to "just work."

---

## What This Means for Your Next GenAI Project

1. **Start with constraints, not features** - Write your CODE_STYLE.md first
2. **Build in small, testable increments** - Not "build the whole thing"
3. **Test immediately after generation** - Don't batch testing for later
4. **Document patterns as they emerge** - CLAUDE.md grows WITH your project
5. **Ship early, iterate with real usage** - Tests validate code, users validate value

**The Meta-Learning:** GenAI doesn't replace software engineering discipline. It amplifies it. Good practices become superpowers. Bad practices become technical debt at light speed.

---

## Real Examples from Building dfo

### Progress Display (PR #16)
- 8 phases: event system → terminal detection → handlers → CLI integration → error handling → tests → docs
- All completed in single session
- 15 new tests, all passing
- Rich mode: tree view with live VM progress
- Simple mode: single-line spinner for CI/narrow terminals
- Automatic adaptation based on terminal width

### Rule Override System (PR #17)
- Found bug: rule file values ignored, always using defaults
- Root cause: unconditional override instead of optional
- Extended from 1 rule to 3 rules (Idle, Right-Sizing, Shutdown)
- Priority: shell env > .env file > rule file
- Fixed .env detection (pydantic doesn't populate os.environ)

### Key Metrics
- 341 tests passing throughout
- 3 PRs created from this collaboration
- Zero breaking changes to existing functionality
- Complete feature implementations in single sessions

---

## Questions to Explore

- What would you add? What surprised you most about building with Claude Code?
- How does this change for teams vs solo development?
- What's the right balance between AI generation and human code review?
- How do you prevent "AI-generated spaghetti" at scale?

---

## TODO for Article

- [ ] Add specific code examples showing before/after
- [ ] Include terminal screenshots of rich vs simple mode
- [ ] Add metrics: lines of code, time savings, bug catch rate
- [ ] Interview perspective: what did the human developer experience?
- [ ] Contrast with traditional development workflow
- [ ] Discuss limitations: where AI struggled, where human insight was critical
