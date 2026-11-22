# Common protocol for pre-registrations #65-#70 (SHORT-only gold, XAUUSD)
Written 2026-11-22 BEFORE any data for these tests was loaded or any result was computed.
(The minute data was still downloading when this file was committed.)

## Data
- Dukascopy XAUUSD 1-minute BID candles, 2004-01 .. 2026-10 (UTC timestamps), downloaded fresh by `code/dl_all.py`.
- FRED daily series in `raw/fred` (DFII10, DTWEXBGS, VIXCLS).
- The loader physically drops every row >= 2024-01-01 unless the environment variable `OPEN_VAULT=1` is set.
  It will be set exactly once, only for candidates that passed discovery + confirmation + gates 1,2,4,5,6,7 and an independent audit.

## Periods (by ENTRY time)
- Discovery: 2004-01-01 .. 2016-12-31 (trades may finish in early 2017).
- Confirmation: 2017-01-01 .. 2023-12-31 (open trades are force-closed on the last bar before 2024-01-01).
- Sealed vault: 2024-01-01 .. 2026-10-31.

## Clock
- Trading day d ends at 15:30 New York time (DST-aware). Daily bar d = minutes in (15:30 NY of d-1, 15:30 NY of d].
  Days with < 600 one-minute bars are dropped (holidays / partial sessions).
- Daily decisions use only daily bars up to and including d. Execution: SHORT at the CLOSE of the minute that
  starts 15:31 NY (one-minute lag after the decision). Daily-checkpoint exits use the same minute.
- ATR14 (daily) = Wilder ATR on the daily bars. SMA/EMA on daily closes.

## Costs (price-relative, per side)
- side cost = 0.5 * 0.24 / P * m(t) + 0.1 bp, where P is the fill price and m(t) = glib.cost_mult (x3 in US-news minutes, x5 in the 20:55-00:15 UTC roll window).
- Round trip = entry side + exit side. Short swap = 0 (Exness XAUUSDc). "Costs x2" doubles both spread and slippage.

## Stops
- Checked intrabar on every minute after the entry minute, on the minute HIGH. If the minute OPEN is already >= stop, fill at the OPEN (gap); else fill at the stop.
- Never checked on closes.

## Statistics
- One position at a time per variant (no overlap). Per-trade net return in bp; t = mean / (sd/sqrt(n)).
- Random baseline: 500 simulations; each draws the same number of entries per calendar year at random 15:31-NY decision minutes, all SHORT, with the identical exit rule (same holding cap, same stop distance in ATR units as the matched real trade). p_rand = share of simulations with mean >= real mean.
- Holm over ALL K=11 pre-declared variants of #65-#70, one-sided p from the discovery t (Student t, n-1 df).

## Pass rule (fixed)
1. Discovery: net mean > 0, t >= 2, Holm-adjusted p < 0.05.
2. Confirmation (same rules, no re-tuning): net mean > 0, t >= 2.
3. Then the 7 gates:
   - G1 reason: written below per test (before results).
   - G2 costs x2: net mean > 0 in discovery AND confirmation.
   - G3 out of sample: confirmation pass (2) and, at the single vault opening, vault net mean > 0.
   - G4 robustness: >= 75% of the pre-declared neighbour settings have net mean > 0 in discovery AND in confirmation.
   - G5 luck: bootstrap (10,000) of confirmation trades P(mean<=0) < 5%; Deflated Sharpe (Bailey & Lopez de Prado) >= 0.95 on discovery+confirmation trades with N_trials = 64 + 11 = 75 and trial-Sharpe variance from the 11 discovery Sharpes.
   - G6 random: p_rand < 0.05 in discovery AND confirmation.
   - G7 sample: >= 100 trades in discovery + confirmation.
4. Independent audit agent (look-ahead + costs) before the vault.

## Portfolio check (reported, not a pass criterion)
Daily P&L correlation with (a) plain Sonic R H1 (both sides, unsized) and (b) plain Overnight 16:00-20:00 NY Mon-Thu, and the change in Sharpe / max drawdown of an equal-risk portfolio, in discovery and confirmation separately.
