# Amendment A to prereg #155–#157 — silver data quality (written after the first silver run, BEFORE computing anything on the restricted window)

## What happened
The pre-registered silver run (2004–2022) was computed (results/results_155_silver.json). It shows silver Williams GROSS
−50bp/trade in 2004–2016, which is implausible. A data-quality check (no strategy returns involved) shows the Dukascopy
XAGUSD hourly BID file is broken before 2011: median hourly range 464/446/294/182/176/180/138 bp in 2004–2010
(gold same years 23–40 bp; silver 2011–2026 38–82 bp), hourly-gap p99 77–373 bp (2011+: 11–25 bp).
Junk prints create artificial negative autocorrelation (= fake "reversal") and destroy stop-entry breakouts, so
gate 2 (F1/F2) and gate 1 (F3) of the original text cannot be read as a test of the hypotheses on 2004–2010.

## Rule (data-quality only, independent of any strategy result)
A silver year is valid if its median hourly range ≤ 3 × gold's median hourly range of the same year AND its hourly-gap
p99 ≤ 30 bp. Result: 2004–2010 invalid, 2011–2026 valid.

## Consequence (stated before computing)
- Clean ground for F1/F2/F3 becomes **silver 2011-01-01 … 2022-12-31**, sub-periods 2011–2016 and 2017–2022.
  All gates otherwise unchanged (t(Δ) ≥ 2, Δ > 0 in both sub-periods, Holm over 3, DSR with N 350,217, var 0.08433).
- The ORIGINAL 2004–2022 result is reported in full next to it, marked "invalid data years included".
- This amendment is a post-hoc deviation; it is reported as such. Trials: no new trials (same 3 rules).
