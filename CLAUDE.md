# IMC Prosperity 4

## Core Principle: Clarity Above All

Every line of code must be immediately understandable. If it needs a comment, rewrite it first. Simple beats clever. Always.

## Code Rules

- **No walls of text.** Keep functions under 30 lines. Break large logic into small, named steps.
- **No magic numbers.** Use named constants with obvious names.
- **No clever one-liners.** Expand them. Readability wins over brevity.
- **No deep nesting.** Early returns, guard clauses. Max 2 levels of indentation in logic.
- **No god files.** One concern per file. Split aggressively.
- **Name things so comments are unnecessary.** `calc_fair_value()` not `calc()`. `best_bid_price` not `bp`.

## Information Overload Prevention

- Do not dump large outputs, logs, or data tables without summarizing first.
- When analyzing data, lead with the insight, then show supporting evidence only if asked.
- Keep responses short. One idea per message when possible.
- Prefer a 3-line summary over a 30-line explanation.

## Project Structure

```
strategies/     # One .py per strategy. This is where you work.
research/       # Notebooks, analysis, exploratory scripts
data/round0/    # Market data by round
backtester/     # Adapted jmerle backtester (do not edit unless extending infra)
docs/reference/ # P3 solutions, writeups for learning
dashboard/      # Interactive Plotly Dash dashboard
backtest.sh     # Quick runner: ./backtest.sh strategies/my_strat.py 0
submit.sh       # Bundle for upload: ./submit.sh strategies/my_strat.py
```

## Quick Start

```bash
# Run a strategy on all round 0 days
./backtest.sh strategies/my_strat.py 0

# Run on a specific day
./backtest.sh strategies/my_strat.py 0--2

# Open in visualizer after
./backtest.sh strategies/my_strat.py 0 --vis
```

## Dashboard

```bash
pip install dash
python3 -m dashboard          # localhost:8050
```

Panels: order book scatter, spread, LOB depth, PnL, position, trade table.
Select a backtest log to overlay your algo's trades, PnL, and position.
Auto-discovers new data in `data/round*/` and logs in `backtests/`.

## Research Tools

```bash
# Visualize price/trades/LOB for a day
python3 research/visualize.py -1        # day -1, round 0
python3 research/visualize.py -2 1      # day -2, round 1

# Trade impact analysis
python3 research/trade_impact.py -1     # day -1, round 0
```

## Strategy Development Workflow

1. Copy `strategies/example.py` to start a new strategy
2. Research in `research/` — keep exploratory code separate from algo code
3. Backtest with `./backtest.sh`
4. Visualize with jmerle's visualizer (`--vis` flag)
5. Bundle for submission with `./submit.sh` (inlines Logger, swaps imports)
6. Algo code stays minimal and production-ready at all times

## References

- **`docs/strategy-principles.md`** — read before designing or modifying any strategy. Non-negotiable design rules (re-tune don't rewrite, no overfitting, explain with real behavior, keep it simple).
- **`docs/reference/`** — P2/P3 writeups and solved strategies. When a new product or mechanic appears, check here for precedent before inventing.
- **P4 Wiki**: https://imc-prosperity.notion.site/prosperity-4-wiki — when the user asks about game mechanics, products, position limits, or round rules, fetch the relevant page via the Notion MCP server first instead of guessing.
- **Visualizer**: https://jmerle.github.io/imc-prosperity-3-visualizer/

## Interpreting Backtests

- The backtester prints a total PnL and a per-product breakdown. Read the per-product line first — a good total can hide one product losing money.
- Prefer **stable parameter regions** over peak PnL. If a ±1 shift in a knob collapses the PnL, it is overfit.
- Compare against the previous run on the same day(s), not against a theoretical maximum.

## Do NOT

- Add type hints, docstrings, or comments to code that is already clear
- Over-engineer for hypothetical future rounds
- Create abstractions until the same pattern appears 3+ times
- Add error handling for impossible states inside algo logic
- Write unit tests for strategy code. The backtest is the test. Tests belong only inside `backtester/` if you are extending infra.
