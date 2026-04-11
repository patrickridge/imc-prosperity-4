---
name: code-scanner-with-recall
description: Use when reviewing, simplifying, refactoring, or "cleaning up" any file in strategies/. Triggers on requests to use the code-simplifier plugin on strategy code, on "this looks weird, can we clean it up", on "why is this constant 0.5", or before any refactor that touches strategy logic. Wraps the code-simplifier with a research-recall gate that prevents stripping load-bearing constants and formulas.
---

# Code Scanner with Recall

## Overview

The default code simplifier sees a constant like `0.5` and thinks "magic number, should be named or removed." But `0.5` might be the output of a parameter sweep, justified by a finding in `research/findings/`. Stripping it without checking is destructive — it deletes the edge.

This skill is the gate: **before any change to strategy code, recall the research that justified it.** If a finding protects the line, the simplifier hands off. If no finding protects it, the simplifier proceeds.

**REQUIRED BACKGROUND:** This skill complements the `code-simplifier` plugin — it does not replace it. The plugin handles the actual simplification mechanics; this skill decides what is safe to touch.

## When to Use

- User asks "simplify `strategies/mm_v1.py`"
- User invokes the code-simplifier plugin on a strategies/ file
- User says "this constant looks weird"
- User asks to refactor strategy logic
- Before any cleanup PR touching `strategies/`

Do NOT use when:
- The code is in `research/`, `backtester/`, or `docs/` — those have different rules and no findings to recall
- The change is purely cosmetic on obvious code (rename `bp` → `best_bid_price`) — no recall needed
- The user is editing CLAUDE.md or other docs

## Iron Rule

**Grep `research/findings/` before suggesting any change to a non-obvious value, formula, or branch in `strategies/`.** No exceptions for "obviously unused" or "clearly a magic number" — those judgments are exactly the ones the findings protect against.

## Three Safety Tiers

Not every line in a strategy file needs a finding. Apply this tier system:

| Tier | Examples | Recall required? | Action |
|---|---|---|---|
| **Cosmetic** | Variable renames, function splits, removing dead imports, fixing indentation | No | Simplifier proceeds normally |
| **Structural** | Reorganizing helpers, extracting functions, changing return types | No, but verify behavior is preserved | Simplifier proceeds, run backtest after |
| **Semantic** | Touching any constant, formula, branching condition, threshold, product-specific code path | **YES — recall before change** | Gated by this skill |

If you cannot decide which tier a change is in, treat it as semantic.

## Workflow

1. **Identify the proposed changes.** Either from the user's request or from a dry-run pass over the file.
2. **Classify each change** into Cosmetic / Structural / Semantic per the table above.
3. **For Cosmetic and Structural changes**, hand off to the simplifier directly. No recall needed.
4. **For Semantic changes**, for each one:
   a. Identify the product(s) affected (look at the code path the constant lives in).
   b. Grep `research/findings/` for that product. Try variants of the name.
   c. Read every matching finding file.
   d. Check the "How it informs the code" section for a back-pointer to this file/line.
5. **Decide per change**:
   - **Active finding back-points to this code** → DO NOT TOUCH. Report: "Protected by `research/findings/X.md` (active). Skipped."
   - **Retired finding back-points** → Flag for the user: "Was justified by `X.md` but the finding is retired (kill condition: ...). Safe to remove if you confirm."
   - **No finding mentions this code** → Two sub-cases:
     - The product has *some* finding files: this specific value is **undocumented**. Flag it: "No finding back-points to this line. Either it's a curve-fit constant (delete-safe but verify with backtest) or it's an undocumented edge (record a finding before changing)."
     - The product has *no* finding files at all: the strategy is **unbacked**. Refuse to simplify any semantic part of it until findings exist. Use `strategy-interpreter` first to inventory what needs documenting.
6. **Run a backtest before AND after any semantic change** that the recall gate did allow. Compare per-product PnL using `backtest-and-interpret`. If the per-product PnL on the affected product changed by more than ~5%, revert and ask the user.

## What "Back-Points To This Code" Means

A finding back-points to a line if its `## How it informs the code` section contains:
- A file path matching the strategy file (e.g. `strategies/mm_v1.py`)
- A line number, function name, or constant name from that file
- A formula description that obviously matches the code

If the finding mentions the product but doesn't reference the file/line, that is **NOT** a back-pointer. It is general context. General context does not protect a specific line — only explicit back-pointers do.

## Output Format

When the user runs the scanner, return:

```
## Cosmetic / structural changes (no recall needed)
- Rename `bp` → `best_bid_price` (line 12)
- Split `make_orders` into `compute_quote_prices` and `submit_quotes` (lines 53-71)
- Remove unused import on line 4

## Semantic changes — recall results
- POSITION_LIMIT = 80 (line 7)
  ⚠ Not a tuning knob — this is a competition cap, not a research constant.
  Skipped.
- FAIR_VALUE_EMERALDS = 10_000 (line 6)
  ✓ Protected by `research/findings/emeralds_fixed_fv.md` (status: active).
  Skipped.
- wall_mid formula uses bids[0] + asks[-1] (lines 21-22)
  ✓ Protected by `research/findings/kelp_wall_mid.md` (status: active).
  Skipped.
- take_orders break condition `ask_price >= fair_value` (line 33)
  ⚠ No finding back-points to this line. This is either a curve-fit choice
  or an undocumented edge. Recommend recording a finding before changing.

## Recommended next step
Apply cosmetic + structural changes. Leave semantic changes alone until
the unjustified ones are documented. Run backtest to confirm PnL unchanged.
```

## Common Mistakes

| Mistake | Why wrong |
|---|---|
| Skip the recall gate for "obvious magic numbers" | Those are exactly the lines findings exist to protect |
| Treat findings that mention the product as protection | Only explicit back-pointers protect; general context does not |
| Honor retired findings as protection | Retired = kill condition fired; that code is dead weight, not protected |
| Apply semantic changes without backtesting after | The whole point of recall is to preserve PnL; verify it actually did |
| Refuse all semantic changes | Unbacked code is fair game *if* the user confirms; the skill is a gate, not a wall |
| Lump cosmetic and semantic changes into one PR | The cosmetic ones are safe; the semantic ones need review. Separate them. |
| Use the simplifier plugin on `strategies/` without this gate | The simplifier alone will strip protected constants. Always wrap. |

## Red Flags — Stop the Simplifier

- "It's just a constant, let me inline it" — could be a tuned value
- "This branch looks redundant, removing" — could be a product-specific edge
- "Simplifying this formula" — could erase the whole thesis
- "The variable name is bad, refactoring while I'm in here" — scope creep into semantic territory

All of these need recall before action.

## Example

User: "Simplify `strategies/mm_v1.py`."

Wrong: invoke code-simplifier directly, accept all suggestions, commit.

Right:
1. Read `strategies/mm_v1.py`.
2. Classify proposed changes (cosmetic vs semantic).
3. Grep `research/findings/` for EMERALDS, KELP, and any other products.
4. Apply only cosmetic + structural changes that survive the recall gate.
5. List every semantic change that was skipped, with the protecting finding.
6. Run backtest before and after. Confirm per-product PnL unchanged.
7. Hand the user a clean PR with safe changes only and a list of items they need to decide on.
