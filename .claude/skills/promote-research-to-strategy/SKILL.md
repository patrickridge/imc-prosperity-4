---
name: promote-research-to-strategy
description: Use when the user wants to turn a research notebook finding, exploratory script in research/, or one-off analysis into a deployable strategy file in strategies/. Triggers on "make this into a strategy", "promote", "productionize", "clean this up for submission", or any move from research/ → strategies/.
---

# Promote Research to Strategy

## Overview

Research code and strategy code have opposite goals. Research code is exploratory: prints everywhere, dead variables, commented-out experiments, fancy plotting helpers, `df` and `x` variable names. Strategy code is production-minimal: every line in the submission. This skill is the discipline of leaving 90% of research code behind.

## When to Use

- User has a finding in `research/*.py` or a notebook and says "let's make this a strategy"
- User asks to "promote" or "productionize" exploratory code
- User wants to copy logic from `research/` into `strategies/`

## The Iron Rules (from CLAUDE.md)

The user's `CLAUDE.md` is the spec. Re-read it before promoting. The relevant rules:

- **No magic numbers** — every threshold gets a `NAMED_CONSTANT`
- **Functions <30 lines** — split aggressively
- **Max 2 levels of indentation** — early returns, guard clauses
- **One concern per file**
- **Names so good comments are unnecessary** — `calc_fair_value()` not `calc()`
- **No type hints, docstrings, or comments on code that is already clear**
- **No error handling for impossible states**
- **No abstractions until the same pattern appears 3+ times**

Violating any of these is a sign you copy-pasted research code instead of rewriting it.

## Workflow

1. **State the edge in one sentence.** What market behavior does this strategy exploit? If you can't say it, do not promote. (This is the "explain with real behavior" rule from `docs/strategy-principles.md`.)
2. **Read `strategies/example.py` first — non-negotiable.** It is the canonical minimal structure. The following are NOT inventable — copy them exactly from the template:
   - `from backtester.datamodel import Order, OrderDepth, TradingState` (the path is `backtester.datamodel`, not `datamodel`)
   - `from strategies.logger import Logger` and `logger = Logger()` at module level
   - `class Trader:` with a `def run(self, state: TradingState):` method (the backtester checks for `Trader` per `__main__.py:208`)
   - Orders are `Order(product, price, quantity)` instances, NOT dicts (the backtester type-checks this in `runner.py:type_check_orders` and will reject dicts)
   - Position is read via `state.position.get(product, 0)` — the attribute is `position` (singular)
   - Return shape: `return orders, conversions, trader_data` where `orders` is a `dict[str, list[Order]]`
   - `logger.flush(state, orders, conversions, trader_data)` is called once at the end of `run`
3. **Open the research file and identify ONLY the lines that compute the trading decision.** Everything else — plotting, prints, dataframe ops, parameter exploration — stays in research.
4. **Rewrite from scratch in the strategy file.** Do not copy-paste. Retype it. This forces you to drop noise.
5. **Pull every magic number into a named constant** at the top of the file. If you can't name it, you don't understand it.
6. **Backtest immediately.** Use the `backtest-and-interpret` skill to read the result.
7. **Compare to the previous strategy on the same days.** If it doesn't beat baseline, the finding was research noise. Delete it from `strategies/` — leave it in `research/`.

## What Stays in `research/`

- Pandas / dataframe code
- Print statements
- Plotting (`matplotlib`, `plotly`)
- Experimentation loops over time windows
- Variable names like `df`, `x`, `y`, `tmp`
- Commented-out alternatives
- Hyperparameter exploration

If any of these survive into `strategies/*.py`, the promotion failed.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Copy-paste research code wholesale | Retype from scratch using the edge as the spec |
| Keep `df.iloc[...]` style code | Strategy code receives `OrderDepth`, not a DataFrame — convert at the boundary |
| Carry over `print()` calls | Use `logger.print()` only, and only where needed |
| Add `# this calculates the fair value` comments | Rename the function to `calc_fair_value` and delete the comment |
| Add `try/except` around impossible cases | Trust the framework; only handle real failure modes |
| Add type hints "for safety" | The `TradingState` types are already imported; new ones add noise |
| Build a `Strategy` base class for one strategy | No abstractions until 3+ uses |
| Inline 60-line `run()` method | Split into helpers: `take_orders`, `make_orders`, `compute_fair_value` |
| Add a config dict / YAML / argparse | Constants at top of file. That is the config. |

## Red Flags — Restart the Promotion

- "Let me just clean this up a bit" (you'll keep 80% of the noise)
- "I'll add a Strategy base class for future flexibility"
- "Let me add type hints to make it safer"
- "I'll keep these prints just in case"
- "This needs a docstring explaining what it does"

All mean: stop. Retype from `strategies/example.py` instead.

## Length Sanity Check

The existing `strategies/mm_v1.py` is ~100 lines including imports, two helpers, and the `Trader` class. A new strategy of similar complexity should be in the same range. If your promoted file is 200+ lines, you carried over research noise.

## Example

Research code (in `research/kelp_signal.py`):
```python
# Hypothesis: KELP wall mid is biased; deepest level is the real anchor
import pandas as pd
import matplotlib.pyplot as plt

df = load_day_prices(-1, 'KELP')
df['wall_mid'] = (df.bid_3 + df.ask_3) / 2
df['naive_mid'] = (df.bid_1 + df.ask_1) / 2
plt.plot(df['wall_mid'] - df['naive_mid'])
plt.show()
# wall_mid lags naive_mid by ~3 ticks but is more honest
print(df['wall_mid'].describe())
```

Wrong promotion: paste it into `strategies/`, swap `df` for `state`.

Right promotion: write a fresh strategy file. The only thing that crosses the boundary is `wall_mid = (deepest_bid + deepest_ask) / 2`. Everything else stays in research.
