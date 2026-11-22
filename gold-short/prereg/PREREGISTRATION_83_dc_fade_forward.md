# Pre-registration #83: GoldDCFade, a forward (live demo) test of the DC overshoot fade
Written BEFORE the EA is run anywhere. Rules are #58 variant B (the realistic post-audit #41 version), frozen. No optimisation.

## Why forward-only
- DC fade has been studied on 2017-2026 (#22-#40, #58, #80), so no clean history is left.
- The gross signal looks real (#80: +0.6..+1.3 bp gross, beats random p = 0.002; #58-B gross +1.2..+2.1 bp) but has been smaller than the costs.
- Only unseen live data can judge it now.

## Instrument and account
- XAUUSD on an Exness **Raw or Zero DEMO** account (server time = UTC; input InpServerUTC = 0).

## Rules (EA GoldDCFade.mq5, Magic 770201)
- **DC:** M1, directional change on minute CLOSES, theta = 0.2% (the same state machine as code/dcfade58.py).
- **Signal on the close of a minute:**
  - After an up-DC: close >= dcPrice x (1 + 2 theta) -> SELL.
  - After a down-DC: close <= dcPrice x (1 - 2 theta) -> BUY.
  - One fade per DC leg. The leg counts as faded even when the entry is blocked by a filter.
  - No signal on the minute where a new DC occurs.
- **Entry:** market order immediately after that minute closes (= next minute open).
- **Catastrophe stop:** 3 theta from the actual fill price, as a broker-side SL.
- **Exit (whichever comes first):**
  - The first new DC (either direction), on a minute close.
  - 24 hours after entry.
  - Force-close at 21:45 UTC (before the swap/rollover and the gold break).
  - The SL.
- **Filters (no entry):**
  - New York hours 00:00-02:59 and 16:00-17:59 (the same as #58).
  - Current spread > InpMaxSpread (default 0.10 USD).
  - Engineering addition, so the 21:45 force-close cannot bite a new trade instantly: no entries from 21:30 to 22:59 UTC.
- **Positions:** one at a time.
- **Size:** 0.25% equity risk on the 3-theta stop distance (or a fixed lot via input).

## Logged per trade (MQL5/Files/GoldDCFade_trades.csv)
- Signal time and theoretical signal price (the minute close).
- Entry time and actual fill (=> slippage), side, spread at entry, SL.
- Exit time, price and reason (DC / 24h / EOD / SL).
- Volume, commission, swap, profit USD.
- Three return measures, in bp of the entry price:
  - **signal_bp:** gross bp from the signal close to the close of the exit minute, i.e. the research definition of gross.
  - **fill_bp:** gross bp between the actual fills (includes spread + slippage).
  - **net_bp:** after commission and swap.

## Duration
Until 300 trades or 3 calendar months from the first trade, whichever comes first.

## Verdict (fixed now)
- **PASS only if ALL of:**
  - (1) mean signal_bp >= +0.6 bp (the signal is alive);
  - (2) mean net_bp > 0 after real commission and spread;
  - (3) day-clustered t of net_bp >= 1.5 (a preliminary small-sample indicator).
- **PASS** -> consider adding it to the live account at a small size (a new decision, not automatic).
- **FAIL** -> the DC file is closed permanently.
- No rule changes during the test. If the EA has a bug that makes trades differ from these rules, the test restarts from zero after the fix, and that is logged.
- Reference: code/dc83_reference.py simulates exactly these rules on historical minutes (Nov-Dec 2023, outside the sealed vault). It is used only to check the EA's behaviour (trades per day, exit mix), never as evidence.
