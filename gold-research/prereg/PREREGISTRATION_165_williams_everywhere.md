# Pre-registration #165 — "Williams Everywhere": the FROZEN #112 rule on markets it has never seen
Written 2026-11-24 BEFORE any data of these markets is downloaded. Cumulative trials before: 350,289.
Rationale: Larry Williams built the volatility breakout on S&P 500 / bond futures; AQR (Moskowitz-Ooi-Pedersen 2012,
Hurst-Ooi-Pedersen 2017) show trend/breakout edges are weak per market but robust across many; the honest public gold
studies (AaroNLaU0307, caleblauhx, datxbt) conclude single-instrument gold edges do not confirm. Our gold #112 passed
discovery, confirmation, vault and OANDA. If the rule is a real phenomenon, it should appear on other liquid markets
with NO parameter change. Lab precedent: BTC cross-check of #112 was positive (descriptive, gold-short).

## Rule (identical to #112, nothing re-fitted)
Day = 17:00 -> 17:00 New York; buy stop at open + 0.6 × previous day's range, sell stop at open − 0.6 × range; first
touched wins (both in one hourly bar -> worse outcome); one trade per day; exit at the day's close. Lab engine.

## Markets (Dukascopy H1 BID; data 2012-01 .. 2026-10, whatever is available) and assumed Exness-like round-trip costs
| market | Dukascopy | round-trip spread (price units) |
|---|---|---|
| US500 | USA500IDXUSD | 0.6 |
| Nasdaq 100 | USATECHIDXUSD | 2.0 |
| DAX 40 | DEUIDXEUR | 2.0 |
| WTI oil | LIGHTCMDUSD | 0.04 |
| USDJPY | USDJPY | 0.012 |
| EURUSD | EURUSD | 0.00010 |
| BTC | Binance BTCUSDT 1h (if reachable) | 6.40 |
+ 2 × 0.1 bp slippage everywhere. No swap (intraday). Gold #112 included for the portfolio (cost 0.24/4000 + 2×0.1bp).

## Tests
1. Per market, 2012-2026: mean net bp, t, one-sided p; random-time p (lab.summ). Holm over the 7 markets.
   A market "confirms Williams" if Holm-adjusted p < 0.05 AND net > 0 in both halves (2012-2018, 2019-2026).
2. Basket: equal-volatility monthly portfolio of all markets with ≥ 5 years of data + gold; Sharpe and max DD vs gold
   alone; D > 0 required in both halves. Correlations reported.
3. Verdict labels: "Williams is general" if ≥ 3 markets confirm; "gold-specific" if 0-1; else "mixed".
4. DSR of the basket's daily P&L with N = 350,297 reported.
Trials added: 8 (7 markets + basket).
