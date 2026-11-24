# Pre-registration #163 — volatility-managed sizing of Williams #112 (written 2026-11-24 BEFORE any number)
Origin: external public research reviewed today — datxbt/xauusd-research-ORB (Exness tick data, pre-registered):
"size ∝ 1/trailing vol is the only forecastable conditioner" (vol AR1 0.70 vs direction AR1 0.12); Moreira & Muir
(2017) volatility-managed portfolios. Our lab already tested vol sizing on Sonic/Overnight (#29, #59, #91: no gain);
Williams was never tested. Cumulative trials before: 350,285.
## Variants (2 trials)
- V1: size = clip(median_252d(ATR20d) / ATR20d, 0.5, 2), ATR20d = mean of the previous 20 completed 17:00-NY daily
  ranges (high-low) divided by the close (known before the day opens).
- V2: size = clip(median_252d(RV60) / RV60, 0.5, 2), RV60 = sd of the previous 60 daily close-to-close log returns.
Base: Williams #112 unsized (combo158 sim_williams, lab engine).
## Metric and gates (cost B primary = 0.24/4000 + 2×0.1bp, no swap for Williams)
Monthly Williams returns at notional ×0.5. D = Sharpe(sized) − Sharpe(base) (JKM + block bootstrap).
1. 2009-2023: D > 0, t ≥ 2 (both). 2. D > 0 in 2009-2016 and 2017-2023. 3. Holm over 2 p < 0.05.
4. DSR ≥ 0.95, N = 350,287. 5. Silver 2023-2026: D > 0. Vault closed. Also reported: max drawdown base vs sized.
