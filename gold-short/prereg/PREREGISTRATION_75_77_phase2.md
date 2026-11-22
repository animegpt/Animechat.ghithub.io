# Pre-registration #75-#77 (phase 2). Written BEFORE computing anything for these tests.
Base protocol: PREREGISTRATION_COMMON_65_70.md + AMENDMENT_65_70_A_hourly_data.md (hourly Dukascopy BID bars, intrabar stops, fill at bar close, vault physically excluded unless OPEN_VAULT=1).

## Disclosure (what was already seen)
- Round 1 (#68) DISCOVERY of the 14:00->15:00 London short: gross +2.07 bp, t 3.05, n 3379. That is what motivates #75.
- Rounds 1-2 discovery results of #65-#74.
- Nothing from 2017-2023 or the vault has been looked at by any short test.

## Confirmation gatekeeping (user rule: at most 2 ideas enter 2017-2023)
- Slot 1 is reserved for #75 (its best discovery variant, if it qualifies).
- Slot 2 goes to whichever of #76 / #77 qualifies in discovery with the larger margin over its pass line.
  - #76 margin = discovery t minus 2.
  - #77 margin = percentage drawdown reduction minus 25, or the Sharpe gain in hundredths.
  - If neither qualifies, slot 2 stays unused.
- Everything else stays out of confirmation.

## Trial count
- Deflated Sharpe N_trials = 80 (all previous tests) + 3 (#75) + 1 (#76) + 2 (#77) = 86.

## #75 PMFIX: short into the London PM fix with explicit cost scenarios
- **Fix time:** 15:00 London throughout 2004-2026. This covers the London Gold Fixing PM until 19 Mar 2015, and the LBMA Gold Price PM electronic auction (ICE) from 20 Mar 2015, also 15:00 London. The time is taken in Europe/London local time with DST.
- **Variants (3):** every London business day Mon-Fri, no stop. Entry/exit = hourly bar closes, which equal the exact clock-time prices for a no-stop rule.
  - V1 `E14_X15`: short at 14:00 London, cover at 15:00 (into the fix).
  - V2 `E13_X15`: short at 13:00, cover at 15:00 (two hours into the fix).
  - V3 `E14_X16`: short at 14:00, cover at 16:00 (through the fix and its aftermath).
  - No day-of-week variant: there is no a-priori reason.
- **Cost scenarios (round trip):**
  - (a) historical: 2 x [0.5 x 0.24/P x m(t) + 0.1 bp], with glib news/roll multipliers m(t) at the fill time.
  - (b) today fixed: 0.24/4000 + 0.2 bp = 0.80 bp per trade (no multipliers), as specified by the user.
  - (c) today x 2: 1.60 bp.
  - Also reported, not a criterion: (b') = (b) with the news multiplier at the fill bar. The 15:00 London exit usually equals 10:00 New York, when US data is released.
- **Discovery (2004-2016) qualification:**
  - Holm over the 3 variants on the one-sided t under (b): adjusted p < 0.05, net > 0.
  - Among qualifiers, the single variant with the highest t under (b) goes to confirmation.
- **Confirmation (2017-2023), one variant only:** net > 0 and t >= 2 under (b), AND net > 0 under (c).
- **7 gates before the vault:**
  - G1 reason: below.
  - G2 = net > 0 under (c) in discovery and confirmation.
  - G3 = confirmation pass, then vault net > 0 under (b).
  - G4 = neighbours (entry +/-1 h around the chosen window, keeping entry < exit; exit +/-1 h; Tue-Thu only; Mon+Fri only): >= 75% net > 0 under (b) in discovery and confirmation.
  - G5 = bootstrap P(mean <= 0) < 5% on confirmation, and DSR >= 0.95 with N = 86.
  - G6 = random baseline: same number of trades per year, random London business day, random entry hour drawn from all hours EXCEPT 12:00-16:00 London, same holding hours, short. p < 0.05 in discovery and confirmation.
  - G7 n >= 100.
  - Then an independent audit agent. Then one vault opening.
- **Reason (G1):** documented pre-fix price pressure (Caminschi & Heaney 2014; Abrantes-Metz & Metz 2014). Dealers pre-hedge net client flows they will fill at the fix, and bullion banks' net selling into the benchmark. Physical sellers (miners, ETF redemptions) use the PM price as their sale benchmark.
- **Descriptive extra (reported, never used for the decision):** split by the DST-mismatch weeks, when 15:00 London = 11:00 New York, to separate the fix from the 10:00 New York data release.

## #76 SHORTAI: walk-forward logistic short model on hourly bars
- **Decision points:** every hourly bar close Mon-Thu, plus Friday before 12:00 NY (no weekend holds).
- **Label:** 1 if C(t+8h) < C(t) x (1 - c_a(t)), where c_a = round-trip historical cost (a) at t. Else 0.
- **Trade:** SHORT at the close of t, cover at the close of t+8 bars, no stop. One position at a time.
- **Features (22, all causal):**
  - Log returns over 1, 2, 4, 8, 24, 72, 120 h.
  - Realized vol 24 h and 120 h, and their ratio.
  - (C - EMA20), (C - EMA50), (C - EMA200) on H1, divided by ATR14 H1.
  - RSI14 H1.
  - Position in the 24 h range.
  - Distance of C from the last completed daily SMA200, in daily ATR.
  - Hour of day (NY) sin/cos, weekday sin/cos.
  - 5-business-day change of DFII10 and DTWEXBGS (2-business-day publication lag).
  - VIX level and its 5-day log change (1-business-day lag).
- **Model:** sklearn StandardScaler + LogisticRegression(C=0.1, L2, max_iter=2000). No tuning.
- **Data starts 2006-02** (DTWEXBGS).
- **Discovery walk-forward:** for each year Y = 2009..2016, train on 2006-02 .. Y-1 and predict year Y. Threshold = 85th percentile of that fold's in-sample training probabilities (top 15%). Enter when p >= threshold.
- **Confirmation:** one model trained on 2006-02 .. 2016-12 with its own 85th-percentile threshold, frozen and applied to 2017-2023. Never retrained, never re-thresholded.
- **Discovery qualification:** net > 0 under (a), t >= 2, and beats random p < 0.05. The random baseline uses the same number of trades per year, the SAME hour-of-day distribution, random days, 8 h hold, short.
  - Also reported: net under (b).
- **Reason (G1):** combine weak short-horizon conditional drifts (vol regime, extension, macro) that each fail alone. The Overnight AI precedent shows a filtered intraday window can survive where the unfiltered one does not.

## #77 HEDGE: conditional short as portfolio insurance
- **Portfolio:**
  - Sonic R H1 plain (both sides, unsized): each trade risks 0.3% of equity, so trade P&L = 0.3% x R.
  - Plain Overnight long 16:00->20:00 NY Mon-Thu at 2x notional.
    - Approximation: the Overnight AI filter cannot be reproduced from the archive (no saved trade list or model inputs), so every night is taken. This is disclosed.
  - Both use cost scenario (a).
- **Hedge:** short gold at 1.0x equity notional while the condition is ON. Checked at the daily checkpoint (15:00 NY bar close, the common clock); enter/exit at that close; cost (a); no stop.
  - V1 `STREAK3`: the last 3 CLOSED Sonic trades were all losers AND the last completed daily close < daily SMA200.
  - V2 `DD5R`: Sonic's closed-trade equity is >= 5R below its running peak AND the daily close < SMA200.
- **Metrics:** daily portfolio returns, summed (no compounding), Sharpe (252) and max drawdown, with vs without the hedge.
- **Discovery qualification (2004-2016):** (Sharpe improves OR max DD falls >= 25%) AND total profit falls by no more than 20%.
- **Confirmation (only if it wins slot 2):** the same criterion in 2017-2023. Plus the vault at the end if it passes, with the audit first.
- **Reason (G1):** Sonic's losing streaks cluster in choppy or bearish regimes. A small short on during exactly those regimes, below SMA200, pays when longs bleed, and costs little because it is OFF in bull markets.
