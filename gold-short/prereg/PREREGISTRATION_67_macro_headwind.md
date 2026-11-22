# Pre-registration #67: macro headwind short (MACRO)
Common protocol: PREREGISTRATION_COMMON_65_70.md. Written before results.

## Hypothesis
When US real yields AND the broad dollar are both rising, gold drifts down.

## Reason (G1)
Gold pays no coupon, so higher real yields raise the cost of holding it. A stronger dollar lowers the dollar price of a globally priced asset.
Macro shocks diffuse slowly into gold through ETF and institutional allocation flows.

## Rules
- FRED DFII10 (10y TIPS real yield) and DTWEXBGS (broad dollar index). Publication lag: at decision day d, use only observations dated <= d minus 2 business days.
- dR_L = DFII10(latest) - DFII10(L observations earlier); dD_L = same for DTWEXBGS.
- Regime ON when dR_L > 0 AND dD_L > 0.
- SHORT at 15:31 NY on the first day the regime is ON. Exit at the 15:31 NY checkpoint of the first day it is OFF, or after 20 trading days (then re-enter the next day if still ON). Catastrophe stop = entry + 3 * ATR14 (intrabar).
- DTWEXBGS starts 2006-01, so discovery effectively starts 2006.

## Variants (2)
- MACRO_L5, MACRO_L20.

## Neighbours for G4
- L in {3, 10, 40}; max hold 10 and 40 days; real yield alone (dR_L>0); dollar alone (dD_L>0).
