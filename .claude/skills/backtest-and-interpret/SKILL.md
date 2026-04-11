---
name: backtest-and-interpret
description: Use when the user runs ./backtest.sh, pastes backtest output, asks "how did X do" about a strategy run, or asks to compare two strategy versions or parameter sweeps. Triggers on PnL questions, mentions of backtests/*.log, or summarizing results from the IMC Prosperity backtester.
---

# Backtest and Interpret

## Overview

The IMC Prosperity backtester prints per-product PnL per day, then a summary across days. Naive readers lead with the total — but the total hides the signals that matter. This skill is the workflow for reading backtest output the way the user actually needs it.

## When to Use

- User runs `./backtest.sh strategies/X.py R` or `R--D`
- User asks "how did X do?" referring to a backtest
- User asks to compare strategy versions or parameter values
- User pastes backtest output and wants a summary

## Critical Facts (not derivable from the output text)

These come from reading `backtester/runner.py` and `backtester/__main__.py`. A fresh agent will miss them.

1. **PnL is mark-to-market at end of day.** `create_activity_logs` in `runner.py` adds `position * mid_price` to closed PnL at the final timestamp. A strategy holding inventory at end of day inflates its number with paper gains. When comparing two strategies, check for this trap: one ending flat vs. one ending with large inventory may not be comparable.

2. **The "Profit summary" block at the end of multi-day runs shows per-day totals only, not per-product totals across days.** To compare a product across days, read each per-day block individually.

3. **Each day reloads the trader module from disk** (`__main__.py:222`). State does not carry across days. Day boundaries reset any in-memory state.

4. **The output log is written to `backtests/<timestamp>.log`** unless `--no-out`. This is the file the visualizer (`--vis`) reads, and where sandbox limit warnings live (e.g., position limit breaches that silently dropped orders).

5. **Bot-dependent strategies backtest poorly.** If the strategy relies on counterparty behavior (taker-bot fills, maker queue position, conversions), the backtester simulates this imperfectly. Past competitors repeatedly saw strong backtests collapse live for exactly this reason. Flag it in the summary; do not treat the number at face value.

## Workflow

0. **State the edge in one sentence before citing the number.** If you cannot say *why* this strategy should make money from first principles, the PnL is unjustified — flag it and refuse to lead with the total. Past writeups are unanimous: unjustified backtest PnL is almost always overfit.
1. **Read per-product first, not total.** Per CLAUDE.md "Interpreting Backtests": a good total hides per-product losses.
2. **Judge PnL relative to position limit, not absolute seashells.** A product earning 5k/day against a 50-share limit is capital-starved, not profitable. Report `pnl / limit / day` alongside the raw number for any product where the ratio looks thin.
3. **Compute per-product trend across days** (if multi-day). Direction of motion matters more than absolute level. **Negative numbers shrinking is improving, not worsening.** Write the sequence out (e.g. `-1,135 → -890 → 215`) before naming the trend — do not eyeball it.
4. **For sparse-edge products (basket arb, options, anything lumpy), report `worst_day / median_day / best_day`, not just total.** Two good days can carry a losing strategy to a positive total; the mean lies when the distribution is skewed.
5. **Check EOD inventory. If any day ends with >30% of position limit held, say so explicitly and discount that day's PnL.** Critical Fact #1 (mark-to-market trap) only bites when inventory is non-trivial — make the check a gate, not a footnote.
6. **Lead the summary with the worst product.** If everything is positive, lead with the smallest margin one.
7. **End with one concrete next action with justification**: open day X in visualizer, widen spread on product Y, grep sandbox logs for limit breaches, etc.

## Output Format

Default to 3 lines or fewer:

```
<WORST_PRODUCT>: <trend if multi-day>, total <pnl>. <one-line diagnosis>
<OTHER_PRODUCT>: <same>
Next: <one concrete action> (see backtests/<timestamp>.log)
```

For single-day runs, drop the trend.

## Common Mistakes

| Mistake | Why wrong |
|---|---|
| Lead with "Total profit: X" | User can read the total themselves; hides product losses |
| Call a 3-day improving total "a positive trend" | 3 days is below noise threshold; do not extrapolate |
| Say "the strategy shows promise" without per-product evidence | Contentless filler |
| Treat end-of-day PnL as realized | It is mark-to-market; inventory inflates the number |
| Frame as "live trading" or "production" | This is a comp backtest, there is no live |
| Skip the log path | The log is the entry point to the visualizer and sandbox warnings |
| Declare a parameter winner from a single day | Need stability across days; one day is noise |
| Cite PnL without a theory for why the edge exists | Unjustified numbers are overfit until proven otherwise |
| Report raw PnL for bot-dependent strategies without caveat | Backtester simulates counterparty fills imperfectly; live diverges |
| Quote backtest totals as seashells instead of per-limit-per-day | Absolute numbers hide capital utilization; small products look fine in isolation |

## Overfit Guardrail

When the user is comparing parameter values:
- Stable region beats peak PnL. Always.
- Parameter winning by a wide margin on one day = noise.
- Parameter winning by a small margin on every day = signal.
- Refuse to declare a winner from a single day.
- **Suspiciously high PnL is a red flag, not a win.** If the total is an order of magnitude above the previous best on the same strategy family, the default reaction is "what broke in the sim" or "what got overfit", not "ship it".
- **Statistical tests on ≤3 days are decoration, not evidence.** Autocorrelation, z-scores, mean-reversion fits on small samples are hypothesis-generating only. Do not cite them as support for a PnL claim.

## Example

Output (multi-day):
```
EMERALDS: 4,820 / 5,210 / 4,975
KELP:    -1,135 / -890 / 215
Total:    3,685 / 4,320 / 5,190
```

Correct summary:
```
KELP: -1,135 → -890 → 215, total -1,810. Losses shrinking, flipped positive on day 0 — worth checking what changed (could be regime, could be inventory mark).
EMERALDS: ~5,000/day, total 15,005. Stable.
Next: open backtests/<timestamp>.log in the visualizer on day -2 to see KELP's trade flow.
```

Lead with the problem product, show the trend, name the mark-to-market caveat, end with a concrete drill-down.
