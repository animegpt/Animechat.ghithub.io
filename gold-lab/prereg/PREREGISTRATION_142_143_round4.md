# Pre-registration #142-#143 (round 4). Written BEFORE computing (EURUSD, gold and silver data still downloading in this session).
Common rules + Amendment A + threshold rule of prereg 135_138. Trials before: **150,172**.
#142 adds 10,000 -> 160,172. #143 adds 50,000 -> 210,172.

Data note: the container was new; Dukascopy hourly BID files for XAUUSD, XAGUSD and EURUSD (2004-01 .. 2026-10) are re-downloaded with `gold-lab/code/dl.py` (now in git). Before any search, the engine check must reproduce Williams #112 (disc n 2053, net1 t 2.25). If it does not, nothing below is run until the difference is explained.

## #142 EURUSD (dollar) -> gold intraday conditions (mirror of #141 with EURUSD instead of silver)
- Universe/outcomes: the 144 same-day gold outcomes of #133.
- New conditions (Dukascopy EURUSD hourly BID aligned on the gold bars/days; tercile bins from a rolling PAST 250-day window):
  EURUSD r1 tercile (3); gold-minus-EURUSD r1 tercile (3); EURUSD return-so-far at E tercile (3); gold-minus-EURUSD return-so-far at E tercile (3); EURUSD 5-day return tercile (3); 20-day correlation of daily gold and EURUSD returns (up to t-1) tercile (3) = 18.
  (EURUSD up = dollar down. "gold-minus-EURUSD" = gold's move not explained one-for-one by the dollar.)
- Rules (seed 142): all 18 singles x 144 = 2,592, plus 7,408 random pairs (one new condition x one #133 library condition from a different group, random outcome) = 10,000.
- Threshold: 20 nulls, circular shift of the outcomes, evaluating the same 10,000 rules + random #133-generator rules to the cumulative size 160,172; 95th percentile of the maxima of t(net1).
- Survivors (t1 > threshold, t2 >= 2, n >= 150, random-time p < 0.05), clustering, confirmation (net1 > 0, net2 > 0, Holm p < 0.05 over those sent), DSR, audit, vault, portfolio: as #133.
- Clean ground (EURUSD is an input, so it cannot be clean ground): gold months after 2026-10 (minute data) — descriptive if too short.

## #143 two-market agreement search (gold AND silver at the search stage)
Goal: keep only effects that exist in both metals in 2004-2016, so single-market luck is filtered out at discovery.
- Universe: the #133 universe (36 windows x {no stop, 0.5 ATR stop} x {long, short} = 144 same-day outcomes) and the 78-condition #133 library, built **separately on each market from that market's own data** (gold conditions from gold, silver conditions from silver; same code `bf.build`). A rule = (outcome, condition or condition pair) is applied identically to each market.
- Costs: gold primary (0.24/price + 0.1 bp/side) and second (0.24/4000 + 0.1 bp/side); silver 0.025/price + 0.1 bp/side (silver second scenario = primary).
- Rules (seed 143): 11,232 singles + 38,768 random pairs from the #133 generator = 50,000 (same generator, new seed; overlap with #133 rules is allowed and counted).
- Statistic: **S = min(t_gold(net1), t_silver(net1))** in discovery 2004-2016, with n >= 150 trades in EACH market (else not scored).
- Luck threshold: 20 nulls. Each null circularly shifts the outcome series of both markets by the same random number of days (250 .. n-250, on each market's own day index) and evaluates the 50,000 rules plus random #133-generator rules up to the cumulative size 210,172, all scored with S. Threshold = 95th percentile of the 20 null maxima of S. The gold-only random-rule threshold at the same size (max t_gold over the same null searches) is also reported, for information only.
- Survivors: S > threshold, AND gold t(net2) >= 2, AND gold random-time p < 0.05, AND silver random-time p < 0.05. Cluster by gold daily-P&L correlation > 0.7 (keep best S per cluster), at most 10 to confirmation.
- Confirmation 2017-2023: gold net1 > 0 and net2 > 0 AND Holm over the candidates sent (one-sided p of gold net1) < 0.05, AND silver net1 > 0 (extra requirement, not a relaxation).
- Clean ground: gold months after 2026-10 (descriptive if too short) and BTCUSDT is NOT used (different universe of hours). Then DSR (N = 210,172), audit, one vault look (gold), portfolio — per common rules.

## Not done this round
- Gold after 2026-10 is used only if a candidate survives confirmation.
- Nothing in the gates, costs or periods changes.
