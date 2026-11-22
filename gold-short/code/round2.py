"""Tests #71-#74 (prereg/PREREGISTRATION_71_74_round2.md). usage: python round2.py disc|conf|vault"""
import sys, json, numpy as np, pandas as pd
import short_batch as sb
from short_batch import *


def regime_exits(X, on, hold):
    ks = np.flatnonzero(on); ex = []
    for k in ks:
        xd = min(k + hold, X.nd - 1)
        for kk in range(k + 1, xd + 1):
            if not on[kk]: xd = kk; break
        ex.append(xd)
    return ks, ex


def donch(X, N=55, Xd=20, stop=2.0):
    lo = pd.Series(X.L).shift(1).rolling(N).min().values
    hi = pd.Series(X.H).shift(1).rolling(Xd).max().values
    ks = np.flatnonzero(X.C < lo); ex = []
    for k in ks:
        xd = X.nd - 1
        for kk in range(k + 1, X.nd):
            if X.C[kk] > hi[kk]: xd = kk; break
        ex.append(xd)
    return X.day_cands(ks, [stop] * len(ks), None, ex)


def trap(X, R=20, H=3, buf=0.25):
    prior = pd.Series(X.H).shift(2).rolling(R).max().values   # max H over d-R-1..d-2
    rng = X.H - X.L; CLV = np.where(rng > 0, (X.C - X.L) / np.where(rng > 0, rng, 1), 0.5)
    Hm1 = np.r_[np.nan, X.H[:-1]]
    ks = np.flatnonzero((Hm1 > prior) & (X.C < prior) & (CLV < 0.5))
    stops = [(max(Hm1[k], X.H[k]) + buf * X.ATR[k] - X.M.c[int(X.E[k])]) / X.ATR[k] for k in ks]
    return X.day_cands(ks, stops, [H] * len(ks))


def fair(X, W=750, zin=2.0, zout=0.5, hold=40):
    s = fred("DFII10"); p = fred_asof(s, X.days, 2); ry = np.where(p >= 0, s.values[np.clip(p, 0, None)], np.nan)
    y = np.log(X.C); z = np.full(X.nd, np.nan)
    for d in range(W, X.nd):
        xx = ry[d - W:d]; yy = y[d - W:d]; ok = np.isfinite(xx)
        if ok.sum() < W * 0.9: continue
        b, a = np.polyfit(xx[ok], yy[ok], 1); res = yy[ok] - (a + b * xx[ok]); sd = res.std()
        if np.isfinite(ry[d]) and sd > 0: z[d] = (y[d] - (a + b * ry[d])) / sd
    ks = np.flatnonzero(z >= zin); ex = []
    for k in ks:
        xd = min(k + hold, X.nd - 1)
        for kk in range(k + 1, xd + 1):
            if z[kk] < zout: xd = kk; break
        ex.append(xd)
    return X.day_cands(ks, [4.0] * len(ks), None, ex)


def quietdn(X, n=100, vw=20, usevol=True):
    s = sma(X.C, n); sl = s < np.r_[np.full(20, np.nan), s[:-20]]
    vol = pd.Series(X.R).rolling(vw).std(); med = vol.rolling(250).median()
    on = (X.C < s) & sl & ((vol < med).values if usevol else True)
    ks, ex = regime_exits(X, on, 20)
    return X.day_cands(ks, [3.0] * len(ks), None, ex)


V2 = {"DONCH_55_20": (donch, dict(N=55, Xd=20)), "DONCH_20_10": (donch, dict(N=20, Xd=10)),
      "TRAP_20_H3": (trap, {}), "FAIR_750_z2": (fair, {}), "QUIETDN_100": (quietdn, {})}

if __name__ == "__main__":
    which = sys.argv[1]; P = {"disc": DISC, "conf": CONF, "vault": VAULT}[which]
    if which == "vault": assert OPEN_VAULT
    M = Market(); X = Ctx(M); print("bars", len(M.c), M.idx.min(), M.idx.max(), flush=True)
    res = {}
    for name, (fn, kw) in V2.items():
        s, tp = evaluate(X, name, fn, kw, P); res[name] = s
        print(f"{which:5s} {name:14s} n={s['n']:5d} net={s['mean_bp']:7.2f}bp t={s['t']:5.2f} gross={s.get('gross_bp',0):6.2f} "
              f"x2={s.get('net2_bp',0):6.2f} win={s.get('win',0)} pf={s.get('pf')} dd={s.get('maxdd_pct')} rand={s.get('rand_bp')} p_rand={s.get('p_rand')}", flush=True)
    names = list(res); adj = holm([res[k].get("p1", 1.0) for k in names])
    for k, a in zip(names, adj): res[k]["holm_p"] = round(float(a), 4)
    print({k: res[k]["holm_p"] for k in names})
    json.dump(res, open(f"{HERE}/results_71_74_{which}.json", "w"), indent=1, default=float)
