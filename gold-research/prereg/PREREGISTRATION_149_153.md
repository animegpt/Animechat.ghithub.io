# Pre-registration #149–#153 — Williams #112 × the three indicators (PAC / Oscillator Matrix / Signals & Overlays)
Written 2026-11-23 BEFORE any evaluation number of this study was computed. The only numbers seen so far are a code
smoke test on 2004-01..2004-07 data (training-only years; 93 trades; shapes/feature counts only, no returns examined).
Nothing here is relaxed later. Any change after a result is seen goes into a dated AMENDMENT file with the reason, and
the original rule stays the one used for the verdict.

## 0. Deviations from the task (forced, recorded before computing)
1. **Inputs were not available.** gold-short-pack.tar.gz, gold-data-part0..3.gz (fingerprint 12654831d0918eaa),
   silver-data.tar.gz (e652ac8de534f862), RESEARCH_HANDOFF.md, sonic_ai.features / pac.py / ind.py and the #147/#148 code
   are not in this container, the repo history, or its releases. The user chose "rebuild from scratch".
2. **Data:** Dukascopy hourly BID candles, XAUUSD 2004-01..2026-10 and XAGUSD 2022-01..2026-10, downloaded in this
   session (same source/endpoint as gold-lab, where Williams #112 reproduced exactly: disc n 2053, net1 t 2.25).
   Fingerprints will NOT match the user's packs.
3. **No M15.** Dukascopy throttles to about one file per 20-60 s; minute data (one file per day, about 12,000 files) is
   not feasible. Timeframes are **H1, H4, D1**.
4. **Indicators are my re-implementations** (`code/ind3.py`), written from public descriptions of the LuxAlgo-style
   suites, not the user's code. So #148's 54-feature result is NOT reproduced or compared one-to-one; my HGB model is
   only an analogue of it.
5. **Trial counter:** the last logged entry I can see is #146 (cumulative 300,172, gold-lab). The trial counts of #147
   and #148 are unknown to me. DSR uses N = 300,172 + this study's trials (a lower bound on the true N).

## 1. Fixed base strategy (frozen #112, not changed)
Day = 17:00→17:00 New York. Buy stop at open + 0.6 × yesterday's range and sell stop at open − 0.6 × yesterday's range;
the first one touched wins (if both are touched in one hourly bar, the worse outcome is used); one trade per day;
exit at the day's close. Cost (primary, `net1`): 0.12/entry + 0.12/exit price (= 0.24 $ round trip on price)
+ 2 × 0.1 bp slippage. No swap (intraday). `net2` (0.24/4000) is reported only. Engine: gold-lab `lab.py`
(`oco_stop_trade`), with the reproduction check required before anything else: disc 2004-2016 n 2053 net1 t ≈ 2.25.

## 2. #149 Features (Phase 1)
- For each trade: entry bar j0 starts at time T0. For every timeframe, use only the last bar whose completion time ≤ T0
  (H1: bar ending at T0; H4: 4-hour blocks from 17:00 NY; D1: 17:00 NY days). The feature code is checked by a
  truncation test: features recomputed on data cut at T0 must equal the full-data features.
- State: PAC swing/internal trend, premium/discount position and zone, HyperWave level/vs signal/slope/zone, Money Flow
  level/slope, Confluence and its agreement, SuperTrend-AI direction/distance/strength/factor, Reversal Band z/outside.
- Event: bars since BOS / CHoCH / CHoCH+ / liquidity sweep (swing and internal), FVG, EQH/EQL, HyperWave 50-cross,
  OM reversal marks, divergences, SuperTrend flips, reversal-band touches; plus OB/FVG counts and distances.
- Alignment: per TF `align3` = # of {PAC swing trend, HyperWave − 50, SuperTrend dir} agreeing with the trade (0-3);
  `mtf_*_votes` (0-3 TFs per indicator), `mtf_align3_majority` (0-3), `mtf_align9` (0-9).
- Directional values × trade side; bull/bear event pairs → with-trade / against-trade. The trade side itself is NOT a
  feature (the question is about the indicators only).
- Total: **206 features** (logged as #149).

## 3. #150 Models (Phase 2)
- Walk-forward by calendar year. Test years 2009..2023; the model for year Y trains on trades 2005-01-01..(Y-1)-12-31
  (2004 dropped as indicator warm-up). Final model for silver/vault: trained on 2005..2023.
- Models: HistGradientBoosting, RandomForest, L1-logistic (classification) / Lasso (regression), ExtraTrees, and the
  Ensemble = mean of the four models' percentile scores.
- Targets: (cls) P(net1 > 0); (reg) net1 winsorised at the training 1st/99th percentiles.
- Hyper-parameters chosen inside the training window only: expanding inner folds whose validation sets are the last 3
  training years (one year each), with 5 trading days purged before each validation year. Criterion = mean Spearman IC
  (prediction vs net1) over the 3 validation years. Grids:
  HGB lr {0.03, 0.1} × max_depth {2, 3} × max_iter {100, 300}, min_samples_leaf 50, l2 1.0;
  RF / ET: 300 trees, max_depth {3, 6}, max_features {sqrt, 0.3}, min_samples_leaf {25, 100};
  L1: C {0.003, 0.01, 0.03, 0.1, 0.3} (Lasso alpha {1e-5, 3e-5, 1e-4, 3e-4, 1e-3}), standardised inputs.
- Size map: pct = empirical CDF position of the test prediction among the pooled inner-validation predictions of the
  chosen setting. Map A: size = 0.5 + pct (0.5-1.5). Map B: size = 0.25 + 1.75 × pct (0.25-2). Sizing only; no trade
  is ever skipped.
- Variants: 5 models × 2 targets × 2 maps = **20** trials.

## 4. #151 Simple rules brute force (Phase 3)
- Atoms (thresholds from discovery 2009-2016 trades): discrete signed features → x>0, x<0; 0/1 features → =1;
  align3/votes → ≥2, =3, =0; align9 → ≥6, ≤3; bars-since → within a short and a long window (H1 ≤6 / ≤24 bars,
  H4 ≤2 / ≤6, D1 ≤1 / ≤5); continuous and counts → above the 67th / below the 33rd percentile (+ counts > 0).
- Rule = AND of 1-3 atoms from different base features; coverage 10%-90% of discovery trades. Action "up": size 1.5
  when true, else 1.0. Action "down": size 0.5 when true, else 1.0.
- Search: all single atoms × 2 actions, then pairs and triples drawn at random (seed 151) until **50,000** rules in total
  (pairs and triples half each of the remainder).
- Luck threshold: the whole search (atoms, thresholds, 50,000 rules with the same seed) re-run 20 times with random
  trade directions (each trade's side flipped with probability 0.5: return = new side × price move − same cost, all
  directional features re-signed for the new side). Threshold = 95th percentile of the 20 null maxima of the discovery
  statistic.

## 5. Metric and verdict (Phase 4)
- Monthly portfolio: per-trade return × size, summed by calendar month of the trade day; months with no trade = 0.
  Sharpe = mean/sd × √12. **D = Sharpe(sized Williams) − Sharpe(plain Williams)** over the same months.
- t of D (primary): Jobson-Korkie with the Memmel correction on the monthly series. Robustness (reported, must also
  be ≥ 2 for a pass): paired circular block bootstrap of months (block 6, 5,000 resamples), t = D / sd(boot D).
- Discovery statistic for rules: t of D in 2009-2016.
- **A model or rule passes only if ALL hold:**
  1. Walk-forward 2009-2023 combined: D > 0 and t ≥ 2 (both the JKM and the bootstrap t).
  2. D > 0 in 2009-2016 and D > 0 in 2017-2023 separately.
  3. Rules only: discovery t > luck threshold (and ≥ 2).
  4. Holm over ALL models and ALL rules tested (20 + 50,000 one-sided p's from the combined period): adjusted p < 0.05.
     (Holm within the 20 models only is reported for information, not used.)
  5. Deflated Sharpe ≥ 0.95 for the overlay series (sized − plain monthly returns), N = 300,172 + trials of this study,
     cross-trial variance of annual Sharpe from this study's model and rule overlays.
  6. Clean ground: the frozen final model (trained 2005-2023 on gold, no re-training) or the frozen rule (gold
     thresholds) applied to Williams on XAGUSD 2023-01..2026-10 (silver cost 0.025 $ on price + 2 × 0.1 bp): D > 0.
  7. Independent audit by a separate agent, then ONE look at the gold vault 2024-01..2026-10: D > 0 reported.
- Tie rule: if a simple rule's combined t is within 0.5 of the best model's, the rule is preferred.
- If nothing passes, the report says so plainly and lists what was learned about the three indicators.

## 6. #152 Clean ground / vault and #153 (optional)
- #152 = the silver test and the vault look for the winner (if any). Without a winner, silver is still reported for the
  best model and the best rule (descriptive, labelled as such); the vault stays closed.
- #153 (optional, only if budget remains): the same feature set + the 5 models (cls target, map A) on Sonic H1 (EMA
  34/89) and Overnight trades (gold-lab `refs.py` hourly versions); same metric and gates 1, 2, 4 (within #153), 5.

## 7. Deliverables
Arabic report with a table for every model and the top rules, STATE.md, test_log.jsonl. Only if a winner passes every
gate: GoldWilliams.mq5 (Magic 770502) with the model exported as trees (300-tree style of build_mt5_ea.py, which is not
available here, so it will be re-written), a Shadow mode (computes and logs the AI size, does not change trades), and
a Pine script for viewing.
