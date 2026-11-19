# Pre-registration of the hidden-period test (written BEFORE loading any data >= 2025-11-01)

Frozen strategy ("RB-Breakout-4/48"):
- Data: Binance SPOT, 1-hour candles.
- Bands: basis = SMA(close, 30); span = ATR(30) (simple mean of true range); upper4 = basis + 4*span.
- Entry: LONG at the close of the first 1h bar whose close is above upper4 (previous bar's close was not above it).
- Exit: at the close 48 bars (48 hours) later. No stop, no target. One position at a time; signals during a trade are ignored.
- Costs: 0.075% fee + 0.02% slippage per side (0.19% round trip).

Hidden period: 2025-11-01 .. 2026-10-31. Tested exactly once.

PASS criteria (all required):
1. BTCUSDT: mean net return per trade > 0 AND beats the year-matched random-entry baseline with p < 0.10.
2. ETHUSDT (second coin, identical settings): same two conditions.
Also reported (not used for pass/fail): SOL, BNB, XRP; year/period stats; max drawdown during trades.

Note: on the development data this strategy already FAILED the Deflated Sharpe test (1,584 trials).
Even a pass here would be weak evidence; a fail ends the search.
