# Pre-registration #71-#74 (round 2, SHORT-only). Written BEFORE computing any of these.
Protocol: PREREGISTRATION_COMMON_65_70.md plus AMENDMENT_65_70_A_hourly_data.md (hourly bars, intrabar stops, day close 14:00 NY, entry at the 15:00 NY bar close).

## Disclosure
Round-1 DISCOVERY results (#65-#70, all failed) were seen before writing this. Confirmation (2017-2023) and the vault have NOT been looked at by any test in this project.
- Holm family for round 2 = the K2 = 5 variants below.
- Deflated Sharpe N_trials = 64 + 11 + 5 = 80.
Same pass rule and the same 7 gates as round 1.

## #71 DONCH: short-only Donchian breakdown (trend following on the down side)
- **Reason:** gold's bear phases (2008, 2011-15, 2022) are slow de-allocations that persist for months. A long-horizon breakdown captures them and goes flat in uptrends. It can also hedge the long book.
- **Rules:** at day d, C_d < min(L_{d-N..d-1}) -> SHORT at the next execution. Stop = entry + 2*ATR14 (intrabar). Exit at the checkpoint of the first day with C > max(H over the previous X days), or at the stop.
- **Variants:** DONCH_55_20 (N=55, X=20) and DONCH_20_10 (N=20, X=10).
- **Neighbours:** N +/- 25%, X +/- 50%, stop 1.5 / 3 ATR.

## #72 TRAP: failed upside breakout (bull trap)
- **Reason:** breakout buyers and short-stop triggers are trapped when price falls back inside the range. Their stop-outs fuel a quick drop.
- **Rules:** H_{d-1} > max(H_{d-21..d-2}) (yesterday broke the prior 20-day high), and today C_d < max(H_{d-21..d-2}) and CLV_d < 0.5 -> SHORT. Stop = max(H_{d-1}, H_d) + 0.25*ATR14. Exit after 3 trading days or at the stop.
- **Variants:** TRAP_20_H3.
- **Neighbours:** range 10 / 40 days, hold 1 / 5, stop buffer 0 / 0.5 ATR.

## #73 FAIR: gold rich vs real yields (valuation reversion)
- **Reason:** gold's fair value moves with real yields. Large positive deviations get arbitraged back by macro allocators.
- **Rules:**
  - Rolling 750-day OLS of ln(C) on DFII10 (DFII10 as known with a 2-business-day lag), estimated on days d-750..d-1. Residual at d.
  - z = residual / std(residuals of the fit window).
  - Trigger z >= 2 -> SHORT. Exit at the first checkpoint with z < 0.5, after 40 days, or at the stop entry + 4*ATR14.
- **Variants:** FAIR_750_z2.
- **Neighbours:** window 500 / 1000, entry z 1.5 / 2.5, max hold 20 / 60.

## #74 QUIETDN: quiet downtrend
- **Reason:** gold shows an inverted leverage effect (volatility rises more on up-moves; Baur 2012). A falling market with LOW volatility means no safe-haven demand and a persistent bleed (2013-15 style).
- **Rules:**
  - Regime ON when C_d < SMA100_d, SMA100_d < SMA100_{d-20}, and vol20_d (std of 20 daily log returns) < median(vol20 over d-249..d).
  - SHORT on ON days. Exit at the first OFF checkpoint or after 20 days (re-enter next day if still ON), or at the stop entry + 3*ATR14.
- **Variants:** QUIETDN_100.
- **Neighbours:** SMA 50 / 150, vol window 10 / 40, without the vol condition.
