# Pre-registration #82: does an Exness Raw/Zero account improve Sonic R + AI and Overnight AI? (cost comparison only)
Written BEFORE computing. This is not a strategy search: the rules, models and thresholds are the research versions, unchanged.
The only thing that varies is the execution cost and swap.

## Strategies (reproduced from the research code in the archive, run as-is)
### Sonic R + AI sizing
- **Trades:** `sonic_ai.trades` (prepare/extra/signals/stop S0/exit C0, H1 mid prices).
- **AI sizing:** frozen model = `sonic_ai.model()` (HistGB) on the 38 `PINE_FEATS`. Trained on trades 2010-01..2016-12 with the research label (R > 0 under the research cost 0.24/price + 2 x 0.1 bp).
- **Size multiplier:** w = 0.5 + rank of p among the training predictions (0.5..1.5), as in a3/#15 "V0 frozen".
- **Out of sample:** trades entered 2017-01..2023-12.
### Overnight AI
- **Walk-forward:** exactly as gates56 / cent_sim61.
  - Features = `ml_overnight.build_dataset` (rebuilt from the raw hourly bid/ask + EURUSD, data < 2024 only), rows >= 2010.
  - Label = gross 16->20 NY minus 2 x (0.12/P16 + 0.1 bp).
  - HistGB classifier, threshold = median training probability, retrained yearly.
- **Out of sample:** years 2012..2023.
- The models and labels stay on the research cost for every scenario (the rules do not change). Only the P&L is re-costed.

## Cost scenarios (round trip, at the historical fill price P)
- **A** Standard/Cent: 0.24/P + 2 x 0.1 bp.
- **B** Raw/Zero: (0.03 + X)/P + 2 x 0.1 bp, with X = 0.07 USD/oz round trip. **This is an ESTIMATE**: the user has not yet supplied the confirmed Exness commission.
- **B2:** 2 x B.

## Swap (each scenario twice: with and without)
- **Long:** -431.6 points per lot per night, with point = 0.001 USD => 0.4316 USD/oz/night. Wednesday night counts x3. **Short:** 0.
- Applied relative to today's price: 0.4316/4000 = 1.079e-4 of notional per night, so 2017 trades are not charged an inflated relative rate.
- Nights = number of 17:00 New York rollovers crossed (Overnight 16->20 NY crosses one every night).

## Outputs
- **Per strategy x scenario (out of sample):** net per trade (bp and R for Sonic), t, annual return and max drawdown of the stand-alone strategy at the EA sizing.
- **Money simulation of the COMBO EA on 10,000 USD (= 10,000 USC cent equivalent in %), real EA rules:**
  - Sonic: 0.3% equity risk x AI multiplier.
  - Overnight: 2x equity notional on AI nights.
  - Lot step 0.01 (1 oz).
  - DD guard: half size while equity < 85% of peak.
  - Common period 2017-01..2023-12 (Overnight OOS covers it).
  - A vs B, with and without swap; B2 reported.
- **Answer:** the difference in CAGR, B vs A (with swap and without).

## Vault
2024-2026 is not loaded: only hourly files < 2024-01 are linked into the working directory.
