"""Portfolio check (reported, not a pass criterion): daily P&L of plain Sonic R H1 (both sides, unsized, 1x notional)
and plain Overnight (long 16:00->20:00 NY Mon-Thu) vs a short candidate. Equal-vol weights per period."""
import numpy as np, pandas as pd
from shortlib import *


def sonic_both(X):
    H1 = X.H1; o, h, l, c = (H1[k].values for k in "ohlc")
    ema = lambda x, s: pd.Series(x).ewm(span=s, adjust=False).mean().values
    eh, el, ec, e89 = ema(h, 34), ema(l, 34), ema(c, 34), ema(c, 89)
    pc = np.r_[c[0], c[:-1]]; tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    mid = (eh + el) / 2; sh5 = lambda x: np.r_[np.full(5, np.nan), x[:-5]]
    up = (mid > e89) & (mid > sh5(mid)) & (e89 > sh5(e89)); dn = (mid < e89) & (mid < sh5(mid)) & (e89 < sh5(e89))
    tl = pd.Series(l <= ec).rolling(5).max().values > 0; ts = pd.Series(h >= ec).rolling(5).max().values > 0
    pcl = np.r_[c[0], c[:-1]]
    L = up & tl & (c > eh) & (pcl <= np.r_[eh[0], eh[:-1]]); S = dn & ts & (c < el) & (pcl >= np.r_[el[0], el[:-1]])
    ll10 = pd.Series(l).rolling(10).min().values; hh10 = pd.Series(h).rolling(10).max().values
    M = X.M; rows = []; busy = -1
    ev = sorted([(k, 1) for k in np.flatnonzero(L) if k > 300] + [(k, -1) for k in np.flatnonzero(S) if k > 300])
    for k, s in ev:
        if k <= busy: continue
        stop = min(ll10[k], c[k] - 0.5 * atr[k]) if s == 1 else max(hh10[k], c[k] + 0.5 * atr[k])
        xe = min(k + 240, len(c) - 1)
        for kk in range(k + 1, xe + 1):
            if (s == 1 and c[kk] < el[kk]) or (s == -1 and c[kk] > eh[kk]): xe = kk; break
        i = int(X.H1last[k]); x = X.cap(i, int(X.H1last[xe])); e = M.c[i]; px = M.c[x]; xi = x
        for j in range(i + 1, x + 1):
            if s == 1 and M.l[j] <= stop: px = M.o[j] if M.o[j] <= stop else stop; xi = j; break
            if s == -1 and M.h[j] >= stop: px = M.o[j] if M.o[j] >= stop else stop; xi = j; break
        net = s * (px - e) / e - M.cost(i) - (M.side_cost_frac[xi] / px + SLIP)
        rows.append((M.idx[xi], net, s)); busy = int(np.searchsorted(X.H1last, xi))
    t = pd.DataFrame(rows, columns=["t", "net", "side"]).set_index("t")
    return t


def overnight(X):
    M = X.M; ny = M.ny.tz_localize(None); mins = ny.hour * 60 + ny.minute
    e = np.flatnonzero((mins == 959) & (ny.dayofweek <= 3)); x = np.flatnonzero(mins == 1199)
    es = pd.Series(e, index=ny[e].normalize()); xs = pd.Series(x, index=ny[x].normalize())
    j = es.to_frame("e").join(xs.to_frame("x"), how="inner")
    i = j.e.values; xx = j.x.values
    net = (M.c[xx] - M.c[i]) / M.c[i] - np.array([M.cost(a) for a in i]) - np.array([M.cost(b) for b in xx])
    return pd.DataFrame({"net": net}, index=M.idx[xx])


def daily(t):
    s = t.net.copy(); s.index = s.index.tz_convert("America/New_York").tz_localize(None).normalize()
    return s.groupby(level=0).sum()


def compare(X, cand_trades, P):
    """cand_trades: DataFrame with net and x (exit minute)"""
    son = daily(sonic_both(X)); ov = daily(overnight(X))
    ct = cand_trades.copy(); ct.index = X.M.idx[ct.x.values]; cs = daily(ct)
    idx = pd.date_range(P[0].tz_localize(None), P[1].tz_localize(None) - pd.Timedelta(days=1), freq="B")
    df = pd.DataFrame({"sonic": son, "overnight": ov, "short": cs}).reindex(idx).fillna(0.0)
    vol = df.std(); w = (1 / vol) / (1 / vol).sum()
    base = df.sonic * (1 / vol.sonic) + df.overnight * (1 / vol.overnight)
    withs = base + df.short * (1 / vol.short)
    def st(x):
        eq = x.cumsum(); dd = (eq - eq.cummax()).min()
        return {"sharpe": round(float(x.mean() / x.std() * np.sqrt(252)), 2), "maxdd_over_vol": round(float(dd / x.std()), 1)}
    # behaviour in the worst 5% of gold-down days (hedge value)
    return {"corr": df.corr().round(3).to_dict(), "base": st(base), "with_short": st(withs),
            "short_alone": st(df.short)}
