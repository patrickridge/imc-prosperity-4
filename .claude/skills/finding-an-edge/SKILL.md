---
name: finding-an-edge
description: Use when the user does NOT yet have a strategy or finding for a product and asks "what should I trade", "is there an edge in X", "let me explore round R", "I want to find a strategy for Y", or starts research on a new product or mechanic. Triggers BEFORE any strategy code is written and BEFORE any backtest is run. Do NOT trigger when the user already has a hypothesis they want to test — that is a different workflow.
---

# Finding an Edge

## Overview

Finding an edge is a two-phase parallel research pipeline, not a single agent task. Phase 1 dispatches three independent scouts in parallel (references, rules, online). Phase 2 dispatches one targeted data scout that consumes phase 1's briefs. Phase 3 is the lead's synthesis and finding-file write.

The four scouts have **zero dependencies on each other in phase 1** — they read different sources and answer different questions. Running them serially is the dominant failure mode.

**REQUIRED BACKGROUND:** `superpowers:dispatching-parallel-agents` for the parallel-dispatch mechanics.

## When to Use

- "What should I trade for product X?"
- "Let me start exploring round R"
- "Is there an edge in this product?"
- "I want to find a strategy for Y"
- New round dropped — what's worth looking at?

Do NOT use when:
- The user already has a hypothesis and wants to test it (use `promote-research-to-strategy` after the test)
- The user wants to interpret an existing strategy (use `strategy-interpreter`)
- The user wants to tune a parameter (use `strategy-tuning`)

## The Pipeline

```
PHASE 1 (parallel — single message, 3 Agent calls)
├── Reference Scout    (Explore subagent, read-only on docs/reference/)
├── Rules Checker      (general-purpose, Notion MCP access)
└── Online Researcher  (general-purpose, WebSearch + WebFetch)
                              ↓
                    Lead bundles the 3 briefs
                              ↓
PHASE 2 (informed EDA)
└── Data Eyeballer     (general-purpose, Bash + Read on data/round0/)
    Receives bundled briefs as input.
    Tests each claim against current data.
                              ↓
PHASE 3 (synthesis by lead)
    Read all 4 briefs together.
    Write `research/findings/<product>_<slug>.md` per the template.
    Propose ONE hypothesis + ONE simplest next test.
```

## Phase 1: Dispatch the Three Scouts in Parallel

**Critical:** all three Agent calls go in a SINGLE message. If you dispatch them sequentially you have failed this skill.

### Reference Scout

```
subagent_type: Explore
description: Reference scout for <PRODUCT>
prompt: |
  Grep docs/reference/ for "<PRODUCT>" (case-insensitive, also try common variants
  and short forms). Read the matched sections in full.

  Also read docs/reference/FrankfurtHedgehogs_polished.py and find any code
  related to <PRODUCT>.

  Return a brief covering, in this exact order:
  1. Fair value formula(s) used in P3
  2. Position limit in P3
  3. Recommended strategy with key rules
  4. Known pitfalls / regime breaks
  5. Expected P3 PnL contribution per round

  Quote the source with file:line refs. Do not paraphrase. Do not propose
  what to do in P4 — that is not your job. Brief should fit in ~250 words.
```

### Rules Checker

```
subagent_type: general-purpose
description: P4 rules check for <PRODUCT>
prompt: |
  Use the Notion MCP server to fetch the IMC Prosperity 4 wiki page for
  <PRODUCT>. The wiki root is at https://imc-prosperity.notion.site/prosperity-4-wiki

  Return ONLY P4-confirmed facts:
  1. Position limit (number)
  2. Tick size / price granularity
  3. Conversion rules (if any) with fees
  4. Any new mechanic introduced in P4 vs prior years
  5. Round-specific notes if the product is round-gated

  Do not interpret. Do not propose strategy. Quote the wiki page.
  Brief should fit in ~150 words.
```

### Online Researcher

```
subagent_type: general-purpose
description: Online research for <PRODUCT>
prompt: |
  Search the web for writeups, blog posts, GitHub repos, and Medium articles
  about <PRODUCT> in past IMC Prosperity competitions (especially P3, 2025).

  Useful queries:
  - "imc prosperity <product>"
  - "imc prosperity 3 <product> strategy"
  - "imc prosperity <product> writeup"

  Return the top 3-5 sources with:
  1. Source name and link
  2. Their core claim about the product (one sentence)
  3. Their expected/reported PnL contribution if mentioned
  4. Any contradiction with other sources you found

  Brief should fit in ~250 words. Skip sources that don't actually discuss
  this product.
```

## Phase 2: Bundle Briefs and Dispatch the Data Eyeballer

After all three phase 1 scouts return, **bundle their briefs verbatim** into the phase 2 prompt. Do not summarize — the data scout needs the exact claims to test.

### Data Eyeballer

