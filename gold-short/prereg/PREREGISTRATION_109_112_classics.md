# Pre-registration #109-#112: famous published strategies, original rules, no optimisation. Written BEFORE computing.
- **Trials:** 48,730 + 6 = 48,736 (Holm over the 6 primary variants).
- **Data:**
  - Daily OHLC 2004-2023 from Dukascopy hourly BID: the day ends 17:00 New York (as in #100). Hourly bars are used inside the day when the intraday order matters.
  - Bundesbank closes 1968-1998 (close-only adaptations where noted).
  - Vault 2024+ sealed.
- **Costs per round trip:**
  - A = 0.24/4000 + 2 x 0.1 bp = 0.80 bp.
  - Raw = 0.10/4000 + 0.2 bp = 0.45 bp.
- **Swap:** long 1.079e-4 per calendar day held; short 0.
- **PRIMARY = cost A, swap-free** (the same convention as #97-#103). With-swap and Raw are always reported.
- **Pass:** discovery 2004-2016 net > 0, t >= 2, Holm < 0.05, random p < 0.05. Every applicable confirmation (1968-1998 close-only; 2017-2023): net > 0.
- **Then:** the portfolio check vs Sonic H1 (daily P&L correlation; does it add?), the audit, the vault once.
- Sonic is never filtered or resized.
- **Prior overlap:**
  - #71 tested short-only Donchian 55/20 and 20/10 (failed). The Turtle tests here are long+short with the original Turtle rules.
  - #20 (intraday ORB) is related to the Williams breakout but not the same rule.

## #109 Connors RSI(2) (Connors & Alvarez, "Short Term Trading Strategies That Work", 2008)
- **Long:** RSI(2) (Wilder) < 10 and close > SMA200 -> buy at the close. Exit at the first close > SMA5.
- **Variant:** RSI2_LONG (primary). The short mirror (RSI(2) > 90, close < SMA200, exit at a close < SMA5) is reported descriptively.
- **Confirmation:** 1968-1998 (closes) and 2017-2023.

## #110 Turtle (Faith, "Way of the Turtle", 2007; the original Turtle rules)
- **N** = 20-day Wilder ATR. **Unit** = 1% equity risk per 1N (P&L measured in % equity).
- **Entry:** System 1 = 20-day breakout; System 2 = 55-day breakout (stop entry at the breakout level, gap -> open).
- **Pyramiding:** add 1 unit at each +0.5N from the last entry, up to 4 units. All stops at 2N from the most recent unit.
- **Exit:** System 1 at the 10-day opposite breakout; System 2 at the 20-day one (stop orders, gap -> open), or at the 2N stop.
- **Same-day conflicts are resolved conservatively:** stop before add/target.
- **System 1 filter:** skip a 20-day breakout if the last S1 breakout signal (taken or not) would have been a winner, with the 55-day failsafe entry.
- **Variants:** TURTLE_S1, TURTLE_S2. Long and short.
- **1968-1998 close-only adaptation:** breakouts, exits and stops evaluated on closes; N = 20-day Wilder average of |dC|.

## #111 IBS (Internal Bar Strength; Pagonidis 2014 / quantitative trading folklore)
- IBS = (C - L)/(H - L). If IBS < 0.2 -> buy at the close, sell at the next day's close.
- **Variants:** IBS (plain), IBS_SMA200 (only if close > SMA200).
- **Confirmation:** 2017-2023 only (needs H/L).

## #112 Larry Williams volatility breakout ("Long-Term Secrets to Short-Term Trading", 1999)
- **Levels:** buy stop at today's open + 0.6 x yesterday's (H - L); sell stop at open - 0.6 x range.
- The first level touched (ordered by hourly bars; if both are in the same hour, the trade is counted as a loss) opens the trade at the level (gap -> the bar open). Exit at the day's close (17:00 NY), no overnight.
- **Variant:** WILLIAMS_06.
- **Confirmation:** 2017-2023 only.
- **Random baseline:** the same days, a random direction.
