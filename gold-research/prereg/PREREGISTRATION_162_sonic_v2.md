# Pre-registration #162 — "Sonic v2": entry × exit × stop family on the GoldComboAI Sonic rules
Written 2026-11-24 BEFORE any number of this study. User request: "a new Sonic strategy".
Cumulative trials before: 350,225. Prior evidence: #57 (DC-reversal exits / filters on Sonic: no survivors), filters that
skip trades usually hurt (#57/#59/#60/#91); Sonic H4 (#103) failed confirmation.

## Base (= GoldComboAI v1.00 Sonic, rebuilt in code/combo158.py, 96 trades/year)
Signal on closed H1 bar i (EMA34 dragon + EMA89 trend), entry at open of i+1, stop S0 = min(LL10, C − 0.5·ATR14),
exit X0 = close beyond the far dragon band (long: C < EMA34(low)) or 240 bars, stop inside bars. No AI sizing in this
study (plain Sonic) so that the AI model does not confound the comparison; the AI-sized result is reported only.

## Family (4 × 5 × 3 = 60 variants, fixed in advance, base included)
Entries:
- E0 base.
- E1 HTF confirm: also require the EA's 4-hour Sonic trend (HTF4) to agree with the signal.
- E2 one-bar confirmation: bar i+1 must also close beyond the dragon band (EMA34 high / low); entry at open of i+2.
- E3 pullback: limit order at EMA34(close) of bar i, valid for the next 5 bars; not filled → no trade.
Exits (stop always active):
- X0 base.
- X1 faster: close beyond EMA34(close) (middle line) or 240 bars.
- X2 chandelier: trailing stop = highest high since entry − 3·ATR14 (long; short mirrored), checked inside bars; + 240 bars.
- X3 structure: exit at next open after an internal (size 5) CHoCH against the trade (EA Structure), or X0, whichever first.
- X4 breakeven: once the price has moved +1R in favour, the stop moves to the entry price; otherwise X0.
Stops:
- S0 base. S1 = C − 1.0·ATR14 (long). S2 = min(LL20, C − 0.5·ATR14).
One position at a time; no new entry on an exit bar (as the EA).

## Costs
Primary: scenario B (price 4000, live long swap 0.8944 $/oz per rollover, Wed ×3; shorts no swap; spread 0.24/4000;
slippage 2 × 0.1 bp). Also A (historical) and C (swap-free) reported.

## Metric
Monthly Sonic returns at 0.15 % risk per trade (return = 0.0015 × R). D = Sharpe(variant) − Sharpe(base),
t = Jobson-Korkie-Memmel (+ block bootstrap). Discovery 2009-2016, confirmation 2017-2023.

## Gates (all, nothing relaxed later)
1. Discovery (cost B): D > 0, t_JKM ≥ 2, Holm over the 59 non-base variants p < 0.05; mean R > 0.
2. Confirmation 2017-2023 (cost B): D > 0.
3. Combined 2009-2023: D > 0 with t ≥ 2 (JKM and bootstrap); D > 0 also under cost A.
4. Deflated Sharpe of the variant's monthly returns, N = cumulative trials (350,285), cross-trial variance from the 60
   variants: ≥ 0.95 is required for "passes"; otherwise "probable, not proven".
5. Clean ground silver 2023-01..2026-10 (silver cost): D > 0.
6. Vault 2024-2026: stays closed in this study unless a variant passes 1-5 AND an independent audit; then the user
   decides on one look.
Tie rule: among passers, the simplest change (fewest components different from base) wins.

## Deliverables
Arabic report with a table of all 60; if a winner passes: GoldComboAI change proposal (Shadow first), else what was learned.
