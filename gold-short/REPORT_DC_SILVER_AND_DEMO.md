# DC overshoot fade: silver test (#84) and the GoldDCFade robot (#83)

## 1) Silver (#84): the signal is confirmed before costs ✅
- **Data:** hash verified (e652ac8de534f862), 939 minute files, 2023-11 .. 2026-10.
- **Price note:** silver was not 20-50 USD across the whole window. It rose from 22 to **121 in January 2026**, then fell back to about 58. The path is continuous with no bad ticks, so the /1000 scale is correct.
- **Rules:** #58-B verbatim. Entry at the next minute's open, stop 3 theta inside the minute, exit at the next DC or after 24 h.
- **Port check:** on gold 2024-26 it reproduces #58 (gross 1.46 vs 1.47, net 0.59 vs 0.61).

| Market | theta | Side | Trades | Per day | Gross (bp) | Day-t | Random | p | Net (real spread) | Gross by year |
|---|---|---|---|---|---|---|---|---|---|---|
| **XAG** | **0.2%** | **Both** | 8545 | 11.0 | **+1.43** | **3.59** | +0.21 | **0.002** | -4.10 | 23: +0.5, 24: +1.6, 25: +0.9, 26: +1.7 |
| XAG | 0.2% | Long | 4345 | 5.6 | +2.04 | 3.34 | +0.40 | 0.002 | -3.48 | |
| XAG | 0.2% | Short | 4374 | 5.7 | +0.66 | 1.44 | +0.03 | 0.068 | -4.83 | |
| XAG | 0.3% | Both | 4453 | 5.8 | +1.56 | 2.15 | -0.04 | 0.008 | -3.81 | |
| XAG | 0.3% | Long | 2205 | 2.9 | +2.73 | 2.43 | -0.17 | 0.006 | -2.66 | |
| XAG | 0.3% | Short | 2304 | 3.0 | +0.36 | 0.43 | +0.07 | 0.37 | -4.96 | |
| **XAU** | **0.2%** | **Both** | 2804 | 3.6 | **+1.46** | **3.10** | -0.13 | **0.002** | +0.59 (0.24$) | 23: +1.2, 24: +1.4, 25: +1.1, 26: +1.7 |
| XAU | 0.2% | Long | 1375 | 1.8 | +2.56 | 3.68 | +0.49 | 0.002 | +1.69 | |
| XAU | 0.2% | Short | 1446 | 1.9 | +0.36 | 0.56 | -0.69 | 0.06 | -0.52 | |
| XAU | 0.3% | Both | 1326 | 1.7 | -0.55 | -0.52 | -0.31 | 0.60 | -1.42 | |

**Pre-registered verdict:** gross > 0, t >= 2 and random p < 0.05 at theta 0.2% both sides on silver -> **PASS**.

**Same pattern in both metals:**
- The same size, about +1.4 bp gross at theta 0.2%.
- Positive in every year in both.
- In both, the edge is concentrated in the **long side** (fading sharp drops): +2.0 / +2.6 bp vs +0.4 / +0.7 for shorts.
  - This matches everything we learned in the short file.
  - **This is a post-hoc observation. It does NOT change the robot's rules** (the pre-registration says both sides, no edits).
- **The difference:** at theta 0.3% silver keeps the signal, but gold loses it.
- **Silver net is clearly negative** (a 0.025$ spread is about 5 bp on silver), as expected. That's why we test the signal on silver and trade it on gold.

## 2) The GoldDCFade robot (#83)
- **File:** `mt5/GoldDCFade.mq5`. Magic 770201, M1, the #58-B rules fixed as constants in the code.
- **Exit:** at the next DC, after 24 h, at **16:45 New York**, or by the broker-side SL at 3 theta from the actual fill.
- **Filters:**
  - No entries in New York hours 00-02 and 16-17.
  - No entry if the spread is above 0.10$.
- **Sizing:** risk 0.25% on the stop distance, or a fixed lot. It reads digits, contract size and tick value from the symbol.
- **SafeClose:** retries every 30 s, the same as GoldComboAI. It never touches any position that isn't its own.
- **CSV:** every trade with signal time and price, actual fill (slippage), spread, SL, exit reason, commission, swap, and signal_bp / fill_bp / net_bp.

### Amendment to your instruction (recorded before any run)
- **21:45 UTC becomes 16:45 New York:**
  - In summer the gold break starts at 21:00 UTC, so 21:45 would have crossed the rollover and the swap.
  - 16:45 New York = 21:45 UTC in winter and 20:45 UTC in summer.
- **No separate no-entry window around 21:45:** the New York 16:00-17:59 filter already covers it.

### ⚠️ What I could NOT do
- **I couldn't compile it or run the Strategy Tester:** my environment is Linux with no MT5 or MetaEditor.
- **In their place:**
  - I reviewed the code line by line for warning causes (type conversions, datetime arithmetic, unused variables).
  - I wrote `code/dc83_reference.py`, which simulates the robot's rules exactly, and exported reference trade lists to compare against the tester:
    - `mt5/reference_trades_2023-11_12.csv`: **1.6 trades/day**, exits 83% DC / 11% SL / 6% EOD.
    - `mt5/reference_trades_2026-09_10.csv`: **4.0 trades/day** (a volatile period), exits 89% DC / 8% SL / 3% EOD.
  - Trades per day are near the research (1-3) in normal conditions, and rise with volatility.
- **If MetaEditor shows any error or warning,** send it to me and I'll fix it right away.

## The decision now
- Silver confirmed the signal -> **run the robot on the Raw Demo** for 300 trades or 3 months.
- The verdict follows the pre-registration exactly (signal >= +0.6, net > 0, t >= 1.5).
- If it fails, the DC file is closed permanently.
