---
product: PRODUCT_NAME
date: YYYY-MM-DD
status: active        # active | retired | refuted
hypothesis: One sentence — what edge you expect from real market behavior
test: One sentence — the simplest measurement you ran
result: confirmed     # confirmed | refuted | inconclusive
---

## Why we looked
Where the idea came from (P3 reference, data anomaly, online writeup, intuition).

## What we measured
The actual EDA. Numbers, not narrative. Reference the research file or notebook
that generated them.

## What we found
The result in plain language. Include the magnitude — "0.31 correlation" not "good signal."

## How it informs the code
Specific file:line references in `strategies/` that exist BECAUSE of this finding.
This is the field the code-scanner-with-recall skill greps before suggesting changes.

## When to retire
What would falsify this finding? If the regime breaks, if the lag closes, if the
correlation drops below X — what should make us mark this `status: retired`?
