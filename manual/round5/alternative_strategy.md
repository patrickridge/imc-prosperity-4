# Manual Trading Challenge Strategy: “Extra! Extra! Read All About It!”

## 1. Challenge Setup

In this manual challenge, we are not placing intraday orders. We are choosing a portfolio that is held until the next day. The source of information is **Ashflow Alpha**, which contains several news stories about Ignith products. Each product has an underlying return anchor and return range chosen by IMC, but the final realised return is also influenced by the aggregate submissions from all participants.

This means the problem is not only about reading the news correctly. It is also about estimating what the rest of the competition will do.

The important grading mechanism is:

- IMC defines an anchor return and a possible return range for every product.
- Participant orders can move the realised return within that range.
- If most teams see a product as a strong buy, that product’s return can be pushed further upward.
- If most teams see a product as a strong short, that product’s return can be pushed further downward.
- Used budget is subtracted from final trade PnL.
- Unused budget does not earn anything, but it also avoids unnecessary fee drag.

So we should **not be blindly contrarian**. When a story is both fundamentally clear and likely obvious to the crowd, consensus can actually help us.

---

## 2. Core Strategy

Our strategy is:

> Size positions by **news impact × crowd obviousness × fee discipline**.

The best trades are the ones where:

1. The news has a clear positive or negative economic effect.
2. The interpretation is obvious enough that many other teams will likely trade in the same direction.
3. The expected edge is large enough to justify the nonlinear fee.

We therefore prefer clean, easy-to-read catalysts over subtle or ambiguous ones.

The aim is not to spend 100% of the budget. Because fees rise quickly with position size, it can be better to leave budget unused than to force weak trades.

---

## 3. Fee-Aware Position Sizing

The fee makes over-sizing expensive. A useful simplified model is:

```text
expected_profit = allocation × expected_return - allocation²
```

Under this simplified quadratic-cost model, the theoretical optimal allocation is:

```text
allocation = expected_return / 2
```

For example:

- If we expect a 20% return, the raw optimal allocation is about 10%.
- If we expect a 28% return, the raw optimal allocation is about 14%.

But manual news interpretation is noisy, so we apply a caution haircut.

Our practical sizing rule is:

```text
allocation ≈ expected_return / 2 × 0.75
```

This keeps us large enough in the strongest stories, but avoids burning too much budget on uncertain estimates.

---

## 4. Signal Buckets

We classify stories into expected move buckets:

| Story Strength | Rough Expected Move | Typical Allocation After Haircut |
|---|---:|---:|
| Weak | 3%–6% | 1%–2% |
| Medium | 8%–14% | 3%–5% |
| Strong | 15%–22% | 6%–9% |
| Very strong / obvious disaster | 25%–30% | 10%–12% |

This is not an exact formula. It is a framework. We then manually nudge sizes based on how obvious the trade is likely to be to the rest of the competition.

---

## 5. Product-by-Product Read

## Strongest Trades

### THERMALITE_CORE — Long

**Direction:** Long  
**Allocation:** +11%

This is one of the cleanest bullish stories. The quarterly forecast says active projected users rise from **1.42 million to 3.89 million** next quarter, with strong average activity time. That is a direct numeric catalyst and easy for the crowd to understand.

This is likely to attract broad buying from participants because the story is simple: demand is projected to grow sharply.

**Why it deserves a large long:**

- Clear numerical growth.
- Direct link to future demand.
- Very obvious positive news.
- Likely to be bought by many teams, creating positive crowd pressure.

---

### LAVA_CAKES — Short

**Direction:** Short  
**Allocation:** -11%

This is the clearest negative story. Health authorities found traces of actual lava, triggering a formal review. Production or official sales have been halted, vendors are returning stock, and civil lawsuits are already piling up.

This is not subtle. It is a direct consumer safety crisis.

**Why it deserves a large short:**

- Health review.
- Product halt.
- Lawsuits.
- Vendor returns.
- Extremely obvious bearish interpretation.
- Likely heavy crowd shorting, which can push returns lower within the allowed range.

---

### PYROFLEX_CELL — Short

**Direction:** Short  
**Allocation:** -7%

The Pyroflex Cell tax cut is being discontinued, effective tomorrow. The article states that removing the 50% tax cut effectively doubles the current levy. Industry groups warn this will disrupt upgrade cycles and slow new purchases.

This is a direct economic shock. It is less dramatic than Lava Cakes, but still very clean.

**Why it deserves a strong short:**

- Tax support removed.
- Effective levy doubles.
- Direct hit to consumer demand.
- Easy crowd interpretation.
- Strong fundamental and consensus alignment.

---

### SULFUR_LTD — Long

**Direction:** Long  
**Allocation:** +7%

Sulfur Ltd. is being added to Elemental Index 118. Index inclusion is usually bullish because index-tracking funds are expected to adjust their holdings.

However, the updated challenge text says the rebalance takes effect **later this cycle**, not necessarily immediately. That makes the signal bullish, but not maximum conviction.

**Why it deserves a long, but not the largest long:**

- Index inclusion is a clean positive catalyst.
- Funds tracking the index are expected to buy.
- Crowd will likely identify this as bullish.
- Timing is slightly delayed, reducing urgency compared with Thermalite.

