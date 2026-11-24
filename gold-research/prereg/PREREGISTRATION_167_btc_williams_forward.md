# Pre-registration #167 — BTC Williams forward test on Exness BTCUSDc (cent) — written 2026-11-24 before it starts
Evidence so far: #165 BTC (frozen #112) +23.2 bp/trade, t 2.77, Holm 0.02, both halves > 0. #166 clean ground on other
crypto: ETH confirms (+26 bp, t 2.42, Holm 0.03, both halves), XRP + (n.s.), SOL −, LTC ~0 -> "weak support"
(pre-registered label). Gold #112 itself: passed discovery, confirmation, vault, OANDA.

## Exactly what runs
- EA: gold-research/mt5/GoldWilliams.mq5 v1.04 on BTCUSDc H1, Magic 770503, InpSkipWeekendKeys = true (research:
  weekend trading-day keys dropped, Monday uses Friday's range), InpExitNYMin = 1010 (16:50 NY), K = 0.6 (frozen).
- Size: InpLev = 0.15 (BTC daily volatility ≈ 3-4× gold's; 0.5 × 1/3.5 ≈ 0.15 keeps the per-trade risk close to the
  gold Williams sleeve). Changing it requires a new amendment.
- Costs: real Exness BTCUSDc spread/commission, recorded per trade (spread column in the CSV).

## What counts (decided now)
- This is a forward SAFETY + reality check, not proof: at ≈130 trades/year and per-trade sd ≈ 320 bp, a t of 2 on the
  research effect (+23 bp) needs ≈ 750 trades (≈ 6 years).
- Quarterly report: n, mean net_bp, cumulative, max drawdown, average live spread vs research assumption (6.40 $).
- STOP rules (any one): (1) live average spread > 2× the research assumption for a month; (2) sleeve drawdown > 20 %
  of the equity allocated to it; (3) after 200 trades the mean net_bp < −10 bp (well below zero, not just noise).
- Nothing else is changed during the test. Gold Williams and the Combo are unaffected.
