# Pre-registration #70: risk-off liquidation short (VIXSPIKE)
Common protocol: PREREGISTRATION_COMMON_65_70.md. Written before results.

## Hypothesis
When equity volatility spikes, gold is sold over the next days as liquid collateral ("dash for cash").

## Reason (G1)
Margin calls and deleveraging (Oct 2008, Aug-Sep 2011, Mar 2020). Funds sell what they can sell, and gold is liquid and in profit.

## Rules
- FRED VIXCLS, lagged one trading day (at day d use the VIX close of d-1).
- Trigger: VIX_{d-1} / min(VIX_{d-6..d-1}) >= 1.4 AND VIX_{d-1} >= 20.
- SHORT at 15:31 NY on day d. Hold 5 trading days. Stop = entry + 2 * ATR14 (intrabar).

## Variants (1)
- VIX_1.4_H5.

## Neighbours for G4
- Ratio 1.3 / 1.5; hold 3 / 10; level floor 15 / 25.
