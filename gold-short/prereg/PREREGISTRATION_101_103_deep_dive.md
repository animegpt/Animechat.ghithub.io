# Pre-registration #101-#103 "deep dive". Written BEFORE any computation for these tests.
- **Trials:** 48,629 + 5 = 48,634. Holm over the 4 t-based variants of #101-#102. #103 is a portfolio criterion.

## Data and disclosures
- **Silver:** Dukascopy XAGUSD hourly BID 2018-01..2026-10 (user archive). No historical silver exists at Bundesbank (BBEX3 has only the DM gold fixing) or FRED (SLVPRUSD 404), so #101 has no 1968-1998 confirmation.
- **Gold:** Dukascopy hourly BID 2004-2023 (vault excluded); Bundesbank fixing USD/oz 1968-1998.
- **FRED:** NASDAQCOM (1971+), VIXCLS (1990+). SP500 on FRED starts only 2016-11 (licence), so it is not used.
- **Disclosure for #102:** #70 (SHORT gold 5 days after a VIX spike: ratio >= 1.4 over 6 days and VIX >= 20) was seen in discovery 2004-2016: n = 27, gross -45.5 bp for the short, i.e. gold tended to RISE. The V20 variant here is therefore partly informed by #70.
- **Disclosure for #103:** Sonic H4 standalone was seen (#100: +22 bp/trade, t 1.65 in 2004-2016; -1.5 bp in 2017-2023 descriptive).
- **Daily close** = the last hourly close at or before 17:00 New York.

## Costs and swap
- **Gold spread** 0.24/P and **silver spread** 0.025/P (P = the fill price), + 0.1 bp slippage per side per leg.
- **Long swap:** 1.079e-4 per calendar day held, applied to whichever leg is long (silver assumed equal to gold). Short 0.
- **Scenarios:** with swap and swap-free. PRIMARY = swap-free for #101 and #103; with swap for #102 (user: every night held is charged).

## #101 Gold/silver pair (market neutral)
- r = ln(gold close / silver close) daily. z = (r - mean_N) / sd_N over the previous N days (excluding today).
- **Entry at the daily close** when |z| >= 2:
  - z >= 2 (gold rich): SHORT gold + LONG silver, equal USD notional (1 unit each leg).
  - z <= -2: the mirror.
- **Exit at the close when:** z crosses 0, OR |z| >= 4 (stop), OR after 60 trading days. One pair position at a time.
- **Return** = the sum of the two legs' returns per unit leg notional, minus costs.
- **Variants:** PAIR_60, PAIR_250 (N).
- **Periods:** discovery 2018-2021 (after the N warm-up); confirmation 2022-2023; vault 2024-2026.
- **Random baseline:** the same entry days and exits with a random direction (1,000 simulations).
- **Pass:**
  - Discovery: net > 0, t >= 2, Holm < 0.05, random p < 0.05, max DD (summed) < 25%.
  - Confirmation: net > 0, t >= 1.5.
  - Expect very few trades. A pass needs them anyway.

## #102 Flight to safety (equity crash -> gold up), LONG only
- **Signal day d:**
  - N2: NASDAQCOM daily return <= -2%.
  - V20: VIXCLS daily change >= +20%.
- **Entry:** 2004+: the gold close at 17:00 NY of day d (after the 16:00 equity close). 1971-1998: the Bundesbank fixing of the next business day (the d fixing is earlier than the US close).
- **Hold:** 5 trading days. One position at a time. A new signal during a trade does not extend it.
- **Variants:** N2_H5, V20_H5. Holding 1 and 10 days reported descriptively.
- **Random baseline:** the same number of long entries per year at random days, the same 5-day hold and costs (1,000 simulations). This must beat gold's own drift.
- **Periods:** discovery 2004-2016; confirmation A 1971-1998 (V20 from 1990); confirmation B 2017-2023; vault after the audit.
- **Pass:** discovery net (with swap) > 0, t >= 2, Holm < 0.05, random p < 0.05; each confirmation net > 0 and t >= 1.5.

## #103 Sonic H4 as an additional, independent strategy
- Sonic H1 (live rules) at 0.3% risk/trade + Sonic H4 (same rules on 4h UTC bars, stops intrabar on hourly bars) at 0.15% risk/trade, vs Sonic H1 alone at 0.3%.
- No H1 trade is skipped or resized.
- **Metrics per period:** monthly Sharpe of summed P&L, max drawdown, H1-H4 monthly correlation, annual return.
- **Pass (both discovery 2004-2016 and confirmation 2017-2023):** combined monthly Sharpe > H1-alone Sharpe AND combined maxDD <= 1.1 x H1-alone maxDD.
