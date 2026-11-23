# Pre-registration #135-#138 (round 2). Written BEFORE computing. Common rules + Amendment A (rate-based swap).
Trials before: 128,756. #135 adds 72, #136-#138 add 3 -> 128,831.

## Luck threshold (clarified, applies from now on)
For every family: threshold = 95th percentile over >= 10 null runs of max( the family's own null statistic, the max t of a random-rule null from the #133 generator topped up to the cumulative trial count ), on the same circular shift. Statistic = t(net1) per trade in discovery.

## #135 ML walk-forward (ridge), 72 trials
- Targets: the 72 (window, stop) same-day outcomes of #133 (36 windows x {no stop, 0.5 ATR}); the model predicts the LONG gross return g of that window.
- Features (all known at entry): the 78 #133 conditions for entry hour E (0/1) + 17 continuous: r1, range/ATR14, CLV, (C - SMA k)/ATR14 for k = 5,10,20,50,100,200, RSI2, RSI14, r5, r20, ATR5/ATR20, rv20, ret-so-far/ATR14, range-so-far/ATR14, last-hour return/ATR14 (NaN -> 0 after standardising with the training mean/sd).
- Model: ridge regression, alpha = 0.1 x n_train (fixed, not tuned), standardised features, intercept.
- Walk-forward: expanding window from 2004-01; train through year Y-1, predict year Y. Discovery statistic over Y = 2008..2016; confirmation Y = 2017..2023 (annual retrain, expanding).
- Trade: long if prediction > that day's primary round-trip cost (0.24/price + 0.2 bp), short if prediction < -cost, else flat.
- Stat: t(net1) per trade over 2008-2016 (>= 150 trades). Null: 20 runs, whole pipeline with the target circularly shifted (by 250..n-250 days) relative to the features, + the random-rule top-up to the cumulative count.
- Survivors: t > threshold, t(net2) >= 2, random-time p < 0.05; cluster corr > 0.7; <= 10 to confirmation; Holm over those (net1 > 0, net2 > 0, Holm p < 0.05).

## #136 ASIANBRK ("London breakout", forex/gold trading lore): Asian range = high/low of the bars 19:00-03:00 NY. From 03:00 to 15:00 NY a buy stop at the Asian high and a sell stop at the Asian low (first touched wins), protective stop = the opposite side of the range, exit at 16:00 NY.
## #137 PREFOMC (Lucca & Moench 2015, pre-FOMC announcement drift): long from the open of the 14:00 NY bar on the trading day before a scheduled FOMC announcement to the close of the 13:00 NY bar on the announcement day (just before the 14:00/14:15 statement). Scheduled meetings from federalreserve.gov (unscheduled 2020-03-03, 2020-03-15 removed). One swap rollover.
## #138 TOM (Lakonishok & Smidt 1988, turn of the month): long from the close of the second-to-last trading day of the month (open of the next day's first bar) to the close of the 3rd trading day of the new month. Swap per rollover.
- #136-#138 = one family of 3: Holm within, plus the threshold above, plus all common gates (random-time placebo; two-sided random direction for #136).
