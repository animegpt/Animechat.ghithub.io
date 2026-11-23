# Pre-registration #140 structured search over intraday level breakouts (round 3). Written BEFORE computing.
Common rules + Amendment A. Trials before 128,832. This search adds exactly the number of rules generated (stated below, fixed by construction) .

## Base rules (stop entries, one trade per day, exit at 16:00 NY close, no swap)
- Entry window starts at NY hour W in {17 (day open), 3, 8} and ends at the 15:00 bar.
- Levels (computed from information before W):
  - WIL k: today's open (17:00) +/- k x yesterday's range, k in {0.2, 0.4, 0.6, 0.8, 1.0, 1.2}
  - ATR k: today's open +/- k x ATR14 (t-1), k in {0.25, 0.5, 0.75, 1.0, 1.25}
  - PD k: yesterday's high + k x ATR / yesterday's low - k x ATR, k in {0, 0.1, 0.25}
  - ASIA k: the 19:00-03:00 NY range high/low +/- k x ATR, k in {0, 0.1, 0.25} (only W = 3 or 8)
  - WEEK: last week's high/low; NDAY N: highest high / lowest low of the prior N days, N in {5, 10, 20}
- Modes: long-only (buy stop at the upper level), short-only (sell stop at the lower level), OCO both (first touched; same bar -> worse).
- Protective stop: none; the opposite level; 0.5 x ATR14 from the entry. (Entry-bar stop counts, worst case.)
- If the level is already crossed when the window opens, no trade that day (a breakout must happen inside the window).
## Filters: none + 20 conditions from the #133 library as of t-1 (never intraday): above/below SMA20, SMA50, SMA200 (6), rng lo/hi (2), r1 lo/hi (2), atrr lo/hi (2), rv lo/hi (2), inside, outside (2), clv lo/hi (2), r20 lo/hi (2).
## Size: base = (6+5+3+1+3) levels x 3 windows + 3 ASIA levels x 2 windows = 60 level-windows; x 3 modes x 3 stops = 540 base rules; x 21 filter states = 11,340 rules. Cumulative after: 140,172.
## Statistic and luck threshold
- t(net1) per trade, discovery 2004-2016, n >= 150.
- Null (20 runs): for every rule, each trade's gross return gets a random sign (same seed across rules in a run, so correlated rules stay correlated), costs re-applied; plus the random-rule top-up from the #133 generator to the cumulative size 140,172 on a circular shift. Threshold = 95th pct of the 20 maxima.
- Survivors: t > threshold, t(net2) >= 2, random-time p < 0.05, cluster corr > 0.7 (also vs Williams #112: corr > 0.7 with #112 -> dropped as a duplicate of an existing strategy), <= 10 to confirmation with Holm. Then clean ground, DSR, audit, one vault look, portfolio.
