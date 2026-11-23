# Pre-registration #154 — Gold short reversal after an up-hour into 16:00 New York
Written 2026-11-23 BEFORE computing this strategy's returns on any period. User request after #153.

## Origin (honest disclosure: this idea is CONTAMINATED on gold 2004-2023)
In #153 (Overnight sizing) the out-of-sample models were found to read short-term mean reversion: the return of the
15:00-16:00 NY bar had Spearman IC -0.22 with the 16:00->20:00 long return (gold 2004-2023, all years same sign).
So gold 2004-2023 has already been looked at for this effect. **Gold dev data cannot confirm it.** It is reported
only as a sanity check (it must be net > 0, but that proves nothing). The verdict rests on data never used:
silver 2023-2026 (clean ground) and the gold vault 2024-2026 (one look, after an independent audit).

## Rule (fixed, no parameters searched)
- Data: Dukascopy hourly BID (same as #149-#153). NY time, trading day 17:00->17:00 (lab.py `Mkt`).
- Signal bar: the hourly bar starting 15:00 NY of day key t. Entry bar: the bar starting 16:00 NY of the same key, and it
  must be the bar right after the signal bar.
- Condition: signal-bar return close/open - 1 > 0 (the hour before 16:00 went up).
- Action: SELL at the open of the 16:00 bar. Short only. One trade per day max.
- Variant A (primary): exit at the close of the 16:00 bar (before the 17:00 rollover). Mon-Fri.
- Variant B: exit at the close of the 19:00 NY bar (the 20:00 exit of the Overnight strategy), next key on the next
  calendar day, Mon-Thu only. Crosses the 17:00 rollover; short swap assumed 0 (lab.py SPEC); a real positive or
  negative short swap is NOT modelled. This is flagged in the report.
- No stop, no target.

## Costs
- net1 (primary): 0.12 $/entry price + 0.12 $/exit price + 2 x 0.1 bp (silver: 0.025 $ spread on price).
- net2: 0.24/4000 + 2 x 0.1 bp (gold only).
- Stress (reported, not a gate): spread doubled (0.48 $), because spreads around 16:00-17:00 NY are often wider.

## Gates (all required, nothing relaxed later)
1. Gold dev 2004-2023 (contaminated sanity check): net1 > 0. Reported with t, p_rand, p_time (lab.summ).
2. Clean ground — silver XAGUSD 2023-01-01..2026-10-31, same rule, silver cost: net1 > 0 and one-sided p < 0.10.
3. Holm over the 2 variants on the silver one-sided p: adjusted p < 0.10 for a variant to continue.
4. Independent audit: a separate agent re-implements the rule from THIS text only and must reproduce the silver and gold
   dev numbers (n within 1%, mean within 0.2 bp).
5. ONE look at the gold vault 2024-01-01..2026-10-31 for the variant(s) passing 1-4: net1 > 0 (primary). Reported:
   t, net2, stress cost.
- The label "passes" needs 1-5. Passing 1-3 only = "candidate, unproven". DSR is reported with N = 350,212 + 2.
- Trials added: 2 (cumulative 350,214).

## Deliverables if it passes
MQL5 EA (short only, separate Magic), Pine script, Demo-first plan. If it fails: say so plainly.
