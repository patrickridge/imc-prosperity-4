# R4 Bot Directional Signals

*All findings independently verified by separate agents on 2026-04-27.*
*7 exploitation hypotheses tested and reviewed on 2026-04-27. See appendix.*

## Method

Computed signed price impact at multiple horizons after each bot trade across all 3 days.
Positive = bot trades predicted future price direction. Negative = bot was wrong.

**Critical timing note:** `market_trades` at timestamp T are from T-100. The +2 tick
impact is measured from trade time to next tick — but by observation time the move is
already priced in. Post-observation continuation is only ~0.1 ticks.

Tool: `python utils/trade_impact.py <day> 4`

## Results

### VELVETFRUIT_EXTRACT — 3 strong signals, 2 weak ones

| Bot | Avg impact | Day 1 | Day 2 | Day 3 | Direction | Notes |
|-----|-----------|-------|-------|-------|-----------|-------|
| Mark 67 | +1.97 | +2.03 | +1.45 | +1.83 | Follow (smart buyer) | Buy-only, 165 trades, t=+26.2 |
| Mark 49 | -1.81 | -1.16 | -1.48 | -1.04 | Fade (wrong direction) | Mostly seller, 122 trades, t=-19.0 |
| Mark 22 | -1.27 | -1.75 | -0.78 | -1.00 | Fade (weaker on Day 3) | Mostly seller, 126 trades. Fades at t+10+ on Day 3 |
| Mark 14 | -0.13 | — | — | — | Weak fade | t=-2.88 at t+1, statistically significant but tiny |
| Mark 01 | +0.22 | — | — | — | Weak follow | t=+4.54 at t+1 but fades at longer horizons |

Mark 55 is noise on VE (flips sign across days).

Mark 67 and Mark 49 are primarily trading **with each other** (76-95% of Mark 49's
sells go to Mark 67). They are the same event from two sides, not independent signals.

### HYDROGEL_PACK — no usable signal

Mark 14 and Mark 38 are counterparties in 97-99% of HP trades. Their signed impacts
are exact negatives by construction — it's really one signal, not two.
Pooled: Mark 14 mean=+0.10 (p=0.44), Mark 38 mean=-0.10 (p=0.43). Zero signal.

## Signal persistence (VE)

Impact appears immediately at t+1. Mean stays roughly stable through t+50 but median
drifts down (2.0 → 1.5). Does not grow — not a momentum signal. Decays by t+100.

| Bot | t+1 | t+5 | t+10 | t+20 | t+50 | t+100 |
|-----|-----|-----|------|------|------|-------|
| Mark 67 (mean) | +1.97 | +1.95 | +2.24 | +1.85 | +1.92 | +1.48 |
| Mark 67 (median) | +2.00 | +2.00 | +2.50 | +1.50 | +1.50 | +1.00 |
| Mark 49 (mean) | -1.81 | -1.82 | -2.12 | -1.86 | — | -2.05 |
| Mark 22 (mean) | -1.27 | -1.32 | -1.15 | — | — | +0.13 |

## VE spread

Median spread = 5 ticks. Signal = ~2 ticks. Signal cannot pay for crossing the spread.

```
Spread distribution (all 3 days, 30k observations):
  5 ticks: 74.4%
  6 ticks: 18.0%
  1-3 ticks: 7.4%
  4 ticks: 0.2%
```

## Backtest: signal-gated taker

`strategies/bot_signal.py` — take the ask/bid when signal fires. CLIP_SIZE=20.

| Day | PnL |
|-----|-----|
| 1 | +6,334 |
| 2 | -16,241 |
| 3 | -20,758 |
| **Total** | **-30,665** |

**Verdict:** Signal is real but too weak to profit as a taker. The 5-tick spread eats the 2-tick edge.

## Information timing

Backtester confirms: `market_trades` at timestamp T are trades from T-100.
The order book at T already reflects those trades. The t+1 impact we measured
IS the price when we first see the trade. The move is already done.

**We are always one tick late. The signal is not reactable.**

## Timing patterns — can we front-run?

Hypothesis: if signal bots trade at predictable times, we could position before.

**Result: no.** All three bots trade at irregular intervals with no periodicity.
CV ~1.0 for all bots (consistent with memoryless exponential process).
No autocorrelation, no FFT peaks, no preferred absolute timestamps.

| Bot | Median gap | Range | Notes |
|-----|-----------|-------|-------|
| Mark 67 | ~13.3k ticks | 300–90k | |
| Mark 49 | ~17.9k ticks | 400–125k | Often trades at same timestamp as Mark 67 |
| Mark 22 | ~4.6k ticks | 100–46k | Trades all VE symbols (spot + options) |

