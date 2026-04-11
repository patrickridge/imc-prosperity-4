# Discord Message Templates


## IMC Prosperity — products & mechanics

1. Your position limit is a wall. If you're already at the cap the order just gets clamped and you're suddenly not in the trade you thought you were in. Worth a check before every send.

2. The book you see is pre-trade state for the tick. You're not the only bot reading it, so your passive fills in backtest are optimistic vs what you'll actually get.

3. Whatever formula you use for fair value (mid, vwap, microprice, whatever), it's a guess. Run it across every day you have before trusting it.

4. Don't share parameters across products. What works on a chill product can get eaten alive by a noisy one. Retune from scratch each time.

5. If a product is stable you can quote tight and be patient. If it's noisy the priority flips: risk first, and edge is whatever's left after you're sure you won't blow up.

6. A trade printing outside the current bid/ask usually means someone smashed a level. Useful tell about who's impatient.

7. Baskets trade near sum of components and the gap is where the edge lives. Most of that gap disappears into inventory risk and the cost of unwinding both legs, though.

8. Conversions have a fee. Always price the fee against the spread you're trying to capture before routing through one.

9. Options are only as good as your vol estimate. The formula isn't the hard part.

10. Triangular currency arb: if A to B to C back to A doesn't close to 1, there's edge somewhere. There's usually also a reason it stays open and finding that reason is the actual work.

11. Round 0 pnl is not round 1 pnl. New bots, new products, sometimes new behavior. Treat every round as a fresh validation problem.

12. Read the wiki page for the round before you write any code. Missing a mechanic is how a strategy silently stops working without throwing an error.

13. Round writeups hide stuff. Read them twice. The second read catches what the first read skimmed past.

14. Limits are per-product, not portfolio-wide. Long one thing and short another doesn't net out in the check.

15. Your compute budget per tick is small. Blow it and you lose orders to timeout, which never shows up as an obvious error on the PnL line.

16. Print everything while developing. Fair value, position, chosen orders, every tick. The visualizer gets a lot more useful when the context is printed right next to the trades.

17. Jmerle's visualizer beats staring at a PnL number. You can see when you're losing, and that almost always points at why.

18. Crushing day -2 and flatlining day -1 means you overfit to day -2. Test on every day you have before getting excited.

19. If it only works on one day it isn't a strategy. Bar is positive across all your test days, not just the best one.

20. Round 0 is a sandbox. Don't fall in love with something that only works on tutorial data.

21. Passive fills are usually bad fills. The order filled because the mid just moved against you, not because someone blessed you. Price quotes assuming this.

22. Inventory skew helps you flatten but it also telegraphs your position. Double-edged tool, use it knowing both edges exist.

23. A quote you leave standing is a promise. If the market moves and you don't update, you own that price. Cancel-replace or accept the risk, but don't forget it's there.

24. The obvious mean-reversion trade on a noisy product usually isn't free. If it were, someone's bot would already be on it and your fill rate would reflect that.

25. Change one thing at a time. Adding a signal and retuning a knob and swapping products in the same run tells you nothing about which change did what.

---

## General quant & market-making wisdom

26. Fair value is where you'd be fine buying or selling. If you can't say yours in a sentence you don't actually have one.

27. Market makers get paid the spread. Takers pay it. Know which side you're on any given moment, and why.

28. Inventory is risk. Every unit you hold is a bet that the price moves in your favor before you can unwind it.

29. Too tight and you get picked off. Too wide and nothing trades. The sweet spot's usually narrower than beginners think.

30. Backtests tell you what definitely won't work. They can't tell you what will.

31. Overfitting is when the strategy learned noise instead of signal. You can often spot it by nudging a parameter. If PnL collapses on a small shift, you fit noise.

32. Pick stable parameter regions over peak PnL. A knob earning 95% of max across a range is much safer than one earning 100% at a single lucky setting.

33. Walk-forward. Train on early days, test on later ones. If the PnL only lives inside the training window, it isn't real.

34. In-sample PnL is a promise you made to yourself. Out-of-sample is the one the market makes to you.

35. Mean reversion works until the mean moves. Momentum works until it stops. Have a plan for the flip, or at least know what the flip looks like.

36. Before adding a signal, say why it should predict the next move. One sentence. If you can't produce that sentence you're fitting noise.

37. Simple strategies you fully understand beat clever ones you don't. When things get weird the simple one debugs in 5 minutes.

38. Size with confidence. Strong signal, bigger trade. Weak signal, smaller. No signal, don't trade.

39. Risk-adjust your PnL. Same returns with less volatility is strictly better, and it's not even close.

40. Every edge should survive a skeptic. "What if this is just the fee structure?" "What if this is just one day's noise?" If it survives, test harder anyway.

41. Strategies that depend on one big trade a day are fragile. Many small trades is robust. Both can be profitable but only one lets you sleep.

42. Know your worst single-trade loss before running live. If the number makes you flinch, size down.

43. A backtest assumes you trade observed prices at any size. Real fills are smaller, slower, worse. Build in slack.

44. Orderbook imbalance is a hint, not a strategy. Use it to tilt decisions you already made, not to make new ones from scratch.

45. Slippage adds up fast. One tick per trade across ten thousand trades isn't rounding. It's most of your PnL.

46. Crossing the spread is expensive. Only cross when the expected move clearly covers the half-spread, and be honest about "clearly."

47. Quoting earns the spread but costs you adverse selection. Those roughly cancel out. What's left after they cancel is your real edge.

48. Markets being efficient is a useful null hypothesis. Your job is to produce evidence you found something unpriced. Keep your bar for that evidence high.

49. Don't chase losses with bigger size. Doubling the limit on yesterday's losing strategy just loses twice as much.

50. Sometimes the best move is to stop. "I don't know what's happening right now" is a position, and it's often the most profitable one.
