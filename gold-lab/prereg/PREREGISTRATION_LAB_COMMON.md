# Pre-registration — Gold Lab common rules (applies to #123 onward). Written BEFORE any computation in this lab.
Date: 2026-11-23. Trial counter at start: **48,746** (last entry #113-#122 in gold-short/test_log.jsonl on branch claude/gold-short-pack-task-f5rkwp).

## Data
- Gold: Dukascopy XAUUSD hourly BID candles (monthly files), 2004-01 .. 2026-11, rebuilt in this session (the original pack/data parts were not available in this container; same source and same endpoint as the earlier lab's `dl_hour.py`). Vault rows (>= 2024-01-01) are physically split into a separate file and not loaded unless `OPEN_VAULT=1`.
- Trading day = 17:00 -> 17:00 New York (as #112). Daily bars built from hourly bars; days with < 10 hourly bars or weekend keys are dropped.
- 1968-1998: Bundesbank Frankfurt gold fixing (DEM/kg) / USD-DEM rate = USD gold, close only.
- Clean-ground markets (never touched in any search): Dukascopy XAGUSD hourly (2023-2026 window used), Binance BTCUSDT hourly, Dukascopy EURUSD hourly, and gold months after 2026-10 (2026-11, partial).

## Periods
- Discovery 2004-01-01 .. 2016-12-31. Confirmation 2017-01-01 .. 2023-12-31. Vault 2024-01-01 .. 2026-10-31 (one look per candidate, after an independent audit by a separate agent).

## Execution (realistic)
- Market entries at the OPEN of the hourly bar after the signal bar. Stop entries trigger inside the bar at the level; a gap through the level fills at the bar open.
- Stops are checked inside every bar after entry; a gap through the stop fills at the open. If stop and target are both inside one bar -> stop first. On the ENTRY bar: if the entry bar's range also reaches the stop, the trade is assumed stopped at the stop (worst case). If two opposite stop entries trigger in the same bar -> the worse of the two outcomes.
- One position at a time per strategy.

## Costs
- PRIMARY: spread 0.24 USD/oz round trip divided by the price at the trade (0.12/entry price + 0.12/exit price) + slippage 0.1 bp per side.
- SECOND scenario: 0.24/4000 + 0.1 bp per side. A pass requires BOTH (net > 0); the primary is the reference.
- Swap: longs pay 0.4316 USD/oz per rollover (17:00 NY), divided by the price; Wednesday rollover x3. Shorts 0.
- Silver clean ground: spread 0.025 USD/oz on price + 0.1 bp/side. BTC: 6.40 USD on price + 0.1 bp/side. EURUSD: 1.0 pip round trip (assumed Exness Standard-like) + 0.1 bp/side.

## Gates for every candidate (all must pass; nothing relaxed later)
1. Discovery: net > 0 and t >= 2 under both costs; Holm-adjusted one-sided p < 0.05 within its family (primary cost); random-direction p < 0.05 for two-sided rules (sign-flip of gross, 2000 sims) AND random-time p < 0.05 for every rule (same number of trades, same side, same entry hour-of-day and same holding length on random days of the same period, 2000 sims, compared on gross mean).
2. Confirmation: net > 0 under both costs.
3. Clean ground: the exact same rule on a clean market/period: net > 0 at that market's cost and one-sided p < 0.10.
4. Luck: for brute-force/GP families, the real best statistic must exceed the 95th percentile of the best statistic of >= 10 full null re-runs (random direction or circular shift) of a search whose size equals the cumulative trial count. Deflated Sharpe (Bailey & Lopez de Prado) of the daily P&L 2004-2023 with N = cumulative trials is REPORTED for every candidate; DSR >= 0.95 is required for the label "passes all gates". A candidate failing only DSR is labelled "probable, not proven" and is not sent to the vault on its own.
5. Independent audit (separate agent re-implements from the prereg text) -> ONE vault look: net > 0 (primary cost).
6. Portfolio: daily-P&L correlation with Sonic H1 (34/89), Overnight (16:00->20:00 NY Mon-Thu) and Williams #112; equal-vol portfolio Sharpe and max drawdown with vs without. If corr > 0.7 with an existing strategy, only the stronger is kept.
- Every test is logged in gold-lab/test_log.jsonl with the running cumulative trial count, failures included.
