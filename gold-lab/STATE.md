# STATE — Gold Lab (infinite rounds)

## Where things are
- Branch: `claude/vigilant-heisenberg-04njh1`, folder `gold-lab/`. Earlier lab: branch `claude/gold-short-pack-task-f5rkwp`, folder `gold-short/` (tests #1-#122, log `gold-short/test_log.jsonl`).
- Data: rebuilt from Dukascopy hourly BID (the original pack/data parts were not in this container). Downloader `/home/user/lab/code/dl.py` (not in git; data in /home/user/lab/raw). Rebuild: run the downloader (XAUUSD BID 2004-01..2026-10, ~30-60 min, flaky server, retries), then `gold-lab/code/lab.py` builds the cache (vault split off).
- Engine check: Williams #112 reproduced exactly (disc n 2053, net1 +5.09bp t 2.25, net2 +7.29 t 3.23; conf n 1123, +1.13 / +2.07).
- Rules: `prereg/PREREGISTRATION_LAB_COMMON.md` (gates, costs, periods, vault = one look after an independent audit).

## Round counter: 2 finished
| Round | Families | Trials added | Cumulative | Luck threshold (t, disc) | Result |
|---|---|---|---|---|---|
| 1 | #123-#132 classics part 3 (Pinball, ORB60, Specialist Trap, Anti, TD9/TD13 D1+H4, Ichimoku, Keltner) | 10 | 48,756 | Holm in family | all fail discovery (best ANTI t 1.29) |
| 1 | #133 brute force, 50,000 same-day rules | 50,000 | 98,756 | 4.03 (20 nulls, size 98,756) | 2 beat threshold, both negative in confirmation |
| 1 | #134 genetic programming, 30,000 evals | 30,000 | 128,756 | 5.37 (10 nulls, size 128,756) | best 5.29 < threshold |
| 2 | Amendment A (rate-based swap); #123-#132 re-run | 0 | 128,756 | - | still all fail (ANTI t 1.92) |
| 2 | #135 ML walk-forward ridge (72 targets, OOS 2008-2016) | 72 | 128,828 | 4.00 | best OOS t 2.35 (own-null p~0.1) |
| 2 | #136 Asian breakout, #137 pre-FOMC, #138 turn-of-month | 3 | 128,831 | Holm + 4.0 | all fail (Asian: gross +4.5bp, p_rand .002, but net1 t 0.99) |

## Current threshold for any new candidate
- Cumulative trials: **128,831**. Threshold rule (prereg 135_138): 95th pct over nulls of max(family's own null, random-rule null at cumulative size). The random-rule part alone gives ~4.0 (t of net1/trade in discovery); GP-type searches ~5.4.
- Benchmark (same engine): Williams #112 disc t1 2.25, Sonic t1 1.83 — the existing portfolio would not pass this threshold either.
- DSR is computed with N = cumulative trials.

## Best candidates and status
- None alive. (Vault untouched in this lab; earlier lab used it once for #112 Williams.)

## Next round (3)
- #139 weekend-gap fade (Sunday open vs Friday close; not in the #133 library because 'so-far' starts at the Sunday open).
- #140 cross-asset intraday library (silver and EURUSD conditions added) — needs XAG/EURUSD hourly (downloading). Clean ground for it: BTC or gold 2026-11 minute data.
