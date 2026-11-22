# Installing GoldDCFade (forward test #83) on a separate Raw/Zero Demo account

**Important:** run it in a **separate MT5 terminal**, on a **Demo** account, completely away from the real GoldComboAI.

## 1) Separate MT5
1. Download MT5 again from Exness, and at install time pick a **new folder**, e.g. `C:\MT5_DCFade`. This gives you a second copy of MT5 that runs alongside your real one.
2. Open the new copy, then: File -> Login to Trade Account -> your **Raw or Zero Demo** account.
3. Make sure the symbol is `XAUUSD` (on Raw/Zero it can carry a suffix; see Market Watch).

## 2) Install the robot
1. In the new copy: File -> Open Data Folder -> `MQL5\Experts\`. Copy `GoldDCFade.mq5` there.
2. Open MetaEditor (F4), open the file and press **Compile (F7)**. You must see `0 errors, 0 warnings`.
   - I could not compile it myself (my environment has no MT5). If any error or warning shows up, send me the line and I'll fix it right away.
3. Back in MT5: open an **XAUUSD M1** chart and drag GoldDCFade onto it.
   - Common tab: tick Allow Algo Trading.
   - Make sure the Algo Trading button at the top is green.

## 3) Settings (Inputs)
| Setting | Value | Note |
|---|---|---|
| InpRiskPct | 0.25 | Risk per trade on the 3-theta stop |
| InpFixedLot | 0 | Or a fixed lot (e.g. 0.01) if you prefer |
| InpMaxSpread | 0.10 | No entry if the spread is above $0.10 |
| InpServerUTC | 0 | Exness server = UTC |
| InpMagic | 770201 | Do not change. It only touches its own trades |

**The signal rules (theta, 2 theta, 3 theta, 24h) are fixed inside the code as constants. Don't change them during the test.**

## 4) Check it works
- **Experts tab:** at start you should see a line like `GoldDCFade #83 on XAUUSD | digits .. contract .. tick value ..`, then `DC state rebuilt from 5000 bars`.
- **Every trade** prints `DCFade ENTRY ...` and then `DCFade exit ...`.
- **The log file:** File -> Open Data Folder -> `MQL5\Files\GoldDCFade_trades.csv` (one row per closed trade).
  - In the Strategy Tester, the file goes to the tester agent's folder instead (`Tester\Agent-...\MQL5\Files`).

## 5) Quick Strategy Tester run (to confirm the code works, NOT to judge it)
1. Strategy Tester: Expert = GoldDCFade, Symbol = XAUUSD, Period = M1, Model = **Every tick based on real ticks**, Dates = the last two months, Deposit = 10000 USD.
2. **Compare with my reference:** `gold-short/mt5/reference_trades_2026-09_10.csv` holds the trades the rules should produce for Sep-Oct 2026 in Dukascopy data.
   - My reference: **about 4 trades a day**, mostly closed by DC, about 9% by SL and about 3% by the 16:45 NY close.
   - Late 2023 was calmer: 1.6 trades a day.
   - Small differences are normal (Exness vs Dukascopy prices, spread filter). A large difference (e.g. 10 trades a day, or none at all) = a bug. Tell me.

## 6) During the test (until 300 trades or 3 months)
- **Don't change anything.** And don't close trades by hand.
- **Once a week (or at the end),** send me `GoldDCFade_trades.csv` and I'll compute the verdict per the pre-registration:
  - (1) mean signal_bp >= +0.6;
  - (2) mean net_bp > 0;
  - (3) day-clustered t >= 1.5.
- **Rollover:** the robot force-closes trades at **16:45 New York**, so no trade crosses the rollover or the gold break. That is 21:45 UTC in winter and 20:45 UTC in summer.
