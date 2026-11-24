# Pre-registration #164 — "Asian drift": long gold during Asian hours, inside one trading day (no rollover, no swap)
Written 2026-11-24 BEFORE computing it. Origin = external literature, not our data:
- Blose, Gondhalekar & Kort (2018, J. Economics & Finance 42: 526-549): gold overnight returns significantly positive,
  day returns negative (COMEX, London fix). Blose & Gondhalekar (2014, Applied Economics Letters).
- Donati & Jung (CBS master thesis): hat-shaped intraday pattern, gold rises in eastern hours, falls the rest of the day.
Why now: the live long swap (0.894 $/oz) kills the 16->20 NY Overnight trade (#158). A window that opens AFTER the
17:00 NY rollover and closes BEFORE the next one pays no swap by construction.
Prior lab coverage: "E_session_asia" (gold-short, P2_E) produced 0 trades (broken); hour windows were part of the
conditional brute-force/GP searches (#133/#144/#146). Cumulative trials before: 350,287.

## Rule (fixed)
Every trading-day key Mon-Fri (17:00 NY -> 17:00 NY; the Sunday evening belongs to Monday's key):
- W1 (primary): BUY at the open of the 19:00 NY bar, SELL at the close of the 02:00 NY bar (= 03:00 NY, London open).
- W2: BUY at the open of the 20:00 NY bar, SELL at the close of the 01:00 NY bar (02:00 NY).
Both bars must exist in the same day key. No stop, no filter. Long only.

## Costs (Dukascopy H1 BID, lab engine)
net1 (A): 0.12/entry + 0.12/exit price + 2 × 0.1 bp. net2 (B = C, no swap): 0.24/4000 + 2 × 0.1 bp.
Stress (reported): spread ×2 (Asian-hour spreads can be wider).

## Gates (all)
1. Discovery 2004-2016: net > 0 and t ≥ 2 under BOTH net1 and net2; random-time p < 0.05 (lab.summ, 2000 sims);
   Holm over the 2 windows (net2 one-sided p) < 0.05.
2. Confirmation 2017-2023: net > 0 under net2 (and reported under net1).
3. Silver clean ground 2023-2026 (silver cost 0.025 $ on price): net > 0, one-sided p < 0.10.
4. DSR of daily P&L 2004-2023 with N = 350,289: reported; ≥ 0.95 for "passes", else "probable, not proven".
5. Vault 2024-2026: only after 1-3 pass AND an independent audit; the user decides on the one look.
