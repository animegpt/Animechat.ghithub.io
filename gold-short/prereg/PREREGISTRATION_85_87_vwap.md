# Pre-registration #85-#87: VWAP on gold. Written BEFORE any computation for these tests.
- **Data:** Dukascopy XAUUSD 1-minute BID 2017-2023 (gold-data-cache; the loader drops >= 2024 unless OPEN_VAULT=1).
- **PAXG/USDT** 1-minute klines from data.binance.vision, 2020-08..2023-12 (downloaded through 2023 only), with real exchange volume.
- **Periods:** discovery 2017-2020, confirmation 2021-2023, vault 2024-2026 (once, after an independent audit).
- **Trial count:** N_trials = 94 + 3 = 97 for the Deflated Sharpe.
- **Prior seen:** the old vwap_study / vwap_long (touch, 2-sigma bands, side-at-NY-open), all ~0, with VWAP = TWAP.

## Common
- **Typical price** = (H+L+C)/3. **VWAP** = cumulative sum(TP x volume) / sum(volume) from the anchor; volume = Dukascopy minute volume (tick-based).
- **PLACEBO (mandatory):**
  - TWAP = the cumulative mean of TP from the same anchor (equal weights), with the identical rule.
  - VWAP must beat TWAP: paired daily (or weekly) P&L difference > 0 with day-clustered t >= 2. Otherwise "the secret is not in VWAP".
- **Execution:** signal at bar close -> fill at the OPEN of the next minute. P&L marked bar by bar.
- **Costs per side:**
  - A: 0.12 USD + 0.1 bp.
  - B (Raw): 0.015 USD + 0.035 USD commission + 0.1 bp.
  - The spread part is x3 if the fill minute is in a glib news window.
  - A flip = 2 sides.
- **Statistics:** day-clustered t (session P&L per day); Holm over the K=3 strategy variants of #85-#86.

## #85 ZA: Zarattini & Aziz (2023) VWAP trend rule on gold
- **Rule as published** (from secondary sources; SSRN was not reachable): long when price is above the session VWAP, short when below, flip on each cross, flat at the end of the session. The paper uses QQQ/TQQQ 2018-2023 on intraday (1-minute) bars.
- **Gold session:** New York 09:30-16:00 (the same clock as the paper). The anchor is the 09:30 NY bar.
- **Position from the first bar close at/after 09:35 NY:** side = sign(C - VWAP), re-evaluated at every bar close. The last position closes at the close of the 15:59 bar (the 15:55 5-minute bar).
- **Variants:** ZA_1m (1-minute bars) and ZA_5m (5-minute bars, decisions on 5m closes, fills at the next minute open).
- **Reason (paper):** VWAP is the institutional benchmark. Price above it means buyers are paying up versus the day's average (demand imbalance), and intraday trends persist (intraday momentum).
- **Pass:** net(B) > 0, day-t >= 2, Holm p < 0.05, net(A) reported; AND VWAP minus TWAP daily t >= 2. Then confirmation (same), then gates and the audit.

## #86 AVWAP: weekly anchored VWAP trend (H1 decisions)
- **Anchor:** the first bar of the trading week (Sunday 18:00 New York).
- At each H1 close (Mon 00:00 .. Fri 15:00 NY), position = sign(C - AVWAP_week); fill at the next minute open.
- Flat from the Friday 16:00 NY bar close (no weekend holding). Flips cost as above.
- **Variant:** AVWAP_WEEK.
- **Placebos:**
  - (1) TWAP from the same anchor.
  - (2) Random-anchor AVWAP: 200 simulations, each week's anchor shifted by U(0, 48) hours forward (still before the week's decisions start, so decisions start after the shifted anchor + 1 h). p = share of sims with mean daily net >= real.
- **Reason:** anchored VWAP = the average cost basis of everyone who traded since the anchor. Above it, the week's buyers are in profit (supportive); below it, they are trapped (supply).
- **Pass:** net(B) > 0, day-t >= 2, Holm p < 0.05, beats TWAP (paired t >= 2) AND random-anchor p < 0.05.

## #87 REALVOL: does real volume change VWAP? (descriptive, no trading claim)
- **On PAXG/USDT 2020-08..2023-12 (real Binance volume):**
  - Session VWAP (NY 09:30 anchor) vs TWAP: median |VWAP - TWAP| in bp at each minute, and the share of minutes where sign(C - VWAP) == sign(C - TWAP).
  - The ZA rule on PAXG prices (VWAP vs TWAP), reported with zero costs only, to see whether the volume weighting changes the decisions.
- **Same measures for Dukascopy XAUUSD** (tick volume) on the same dates.
- **Interpretation fixed now:**
  - Sign agreement >= 95% and |VWAP - TWAP| < 2 bp median -> volume weighting adds essentially nothing at the decision level.
  - **Caveat:** PAXG volume is crypto-venue flow, not COMEX/LBMA flow.
