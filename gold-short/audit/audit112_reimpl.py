"""Independent re-implementation of #112 Williams volatility breakout (audit). Does NOT import classics109.
run: cd gold-short/code && BARS=1h GDATA=... python /tmp/claude-0/audit112/reimpl.py"""
import os, sys, json
os.environ["BARS"] = "1h"
sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd
import shortlib as sl

CUT = pd.Timestamp("2024-01-01", tz="UTC")
m = sl.load_minutes()
m = m[m.index < CUT].sort_index()
assert m.index.max() < CUT and m.index.is_unique and m.index.is_monotonic_increasing

# --- own day assignment: NY local time of bar START; a bar starting at/after 17:00 NY belongs to the next date
ny = m.index.tz_convert("America/New_York")
nyl = ny.tz_localize(None)
hr = nyl.hour.values
date = np.where(hr >= 17, (nyl + pd.Timedelta(days=1)).normalize(), nyl.normalize())
date = pd.DatetimeIndex(date)
o, h, l, c = (m[k].values for k in "ohlc")

# group boundaries
codes, uniq = pd.factorize(date, sort=False)
assert (np.diff(codes) >= 0).all()           # days are contiguous and ordered
starts = np.r_[0, np.flatnonzero(np.diff(codes)) + 1]; ends = np.r_[starts[1:], len(codes)]
days = pd.DataFrame({"d": uniq, "s": starts, "e": ends, "n": ends - starts})
days["o"] = o[starts]; days["c"] = c[ends - 1]
days["h"] = [h[a:b].max() for a, b in zip(starts, ends)]; days["l"] = [l[a:b].min() for a, b in zip(starts, ends)]
days["first_hr"] = hr[starts]; days["last_hr"] = hr[ends - 1]
days = days[(days.n >= 10) & (days.d.dt.dayofweek <= 4)].reset_index(drop=True)

diag = {"n_days": len(days), "first_bar_hour_counts": days.first_hr.value_counts().head(6).to_dict(),
        "last_bar_hour_counts": days.last_hr.value_counts().head(6).to_dict()}
gapd = days.d.diff().dt.days.values
diag["prev_day_gap_dist"] = pd.Series(gapd[1:]).value_counts().to_dict()

rows = []
for t in range(1, len(days)):
    p, r = days.iloc[t - 1], days.iloc[t]
    rng = p.h - p.l
    if rng <= 0: continue
    bu, sd = r.o + 0.6 * rng, r.o - 0.6 * rng
    side = 0; amb = False; ep = np.nan; jtrig = -1; gap = False
    for j in range(r.s, r.e):
        up, dn = h[j] >= bu, l[j] <= sd
        if up and dn: amb = True; jtrig = j; break
        if up: side, ep, gap = 1, max(bu, o[j]), o[j] > bu; jtrig = j; break
        if dn: side, ep, gap = -1, min(sd, o[j]), o[j] < sd; jtrig = j; break
    if not amb and side == 0: continue
    C = r.c
    if amb:
        gl, gs = C / bu - 1, 1 - C / sd   # long from bu / short from sd (classics109 uses (sd-C)/sd: identical)
        g = min(gl, gs); side = 1 if gl <= gs else -1; ep = bu if side == 1 else sd
    else:
        g = side * (C / ep - 1)
    rows.append(dict(t=r.d, side=side, gross=g, ep=ep, C=C, amb=amb, gap=gap, k=jtrig - r.s, hr=hr[jtrig],
                     prevgap=(r.d - p.d).days))
T = pd.DataFrame(rows)
CA = 0.24 / 4000 + 2e-5
T["netA"] = T.gross - CA
T["netP"] = T.gross - (0.24 / T.ep + 2e-5)      # spread at historical price

def st(x):
    x = np.asarray(x); n = len(x)
    if n < 3: return dict(n=n)
    return dict(n=n, bp=round(x.mean() * 1e4, 2), t=round(x.mean() / (x.std(ddof=1) / np.sqrt(n)), 2))

P = {"disc": ("2004-01-01", "2017-01-01"), "conf": ("2017-01-01", "2024-01-01")}
out = {"diag": {k: {str(a): int(b) for a, b in v.items()} if isinstance(v, dict) else v for k, v in diag.items()}}
for nm, (a, b) in P.items():
    X = T[(T.t >= a) & (T.t < b)]
    early = X.hr.isin([17, 18])
    R = {"gross": st(X.gross), "netA": st(X.netA), "netP_histprice": st(X.netP),
         "share_trig_k0": round((X.k == 0).mean(), 3), "share_trig_k<=1": round((X.k <= 1).mean(), 3),
         "share_trig_17_18NY": round(early.mean(), 3),
         "netA_excl_17_18": st(X.netA[~early]), "netP_excl_17_18": st(X.netP[~early]),
         "netA_only_17_18": st(X.netA[early]),
         "n_amb": int(X.amb.sum()), "amb_mean_bp": round(X.gross[X.amb].mean() * 1e4, 1) if X.amb.any() else None,
         "netA_excl_amb": st(X.netA[~X.amb]),
         "n_gap": int(X.gap.sum()), "gap_mean_gross_bp": round(X.gross[X.gap].mean() * 1e4, 1) if X.gap.any() else None,
         "long": st(X.netA[X.side == 1]), "short": st(X.netA[X.side == -1]),
         "prevgap_gt3": int((X.prevgap > 3).sum()), "mean_price": round(X.ep.mean(), 1),
         "trig_hour_top": {str(k): int(v) for k, v in X.hr.value_counts().head(5).items()}}
    out[nm] = R
print(json.dumps(out, indent=1, default=float))
T.to_csv("/tmp/claude-0/audit112/trades.csv", index=False)
