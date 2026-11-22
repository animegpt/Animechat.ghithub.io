"""#77 HEDGE (prereg/PREREGISTRATION_75_77_phase2.md). usage: python hedge77.py disc|conf|vault"""
import sys, json, numpy as np, pandas as pd
from shortlib import *
from short_batch import Ctx, sma

RISK = 0.003


def sonic_trades(X):
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
        rows.append((M.idx[xi] + M.step, net / (abs(e - stop) / e), s)); busy = int(np.searchsorted(X.H1last, xi))
    return pd.DataFrame(rows, columns=["t", "R", "side"]).set_index("t")


def overnight(X):
    M = X.M; ny = (M.idx).tz_convert("America/New_York").tz_localize(None)
    endh = (ny + pd.Timedelta(hours=1)).hour; dow = ny.dayofweek
    e = np.flatnonzero((endh == 16) & (dow <= 3)); x = np.flatnonzero(endh == 20)
    j = pd.Series(e, index=ny[e].normalize()).to_frame("e").join(pd.Series(x, index=ny[x].normalize()).to_frame("x"), how="inner")
    i = j.e.values; xx = j.x.values
    net = (M.c[xx] - M.c[i]) / M.c[i] - np.array([M.cost(a) for a in i]) - np.array([M.cost(b) for b in xx])
    return pd.Series(2.0 * net, index=M.idx[xx] + M.step)


def nyday(idx): return idx.tz_convert("America/New_York").tz_localize(None).normalize()


def hedge(X, son, rule):
    M = X.M; E = X.E; T = M.idx[E] + M.step       # checkpoint times
    s200 = sma(X.C, 200); below = X.C < s200
    st = son.copy(); st["win"] = st.R > 0; eq = st.R.cumsum(); st["dd"] = eq - eq.cummax()
    st["l3"] = (~st.win).rolling(3).sum() == 3
    p = np.searchsorted(st.index.values, T.values, side="right") - 1      # last closed Sonic trade at checkpoint
    if rule == "STREAK3": cond = np.where(p >= 2, st.l3.values[np.clip(p, 0, None)], False)
    else: cond = np.where(p >= 0, st.dd.values[np.clip(p, 0, None)] <= -5, False)
    pos = (cond & below).astype(float)
    c = M.c[E]; ret = np.zeros(len(E))
    ret[1:] = -pos[:-1] * (c[1:] - c[:-1]) / c[:-1]
    chg = np.abs(np.diff(np.r_[0, pos])); costs = chg * np.array([M.cost(i) for i in E])
    r = ret - costs
    return pd.Series(r, index=T), pos


def stats_(x):
    eq = x.cumsum(); dd = float((eq - eq.cummax()).min())
    return {"sharpe": round(float(x.mean() / x.std() * np.sqrt(252)), 3), "maxdd_pct": round(dd * 100, 2),
            "total_pct": round(float(x.sum() * 100), 2)}


if __name__ == "__main__":
    which = sys.argv[1]; P = {"disc": DISC, "conf": CONF, "vault": VAULT}[which]
    if which == "vault": assert OPEN_VAULT
    M = Market(); X = Ctx(M); son = sonic_trades(X); ov = overnight(X)
    days = pd.bdate_range(P[0].tz_localize(None), min(P[1], M.idx.max()).tz_localize(None) - pd.Timedelta(days=1))
    agg = lambda s: s.groupby(nyday(s.index)).sum().reindex(days).fillna(0.0)
    base = agg(son.R * RISK) + agg(ov)
    out = {"base": stats_(base), "sonic_only": stats_(agg(son.R * RISK)), "overnight_only": stats_(agg(ov)),
           "sonic_trades": int(((son.index >= P[0]) & (son.index < P[1])).sum())}
    for rule in ("STREAK3", "DD5R"):
        h, pos = hedge(X, son, rule); hd = agg(h); w = base + hd
        s = stats_(w); b = out["base"]
        on = pos[(M.idx[X.E] >= P[0]) & (M.idx[X.E] < P[1])].mean()
        q = {"with": s, "hedge_alone": stats_(hd), "on_share": round(float(on), 3),
             "dd_reduction_pct": round(100 * (1 - s["maxdd_pct"] / b["maxdd_pct"]), 1),
             "profit_change_pct": round(100 * (s["total_pct"] / b["total_pct"] - 1), 1), "corr_hedge_base": round(float(np.corrcoef(hd, base)[0, 1]), 3)}
        q["pass"] = bool((s["sharpe"] > b["sharpe"] or q["dd_reduction_pct"] >= 25) and q["profit_change_pct"] >= -20)
        out[rule] = q
    print(json.dumps(out, indent=1))
    json.dump(out, open(f"{HERE}/results_77_{which}.json", "w"), indent=1)
