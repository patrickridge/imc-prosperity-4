# Round 4 — Rook-E1 Advisor Hints

## Binary Put: Threshold Concentration

A binary put is defined by a single threshold. Everything concentrates there. Above
the threshold, nothing. Below it, everything. That abrupt discontinuity creates a
fundamentally different risk profile compared to a standard put, where sensitivity is
distributed gradually across a range of prices.

## Knock-Out Put: Path Dependency

The knock-out put introduces a different structural challenge. Its value does not merely
shift at a threshold. It can be eliminated entirely depending on the path the underlying
takes. Not the destination, the path. A position that looks sound at entry can cease to
exist before it ever reaches resolution.

## Hedging with Vanillas

In both cases, ask whether vanilla options can be used to offset the most extreme
scenarios. A carefully constructed vanilla position can soften the abrupt payoff cliff
of the binary. It can provide a buffer against the knock-out trigger before it becomes
an irreversible outcome. Restructuring the payoff this way will change its shape, yes.
But a payoff you can model clearly under adverse conditions is worth considerably more
than an elegant one that fails without warning.

When payoffs are discontinuous, risk management becomes structural rather than
occasional. Structure your risk accordingly.
