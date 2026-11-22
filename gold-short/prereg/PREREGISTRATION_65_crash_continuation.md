# Pre-registration #65: crash continuation short (CRASH)
Common protocol: PREREGISTRATION_COMMON_65_70.md. Written before results.

## Hypothesis
After a large down day that closes near its low, gold keeps falling over the next 1-5 days.

## Reason (G1)
Forced selling clusters: COMEX margin calls, CTA/trend stop cascades and ETF outflows are autocorrelated after a shock.
Gold "takes the stairs up and the elevator down". The selling pressure is not finished when the day closes near its low.

## Rules
- r_d = ln(C_d / C_{d-1}) on daily bars. sigma20 = sample std of r over d-19..d-1 (excludes today).
- CLV_d = (C_d - L_d) / (H_d - L_d).
- Trigger at day d: r_d <= -k * sigma20 AND CLV_d <= 0.25.
- SHORT at 15:31 NY on day d. Stop = entry + 1.0 * ATR14_d (intrabar).
- Exit at 15:31 NY of trading day d+H, or at the stop.

## Variants (4)
- CRASH_k1.5_H1, CRASH_k1.5_H5, CRASH_k2.0_H1, CRASH_k2.0_H5.

## Neighbours for G4 (around each variant)
- k +/- 0.25; H in {H-1 (min 1), H+2}; stop 0.75 and 1.5 ATR; CLV threshold 0.15 / 0.35.