No dominant modulo pattern at %500 or %1000 (after accounting for tick grid artifact).

## Cross-product signals

**VE ↔ HP: no correlation.** Price change correlation ≈ 0.01 across all 3 days.
No lead-lag relationship. VE bot trades do not predict HP moves (|t| < 1.5),
and HP bot trades do not predict VE moves (|t| < 1.3, not significant).
Even Mark 14 (trades both) shows nothing cross-product. Products move independently.

## VEV option bot patterns

Four bots trade VEV options: Mark 01, Mark 14, Mark 22, Mark 38.

**No directional signal on any VEV strike.** All t+20 impact |t-stats| < 2.12,
none significant after multiple-comparison correction.

Two distinct ecosystems:

### VEV_4000 (deep ITM) — execution edge only

| Bot | Role | Edge | Directional t+20 |
|-----|------|------|-------------------|
| Mark 14 | Both sides | +10.4 (great fills) | -0.20 (t=-0.95, n.s.) |
| Mark 38 | Both sides | -10.4 (terrible fills) | +0.22 (t=+1.05, n.s.) |

Consistent across all 3 days (±0.2 variation).

### VEV_5200–5500 (near ATM) — execution edge only

| Bot | Role | Edge | Directional t+20 |
|-----|------|------|-------------------|
| Mark 01 | Buyer (705 trades) | +0.6 to +1.0 | n.s. |
| Mark 22 | Seller (791 trades) | -0.5 to -0.9 | n.s. |
| Mark 14 | Buyer (83 trades) | +0.5 to +1.0 | n.s. |

Mark 22 consistently sells below mid. Our passive bid strategy already captures this.

## Structural facts about the bots

- Mark 67 is a **pure buyer** on VE — never sells, accumulates 400-570 long per day.
- Mark 49/22 are overwhelmingly sellers (-292 to -360 and -148 to -213 per day).
- Bots have **no 200 position limit** (that limit applies to the player, not bots).
- Trade sizes vary (range 1-15, median ~9). Size carries no additional signal (H7).

## Exhaustive exploitation hypothesis testing

Eight hypotheses tested in parallel, each independently reviewed. All rejected.

| # | Hypothesis | Verdict | Key reason |
|---|-----------|---------|------------|
| H1 | Signal-biased MM | Dead end | Post-observation signal is 0.1 ticks, 10x too weak to offset spread cost |
| H2 | Signal + narrow spread | Dead end | Narrow spreads are caused by bot trades, revert by next tick. ~10 events/3 days, not exploitable |
| H3 | HP regime detection | Dead end | Roles flip mid-day (not just between days). Pooled signal is zero. |
| H4 | Cumulative inventory | Dead end | Inventory level doesn't predict beyond individual trades. 2nd-half strengthening is partly trend artifact (holds 2/3 days). |
| H5 | Vol/spread prediction | Dead end | No bot predicts spread or volatility changes on either product |
| H6 | Counterparty pairing | Dead end | Mark 67's signal is identical (+2.0) regardless of counterparty |
| H7 | Trade size conviction | Dead end | 5-lot and 15-lot Mark 67 buys produce the same ~2 tick impact |
| H8 | Options → spot linkage | Dead end | Mark 01 buys 100% from Mark 22 (same counterparty trap). Deduplicated n=318, t=1.17 n.s. Inconsistent across days. |

**Review corrections applied:**
- H2 had a fill-timing bug (off by one tick). Corrected PnL is weakly negative, not strongly negative. Still not exploitable (N=10 events).
- H4's "2nd-half strengthening" is partially a market trend artifact. After trend adjustment, alpha strengthens on Days 1+3 but not Day 2. Not robust on 3 days.
- H3's two-bot framing is redundant (Mark 14/38 are exact negatives by construction).

Scripts: `research/h1_signal_biased_mm.py` through `research/h8b_options_signal_deep.py`.

## Implication

The signal is real, consistent, but **not actionable** via:
- Taking (spread > signal)
- Maker bias (post-observation continuation is ~0.1 ticks)
- Front-running (timing unpredictable)
- Narrow-spread windows (caused by bot trades, revert instantly)
- Cross-product (no correlation)
- Trade size filtering (no size-conviction relationship)
- Volatility prediction (no spread/vol signal)
- Counterparty pairing (no amplification)
- Options → spot lead (counterparty duplication artifact, n.s. after dedup)

VEV options have execution edge patterns but no directional signal.
Our existing passive bid strategy already benefits from Mark 22's cheap selling.

**Recurring counterparty trap:** VE spot (67/49), HP (14/38), VEV options (01/22) all
share the same structure — two bots primarily trading with each other, creating the
illusion of two confirming signals from one event.

**Bot signal investigation closed.** No strategy change warranted.
