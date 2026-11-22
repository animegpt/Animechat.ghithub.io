# Pre-registration #84: DC overshoot fade on SILVER (XAGUSD), an out-of-market test of the signal
Written BEFORE any silver number was computed.
- **Numbering:** the user called this #83; #83 was already used by PREREGISTRATION_83_dc_fade_forward.md (the gold demo forward test), so this is #84.

## Data
- User-supplied silver-data.tar.gz (sha256 prefix e652ac8de534f862 verified).
- Dukascopy XAGUSD 1-minute BID 2023-11-01 .. 2026-10-30 (939 daily files). Prices /1000.
- **Sanity check before use:** prices must lie within ~20..60 USD.
- DC fade has never been run on silver in this project, so the whole window is a clean sample.

## Rules (#58 variant B, verbatim, both sides)
- M1 closes; directional change with threshold theta.
- **Signal:** after an up-DC, a close >= dcPrice x (1 + 2 theta) -> SHORT; after a down-DC, a close <= dcPrice x (1 - 2 theta) -> LONG. One fade per DC leg.
- **Entry:** OPEN of the next minute.
- **Stop:** 3 theta from the entry, checked intrabar on minute high/low; a gap fills at the minute open.
  - The stop is also checked on the entry minute itself, exactly as code/dcfade58.py.
- **Exit:** the first new DC on a minute close (checked from the minute after entry), or 24 h (1440 minutes), at that minute's close.
- **No entry** when the New York hour of the signal minute is 00-02, 16 or 17.
- One position at a time. The port is identical to dcfade58.run (same state machine) plus a side filter.

## Variants (6)
- theta in {0.2%, 0.3%} x side in {both, long only, short only}.

## Statistics
- **Gross** bp per trade (no costs).
- **Day-clustered t:** trading day starts 18:00 New York.
- **Random baseline:** 500 simulations.
  - Each real trade is matched by a random entry minute in the same calendar month, at the same minute of day (New York), with the same side, the same 3-theta stop, and the same exit rule (first DC after entry from the real DC event sequence, or 24 h).
  - p = share of sims with mean gross >= real.
- **Net (information only):** silver spread 0.025 USD at the actual price + 0.1 bp slippage per side.

## Pass rule (signal is "a market law")
- theta 0.2%, BOTH sides: mean gross > 0 AND day-clustered t >= 2 AND random p < 0.05.
- The other 5 variants are descriptive.

## Comparison
- Gold XAUUSD, same rules, same window 2023-11..2026-10, reported side by side.
- **Disclosure:** that is gold's sealed vault window. DC fade on gold 2024-26 was already computed and seen in #58 ("seen_2024_26"), so this re-run reveals nothing new about that window for this idea. The vault remains sealed for every other idea.

## Decision (user's rule)
- Silver confirms -> continue with the GoldDCFade demo forward test (#83).
- Silver does not confirm -> close the DC file permanently.
