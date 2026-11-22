"""Tests #65-#70 (pre-registered in prereg/). Builds candidates per variant, simulates on minutes, splits periods.
usage: python short_batch.py [disc|conf|vault]   (vault needs OPEN_VAULT=1)"""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, __import__("os").path.dirname(__file__))
from shortlib import *

INF = 1e18


class Ctx:
    def __init__(self, M):
        self.M = M; D = M.d; self.D = D
        self.C = D.c.values; self.H = D.h.values; self.L = D.l.values; self.ATR = D.atr.values; self.R = D.r.values
        self.E = D.entry.values; self.nd = len(D)
        self.days = D.index                       # naive dates (day key)
        # last minute before each period end (force close)
        self.cut = {}
        for P in (DISC, CONF, VAULT):
            self.cut[P] = np.searchsorted(M.idx.values, P[1].to_datetime64(), side="left") - 1
        H1 = M.m.resample("1h", label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
        pos = pd.Series(np.arange(len(M.idx)), index=M.idx)
        lastpos = pos.resample("1h", label="left", closed="left").last().reindex(H1.index)
        self.H1 = H1; self.H1last = lastpos.values.astype(np.int64)

    def cap(self, i, x):
        """force-close at the end of the period that contains entry i"""
        t = self.M.idx[i]
        for P in (DISC, CONF, VAULT):
            if P[0] <= t < P[1]: return min(x, self.cut[P])
        return x

    def day_cands(self, ks, stops_atr, holds, exit_days=None):
        out = []
        for j, k in enumerate(ks):
            if k + 1 >= self.nd: continue
            xd = exit_days[j] if exit_days is not None else min(k + holds[j], self.nd - 1)
            i = int(self.E[k]); x = int(self.E[xd]) if xd < self.nd else len(self.M.c) - 1
            x = self.cap(i, x)
            if x <= i: continue
            a = stops_atr[j]
            stop = self.M.c[i] + a * self.ATR[k] if np.isfinite(a) else INF
            out.append({"i": i, "stop": stop, "xmax": x, "k": int(k), "hold": int(xd - k), "a": float(a)})
        return out


def sma(x, n): return pd.Series(x).rolling(n).mean().values


# ------------------------------------------------------------------ hypotheses
def crash(X, k=1.5, H=1, stop=1.0, clv=0.25):
    sig20 = pd.Series(X.R).shift(1).rolling(20).std().values
    rng = X.H - X.L
    CLV = np.where(rng > 0, (X.C - X.L) / np.where(rng > 0, rng, 1), 0.5)
    ks = np.flatnonzero((X.R <= -k * sig20) & (CLV <= clv))
    return X.day_cands(ks, [stop] * len(ks), [H] * len(ks))


def exhaust(X, Z=3.0, hold=15, buf=0.5, n=50):
    z = (X.C - sma(X.C, n)) / X.ATR
    zmax = pd.Series(z).rolling(5).max().values
    s20 = sma(X.C, 20)
    ks = np.flatnonzero((zmax >= Z) & (X.C < np.r_[np.inf, X.C[:-1]]))
    hh5 = pd.Series(X.H).rolling(5).max().values
    ex = []; stops = []
    for k in ks:
        xd = min(k + hold, X.nd - 1)
        for kk in range(k + 1, min(k + hold, X.nd - 1) + 1):
            if X.C[kk] < s20[kk]: xd = kk; break
        ex.append(xd)
        stops.append((hh5[k] + buf * X.ATR[k] - X.M.c[int(X.E[k])]) / X.ATR[k])   # in ATR units from entry
    return X.day_cands(ks, stops, None, ex)


def macro(X, L=5, hold=20, mode="both"):
    days = X.days
    out = np.ones(X.nd, bool)
    for name in (["DFII10"] if mode == "ry" else ["DTWEXBGS"] if mode == "usd" else ["DFII10", "DTWEXBGS"]):
        s = fred(name); p = fred_asof(s, days, 2); v = s.values
        ok = (p - L >= 0)
        d = np.where(ok, v[np.clip(p, 0, None)] - v[np.clip(p - L, 0, None)], np.nan)
        if name == "DTWEXBGS": ok &= days >= pd.Timestamp("2006-01-01") + pd.offsets.BDay(L + 3)
        out &= ok & (d > 0)
    ks = np.flatnonzero(out)
    ex = []
    for k in ks:
        xd = min(k + hold, X.nd - 1)
        for kk in range(k + 1, min(k + hold, X.nd - 1) + 1):
            if not out[kk]: xd = kk; break
        ex.append(xd)
    return X.day_cands(ks, [3.0] * len(ks), None, ex)


def fix(X, ent=(14, 0), ext=(15, 5), days=(0, 1, 2, 3, 4)):
    M = X.M
    if not hasattr(X, "lon"):
        X.lon = M.idx.tz_convert("Europe/London").tz_localize(None)
        X.lonmin = X.lon.hour * 60 + X.lon.minute
        X.londate = X.lon.normalize()
    em = ent[0] * 60 + ent[1]; xm = ext[0] * 60 + ext[1]
    ei = np.flatnonzero(X.lonmin == em); xi = np.flatnonzero(X.lonmin == xm)
    es = pd.Series(ei, index=X.londate[ei]); xs = pd.Series(xi, index=X.londate[xi])
    j = es.to_frame("e").join(xs.to_frame("x"), how="inner")
    j = j[j.index.dayofweek.isin(days)]
    out = []
    for i, x in zip(j.e.values, j.x.values):
        x = X.cap(int(i), int(x))
        if x > i: out.append({"i": int(i), "stop": INF, "xmax": int(x), "hold": int(x - i), "a": np.inf})
    return out


def sonic_short(X, n=200, slope=20, mode="trend", filt=True):
    H1 = X.H1; o, h, l, c = (H1[k].values for k in "ohlc")
    ema = lambda x, s: pd.Series(x).ewm(span=s, adjust=False).mean().values
    eh, el, ec, e89 = ema(h, 34), ema(l, 34), ema(c, 34), ema(c, 89)
    pc = np.r_[c[0], c[:-1]]; tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    mid = (eh + el) / 2
    sh5 = lambda x: np.r_[np.full(5, np.nan), x[:-5]]
    dn = (mid < e89) & (mid < sh5(mid)) & (e89 < sh5(e89))
    touch = pd.Series(h >= ec).rolling(5).max().values > 0
    short_ = dn & touch & (c < el) & (np.r_[c[0], c[:-1]] >= np.r_[el[0], el[:-1]])
    hh10 = pd.Series(h).rolling(10).max().values
    # daily filter from last COMPLETED daily bar (end = day 15:30 NY)
    dend = (pd.DatetimeIndex(X.days) - pd.Timedelta(days=0)).tz_localize(None) + pd.Timedelta(hours=15, minutes=30)
    dend = dend.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
    s = sma(X.C, n); sl = s - np.r_[np.full(slope, np.nan), s[:-slope]]
    okd = (X.C < s) & ((sl < 0) if mode == "trend" else True)
    h1close = H1.index + pd.Timedelta(hours=1)
    dpos = np.searchsorted(dend.values, h1close.values, side="right") - 1
    okh = np.where(dpos >= 0, okd[np.clip(dpos, 0, None)], False) if filt else np.ones(len(c), bool)
    ks = np.flatnonzero(short_ & okh & (np.arange(len(c)) > 300))
    out = []
    for k in ks:
        stop = max(hh10[k], c[k] + 0.5 * atr[k])
        xe = min(k + 240, len(c) - 1)
        for kk in range(k + 1, min(k + 240, len(c) - 1) + 1):
            if c[kk] > eh[kk]: xe = kk; break
        i = int(X.H1last[k]); x = X.cap(i, int(X.H1last[xe]))
        if x > i: out.append({"i": i, "stop": stop, "xmax": x, "hold": int(xe - k), "a": (stop - c[k]) / atr[k], "hk": int(k)})
    X.h1atr = atr
    return out


def vix(X, ratio=1.4, H=5, floor=20.0, stop=2.0):
    s = fred("VIXCLS"); p = fred_asof(s, X.days, 1); v = s.values
    cur = v[p]; mn = pd.Series(v).rolling(6).min().values[p]
    ks = np.flatnonzero((cur / mn >= ratio) & (cur >= floor) & (p >= 6))
    return X.day_cands(ks, [stop] * len(ks), [H] * len(ks))


VARIANTS = {
    "CRASH_k1.5_H1": (crash, dict(k=1.5, H=1)), "CRASH_k1.5_H5": (crash, dict(k=1.5, H=5)),
    "CRASH_k2.0_H1": (crash, dict(k=2.0, H=1)), "CRASH_k2.0_H5": (crash, dict(k=2.0, H=5)),
    "EXHAUST_Z3": (exhaust, dict(Z=3.0)), "EXHAUST_Z4": (exhaust, dict(Z=4.0)),
    "MACRO_L5": (macro, dict(L=5)), "MACRO_L20": (macro, dict(L=20)),
    "FIX_1400_1505": (fix, {}),
    "SONICDN_200_20": (sonic_short, {}),
    "VIX_1.4_H5": (vix, {}),
}
KIND = lambda name: "fix" if name.startswith("FIX") else "sonic" if name.startswith("SONIC") else "day"


# ------------------------------------------------------------------ random baseline
def random_base(X, t, kind, P, nsim=500, seed=11):
    M = X.M; rng = np.random.default_rng(seed)
    if len(t) < 5: return np.nan, np.nan
    yrs = t.index.year.values
    if kind == "day":
        dy = pd.DatetimeIndex(X.days).year.values
        pools = {y: np.flatnonzero((dy == y) & (np.arange(X.nd) < X.nd - 1)) for y in np.unique(yrs)}
    elif kind == "sonic":
        hy = X.H1.index.year.values
        pools = {y: np.flatnonzero((hy == y) & (np.arange(len(hy)) > 300)) for y in np.unique(yrs)}
    else:
        my = X.M.year_of_min
        pools = {y: np.flatnonzero(my == y) for y in np.unique(yrs)}
    ent = []; stp = []; xm = []
    for s in range(nsim):
        for yy, hold, a in zip(yrs, t.hold.values, t.a.values):
            k = int(rng.choice(pools[yy]))
            if kind == "day":
                i = int(X.E[k]); x = int(X.E[min(k + hold, X.nd - 1)]); atrk = X.ATR[k]
            elif kind == "sonic":
                i = int(X.H1last[k]); x = int(X.H1last[min(k + hold, len(X.H1last) - 1)]); atrk = X.h1atr[k]
            else:
                i = k; x = min(k + hold, len(M.c) - 1); atrk = 0.0
            x = X.cap(i, x)
            if x <= i: x = min(i + 1, len(M.c) - 1)
            ent.append(i); xm.append(x); stp.append(M.c[i] + a * atrk if np.isfinite(a) else INF)
    r = simulate(M, ent, stp, xm)
    means = r.net.values.reshape(nsim, -1).mean(1)
    real = t.net.mean()
    return float(means.mean()), float((np.sum(means >= real) + 1) / (nsim + 1))


def evaluate(X, name, fn, kw, P, nsim=500, cmult=1.0):
    cands = fn(X, **kw)
    t = run_sequential(X.M, cands, cmult)
    tp = period(t, P)
    s = summ(tp)
    if nsim and len(tp) >= 5:
        rb, pr = random_base(X, tp, KIND(name), P, nsim)
        s["rand_bp"] = round(rb * 1e4, 2); s["p_rand"] = round(pr, 4)
    return s, tp


if __name__ == "__main__":
    which = sys.argv[1]
    P = {"disc": DISC, "conf": CONF, "vault": VAULT}[which]
    if which == "vault": assert OPEN_VAULT
    M = Market(); X = Ctx(M)
    print("minutes", len(M.c), M.idx.min(), M.idx.max(), "days", X.nd, flush=True)
    res = {}
    for name, (fn, kw) in VARIANTS.items():
        s, tp = evaluate(X, name, fn, kw, P)
        res[name] = s
        print(f"{which:5s} {name:16s} n={s['n']:5d} net={s['mean_bp']:7.2f}bp t={s['t']:5.2f} gross={s.get('gross_bp',0):6.2f} "
              f"x2={s.get('net2_bp',0):6.2f} win={s.get('win',0)} pf={s.get('pf')} rand={s.get('rand_bp')} p_rand={s.get('p_rand')}", flush=True)
    names = list(res); p = [res[k].get("p1", 1.0) for k in names]; adj = holm(p)
    for k, a in zip(names, adj): res[k]["holm_p"] = round(float(a), 4)
    print(json.dumps({k: {"holm_p": res[k]["holm_p"], "p1": round(res[k].get("p1", 1), 5)} for k in names}))
    json.dump(res, open(f"{HERE}/results_65_70_{which}.json", "w"), indent=1, default=float)
