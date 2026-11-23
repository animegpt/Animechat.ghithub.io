# Pre-registration #92-#94 "the juicer" (operations research on existing signals). Written BEFORE computing.
- **Trials:** 48,604 + 3 (#92) + 3 (#93) + 3 (#94) = 48,613.
- **Vault (2024+) for gold:** not used. The loader drops >= 2024.
- **Silver 2023-11..2026-10:** used only as the out-of-market confirmation of #92. No optimal-stopping result has been computed on it.
- **Execution, costs and no-entry windows:** as in #78-#81 (entry at the next minute open; stop first inside the minute; gap fills at the open; no entries 20:45-23:15 UTC / news windows / Friday after 19:30; force-close 20:44 UTC).
  - Cost B (Raw) = 0.03 USD spread + 0.07 USD/oz commission + 0.1 bp/side.
  - C = 2 x B.
  - A = 0.24 spread.

## #92 Optimal mean-reversion stopping with costs (Bertram 2010 / Leung & Li 2015) for the DC-fade signal family
- **State variable:** X_t = ln C_t - ln EMA60(C)_t on 1-minute closes. EMA60 is the 60-minute anchor of the short mean reversion that drives DC fade.
- **OU fit on DISCOVERY 2017-2020 only:**
  - AR(1) X_{t+1} = alpha + beta X_t + e.
  - kappa = -ln beta per minute, mu = alpha/(1-beta), sigma = sd(e) x sqrt(2 kappa/(1-beta^2)).
  - Stationary sd s = sigma/sqrt(2 kappa).
- **Optimal bands (Bertram):**
  - Maximise (m - a - c) / (E[T(a->m)] + E[T(m->a)]) over a < m.
  - OU first-passage expectations are computed numerically from the scale/speed-density integral.
  - c = cost B in log units at the mean discovery price (plus the mean news multiplier on exits).
  - The bands are stored in units of s, so they transfer across price levels. In application, s is replaced by a causal rolling 1440-minute std of X.
- **Variants (3, Holm over 3):**
  - **OU_BOTH:** long when X <= a*; exit when X >= m*. Short mirrored (enter when X >= -a*, exit when X <= -m*). Safety: 24 h cap, catastrophe stop 6 s from the entry.
  - **OU_LONG:** the long side only.
    - Disclosure: "long side stronger" was seen in #84/#88, so this variant is partly post-hoc.
  - **DC_OUEXIT:** the existing DC fade entries (#58-B: theta 0.2%, overshoot 2 theta, stop 3 theta, NY-hour filter). The exit becomes "X crosses the OU-optimal exit level m* (mirror for shorts)" instead of the next DC; 24 h cap kept.
- **Baseline (reported):** DC fade #58-B with the next-DC exit under the same costs.
- **Pass:**
  - Discovery: net B > 0, day-t >= 2, Holm p < 0.05, net C > 0, AND net B per day > the baseline's.
  - Gold confirmation 2021-2023: net B > 0, day-t >= 2, net C > 0.
  - Silver 2023-11..2026-10 (same z-bands, silver data): gross > 0 with day-t >= 2. Net at the real silver spread is information only.
  - Then the audit, the gold vault once, and the Demo.

## #93 Optimal risk allocation (Sonic, Overnight; DC only if #92 passes)
- **Unit daily P&L series** (gvz91 pipeline): Sonic plain at 1% risk per trade; Overnight AI walk-forward at 1x notional.
  - Costs A + swap (the current account). B is reported as well.
- **Estimation window 2012-2020** (Overnight OOS starts 2012). **Test 2021-2023.**
- **Methods (3):**
  - (K) Fractional Kelly: w = f x Sigma^-1 mu.
  - (RP) Risk parity: w_i proportional to 1/sigma_i.
  - (RB) Robust: mu replaced by the lower 1-standard-error bound of each mean, floored at 0, then Sigma^-1 mu_robust.
  - Each is scaled so that in 2,000 stationary-block-bootstrap (20-day blocks) 3-year paths of the estimation-window returns, the 95th percentile of the max drawdown = 15%.
  - The current setting (Sonic 0.3%, Overnight 2x) is evaluated unscaled.
- **Report on the test:** annual return, Sharpe, max DD for each method vs the current setting.
- **"Better":** a higher test annual return with test maxDD <= 15%, and a Sharpe not lower than the current.

## #94 Overnight execution
- **Nights:** the Overnight AI walk-forward selected nights 2017-2023.
- **Prices:** minute BID. Spread per minute = the median hourly (ask - bid) of that NY hour and year (from the hourly ask files). This is an approximation, disclosed.
- **Variants vs E0** (market buy at the 16:00 NY minute open, market sell at the 20:00 open; pay half-spread x2 + Raw/A costs):
  - **E_TWAP:** entry = the average of the 10 minute opens 15:55-16:04; exit = the average of 19:55-20:04 (each slice pays its half-spread).
  - **E_LIMIT:** buy limit at (16:00 bid open - 0.10 USD), valid 16:00-16:04. Filled at the limit (no spread) if a minute low <= limit - spread. Otherwise market at the 16:05 open. Exit as in E0.
  - **E_EARLY:** entry at the 15:58 open (2 minutes early), exit at the 19:58 open.
- **Also reported:** delay 1-5 minutes (fragility curve).
- **Pass:** paired (variant - E0) mean per night > 0 with t >= 2 on 2017-2020, AND > 0 on 2021-2023.
