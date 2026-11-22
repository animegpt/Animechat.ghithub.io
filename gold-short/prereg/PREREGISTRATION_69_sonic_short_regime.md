# Pre-registration #69: Sonic R shorts only in a daily downtrend (SONICDN)
Common protocol: PREREGISTRATION_COMMON_65_70.md. Written before results.

## Hypothesis
Sonic R shorts are ~0 overall (#56) because most of them fight gold's secular uptrend. Taken only when the daily trend is down, they are profitable.

## Reason (G1)
Trading with the primary trend: in daily downtrends (2008, 2013-2015, 2022), H1 pullback-and-break shorts ride institutional de-allocation. In uptrends they get squeezed.

## Rules
- Sonic R H1 short exactly as in the live system: dragon = EMA34 of H/L/C, trend = EMA89.
  - Setup: dragon-mid < EMA89 and both falling vs 5 bars ago; high >= EMA34-close within the last 5 bars; the bar closes below EMA34-low after the previous close was >= the previous EMA34-low.
  - SHORT at that H1 close. Stop = max(highest high of 10 bars, close + 0.5 ATR14_H1), intrabar on minutes.
  - Exit at the first H1 close above EMA34-high, or after 240 H1 bars.
- Filter: the last COMPLETED daily bar (15:30 NY) has C < SMA200 AND SMA200 < SMA200 of 20 trading days earlier.
- Costs and execution from the common protocol. The entry is the H1 bar close, i.e. the minute close at the hour.

## Variants (1)
- SONICDN_200_20.

## Neighbours for G4
- SMA150 / SMA250; slope window 10 / 40; filter "C < SMA200" only.
