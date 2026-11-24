# Pre-registration #158–#161 — The COMBO portfolio (Sonic AI + Overnight AI + Williams #112) × costs × indicators × allocation
Written 2026-11-24 BEFORE any number of this study. (The user asked for "#154+"; #154–#157 are already used.)
Cumulative trials before: 350,217. Vault 2024-01..2026-10 stays CLOSED for this whole study (user rule).

## 0. Source of truth and honest limits
- Strategy logic = GoldComboAI.mq5 v1.00 as pasted by the user (2026-11-24) + GoldWilliams.mq5 (#112).
- **The EA's Sonic-AI trees and Overnight coefficients were trained on all data up to their cutoff (policy #106), so
  applying them to 2009-2023 is IN-SAMPLE.** They are used only for (a) a fidelity check of the rebuilt features and
  (b) the frozen silver test. All historical evaluation uses a **walk-forward reproduction** of both models (same
  features, same model type, yearly expanding training, test years 2009-2023), defined below.
- Data: Dukascopy H1 BID (gold 2004-2023 dev; silver 2022-2026; EURUSD 2004-2026 for the Overnight EUR feature —
  if EURUSD is incomplete, the feature is set to 0 exactly as the EA does when EURUSD is missing, and this is reported).
- Portfolio simplifications (reported): the EA's shared rules (DD guard, daily loss limit, max leverage) are not
  simulated; the Overnight-skip-when-Sonic-short rule IS simulated; returns are simple (non-compounded) monthly sums.

## 1. Strategy rebuild (exactly the EA rules, on closed H1 bars)
- **Sonic**: signal on closed bar i (EA `SonicSignal`), entry at the open of bar i+1. Stop = min(LL10, C − 0.5·ATR14rma)
  (short mirrored), skipped if the entry price is already beyond it. Exit: stop hit inside a bar (gap → open), else on a
  closed bar k with close beyond the dragon (C<EMA34low long / C>EMA34high short) or age ≥ 240 bars → exit at open k+1.
  No new entry on the bar of an exit; one position at a time. R = net P&L / (entry − stop).
- **Sonic AI (walk-forward)**: the 38 EA features (`SonicFeatures`, incl. prevR), HistGradientBoostingClassifier,
  300 trees, max_depth 3, learning_rate 0.05, min_samples_leaf 20, target R>0 (cost A). Size multiplier = EA
  `RankMult`: 0.5 + percentile of the probability among the training-set probabilities (101 quantiles).
  Train on trades 2005..Y−1, apply to year Y, Y = 2009..2023. Final model (2005-2023) for silver.
- **Overnight AI (walk-forward)**: buy at the open of the 16:00 NY bar Mon-Thu, exit at the open of the 20:00 bar
  (= close of the 19:00 bar), skipped if a Sonic short is open. 18 EA features (`OvernightProb`). Logistic regression
  (standardised, L2, C=1), target = night gross return > 0. Threshold for year Y = quantile q of the training-set
  probabilities, q = share of nights the FROZEN EA model rejects on 2004-2008 (calibration only).
  Also reported: plain Overnight (every Mon-Thu night).
- **Williams #112**: lab engine (n 2053 check). Option: sized by the #150 RF out-of-sample percentile (0.5-1.5).

## 2. Cost scenarios (all strategies, all tables)
Fractions of price per trade; slippage 2 × 0.1 bp always.
| | spread (round trip) | long swap per rollover (Wed ×3) |
|---|---|---|
| A historical | 0.24 $ / price at the trade | 0.4316 $ / price |
| B today | 0.24 / 4000 | 0.4316 / 4000 |
| C today, swap-free | 0.24 / 4000 | 0 |
| D Raw, swap-free | 0.12 / 4000 | 0 |
Shorts pay no swap. Silver (clean ground): 0.025 $ / price, no swap.

## 3. #158 Base portfolio (descriptive, 1 trial)
Monthly returns 2009-2023 with the user's sizes: Sonic risk 0.15 % × AI multiplier, Overnight notional ×1.0 (AI filter),
Williams notional ×0.5. Per scenario: each strategy's mean/t, annualised Sharpe, max DD, monthly correlations, and the
portfolio's. Answer "when to run Overnight": Overnight (AI and plain) net per night and t by scenario and period.

## 4. #159 Do the three indicators improve the combo? (4 trials)
- Features: the 206 #149 features at each trade's entry (bars completed before the entry bar), all three strategies.
- Structures × algorithms: {joint model over all trades (+ strategy one-hot), one model per strategy} ×
  {RF regression (#150 rf_reg settings: 300 trees, depth 6, sqrt, leaf 100), Ensemble of HGB/RF/L1/ET classification}.
  Target = trade return divided by the strategy's training-set sd (joint) / net return (per strategy), cost A.
- Walk-forward yearly 2009-2023, training 2005..Y−1, no hyper-parameter search (fixed #150 settings).
- Size = 0.5 + percentile (vs training-set in-sample predictions), applied ON TOP of the base sizes. Sizing only.
- Metric: portfolio monthly Sharpe, D = Sharpe(sized) − Sharpe(base) (scenario A primary; B/C/D reported).
- Gates (all): D > 0 and t ≥ 2 (JKM and block bootstrap) 2009-2023; D > 0 in 2009-2016 and 2017-2023;
  Holm over the 4 trials (+ all trials of #158-#161) p < 0.05; DSR ≥ 0.95 on the overlay with N = cumulative total;
  silver: D > 0 with the frozen final model. Vault: NOT opened in this study.

## 5. #160 Risk allocation (3 trials)
Weights w (multipliers on the base sizes) for Sonic, Overnight, Williams, estimated on 2009-2016 monthly returns,
tested on 2017-2023, per cost scenario:
- Risk parity: w ∝ 1/σ_i.
- Fractional Kelly: w ∝ Σ⁻¹μ, negative weights set to 0.
- Robust: risk parity × min(1, max(0, t_i/2)) (strategies with weak discovery evidence are de-weighted, t ≤ 0 → off).
Each is scaled to the largest level whose 95th percentile max drawdown over 36 months ≤ 15 % (5,000 stationary block
bootstraps, block 6, of the 2009-2016 monthly portfolio returns with the means shrunk by 50 %).
Output: InpRiskPct = 0.15·w_S, InpOnLev = 1.0·w_O, InpLev = 0.5·w_W. Test-period Sharpe, return, max DD reported.

## 6. #161 Clean ground — silver 2023-2026
The three strategies on XAGUSD with frozen gold-trained walk-forward final models (Sonic AI, Overnight AI, #159 models),
silver cost. Reported: each strategy, base portfolio, and #159 sized portfolio (D).

## 7. Deliverables
Arabic table "if your account is X → run Y with these settings"; STATE.md; test_log. GoldCombo_Shadow.mq5 only if a
#159 model passes every gate above.
