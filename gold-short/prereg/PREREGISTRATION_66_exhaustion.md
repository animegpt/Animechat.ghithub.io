# Pre-registration #66: exhaustion fade short (EXHAUST)
Common protocol: PREREGISTRATION_COMMON_65_70.md. Written before results.

## Hypothesis
After gold stretches far above its 50-day average, the first down close starts a mean reversion.

## Reason (G1)
Crowded speculative longs (COT extremes) and late trend-chasers. Once momentum stalls, profit-taking and stop-outs pull price back toward value (SMA20/50).

## Rules
- z_d = (C_d - SMA50_d) / ATR14_d.
- Trigger at day d: max(z_{d-4..d}) >= Z AND C_d < C_{d-1}.
- SHORT at 15:31 NY on day d. Stop = max(H_{d-4..d}) + 0.5 * ATR14_d (intrabar).
- Exit at the first daily checkpoint (15:31 NY) where C < SMA20, or after 15 trading days, or at the stop.

## Variants (2)
- EXHAUST_Z3, EXHAUST_Z4.

## Neighbours for G4
- Z +/- 0.5; max hold 10 and 20 days; stop buffer 0.25 and 1.0 ATR; SMA50 -> SMA40 / SMA60.
