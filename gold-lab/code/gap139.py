"""#139 weekend-gap fade (prereg/PREREGISTRATION_139_gapfill.md)"""
import json, numpy as np, pandas as pd
import lab
from lab import run_exit, trade_row
from lablog import log
M = lab.Mkt(lab.load_hourly("XAUUSD")); D = M.D; C = D.c.values; H = D.h.values; L = D.l.values
pc = np.r_[C[0], C[:-1]]; tr = np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc))); atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
rows = []
for t in range(20, len(M.days)):
    if M.days[t].dayofweek != 0 or (M.days[t] - M.days[t - 1]).days < 3: continue
    fc = M.c[M.e[t - 1]]; so = M.o[M.s[t]]; gap = so - fc
    if abs(gap) < 0.25 * atr[t - 1]: continue
    j0 = M.dh[t, 19]; jx = M.dh[t, 7]
    if j0 < 0 or jx < 0 or jx <= j0: continue
    side = -1 if gap > 0 else 1; ep = M.o[j0]
    if (side == -1 and ep <= fc) or (side == 1 and ep >= fc): continue
    stop = ep - side * abs(gap)
    xj, xp, how = run_exit(M.o, M.h, M.l, M.c, j0, side, stop, fc, jx, False)
    rows.append(trade_row(M, side, j0, ep, xj, xp, how=how))
T = pd.DataFrame(rows)
r = lab.summ(M, T, lab.DISC, two_sided=True); print(json.dumps(r, default=float))
json.dump(r, open(f"{lab.HERE}/results/results_139_disc.json", "w"), indent=1, default=float)
log({"id": "139", "test": "weekend-gap fade (prereg 139)", "trials_added": 1, "cum_trials": 128832, "disc": r})
