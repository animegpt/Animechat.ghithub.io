# Pre-registration #88: open search for an M1 trend strategy on gold (tail-of-entry-candle stop)
Written BEFORE any number of this search was computed.
- **Data:** Dukascopy XAUUSD 1-minute BID 2017-2023 (the loader drops >= 2024 unless OPEN_VAULT=1).
- **Periods:** discovery 2017-2020 (the search sees ONLY this), confirmation 2021-2023, vault 2024-2026.
- **Seen before:** tests #1-#87 (handoff, test_log). Not repeated as-is: DC fade (#22-#40, #58, #80, #84), ZA-VWAP (#85), ORB grid (#20), streaks (#50), squeeze (#44).
  - Here they may only appear as one condition among others inside random combinations.

## 1. Execution and costs (identical for every rule)
- Signal on the close of minute t. Entry at the OPEN of minute t+1 (market).
- **Stop (base) = "tail of the signal candle":**
  - Long: low_t - 0.1 x ATRm. Short: high_t + 0.1 x ATRm.
  - Minimum distance from the entry = 3 x the round-trip cost B in price (0.10 USD + 0.2 bp x P); if the tail is closer, the stop is pushed out to that minimum.
  - If the entry open is already beyond the stop: no trade.
  - ATRm = Wilder ATR(60) of 1-minute true ranges.
- Stop/target are checked intrabar from minute t+1. Stop first if both are touched in one minute. A gap beyond the stop fills at the minute open. A target fills at the target price.
- **Exit templates (part of the search space, 6):**
  - E1: target 1R, max 60 min.
  - E2: target 2R, max 120 min.
  - E3: target 3R, max 240 min.
  - E4: chandelier trail (exit on a close below highest-close-since-entry - 2 ATRm for longs; mirror for shorts), max 240 min.
  - E5: time 30 min.
  - E6: time 120 min.
  - All templates also force-close at the 20:44 UTC minute close.
- **No entries:** 20:45-23:15 UTC, glib news windows (12:25-12:40, 13:25-13:40, 13:55-14:10, 14:55-15:10, 17:55-18:10, 18:55-19:10 UTC), Friday after 19:30 UTC. One position at a time per rule.
- **Costs per side (P = fill price):**
  - A: 0.12 USD.
  - B: 0.015 USD + 0.035 USD commission.
  - C = 2 x B.
  - Plus 0.1 bp slippage per side (doubled in C). The exit spread is x3 in news windows.

## 2. Search space
- **Condition library (~120 binary conditions, each in a long orientation with a mirrored short version; non-directional ones apply to both sides):**
  - Moving averages: EMA/SMA/HMA/KAMA, several lengths. Price above/below, fast/slow crosses, slopes.
  - Session VWAP and weekly anchored VWAP.
  - Donchian breakouts (several lengths).
  - Bollinger and Keltner bands (breakout and re-entry).
  - ATR regime: ATR60/ATR1440 high/low.
  - RSI levels.
  - MACD histogram sign and cross.
  - Stochastic.
  - ADX > 25.
  - Supertrend(10,3).
  - Ichimoku (close vs cloud, tenkan/kijun).
  - Heikin-Ashi run of N same-colour candles.
  - DC/intrinsic time: run direction and overshoot k x theta, theta in {0.1, 0.2, 0.5}%.
  - Tick-volume z-score.
  - Time-of-session buckets (Asia/London/NY open/NY afternoon).
  - Distance to / break of day, previous-day and week high/low.
  - H1 and H4 Sonic trend.
  - Candle shape: strong body closing near the extreme; range > 2 ATRm.
- **Entry event:** the rising edge (false -> true) of the rule mask.
- **Random rule generator:**
  - Side in {long, short}.
  - 1-4 conditions combined as AND, or as A AND (B OR C) with probability 0.25.
  - Exit template uniform over E1-E6.
- **Genetic programming (in the spirit of gp28.py):**
  - Random expression trees (depth <= 4) over {close, open, high, low, tick volume, typical price, 1-minute return} with operators {+, -, x, protected /, EMA(n), STD(n), DIFF(n), rolling MAX/MIN(n), ABS, SIGN}, n in {5, 15, 60, 240}.
  - Output z-scored over a rolling 1440 minutes. Long on an upward cross of +k, short on a downward cross of -k, k in {1, 2}. Exit template evolved too.
  - Population 60, 25 generations, tournament selection, subtree crossover and mutation.
- **Budget per search run:** 47,000 random rules + 1,500 GP evaluations = **48,500 evaluated rules**. Wall clock cap: 4 hours for everything; if it is reached, stop and report what finished.
- **Minimum trades:** a rule with < 300 discovery trades scores 0.

## 3. Fitness and winner selection
- **Fitness:** day-clustered t of net B (daily sums of trade returns, trading day starting 18:00 New York) over discovery 2017-2020.
- **Eligible winners:** net B > 0 and net C > 0 in discovery.
- **Top-5 list:** distinct rules (Jaccard of entry minutes < 0.5 with every better-ranked rule).

## 4. Luck threshold (the key rule)
- The ENTIRE search (same generator, same seeds scheme, same GP, same budget) is re-run **16 times on random-direction targets**.
  - Each trading day independently, with probability 0.5, swaps the long and short outcome series (P&L and exit times) for every minute of that day.
  - This destroys any directional skill and keeps timing, volatility and cost structure.
- The best fitness of each null run is recorded. **THRESHOLD = 95th percentile of the 16 null maxima.**
- A real discovery must have fitness > THRESHOLD.

## 5. Confirmation and gates (only for rules above THRESHOLD; at most the top 3)
- **Confirmation 2021-2023:** net B > 0, day-t >= 2, Holm p < 0.05 over the candidates sent, net C > 0.
- **Mandatory comparisons:**
  - (a) Random entries at the same minute-of-day/month with the same stop and exit: p < 0.05.
  - (b) A placebo with the same rule but its exotic indicator replaced by an ordinary EMA(20) cross: the winner must beat it.
  - (c) Tail stop vs a wide 3 x ATRm stop, reported.
- **Deflated Sharpe:** N_trials = 97 + 48,500 (+ null runs not counted as trials), trial-Sharpe variance from the real run.
- Then an independent audit agent, then one vault opening.
- **Deliverables if something passes:** simple Arabic description of the rule, period results, correlation with Sonic/Overnight, Pine and MQL5 (Magic 770301).
- **If nothing beats THRESHOLD:** report the top 5, their distance to THRESHOLD, and what was learned.

## Amendment A (before the real run; only a 1,000-rule timing test on a NULL target had been run)
- **The flaw:** the null "best fitness" could be undefined (-99) if a null run finds no rule with net B > 0 and net C > 0. That would make any eligible real rule "beat" the threshold.
- **The fix:** THRESHOLD = 95th percentile of the 16 null maxima of the RAW day-t of net B over ALL evaluated rules (no eligibility filter).
  - This is at least as high as the eligible-only maximum, so it is conservative.
  - The real winner must still be eligible (B > 0, C > 0) AND have t > THRESHOLD.
