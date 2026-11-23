# Pre-registration #155–#157 — Fusion lab (Williams #112 × our findings × published research)
Written 2026-11-23 BEFORE computing any of these three rules on any period. Committed to git before the first run.
Cumulative trials before: 350,214. This study adds exactly 3 (cumulative after: 350,217).

## Why these three (chosen from 15 fusion hypotheses, see REPORT_FUSION.md §2; selection made without any new computation)
- #155 F1 (Williams × short reversal): our strongest stable fact (15:00 NY bar return predicts the next bar with
  IC −0.22, same sign every year 2009–2023; #154 gross reversal real on gold and on silver) failed ONLY because it is
  smaller than the spread as a stand-alone trade. Used as an EXIT-timing change on an existing Williams position it
  costs zero extra spread and adds zero trades. This is the cleanest way to harvest an edge that is "real but below cost".
- #156 F2 (Williams × published intraday seasonality / COMEX settlement): literature (Baltussen–Da–Lammers–Martens 2021
  JFE, Gao–Han–Li–Zhou 2018 JFE: intraday momentum runs into the CLOSE of the main session; gold "day returns
  negative / overnight positive" studies) suggests the trend-following part of a breakout day is concentrated before the
  main futures session ends (COMEX gold settlement 13:30 NY). Afternoon hours after settlement are thin. Never tested
  for Williams in this lab.
- #157 F3 (Williams on two metals): if the Williams edge is a generic metal-breakout effect, it must exist on silver
  2004–2022 (never used for Williams) and a gold+silver Williams portfolio must beat gold alone.

## Data, engine, costs (unchanged from #149–#154)
- Dukascopy hourly BID, gold XAUUSD and silver XAGUSD, 2004-01 → 2026-10, `code/lab.py` (`Mkt`: trading day
  17:00→17:00 NY). Gold vault (≥ 2024-01-01) is physically split and not loaded unless OPEN_VAULT=1.
- Williams #112 exactly as `features149.williams` (open ± 0.6 × yesterday's range, stop entries, OCO, first touch wins,
  same bar → worse outcome, exit at the close of the last bar of the day = 17:00 NY).
  Engine check before anything: gold disc 2004–2016 must give n 2053, net1 +5.09bp, t 2.25.
- Costs (primary net1): spread 0.24 $ (gold) / 0.025 $ (silver) on price (half at entry price, half at exit price)
  + 2 × 0.1 bp slippage. Intraday only, no swap. net2 (gold only): 0.24/4000 + 2 × 0.1bp (reported).

## Rules
- **F1 #155** — For a Williams trade of day t, let A = the 15:00 NY bar and B = the 16:00 NY bar of day t. If B is the
  trade's normal exit bar, A = B − 1, the entry bar j0 ≤ A, and side × (close(A)/open(A) − 1) > 0 (the hour before 16:00
  moved WITH the trade), exit at close(A) (= 16:00 NY) instead of close(B). Otherwise unchanged.
- **F2 #156** — If the entry bar j0 ≤ the 13:00 NY bar of day t (C), exit at close(C) (= 14:00 NY, first hourly close
  after the 13:30 COMEX settlement) instead of 17:00. Trades entered after 14:00 NY are unchanged.
- **F3 #157** — Williams #112 unchanged, applied to silver XAGUSD with silver costs.
- No parameters. Nothing else is tried. No rule search → no luck threshold needed (stated, not skipped).

## Statistics
- F1/F2 paired difference per Williams trade: Δ = net1(variant) − net1(base) (0 when unchanged). t(Δ) over ALL Williams
  trades of the period; p one-sided. Also variant monthly Sharpe vs base (metric149.evaluate: D, t JKM).
- F3: t of net1 per trade; portfolio = equal-vol daily P&L of gold Williams + silver Williams (vol from the same period),
  annualised Sharpe vs gold alone.

## Grounds (golden rule: an idea born on gold 2004–2023 is CONTAMINATED there)
- F1 is contaminated on gold 2004–2023 (the reversal was found there) and on silver 2023–2026 (#154 looked at the
  up-hour leg there). Clean ground for F1 = **silver 2004-01-01 … 2022-12-31**.
- F2: gold 2004–2023 hourly Williams paths were never split by hour in our logs, but gold dev has been searched heavily
  (#140 level breakouts with day-close exits) → treated as development only. Clean ground = silver 2004–2022.
- F3: clean ground = silver 2004–2022 (silver Williams never computed there; #152 saw silver 2023–2026 only).
- Gold vault 2024–2026: **Williams #112 itself was opened there once (#112: n 476, +12.35bp)**. The vault is therefore
  NOT clean for Williams; it is still unseen for the DIFFERENCE Δ of F1/F2. One look at Δ only, after the audit.
- Gold after 2026-10 (November 2026, ~3 weeks): descriptive only (n ≈ 15 trades cannot carry a verdict).

## Gates (all required; nothing relaxed after seeing results)
F1 / F2:
1. Gold dev (sanity, contaminated for F1): variant net1 > 0 under net1 and net2, and Δ mean > 0, in BOTH 2004–2016 and
   2017–2023.
2. Silver 2004–2022 (clean): mean Δ > 0 with t(Δ) ≥ 2, and mean Δ > 0 in both 2004–2016 and 2017–2022.
3. Holm over the 3 hypotheses on the clean-ground one-sided p (F3 uses its net1 p): adjusted p < 0.05.
4. DSR of the monthly overlay (variant − base, silver 2004–2022, `metric149.dsr_monthly`) with N = 350,217 and
   var_sr_annual = 0.08433 (the cross-trial variance from #152, fixed now): DSR ≥ 0.95. If 1–3 pass and DSR fails →
   label "probable, not proven" (as LAB_COMMON).
5. Independent audit (separate agent re-implements from THIS text) must reproduce gold-dev and silver numbers
   (n within 1 %, mean Δ within 0.2bp). Then ONE look at the gold vault 2024-01 … 2026-10: mean Δ > 0 (net1).
F3:
1. Silver 2004–2022: net1 > 0, t ≥ 2, net1 > 0 in 2004–2016 and in 2017–2022.
2. Portfolio Sharpe (gold+silver) > gold alone in 2004–2016 AND in 2017–2023 (silver 2017–2022 for the silver leg's
   clean part; 2023 silver included only for the portfolio period alignment — disclosed).
3. Holm (as above), DSR of the silver daily P&L with the same N/var.
- "Passes" = all gates. Gates 1–3 only = "candidate, unproven". Otherwise FAIL, stated plainly.

## Deliverables
- If F1 or F2 passes: Shadow version of GoldWilliams (logs what the alternative exit would have done, does NOT change
  trading), and a Demo plan. If nothing passes: what we learned and the best next direction.
