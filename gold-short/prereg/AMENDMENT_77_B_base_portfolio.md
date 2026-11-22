# Amendment B to #77 (written AFTER seeing the discovery output of the original #77 spec: full disclosure)

## What went wrong
- The pre-registered base portfolio included plain Overnight (every night, 2x) under cost scenario (a). It loses -402% over 2004-2016: the 16:00/20:00 NY fills sit in the x5 roll-spread window, and #51 already showed the unfiltered Overnight has no edge.
- That base (Sharpe -2.64) makes the "Sharpe improves" criterion meaningless. Both hedges "passed" only because the base was terrible. **That pass is VOID.**

## Change
- The base portfolio = plain Sonic R H1 at 0.3% risk per trade (the reproducible core of the live EA). Everything else in #77 is unchanged: hedge rules, 1.0x notional, criterion.
- **What I saw before writing this:**
  - Sonic-only discovery stats (Sharpe 0.459, maxDD -13.28%, total +41.6%).
  - Each hedge's standalone discovery stats (STREAK3 +20.1%, Sharpe 0.24; DD5R -15.1%, Sharpe -0.12).
  - So the discovery outcome of this amendment is largely foreseeable and **carries no evidential weight**. Only the confirmation (2017-2023, untouched) counts.
- **Slot 2 (#76 failed):** the hedge rule that passes the amended discovery criterion with the larger margin goes to confirmation, alone.
