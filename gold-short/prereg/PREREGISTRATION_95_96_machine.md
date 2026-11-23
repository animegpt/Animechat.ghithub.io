# Pre-registration #95-#96 "machine thinking". Written BEFORE any computation for these tests.
- **Trial count:** 48,613 + 2 (#95 combos) + 4 (#96) = 48,619. Placebo / random draws are not counted as trials.
- **Gold:** minute BID 2017-2023 (the vault 2024+ is dropped by the loader); hourly ask for spreads.
- **PAXG/USDT:** minute klines 2020-08..2023-12 (data.binance.vision).
- **Execution rules as #78-#81:**
  - Fills at the next minute open.
  - No entries 20:45-23:15 UTC / news windows / Friday after 19:30 UTC.
  - Force flat at 20:44 UTC (so no swap is ever paid in #95).
- **Costs:** B (Raw) 0.03 spread + 0.07 commission + 0.1 bp/side; C = 2 x B; A = 0.24.
- **Disclosure:** every #95 component was itself found on this data (2017-2023). The decisive evidence is the gold vault and a Demo.

## #95 Combination of weak signals + cost-aware (Garleanu-Pedersen style) trading
**Components (causal, computed at every minute close; then z-scored with discovery mean/sd):**
- s1 DC_FADE: -(current DC overshoot in theta units), theta = 0.2%, clipped to [-4, 4].
- s2 OU: -X/s with X = ln C - ln EMA60, s = rolling 1440-minute std of X, clipped to [-4, 4].
- s3 OVERNIGHT: +1 from 16:00 to 20:00 New York Mon-Thu, else 0 (plain window, no AI).
- s4 SONIC_H1: +1 / -1 / 0 = the H1 Sonic up / down / neutral regime at the last completed H1 bar.
- s5 SCALE_LAW: sign(r240) if |r240| > 0.75% (big moves continue), else 0. r240 = 240-minute log return.

**Target:** forward 30-minute log return in bp (from the next minute open to the open 30 minutes later). Fitted on discovery 2017-2020, sampled every 5 minutes.

**Combined forecasts f_t (bp per 30 min):**
- COMBO_RIDGE: ridge regression of the target on z1..z5 (alpha = 1% of n), discovery only.
- COMBO_GK: Grinold-Kahn, f = sum_i IC_i x sd(target) x z_i, with IC_i = the discovery correlation of z_i with the target.

**Trading rule (fixed, not tuned):**
- c = round-trip cost B in bp at the current price.
- Target position x* = sign(f) x min(1, (|f| - c)/c) if |f| > c, else 0. Units = 1x equity notional, long/short.
- Partial move each minute: x_new = x + 0.25 (x* - x), executed only if |x_new - x| >= 0.1 (no-trade band).
  - Trades are filled at the next minute open. Each traded unit pays the per-side cost.
- Flat outside the trading windows.

**Comparisons:**
- Each single component through the same engine. Its own forecast = the univariate discovery regression of the target on that z.
- NOBAND: x* = clip(f/c, -1, 1) with full immediate rebalancing (tau = 1, no minimum trade).
- Placebo: 200 random weight vectors (Gaussian, rescaled to the ridge forecast's discovery sd) through the banded engine. p = share with daily net >= real.

**Pass (each combo; Holm over the 2):**
- Discovery: net B day-t >= 2, Holm < 0.05, net C > 0.
- AND net B per day > the best single component, > NOBAND, and placebo p < 0.05.
- Confirmation 2021-2023: net B > 0, day-t >= 2, net C > 0.

## #96 The weekend oracle (PAXG trades 24/7, spot gold does not)
**Timing (UTC, exact minutes):**
- Gold Friday close = the last gold minute of the week (P_F); PAXG close of the same minute (Q_F).
- Gold reopen = the first gold minute after the weekend.
- Entry minute e = the reopen minute + 5 (to skip the very first spread). G_e = gold open at e; Q_e = the PAXG close of minute e-1.
- d = ln(Q_e/Q_F) - ln(G_e/P_F): what PAXG "says" minus what gold has already done.

**Hypotheses (direction fixed now):**
- B1 (convergence): if |d| >= 0.10%, trade gold in the direction of sign(d). Variants B1_1h (exit after 60 min) and B1_4h (exit after 240 min).
- B2 (big-news continuation): m = ln(Q_e/Q_F). If |m| >= 1.0%, trade gold in the direction of sign(m), exit after 8 h.
- B3 (daily break, the same idea): the last gold minute before the daily break (20:40-22:00 UTC window) and the first minute after it; entry = reopen + 5. If |d| >= 0.05%, trade sign(d), exit after 60 min.

**Costs:**
- Spread at entry and exit = the median hourly (ask - bid) close spread of that UTC hour and year: x1 (base) and x2 (safety). Plus 0.07 commission + 0.1 bp/side.
- USDT/USD and the PAXG premium cancel in the changes over the window (Friday -> reopen). Their residual drift is part of the noise.

**Random baseline:** the same events, timing and holding, with a random direction (1,000 sims). p = share >= real.

**Periods:** discovery 2020-08..2022-12; confirmation 2023; vault 2024-2026 after the audit.

**Pass:** discovery net (spread x1) > 0, t >= 2, Holm < 0.05 over the 4, random p < 0.05, net (spread x2) > 0. Then confirmation 2023: net x1 > 0 and t >= 1.5 (one year only), net x2 > 0.

**Descriptive:** the correlation of |m| with Monday's realized volatility.
