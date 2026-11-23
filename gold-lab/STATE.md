# STATE — Gold Lab (infinite rounds)

## Where things are
- Branch: `claude/vigilant-heisenberg-04njh1`, folder `gold-lab/`. Earlier lab: branch `claude/gold-short-pack-task-f5rkwp`, folder `gold-short/` (tests #1-#122, log `gold-short/test_log.jsonl`).
- Data: rebuilt from Dukascopy hourly BID (the original pack/data parts were not in this container). Downloader `/home/user/lab/code/dl.py` (not in git; data in /home/user/lab/raw). Rebuild: run the downloader (XAUUSD BID 2004-01..2026-10, ~30-60 min, flaky server, retries), then `gold-lab/code/lab.py` builds the cache (vault split off).
- Engine check: Williams #112 reproduced exactly (disc n 2053, net1 +5.09bp t 2.25, net2 +7.29 t 3.23; conf n 1123, +1.13 / +2.07).
- Rules: `prereg/PREREGISTRATION_LAB_COMMON.md` (gates, costs, periods, vault = one look after an independent audit).

## Round counter: 1 finished
| Round | Families | Trials added | Cumulative | Luck threshold (t, disc) | Result |
|---|---|---|---|---|---|
| 1 | #123-#132 classics part 3 (Pinball, ORB60, Specialist Trap, Anti, TD9/TD13 D1+H4, Ichimoku, Keltner) | 10 | 48,756 | Holm in family | all fail discovery (best ANTI t 1.29) |
| 1 | #133 brute force, 50,000 same-day rules | 50,000 | 98,756 | 4.03 (20 nulls, size 98,756) | 2 beat threshold, both negative in confirmation |
| 1 | #134 genetic programming, 30,000 evals | 30,000 | 128,756 | 5.37 (10 nulls, size 128,756) | best 5.29 < threshold |

## Current threshold for any new candidate
- Cumulative trials: **128,756**. Luck threshold ~ **5.37** (t of net1 per trade in discovery, max of a cumulative-size null). Any new family must also beat this (top up its null with random #133-generator rules to the cumulative size).
- DSR is computed with N = cumulative trials.

## Best candidates and status
- None alive. (Vault untouched in this lab; earlier lab used it once for #112 Williams.)

## Next round (2)
- Prereg #135-#139 before computing: Asian-range ("London") breakout, pre-FOMC drift (Fed calendar from federalreserve.gov), turn-of-month, ML walk-forward family (fixed hyperparameters, OOS walk-forward statistic), and a silver->gold / EURUSD->gold intraday lead-lag (if XAG/EURUSD data finish).
