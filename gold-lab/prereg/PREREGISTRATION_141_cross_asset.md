# Pre-registration #141 silver -> gold cross-asset intraday conditions (round 3). Written BEFORE computing (silver data still downloading).
Common rules + Amendment A + threshold rule of prereg 135_138. Trials before 140,172; +10,000 -> 150,172.
- Universe/outcomes: the 144 same-day gold outcomes of #133.
- New conditions (Dukascopy XAGUSD hourly BID aligned on the same UTC bars/days; percentile bins from a rolling PAST 250-day window):
  silver r1 tercile (3); gold-minus-silver r1 tercile (3); silver return-so-far at E tercile (3); gold-minus-silver return-so-far at E tercile (3); silver 5-day return tercile (3); gold/silver ratio z-score (20 days, t-1) tercile (3) = 18.
- Rules (seed 141): all 18 singles x 144 = 2,592, plus 7,408 random pairs (one new condition x one #133 library condition from a different group, random outcome) = 10,000.
- Threshold: 20 nulls, circular shift of the outcomes, evaluating the same 10,000 rules + random #133-generator rules to the cumulative size 150,172; 95th pct of maxima of t(net1).
- Survivors/confirmation/clean ground/DSR/audit/vault/portfolio as #133. Clean ground for these rules (silver is an input): gold months after 2026-10 (minute data) — descriptive if too short.