```
subagent_type: general-purpose
description: Data EDA for <PRODUCT>
prompt: |
  You are testing existing claims about <PRODUCT> against the day data in
  data/round0/. Below are three briefs from the research scouts.

  --- REFERENCE BRIEF ---
  <verbatim phase 1 reference brief>

  --- RULES BRIEF ---
  <verbatim phase 1 rules brief>

  --- ONLINE BRIEF ---
  <verbatim phase 1 online brief>

  Your job: for EACH claim in the briefs that can be tested with data,
  load the relevant CSV files in data/round0/ and verify or refute it.
  Use research/visualize.py if helpful (run with `python3 research/visualize.py <day>`).

  Specifically test:
  1. Does the P3 fair value formula still hold on the current data?
  2. Does the position limit from the rules brief match what the data shows?
  3. Are the regimes/anomalies the references mention present?
  4. Is there any obvious anomaly the briefs DON'T mention?

  Return:
  - Confirmed claims (with evidence)
  - Refuted claims (with counter-evidence)
  - New observations not in the briefs
  - One sentence: "The simplest test of <hypothesis> would be <measurement>"

  Use the backtester data model: read CSVs directly with pandas,
  do not invent file paths. Brief should fit in ~400 words.
```

## Phase 3: Synthesis and Finding File

After phase 2 returns, the lead does THREE things:

1. **Look for agreement and contradiction** across all four briefs. Where they agree is solid ground; where they contradict is where the work is.
2. **Propose ONE hypothesis and ONE simplest test.** Not three. One. Per `docs/strategy-principles.md`: "Keep it simple."
3. **Write `research/findings/<product>_<slug>.md`** following `research/findings/_TEMPLATE.md`. The "How it informs the code" field starts empty (no code yet) — it gets populated when `promote-research-to-strategy` creates the file. The "When to retire" field is the kill condition you would accept.

## Conditional Follow-up

After phase 2, if the lead cannot resolve a critical contradiction from the existing briefs, dispatch ONE focused follow-up scout:
- Re-grep references with a different query
- Re-run data EDA on a specific narrow question
- Search online for a specific contradiction

**Maximum 2 follow-up rounds.** If you still can't resolve after 2 follow-ups, write the finding as `status: inconclusive` and stop. Inconclusive findings are valid — they prevent re-doing the same dead-end research later.

## Common Mistakes

| Mistake | Why wrong |
|---|---|
| Dispatch the three phase 1 scouts sequentially | Defeats the entire point of the skill — wastes 3x wall time |
| Skip the Rules Checker because "P3 limits probably still apply" | Limits change between years; one verification call costs almost nothing |
| Have one scout do both reference and online work | Loses focus, dilutes prompt, returns mush |
| Bundle phase 1 briefs into phase 2 by summarizing | The data scout needs verbatim claims to test specific numbers |
| Skip phase 2 and go straight to synthesis | The whole point is to test claims against current data, not propagate P3 wisdom blindly |
| Write the finding file before phase 2 | The finding is supposed to be informed by data, not by prior writeups alone |
| Propose 3 hypotheses in the synthesis | One hypothesis. Pick the most likely to matter. The others are notes, not the finding. |
| Do all this work for a product that already has a finding file | Check `research/findings/` first; if a finding exists, this is a tuning task, not an edge-finding task |

## Red Flags — Stop and Reconsider

- "Let me just look at the data first" (before phase 1) — this leads to data mining and overfitting
- "I already know what's going to be in the references" — then why are we researching?
- "Let me dispatch a scout to do all four jobs" — defeats the parallelism
- "Phase 2 is overkill, the briefs already say everything" — they say what *was* true; phase 2 says what *is* true
- "Let me skip the finding file, it's overhead" — the file is the deliverable; without it the work is unrecallable

## What the Finding File Is For

Other skills depend on this file existing:

- `strategy-interpreter` reads it to explain WHY a strategy looks the way it does
- `code-scanner-with-recall` reads it before suggesting code simplifications, to avoid stripping load-bearing constants
- `promote-research-to-strategy` reads it to know what edge it's promoting
- Future you, three rounds later, reads it to remember why KELP uses wall_mid

If you do not write the file, the entire downstream chain is blind.

## Example

User: "I want to find a strategy for SQUID_INK in round 1."

Step 1: Check `research/findings/squid_ink*.md` — none exists.

Step 2: Dispatch all three phase 1 scouts in a single message (parallel).

Step 3: Wait for all three. Bundle briefs.

Step 4: Dispatch data eyeballer with bundled briefs.

Step 5: Synthesize. Write `research/findings/squid_ink_initial.md`. Propose one hypothesis + one simplest test.

Step 6: Hand off to the user with: "Hypothesis: X. Simplest test: Y. If you want to run the test, the next skill is `promote-research-to-strategy` once Y confirms."
