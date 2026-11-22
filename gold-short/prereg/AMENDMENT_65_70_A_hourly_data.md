# Amendment A to #65-#70 (written BEFORE any result; no data for these tests had been loaded yet)

## Why
Dukascopy rate-limits the 1-minute endpoint (fast HTTP 503 after a few files). Downloading ~7,100 daily minute files for 2004-2026 is not feasible in this session.
Hourly BID candles (monthly files) do download.

## Changes (the only changes; everything else in PREREGISTRATION_COMMON_65_70.md stands)
1. **Bars:** all simulation runs on Dukascopy XAUUSD 1-hour BID candles. Stops are checked INTRABAR on every hourly HIGH after the entry bar. If the bar OPEN is already >= stop, fill at the OPEN (gap); else fill at the stop.
   - Every rule in #65-#70 is short-only with a single stop and no profit target, so the intrabar path only matters for gaps that happen inside an hour.
   - Never checked on closes.
2. **Clock:** trading day d = hourly bars starting in [14:00 NY of d-1, 14:00 NY of d), so the daily close is at 14:00 NY.
   - Days with < 15 hourly bars are dropped.
   - Execution = close of the bar starting 14:00 NY (i.e. 15:00 NY), a one-bar lag after the decision. Daily-checkpoint exits use the same bar.
3. **#68 FIX:** short at the close of the 13:00 London bar (= 14:00 London), cover at the close of the 14:00 London bar (= 15:00 London, the fix time) instead of 15:05.
   - Neighbours: entry 13:00 London, exit 16:00 London, Tue-Thu only.
4. **Costs:** the cost multiplier m(t) is evaluated at the bar CLOSE time (fill time).
5. **Minute verification:** if any variant survives discovery and confirmation, its confirmation trades are re-simulated on 1-minute data, downloaded only for those trade windows, before the vault. A material difference (sign change or t < 2) = fail.
