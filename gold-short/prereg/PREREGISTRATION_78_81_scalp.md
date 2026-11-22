# Pre-registration #78-#81: SHORT scalping family on 1-minute bars. Written BEFORE any computation on this data.
Data: user-supplied `gold-data-cache.tar.gz` (sha256 prefix 12654831d0918eaa verified), Dukascopy XAUUSD 1-minute BID 2017-01..2026-10.
- The loader drops rows >= 2024-01-01 unless OPEN_VAULT=1.
- Disclosure: phase-1/2 hourly results were seen. No 1-minute result of any kind has been computed in this project yet.

## Periods (new family)
- Discovery: 2017-01-01 .. 2020-12-31.
- Confirmation: 2021-01-01 .. 2023-12-31.
- Vault: 2024-01-01 .. 2026-10-31. One opening, after an independent audit.
- At most 2 variants enter confirmation: the 2 qualifiers with the highest discovery day-clustered t under B.

## Costs (round trip, price-relative; P = fill price)
- **A** (Standard/Cent): spread 0.24 USD + 0.1 bp slippage per side.
- **B** (Raw/Zero): spread 0.03 USD + commission 0.07 USD/oz round trip + 0.1 bp slippage per side.
- **C**: B x 2.
- Each is computed at the historical fill price (primary), and also at a fixed P = 4000 (A4000, B4000, C4000; reported).
- **News exits:** if an EXIT falls in a glib news window (12:25-12:40, 13:25-13:40, 13:55-14:10, 14:55-15:10, 17:55-18:10, 18:55-19:10 UTC), the spread part of that side is x3.
- If Exness confirms a different Raw commission before results are computed, B and C are updated (this file amended); otherwise 0.07 stands.

## Execution (common to all variants)
- Signal on the close of minute t. Entry SHORT at the OPEN of minute t+1.
- Stop and target are checked intrabar from minute t+1 on, using minute HIGH (stop) and LOW (target).
  - If both are touched in the same minute, the stop wins.
  - Gap: a minute OPEN >= stop fills at the open. A target fills at the target price (never better).
- Time exit at the CLOSE of minute t+H.
- **No new entries:**
  - 20:45-23:15 UTC (daily roll / server 22:00-23:00, both DST cases).
  - Inside the news windows above.
  - Friday after 19:30 UTC.
- Any open trade is force-closed at the close of the 20:44 UTC minute.
- One position at a time per variant.
- **Volatility unit:** ATRm = Wilder ATR (alpha 1/60) of 1-minute true ranges. sigma1 = std of 1-minute log returns over the previous 1440 minutes.

## Variants (8; Holm over these 8)
### #78 EXH: short-term exhaustion
- **Reason:** a sharp 15-60 min spike is often liquidity-driven (stop runs, late chasers). The first break of short-term support marks exhaustion, and a small retrace follows.
- **Rules:**
  - z30 = ln(C_t / C_{t-30}) / (sigma1 x sqrt(30)).
  - Trigger: max(z30 over the last 10 minutes) >= Z, AND C_t < min(L_{t-3..t-1}) (first close below the prior 3-minute low).
  - Stop = max(H over the last 30 min) + 0.1 x ATRm. Target = entry - 1.0 x (stop - entry). H = 60 min.
  - After a trade, no new EXH entry until z30 has dropped below 1 again.
- **Variants:** EXH_Z3, EXH_Z4.

### #79 FAILHI: failed break of the high (buy trap)
- **Reason:** breakout buyers and short-stops cluster just above an obvious high. A quick return below it traps them and their exits push price down.
- **Rules:**
  - Level = (a) session high: highest high since 23:00 UTC, frozen at the moment of the break; requires >= 120 minutes of session. Or (b) the previous full session's high (23:00-20:45 UTC of the prior day).
  - Break: some minute in the last 15 had H > level.
  - Trigger: C_t < level, with the break having occurred within the last 15 minutes.
  - Stop = max H since the break + 0.1 x ATRm. Target = 1R. H = 60 min. First trigger per level per day only.
- **Variants:** FAILHI_SESS, FAILHI_PREVDAY.

### #80 DCOS: directional-change overshoot fade, short only
- **Reason:** after an up directional change, an overshoot of 2 theta is statistically extended (intrinsic-time scaling law), so a retrace is likelier than continuation. Previously failed on the Standard cost with close-based stops (#41) and with intrabar stops at theta 0.5% (#58). This tests the cheaper Raw cost at small theta, with intrabar stops.
- **Rules:**
  - Classic DC on minute closes with threshold theta. Up-DC is confirmed when C >= last extreme low x (1 + theta); DC price p_dc = that close.
  - Trigger: the first close with C >= p_dc x (1 + 2 theta) during that up-run.
  - Stop = entry x (1 + theta). Target = entry x (1 - theta). H = 120 min.
- **Variants:** DCOS_010 (theta 0.10%), DCOS_020 (theta 0.20%).

### #81 TRENDPB: short the 5-minute pullback inside an H1 uptrend
- **Reason (user idea):** inside a strong H1 uptrend, profit-taking creates brief, orderly 5-minute down-legs. Riding them short captures a small, momentum-driven move.
- **Rules:**
  - H1 Sonic uptrend at the last COMPLETED H1 bar: dragon mid > EMA89, both rising vs 5 bars ago.
  - 5-minute bars (completed): EMA8 crosses below EMA20 on that bar, AND C5 < EMA20.
  - Signal at the 5m bar's last minute. Stop = max H of the last 6 completed 5m bars. H = 90 min.
- **Variants:** TRENDPB_1R (target 1R), TRENDPB_2R (target 2R).

## Reported per variant and period
- Net bp/trade under A, B, C (and the @4000 versions).
- Day-clustered t: daily sums of trade returns, t over trading days with >= 1 trade.
- Win rate, mean holding minutes, trades per day.
- Random baseline: 500 sims; each real trade is matched by a random day in the same year at the SAME minute of day (eligible minutes only), with the same stop and target distances in ATRm units, same H, short, and the same execution rules.

## Pass rule
1. Discovery: net(B) > 0, day-t(B) >= 2, Holm-adjusted p < 0.05 (one-sided, from day-t), AND net(C) > 0.
2. Confirmation (at most 2 variants): net(B) > 0, day-t(B) >= 2, net(C) > 0.
3. **Gates:**
   - G2: C > 0 in both periods.
   - G4 neighbours: each numeric parameter +/-25% and the target 0.75R / 1.5R; >= 75% must have net(B) > 0 in both periods.
   - G5: bootstrap over days P(mean <= 0) < 5% on confirmation, and DSR >= 0.95 with N_trials = 86 + 8 = 94.
   - G6: random p < 0.05 in both periods.
   - G7: n >= 100.
4. Independent audit agent (look-ahead, fills, costs). Then a single vault opening; pass if vault net(B) > 0 and net(C) > 0.
