# Amendment A to #158-#161 — live account facts (written 2026-11-24 BEFORE any number of this study)
Source: the user's local MT5 session, same day.
1. Live sizes on the real account: InpRiskPct = 0.3, InpOnLev = 2.0 (the prereg used the capital-plan stage-1 sizes
   0.15 / 1.0). All portfolio tables are reported at BOTH: "plan" (Sonic 0.15 %, Overnight ×1.0, Williams ×0.5) and
   "live" (Sonic 0.3 %, Overnight ×2.0, Williams ×0.5). Model gates (#159) use the plan sizes as pre-registered.
2. Live long swap on XAUUSDc = −894.4 points per night = 0.8944 $/oz (the prereg's 0.4316 is the old value).
   Scenario B ("today") uses 0.8944 / 4000 per rollover (Wed ×3). Added scenario B0 = 0.4316 / 4000 (old swap) for
   comparison. Scenario A (historical) unchanged. Shorts: no swap (confirmed by the user).
3. Account: USC cent, contract 1 oz, the EA sizes with tick value (no cent bug). Shared risk inputs: InpDDGuard 15 %,
   InpDayLimit 3 %, InpMaxLev 20 (not simulated, as in the prereg).
