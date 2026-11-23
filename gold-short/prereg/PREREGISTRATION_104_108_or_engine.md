# Pre-registration #104-#108 "full operations-research engine". Written BEFORE computing.
- **Data:** 2004-2023 only (gold hourly/minute; the vault 2024-2026 stays sealed).
- **Trials:** 48,634 + (36 Sonic grid + 15 Overnight configs + 45 DC configs) = 48,730 for the Deflated Sharpe.

## #104 Module 1: PBO via CSCV (Bailey, Borwein, Lopez de Prado, Zhu 2017)
**Strategy families:**
- **(a) Sonic H1** (live rules, 1% risk unit, cost A, swap-free). Grid: dragon EMA in {21, 28, 34, 40, 48, 55} x trend EMA in {55, 75, 89, 105, 144, 200} = 36 configs. Monthly returns 2004-2023 (240 months).
- **(b) Overnight AI** (research walk-forward 2012-2023, HistGB as gates56). Configs: training-probability threshold quantile in {0.3, 0.4, 0.5, 0.6, 0.7} x max_depth in {2, 3, 4} = 15. Monthly returns 2012-2023 (144 months).
- **(c) DC fade** (#58-B engine, Raw cost B). Grid: theta in {0.10, 0.15, 0.20, 0.25, 0.30}% x overshoot k in {1.5, 2.0, 2.5} x stop in {2, 3, 4} theta = 45. Monthly returns 2017-2023 (84 months, minute data).

**CSCV:**
- S = 16 equal blocks of months (12 for DC), all C(S, S/2) IS/OOS splits.
- **Selection:** the config with the best IS Sharpe. Its OOS rank -> logit.
- **PBO** = P(logit <= 0).
- Also reported: P(OOS Sharpe of the IS-best < 0), and the IS-vs-OOS Sharpe degradation slope.
- **Purging/embargo:** returns are attributed to exit months. Trades are short relative to monthly blocks (Sonic <= 10 days, Overnight 4 h, DC <= 24 h), so a 1-month embargo is applied by dropping from each OOS set any block adjacent to an IS block for the Sonic family. For the others it is reported as not needed.
- **Deflated Sharpe:** for the live config (Sonic 34/89; Overnight q0.5/depth 3; DC 0.20/2/3) on its full monthly series, N_trials = 48,730, trial-Sharpe variance from the family grid.
- **Verdict rule (user):** PBO > 50% => the strategy is called "lucky" and work on it stops.

## #105 Module 2: robust plateau
- **Sonic heatmap:** monthly Sharpe per config in each of 4 windows (2004-08, 2009-13, 2014-18, 2019-23), plus the 3x3-neighbourhood mean.
  - Report the rank of 34/89 and the location of the most stable region: max over configs of min-over-windows of the neighbourhood-mean Sharpe.
- **Overnight:** net/Sharpe vs threshold quantile per window.
- **A different "robust centre"** is only proposed if it beats 34/89 on min-over-windows by a margin with every window positive. It is offered as an OFF-by-default option. The vault is never used.

## #106 Module 3: retraining policy (walk-forward 2012-2023)
- **Overnight AI (HistGB, median threshold) policies:**
  - P0: train once on data up to 2011, never retrain.
  - P1: yearly, expanding window.
  - P2: yearly, rolling 5 years.
  - P3: yearly, rolling 8 years.
  - P4: every 6 months, expanding.
- **Metric:** OOS mean net per night, t, Sharpe. Best = the highest OOS Sharpe. Ties within 0.1 -> the simplest (P1).
- **Sonic AI sizing:** P0 (train <= 2012) vs P1 (yearly expanding) on 2013-2023. Metric: AI-sized total R minus unsized total R.
- **Deliverable:** retrain.py (rebuilds the models up to a cutoff and generates GoldComboAI.mq5 via build_mt5_ea, with a parity check). Tested here with cutoff 2023-12-31.

## #107 Module 4: monitoring (CUSUM)
- **Reference distributions = out-of-sample trades:** Sonic 2017-2023 R per trade; Overnight walk-forward nights 2012-2023; DC #58-B trades 2017-2023 at cost B.
- **One-sided CUSUM** on standardised trade results against the null "edge = OOS mean": S = max(0, S + (mu0 - x)/sd - k), with k = mu0/(2 sd) (detecting a drop to 0).
- **Thresholds h_yellow / h_red set by bootstrap** of the OOS trades so that the false-alarm probability per year (at each strategy's trade rate) is 20% / 5%.
- **Also reported:** the expected number of trades to a red alarm if the true edge is 0, and the probability of N consecutive losses.
- **Deliverable:** monitor.py (MT5 HTML/CSV report or GoldDCFade CSV -> green/yellow/red per robot).

## #108 Module 5: capital plan (Bayesian + Kelly)
- **Prior on each edge:** normal, mean = OOS estimate shrunk 50% toward 0, sd = its standard error. Updated with live trades (conjugate normal).
- **Monte Carlo:** 3-year paths under edge = 100% / 50% / 0% of the OOS estimate, bootstrap residuals.
- **Sizes chosen** so that the 95th-percentile max DD <= 15% under the 100% case; behaviour reported under 50% / 0%. With swap and swap-free.
- **Deliverable:** capital_plan.md with start size, scale-up / scale-down / stop rules.
