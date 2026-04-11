---
name: p3-reference-lookup
description: Use when the user mentions a new IMC Prosperity product, mechanic, or round (e.g. RAINFOREST_RESIN, KELP, SQUID_INK, basket arb, options, conversion, foreign exchange) and is about to design or implement a strategy for it. Trigger BEFORE writing any new strategy code, BEFORE proposing a fair value formula, and BEFORE inventing position limits — top P3 teams already solved most of these and the writeups live in docs/reference/.
---

# P3 Reference Lookup

## Overview

The IMC Prosperity competition reuses products and mechanics across years. The user's `docs/reference/` directory contains comprehensive writeups from top P2 and P3 teams covering fair values, strategies, position limits, and pitfalls per product. **Reinventing what is already in those files is the single biggest waste of effort in the comp.** This skill enforces "look it up first."

## When to Use

Use BEFORE any of these:
- Designing a strategy for a named product
- Proposing a fair value formula for a product
- Picking a position limit
- Implementing a new mechanic (basket arbitrage, options, conversions, FX)
- Saying "this product behaves like X"

Use AT THE START of every new round, to scan what is already known.

## Iron Rule

**Grep `docs/reference/` before writing any new product logic. No exceptions.**

If `prosperity-3-solutions.md` or `prosperity-2-solutions.md` mentions the product, that content is the starting point. Do not propose alternatives without naming what the reference says first.

## Workflow

1. **Identify the product or mechanic name** from the user's request.
2. **Grep `docs/reference/` for that exact name** (case-insensitive). Try variants: "RAINFOREST_RESIN", "resin", "rainforest".
3. **Read the matched section in full.** Note: fair value, position limit, recommended strategy, common pitfalls.
4. **Cross-check `docs/reference/FrankfurtHedgehogs_polished.py`** if the product appeared in P3 — this is a top-team reference implementation.
5. **State to the user what the reference says** before proposing anything new. Quote the relevant lines.
6. **Only after the reference is on the table** discuss what to keep, what to adapt, and what (if anything) is different in P4.

## What to Look Up Per Product

| Question | Where it lives |
|---|---|
| Fair value formula | `prosperity-3-solutions.md` (per-product sections) |
| Position limit | Same |
| Known winning strategy | Same, plus `FrankfurtHedgehogs_polished.py` |
| Pitfalls / regime breaks | `prosperity-3-hedgehogs.md` |
| Earlier-year context | `prosperity-2-solutions.md` |
| Top team repos | `list_of_repos.md` |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Propose a fair-value formula without grepping | Stop, grep the product name first |
| "Let's analyze the data and figure it out from scratch" | Only after confirming the reference has nothing — most products are already solved |
| Use the reference's P3 position limit blindly in P4 | Limits sometimes change between years; verify against the P4 wiki via Notion MCP |
| Skip `FrankfurtHedgehogs_polished.py` | It's a working implementation — read it before writing your own |
| Quote the reference vaguely ("I think P3 had something like…") | Quote the exact line numbers or section headings |

## What This Skill Does NOT Do

- Does not give you the answer for P4-specific products (those need the P4 wiki via Notion MCP)
- Does not replace backtesting — references tell you what to try, backtests tell you if it still works
- Does not override `docs/strategy-principles.md` — even if a reference says "do X", explain why the edge exists in market behavior before adopting it

## Example

User: "I want to start trading SQUID_INK in round 1. How should I think about it?"

Wrong: "SQUID_INK is volatile — let me design a momentum strategy."

Right:
1. Grep `docs/reference/prosperity-3-solutions.md` for SQUID_INK.
2. Report what P3 teams found: position limit, regime, what worked, what didn't.
3. Then discuss what to carry forward to P4 vs. what to verify against new data.

If grep returns nothing, say "No P3 reference for this product — falling back to first-principles design" and only then start fresh.
