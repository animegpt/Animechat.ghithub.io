# Pre-registration #97-#100 "the long field" (days to months). Written BEFORE any computation for these tests.
- **Trials:** 48,619 + 10 = 48,629. Holm over all 10 discovery variants.
- **Data:**
  - Dukascopy XAUUSD hourly BID 2004-2023: daily close = the bar closing 17:00 New York; H4 = 4-hour UTC bars. Vault 2024+ excluded.
  - Bundesbank Frankfurt fixing in USD/oz 1968-06..1998-12: close only.
  - FRED DFII10.
- **Costs (user):** spread 0.24/4000 + 0.1 bp per side = 0.80 bp per round trip.
- **Swap:**
  - With swap: long 0.4316 USD/oz/night at today's price = 1.079e-4 per calendar day held; short 0.
  - Swap-free: none.
  - **PRIMARY = swap-free** (the user is moving to a swap-free account). With-swap is always reported. A winner that fails with swap is labelled "swap-free only".
- **Periods:**
  - Discovery 2004-2016 (#99: 2003-2016).
  - Confirmation A: 1968-1998 (close-only ideas #97, #98).
  - Confirmation B: 2017-2023.
- **Pass:**
  - Discovery: net > 0, t >= 2, Holm < 0.05.
  - Every applicable confirmation: net > 0 and t >= 1.5.
  - Max drawdown (1x notional, summed returns) < 25% in each period.
  - Random-direction baseline p < 0.05 in discovery: the same trades/months with random signs, 1,000 simulations.
- **Then:** portfolio check vs Sonic/Overnight (correlation, Sharpe, DD), the audit, and the vault once.
- **Sonic is never filtered or resized.** Any winner is a separate strategy.

## #97 DC follow on daily closes (large scale law, #39 extension)
- Directional change on daily closes with threshold theta. Always in the market: long after an up-DC, short after a down-DC, flipping at each opposite DC (the reverse DC is the stop, evaluated on closes). Entry/exit at that day's close.
- **Variants:** theta = 2%, 3%, 5% (3).
- Long-only and short-only legs reported descriptively.
- **t:** per-trade.
- **Prior:** #39 (H1 bars) saw follow at 2% positive in both periods with t < 2.

## #98 Time-series momentum, monthly (Moskowitz-Ooi-Pedersen 2012)
- At each month-end close: sign of the past L-month return -> hold long or short (1x) through the next month.
- **Variants:** L = 3, 6, 12 months (3).
- **t:** of monthly net returns.
- **Disclosure:** a near-repeat of #47 (daily-rebalanced TSMOM with 21/63/126/252-day lookbacks), which failed. This monthly version is run at the user's request.

## #99 Real-yield regime (monthly)
- At each month-end: d = DFII10(latest obs <= month-end - 2 business days) - DFII10(about 63 business days earlier).
- **Variants (2):**
  - RY_LS: long if d < 0, short if d > 0.
  - RY_LF: long if d < 0, else flat.
- Next-month holding.
- **Periods:** discovery 2003-2016, confirmation B 2017-2023. No 1968 data (TIPS start 2003).

## #100 Sonic R on bigger bars
- Exactly the live Sonic rules (dragon EMA34 H/L/C, EMA89 trend, pullback-break, stop max/min(10-bar extreme, close +/- 0.5 ATR), exit on a close beyond the dragon or 240 bars), on bid bars.
- Stops checked intrabar on the HOURLY highs/lows inside the bigger bar.
- **Variants (2):** H4 (UTC 4h bars), D1 (17:00 NY daily bars).
- **Disclosure:** H4 was seen descriptively in the original Sonic study (+34.5 bp/trade, t vs random 1.23).
- **Confirmation:** B only (Bundesbank has no highs/lows).
