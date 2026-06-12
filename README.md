# Project Paradise IMC Prosperity 4 Toolkit

Shared infrastructure and strategies for [IMC Prosperity 4](https://prosperity.imc.com), built and maintained by [Project Paradise](https://project-paradise.co.uk) — a student community working on mathematical modelling competitions and projects together.

This toolkit is open for everyone to use, modify, and share. If you're interested in quant, ML or mathematical modelling more broadly and want to learn by building things with others, [come join the community](https://project-paradise.co.uk/join/).

## The team

Lev Rozanov, Patrick Ridge, Kaushal, Kieran Chung, George

## What's inside

- **`backtester/`** — local backtester adapted from [jmerle's prosperity backtester](https://github.com/jmerle/imc-prosperity-3-backtester), extended with per-round position limits, trade-matching modes and submission-log parsing
- **`strategies/`** — one file per strategy, from round 1 market making through the round 5 multi-product combined runner
- **`research/`** — hypothesis-test scripts and findings; each round got its own numbered series (H1, H2, ...) testing pair stability, drift persistence, order-book imbalance, cointegration, lead-lag and more
- **`manual/`** — the manual challenge work per round: auction game theory, exotic option pricing via Monte Carlo, news-driven portfolio allocation under quadratic fees
- **`dashboard/`** — interactive Plotly Dash app for order books, spreads, depth, PnL and position, with backtest-log overlay and strategy comparison
- **`data/`** — official market data by round

## Setup

```bash
pip install -e .
```

## Usage

### Backtest a strategy

```bash
# Run on all round 0 days
./backtest.sh strategies/example.py 0

# Run on a specific day
./backtest.sh strategies/example.py 0--2

# Open in visualizer after
./backtest.sh strategies/example.py 0 --vis
```

### Bundle for submission

```bash
./submit.sh strategies/my_strat.py
# Output: submissions/my_strat.py (upload to prosperity.imc.com)
```

For multi-file strategies (like the round 5 combined runner) use the bundler, which inlines every sub-strategy into one upload-ready file:

```bash
python3 research/round5_build_submission.py
```

### Dashboard

```bash
pip install dash
python3 -m dashboard          # localhost:8050
```

Auto-discovers data under `data/round*/` and backtest logs under `backtests/`. Select a log to overlay your algo's trades, PnL and position on the market view, or compare two runs side by side.

### Research tools

```bash
# Visualize price/trades/LOB for a day
python3 utils/visualize.py -1        # day -1, round 0
python3 utils/visualize.py -2 1      # day -2, round 1

# Trade impact analysis
python3 utils/trade_impact.py -1

# Analyze submission/backtest logs
python3 utils/analyze_logs.py backtests/my_run.log
```

### Parse submission logs into data

```bash
# Convert official submission logs into backtester-compatible CSVs
python3 backtester/parse_submission_logs.py path/to/log.log <round> <day>
```

## Writing a strategy

Copy `strategies/example.py` and implement your `Trader.run()` method. The logger in `strategies/logger.py` is automatically inlined by `submit.sh`.

## Acknowledgements

- [jmerle](https://github.com/jmerle) for the open-source backtester and [visualizer](https://jmerle.github.io/imc-prosperity-3-visualizer/) the whole community builds on
- IMC for running Prosperity
- The writeups from past top teams (linked throughout `docs/reference/`), which saved us from reinventing several wheels
