# Pre-registration #89-#91: three new doors. Written BEFORE any return was computed on these data.
- **Trial count before:** 48,597. This adds 4 (#89) + 2 (#90) + 1 (#91) = 7, for 48,604.
- **Seen:** only the price-scale sanity check (Frankfurt fixing 1968-06-18 = 5,290 DM/kg, which is about $41/oz).

## Data
- **Gold 1968-06-18..1998-12-31:** Bundesbank BBEX3.D.XAU.DEM.EA.AC.C01 (Frankfurt fixing, DM per kg, ~13:00 CET), converted with BBEX3.D.USD.DEM.AA.AC.000 (Frankfurt official USD fixing, same session): USD/oz = DM/kg / (DM per USD) / 32.1507.
  - **Deviation from the request:** the Bundesbank no longer publishes the London USD fix (removed, like FRED's LBMA series). Its only gold price series stops at 1998, so the clean window is **1968-1998** (not 1968-2003), and **1986-1998** for COT discovery.
- **FOMC:** scheduled meetings from federalreserve.gov/monetarypolicy/fomchistoricalYYYY.htm (conference calls excluded). Decision day = the last day of the meeting.
- **COT:** CFTC legacy futures-only ("deacot", COMEX gold, market code 088691) 1986-2023; disaggregated (Managed Money) 2006-2023.
- **GVZ:** FRED GVZCLS 2008+.
- **Dukascopy XAUUSD hourly 2004-2023:** used for the #90 confirmation and for #91. Vault 2024+ excluded.

## Costs (all doors)
- 0.24 USD / P + 0.1 bp per side.
- **Long swap:** 0.4316 USD/oz per night (Exness -431.6 points/lot, point 0.001), charged relative to today's price: 1.079e-4 of notional x calendar days held (the Wednesday triple covers the weekend). Short swap 0.

## #89 DOOR 1: watch-list patterns, out-of-sample on 1968-1998 (confirmation, not discovery)
The rules are those found on 2004-2026, translated to one daily fixing (~13:00 Frankfurt). This is unavoidable with daily data and is disclosed per rule:
- **TOM** (#32): long from the fixing of trading day L-1 to the fixing of F3 (L = last trading day of the month).
- **JANFEB** (#45): long from the last December fixing to the last February fixing (one trade per year).
- **FRI** (#32 was Friday 12:00 -> 17:00 NY, intraday): daily proxy, long from the Thursday fixing to the Friday fixing.
  - This is a different window. A pass or fail here speaks for the Friday daily return, not the intraday rule.
- **PREFOMC** (#31 was 14:00 the day before -> 13:55 decision day): daily proxy, long from the fixing of the trading day before the decision day to the fixing on the decision day (which is before any US announcement).
  - Note: before 1994 the Fed did not announce decisions. The 1994-1998 subset is reported descriptively.
- **Pass (each):** same direction (net mean > 0), t >= 2 on per-trade net returns 1968-1998, AND Holm p < 0.05 over the 4.
- A pattern that passes becomes a candidate for a small EA add-on (a separate decision).

## #90 DOOR 2: COT speculator crowding
- **Positioning:** legacy Non-commercial net (long - short) / open interest, from the report as of Tuesday t.
  - Published Friday: the signal is usable from the first fixing (or the daily close) on or after Tuesday + 4 calendar days.
- **Crowding:** percentile rank of the current value within the last 156 weekly values (including the current one).
  - LONG-CROWDED >= 0.90; SHORT-CROWDED <= 0.10.
- **Variants (2; Holm over 2):**
  - **CS_LONG:** when SHORT-CROWDED starts (flag turns on), go LONG for 20 trading days. One position at a time.
  - **CL_SHORT:** when LONG-CROWDED starts, go SHORT for 20 trading days.
- **Periods:** discovery 1986-1998 (Bundesbank fixings). Confirmation 2004-2023 (Dukascopy daily closes at 17:00 NY), only for discovery qualifiers. Vault 2024-2026 after the audit.
- **Pass:** discovery net > 0, t >= 2, Holm < 0.05; confirmation net > 0, t >= 2.
  - Per the user's lesson, the live use would be sizing (x0.5 / x1.5 on Sonic/Overnight), never skipping.
  - The sizing overlay is evaluated only if the signal passes both periods.
- **Descriptive (no pass rule):** the same with Managed Money (disaggregated) 2006-2023.

## #91 DOOR 3: GVZ volatility targeting for Sonic + Overnight
- **Strategies (research versions, unchanged):**
  - Sonic R plain (unsized), H1 mid prices, 2004+, at 0.3% risk per trade.
  - Overnight AI walk-forward (gates56/raw82 pipeline, out of sample from 2012), at 2x notional.
  - Costs A, with swap.
- **Sizing:** multiplier m = clip(median(GVZ over the previous 252 days) / GVZ(previous business day), 0.5, 2.0), applied to each trade at entry.
- **Comparison (reported, not a criterion):** the same with ATR-based vol targeting, m = clip(median(ATR14 daily, 252) / ATR14 daily at entry, 0.5, 2.0).
- **Periods:** discovery 2008-06..2016 (Overnight from 2012); confirmation 2017-2023; vault after the audit.
- **Pass (both periods):** portfolio Sharpe (daily, summed P&L) with GVZ sizing > fixed sizing, AND max drawdown not larger.