---

## Medium Trades

### OBSIDIAN_CUTLERY — Short

**Direction:** Short  
**Allocation:** -5%

The manufacturing facility suspended production after completed blades cut through parts of the assembly line. The breach caused contamination concerns and temporary evacuation.

This is clearly negative, but the story is more operational than consumer-facing. It may not be as aggressively traded by the crowd as Lava Cakes.

**Reasoning:**

- Production halt is bad.
- Contamination concerns add risk.
- Could affect manufacturing capacity.
- Less emotionally obvious than health risks in Lava Cakes.

---

### SCORIA_PASTE — Long

**Direction:** Long  
**Allocation:** +4%

Lava D. Ray urges households to stockpile Scoria Paste and frames it as essential to residential repairs and infrastructure upkeep. The article also links Scoria Paste to household conditions.

This is bullish, but partly driven by an influencer-style recommendation rather than hard numbers. It is useful, but not as clean as Thermalite.

**Reasoning:**

- Stockpiling call can create demand.
- Product is described as central to daily maintenance.
- Possible crowd buying from the headline.
- Less reliable because it relies on public sentiment and influencer effect.

---

### ASHES_OF_THE_PHOENIX — Short

**Direction:** Short  
**Allocation:** -3.5%

A resurfaced video has caused public concern about the sourcing method for the product. This is a PR scandal and likely negative for demand.

However, the typo clarification says **Forever Feathers Ltd. is the same as Eternal Feathers Ltd.**, so the company-name confusion does not change the economics. The story remains bearish, but less direct than lawsuits, sales halts, or taxes.

**Reasoning:**

- Public outrage is bearish.
- Sourcing scandal damages brand perception.
- Less direct than a formal product halt or tax shock.
- Position should be smaller than Lava Cakes or Pyroflex.

---

## Weak / Small Trades

### VOLCANIC_INCENSE — Long

**Direction:** Long  
**Allocation:** +2%

Volcanic Incense has extended its rally after Whiff Nostralico publicly encouraged people to follow his lead and buy. This is momentum and social-signal driven.

It is bullish, but less fundamentally grounded.

**Reasoning:**

- Momentum signal.
- Public figure encouraging buying.
- Could benefit from crowd chasing.
- Weak fundamental basis, so keep small.

---

### LAVA_FOUNTAIN_PEN — Long

**Direction:** Long  
**Allocation:** +1%

The limited-edition Lava Fountain Pen launch drew large crowds and long lines. This is positive for hype and brand attention.

However, it may be a one-off launch rather than a durable demand shock.

**Reasoning:**

- Strong launch hype.
- Crowds waited over six hours.
- Positive sentiment from product release.
- Limited-edition nature makes it less scalable, so allocation remains small.

---

## 6. Final Allocation

| Product | Direction | Allocation |
|---|---:|---:|
| THERMALITE_CORE | Long | +11% |
| SULFUR_LTD | Long | +7% |
| SCORIA_PASTE | Long | +4% |
| VOLCANIC_INCENSE | Long | +2% |
| LAVA_FOUNTAIN_PEN | Long | +1% |
| LAVA_CAKES | Short | -11% |
| PYROFLEX_CELL | Short | -7% |
| OBSIDIAN_CUTLERY | Short | -5% |
| ASHES_OF_THE_PHOENIX | Short | -3.5% |

Total absolute budget used:

```text
11 + 7 + 4 + 2 + 1 + 11 + 7 + 5 + 3.5 = 51.5%
```

So the strategy uses about **51.5% of the available budget**.

We deliberately leave the rest unused because forcing the remaining budget into weaker trades would likely reduce net PnL after fees.

---

## 7. Why We Do Not Use 100% Budget

The challenge explicitly says unused budget expires worthless, which makes it tempting to spend everything. But used budget is subtracted through the fee structure, so weak trades can be worse than no trade.

The fee curve means each extra unit of size is more expensive than the previous one. Therefore, the correct approach is not “spend everything”; it is “spend only where expected return beats the marginal fee.”

This is why we use only about half the budget.

---

## 8. Main Risk

The main risk is that the crowd component can overwhelm our fundamental read.

For example:

- A story that looks bullish may already be too obvious and overbought.
- A subtle story may be ignored by most teams and fail to move.
- Some jokes or flavour text may be misread by the crowd.
- IMC’s hidden anchor/range may not match the apparent severity of the article.

To handle this, we avoid extreme concentration and apply a haircut to the theoretical optimal sizes.

---

## 9. Strategy Summary

Our best edge is to lean into the cleanest stories where both the fundamental interpretation and expected crowd reaction point in the same direction.

The highest-conviction trades are:

- **Long THERMALITE_CORE** because of the sharp projected user growth.
- **Short LAVA_CAKES** because of the health review, sales halt, lawsuits, and returns.
- **Short PYROFLEX_CELL** because the canceled tax cut directly worsens product economics.
- **Long SULFUR_LTD** because index inclusion should create fund demand, although the delayed timing means it should be smaller than Thermalite.

The overall portfolio is intentionally fee-aware, diversified across several clear news catalysts, and sized at roughly **51.5% budget usage** rather than forcing a full-budget allocation.
