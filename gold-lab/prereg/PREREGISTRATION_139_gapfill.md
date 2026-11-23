# Pre-registration #139 weekend-gap fade (round 3). Written BEFORE computing. Common rules + Amendment A.
Trials before 128,831; +1 -> 128,832.
- Gap = Sunday open (first bar of the Monday trading day) minus the Friday close (last bar of the previous trading day), in units of ATR14 (daily, as of Friday).
- Rule (trading lore "weekend gaps get filled"): if |gap| >= 0.25 ATR, fade it: enter at the OPEN of the 19:00 NY bar on Sunday (2 hours after the open, to avoid the widest Sunday spread), direction opposite to the gap; target = the Friday close; protective stop = entry +/- 1.0 x |gap| against the trade; time exit at the close of the 07:00 NY bar on Monday (08:00 NY). No overnight swap (exit before 17:00 NY Monday).
- Only if the gap is not already filled before 19:00 NY (if the price at the 19:00 open is already beyond the Friday close in the fade direction, no trade).
- Gates: common gates; two-sided -> random-direction p and random-time p; threshold = 95th pct of the random-rule null at the cumulative size (~4.0) per prereg 135_138.
