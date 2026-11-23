# Pre-registration #144-#146 "Modern Gold Lab" (round 5). Written BEFORE downloading the new data and BEFORE computing.
Common rules + Amendment A + threshold rule of prereg 135_138, EXCEPT the periods below.
Trials before: **210,172** (round 4 #142-#143, pre-registered in the parallel session on branch claude/busy-cannon-9cnt9p, counted in full even if not yet run).
#144 adds 50,000 -> 260,172. #145 adds 10,000 -> 270,172. #146 adds 30,000 -> 300,172.

## Why
Rounds 1-3: 12 rules beat the luck threshold in 2004-2016 and ALL died in 2017-2023 (regime change after 2016). This round searches the modern regime directly.

## Periods (modern split)
- Discovery 2017-01-01 .. 2021-12-31. Confirmation 2022-01-01 .. 2023-12-31. Vault 2024-01-01 .. 2026-10-31 (unchanged; never seen by any rule of this round; ONE look per candidate after an independent audit).
- 2016 used only as warm-up for indicators/percentiles. Nothing before 2017 is scored.
- Clean ground after confirmation: (a) the same rule on silver 2024-2026 (silver as the traded market, its own data) and (b) gold months after 2026-10 (1-minute daily files) — descriptive if too short.

## #144 modern brute force: the #133 universe (144 same-day outcomes x 78-condition library), seed 144, 11,232 singles + 38,768 random pairs = 50,000 rules. Statistic t(net1) per trade in discovery 2017-2021, n >= 100 trades.
- Threshold: 20 nulls; each circularly shifts the outcomes inside the discovery days (by 120 .. n-120 days) and evaluates the 50,000 rules + random #133-generator rules up to the cumulative size 260,172. Threshold = 95th pct of the 20 maxima.
## #145 modern cross-asset: new conditions from Dukascopy hourly USDCNH (offshore yuan: Chinese demand proxy), USA500IDXUSD (S&P 500 CFD: risk appetite) and USDJPY (yen/real-rate proxy), aligned on the gold bars, tercile bins from a rolling PAST 250-day window:
  CNH r1, CNH return-so-far at E, CNH 5-day return; SPX r1, SPX return-so-far at E; JPY r1, JPY return-so-far at E (7 groups x 3 = 21 conditions). Rules (seed 145): 21 x 144 = 3,024 singles + 6,976 random pairs (one new x one library condition) = 10,000. Threshold as #144 at cumulative 270,172.
## #146 modern GP: the #134 GP (pop 1,000 x 30 generations = 30,000 evaluations, literals from the #133 library + the #145 conditions), seed 146, fitness = discovery t(net1) with n >= 100, parsimony 0.1 per literal beyond 2. Threshold: 10 null GP runs on shifted outcomes, each topped up with random rules to 300,172.
## Gates (unchanged in spirit; nothing relaxed)
- Survivors: t1 > threshold, t2 >= 2, random-time p < 0.05; cluster corr > 0.7 (also vs Williams #112 / Sonic / Overnight: corr > 0.7 -> dropped as duplicate); <= 10 per family to confirmation.
- Confirmation 2022-2023: net1 > 0 and net2 > 0 AND Holm (one-sided net1) < 0.05 over the candidates sent.
- Then clean ground, DSR (N = cumulative), independent audit (separate agent), ONE vault look, portfolio check.
