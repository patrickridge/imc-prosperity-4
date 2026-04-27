---
name: strategy-tuning
description: Use when the user asks how to improve a strategy, tune parameters, run a parameter sweep, optimize a knob, or "make X do better". Triggers on phrases like "tune", "optimize", "sweep", "parameter", "improve PnL", or any request to push a working strategy further. Do NOT trigger this skill for writing a brand-new strategy from scratch.
---

# Strategy Tuning

## Overview

Tuning is the act of moving an existing knob, never adding new ones. This skill enforces the discipline from `docs/strategy-principles.md`: re-tune don't rewrite, minimize parameters, explain with real behavior, prefer stable regions over peaks. The default failure mode is multi-knob grid search picking the peak — that is overfitting.

**Read `docs/strategy-principles.md` before every tuning session.** It is the source of truth.

## When to Use

- User asks "how do I improve mm_v1" / "tune this" / "make X do better"
- User wants to run a parameter sweep
- User has results from `utils/optimize.py` and wants to interpret them
- User is comparing two parameter values

Do NOT use when: the user wants to write a new strategy from scratch (different workflow), or wants to add a new product (also different).

## The Iron Rules

These come from `docs/strategy-principles.md`. Violating any of them is overfitting, full stop.

1. **One knob at a time.** Pick the single parameter most likely to matter and sweep only that one. Hold all others fixed. **Verify the knob is actually tunable** — `POSITION_LIMIT` and other competition-imposed caps are NOT knobs. They are hard ceilings set by the rules. You can use less of them, but you cannot tune them. A real knob is something the strategy chose, not something the comp gave you.
2. **Stable region beats peak.** A flat plateau of values that all perform similarly well = signal. A single value that wins by a wide margin = noise.
3. **Sweep across all available days, not one.** A parameter that wins on every day even by a small margin > a parameter that crushes day -2 and tanks day 0.
4. **No new knobs.** If the current strategy has 3 parameters, tune the existing 3. Do not add a 4th to "give yourself more flexibility."
5. **Explain why before tuning.** Before any sweep, state in one sentence what market behavior you expect the knob to capture. If you can't, do not tune it.
6. **Dramatic improvements from small shifts = overfit alarm.** If shifting a knob by 1 unit doubles your PnL, you found noise, not signal.

## Workflow

1. **Read `docs/strategy-principles.md`** (always — it's short).
2. **Identify the candidate knob.** Look at the strategy file. Pick the one parameter whose effect on real market behavior you can articulate. State the hypothesis: "I expect raising `take_edge` from 0 to 1 to reduce adverse selection on EMERALDS because the L1 quotes are more honest than the user thinks."
3. **Define the sweep range.** 5–7 values, evenly spaced, centered on the current value. Do not go wide — narrow sweeps reveal local stability.
4. **Run the sweep on every available day.** Use `utils/optimize.py` as a starting point, but be aware: as written, it sweeps 4 dimensions and sorts by total profit. **Modify it to sweep one dimension and report per-day PnL.** Do not trust the top-15-by-total list.
5. **Look for the stable region.** Plot or tabulate per-day PnL across the swept values. The right answer is the middle of the widest plateau where all days are positive (or all days improve over baseline).
6. **Pick the midpoint of the stable region**, not the peak.
7. **Refuse to commit if no stable region exists.** Report "no stable region found, current value retained" — this is a valid outcome.

## Reading `utils/optimize.py` Output Safely

The current `utils/optimize.py` (as of writing) sweeps 4 parameters simultaneously and prints the top-15 by total profit. **This output is dangerous as-is.**

- The top row is the peak — almost certainly overfit on the 2 days it tested.
- A 4-dimensional sweep cannot reveal stability without per-dimension marginal analysis.
- It only runs on days -2 and -1 — not all available days.

When the user runs it, do NOT recommend a parameter set from the top of the list. Instead, suggest rewriting the sweep to vary one dimension at a time across all days.

## Common Mistakes

| Mistake | Why wrong |
|---|---|
| Sweep multiple knobs at once | Curse of dimensionality; almost guaranteed overfit |
| Pick the peak from a sweep | Peaks are noise; pick from a stable plateau |
| Sweep on one day | One day is variance, not signal |
| "Small change → big PnL win, ship it" | This is the alarm, not the signal |
| Add a new knob to fix a problem | New knobs are new strategies — tune existing first |
| "Adjust spreads, inventory, fair value, sizing all at once" | Five overfits stacked |
| Recommend the top row of `optimize.py` output | That output is sorted by peak, not stability |
| Skip "explain why" | If you can't articulate the market behavior, you're curve-fitting |

## Red Flags — Stop and Reconsider

- "Let me try a few combinations and see what works"
- "The best parameter set is X according to the sweep"
- "We can fine-tune the inventory skew, take edge, and quote offset together"
- "This value gives 2x PnL — let's use it"
- "Let me add one more parameter"

All of these mean: stop, re-read the iron rules, restart with one knob.

## Example

User: "mm_v1 makes 13k. How do I push it higher?"

Wrong response: "Tune spread, inventory, fair value, and order size in parallel."

Right response:
> Before tuning anything, what specific market behavior do you think the strategy is leaving on the table? If KELP is the losing product (per the backtest), the candidate knob is the KELP fair-value method (`wall_mid`) or the take edge. Pick one. I'd start with `take_edge` since the existing strategy currently takes anything below fair value — raising the threshold by 0.5 / 1 / 1.5 might reduce adverse selection. Sweep that one knob across all 3 round-0 days, look for a value where all 3 days improve over baseline, and pick the middle of that range. If no value improves on all 3 days, we keep the current value and look at a different knob next.
