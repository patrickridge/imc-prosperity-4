---
name: strategy-interpreter
description: Use when the user asks to explain, interpret, or walk through an existing strategy file in strategies/. Triggers on "explain mm_v1", "what does this strategy do", "why does X use Y", "walk me through this code", or onboarding to a strategy you didn't write. Distinct from backtest-and-interpret (which reads results) — this reads CODE and recalls the research that justified it.
---

# Strategy Interpreter

## Overview

Interpreting a strategy is not the same as describing it. Description says "this function takes orders below fair value." Interpretation says "this function takes orders below fair value because the P3 reference shows the L1 quotes have ~0.5 SeaShell adverse selection on KELP — see `research/findings/kelp_l1_bias.md`." The first is narration; the second is justification.

This skill is the workflow for reading strategy code WITH its research context attached.

## When to Use

- "Explain `strategies/mm_v1.py`"
- "Walk me through this strategy"
- "Why does this use wall_mid instead of the L1 mid?"
- "What's the thesis of this code?"
- Onboarding to a strategy after a break
- Reviewing a strategy before tuning it

Do NOT use when:
- The user wants to interpret backtest results (use `backtest-and-interpret`)
- The user wants to fix or rewrite the strategy (different workflow)
- The strategy file is brand new and has no research backing yet (the answer is "no findings yet, code is unjustified")

## Iron Rule

**Read `research/findings/` BEFORE explaining any non-obvious code decision.** If you explain a constant or formula without checking the findings, you are inventing intent.

## Workflow

1. **Read the strategy file fully.** Note every: named constant, branching condition, fair-value formula, position-management rule, product-specific code path.
2. **Inventory the non-obvious decisions.** A constant is non-obvious if you can't predict its value from first principles. A formula is non-obvious if there's more than one reasonable choice. A branch is non-obvious if it treats one product differently.
3. **For each non-obvious decision, grep `research/findings/`** for the relevant product. Try variants of the product name. Read any matching finding file in full.
4. **Match decisions to findings.** Each decision should map to either:
   - A finding that justifies it (status: active)
   - A finding that USED to justify it (status: retired) — flag this loudly
   - No finding at all — flag as "unjustified" with the same loudness
5. **Build the explanation in three layers**:
   - **Structure:** what the code does mechanically (one paragraph)
   - **Thesis:** what edge it's exploiting (one sentence per non-obvious decision)
   - **Backing:** which finding file justifies each part (file path + status)
6. **Lead with the unjustified decisions.** If anything has no finding, that is the most important thing to surface — the user has either an undocumented edge or a piece of curve-fit code, and they need to know which.

## Output Format

```
## Structure
<one paragraph: how the code flows mechanically>

## Decisions and their justification
- <decision 1>: <one-sentence thesis> — `research/findings/<file>.md` (status: active)
- <decision 2>: <one-sentence thesis> — `research/findings/<file>.md` (status: active)
- <decision 3>: ⚠ NO FINDING — this constant/formula has no research backing.
  Either document why or treat it as suspect.

## Open questions
<things the code does that no finding justifies and no first principles explain>
```

## Common Mistakes

| Mistake | Why wrong |
|---|---|
| Narrate the code without checking findings | "It takes orders below fair value" is true but not interpretation. The user can read the code. |
| Invent reasons for decisions not in findings | Confabulation. If you don't know, say "no finding". |
| Treat retired findings as still valid justification | Retired means the kill condition fired. Code resting on retired findings is dead weight. |
| Skip the unjustified-decision callout | This is the most important output of this skill. Bury the lede and the user makes bad decisions later. |
| Explain obvious code | The CLAUDE.md rules require code to be self-explanatory at the line level. Your job is to explain *intent*, not lines. |
| Read only one finding and assume it covers all decisions | One finding per decision. Map them individually. |
| Quote findings vaguely ("the research says it works") | Quote the file path and the relevant section. |

## Special Case: No Findings Directory or Empty

If `research/findings/` is empty or missing, the answer is direct: "This strategy has no recorded research backing. Every non-obvious decision in it is currently unjustified. Before tuning or extending this code, the research should be reconstructed and recorded as findings."

This is a valid output. It is more useful than fabricating justifications.

## Example

User: "Explain `strategies/mm_v1.py`."

Right response (if KELP finding exists):
```
## Structure
mm_v1 is a market maker that runs a take-then-make loop per product.
For EMERALDS it uses a fixed fair value of 10,000. For everything else
it computes wall_mid from the deepest book level. It takes any orders
priced through fair value, then quotes inside the spread skewed by
inventory position.

## Decisions and their justification
- EMERALDS fair value = 10,000 (constant): EMERALDS oscillates ±4 around
  a fixed anchor — `research/findings/emeralds_fixed_fv.md` (status: active)
- Non-EMERALDS uses wall_mid: deepest book level is more honest than L1
  due to L1 noise traders — `research/findings/kelp_wall_mid.md` (status: active)
- POSITION_LIMIT = 80: ⚠ NO FINDING — but POSITION_LIMIT is a competition cap,
  not a tuning knob. This is the rules-imposed maximum, not a research decision.
  Verify against the P4 wiki for the active round.

## Open questions
- The take loop breaks at the first ask >= fair_value. No finding covers
  whether to be more aggressive (take through fair value by N ticks) on
  high-confidence products.
```

Wrong response: a 4-paragraph narration of what each function does, with no reference to research and no flag on unjustified constants.
