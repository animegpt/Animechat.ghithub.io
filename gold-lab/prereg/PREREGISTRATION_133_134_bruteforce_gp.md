# Pre-registration #133 (structured brute force, 50,000 rules) and #134 (genetic programming). Written BEFORE computing.
Common rules: PREREGISTRATION_LAB_COMMON.md. Trials before: 48,756 (after #123-#132). #133 adds 50,000 -> 98,756. #134 adds 30,000 -> 128,756.

## Universe (both searches): same-day trades, no overnight, no swap
- Entry at the OPEN of the hourly bar starting at NY hour E, exit at the CLOSE of the bar ending at NY hour X, inside the 17:00->17:00 NY day.
- E in {19, 0, 3, 6, 8, 9, 10, 12, 14}; X in {3, 8, 10, 12, 14, 16}; X after E in day order -> 36 windows.
- Stop variants: none, or a protective stop at 0.5 x ATR14(daily, as of t-1) from the entry (intrabar, gap -> open, entry bar not checked since entry is at the open).
- Direction long or short. -> 144 outcome series. One trade per day per rule.
- Costs/periods per common rules (primary = 0.24/price + 0.1bp/side). Rules need >= 150 discovery trades.

## Condition library (all computable at the entry time; percentile bins use a rolling PAST 250-day window only)
Prior day t-1: return tercile (3); range/ATR14 tercile (3); CLV <0.25 / >0.75 / middle (3); inside day, outside day (2); close above H(t-2), close below L(t-2) (2); >=3 consecutive up closes, >=3 down (2).
Trend: close(t-1) above/below SMA 5,10,20,50,100,200 (12); close(t-1) is the highest/lowest close of the prior N days, N=5,10,20,55 (8); RSI2 <10, >90, RSI14 <30, >70 (4); 5-day and 20-day return terciles (6); close(t-1) above last week's high / below last week's low / above last month's high / below last month's low (4).
Volatility: ATR5/ATR20 tercile (3); 20-day realized vol percentile tercile (3).
Intraday so far (day open 17:00 NY -> the bar before E): return-so-far tercile (rolling past percentiles at the same E) (3); price at E vs yesterday: above PDH / below PDL / inside and above PDC / inside and below PDC (4); range-so-far/ATR tercile (3); last-hour return tercile (3); last bar closed at the day's high so far / at the day's low so far (2).
Calendar: day of week (5); first / last trading day of the month (2).
Plus "always". Total 78 conditions. For E=19 the intraday conditions use the bars 17:00-19:00 only (2 bars).

## #133 generation (seed 133): all 78 single conditions x 144 outcomes = 11,232 rules, plus 38,768 random (condition pair from different groups, outcome) draws without replacement = 50,000 rules exactly.
- Score: t of net1 (primary) per trade, discovery 2004-2016.
- **Luck threshold:** 20 null re-runs. Each null circularly shifts the outcome series by a random number of days (>= 250 and <= n-250) relative to the conditions (kills alignment, keeps drift, autocorrelation and the cost structure) and evaluates the same 50,000 rules PLUS 48,756 further random pair rules from the same generator, so each null search has the cumulative size 98,756. Threshold = 95th percentile of the 20 null maxima of t(net1).
- Survivors: t(net1) > threshold, t(net2) >= 2, n >= 150, and random-time p < 0.05 (same entry hour and holding, random days). Cluster by daily-P&L correlation > 0.7 (keep the best per cluster), at most 10 sent to confirmation.
- Confirmation: net1 > 0 and net2 > 0, AND Holm over the candidates sent (one-sided p of net1) < 0.05.
- Then: clean ground, DSR (N = cumulative, V[SR] = cross-rule variance of the annual Sharpe of the 50,000 real rules), audit, one vault look, portfolio — per common rules.

## #134 genetic programming (seed 134)
- Genome: (window E/X, stop variant, direction, AND of 1..4 literals; a literal is a condition or its negation). Population 1,000, 30 generations = 30,000 evaluations (duplicates are counted). Tournament selection (k=5), crossover of literal sets 0.7, mutation 0.3 (swap a literal / flip negation / change window / add or drop a literal), elitism 20.
- Fitness = discovery t(net1) if n >= 150 else -inf; minus 0.1 per literal beyond 2 (parsimony).
- Luck threshold: 10 null GP runs, identical settings, on circularly shifted outcomes (as #133), each topped up with random rules from the #133 generator to the cumulative size 128,756. Threshold = 95th percentile of the 10 null maxima (of raw t, without parsimony).
- Survivors/confirmation/clean ground/DSR/audit/vault/portfolio exactly as #133. Holm over the GP candidates sent to confirmation (max 10, after correlation clustering, also clustered against #133 candidates).
