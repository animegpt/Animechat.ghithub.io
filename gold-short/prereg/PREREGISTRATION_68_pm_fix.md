# Pre-registration #68: London PM-fix short (FIX)
Common protocol: PREREGISTRATION_COMMON_65_70.md. Written before results.

## Hypothesis
Gold drifts down in the hour into the London afternoon fix/auction (15:00 London).

## Reason (G1)
Documented price pressure before the fix (Caminschi & Heaney 2014; Abrantes-Metz & Metz 2014): fix participants hedging or front-running their net sell flows.
It may have decayed after the 2015 LBMA auction reform; the confirmation period (2017-2023) would expose that.

## Rules
- Every trading day (Mon-Fri), SHORT at the close of the minute starting 14:00 London (Europe/London DST). Cover at the close of the minute starting 15:05 London. No stop.

## Variants (1)
- FIX_1400_1505.

## Neighbours for G4
- Entry 13:45 / 14:15; exit 15:01 / 15:15; Tue-Thu only.
