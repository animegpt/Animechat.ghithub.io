"""#76 SHORTAI (prereg/PREREGISTRATION_75_77_phase2.md). usage: python shortai76.py disc|conf|vault"""
import sys, json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from shortlib import *
from short_batch import Ctx, sma

HOLD = 8
CB = 0.24 / 4000 + 0.2e-4


def build(M, X):
    c, h, l = M.c, M.h, M.l; n = len(c); lc = np.log(c); S = lambda x: pd.Series(x)
    f = {}
    for k in (1, 2, 4, 8, 24, 72, 120): f[f"r{k}"] = lc - np.r_[np.full(k, np.nan), lc[:-k]]
    r1 = f["r1"]; f["v24"] = S(r1).rolling(24).std().values; f["v120"] = S(r1).rolling(120).std().values; f["vr"] = f["v24"] / f["v120"]
    pc = np.r_[c[0], c[:-1]]; tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))); atr = S(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    for s in (20, 50, 200): f[f"e{s}"] = (c - S(c).ewm(span=s, adjust=False).mean().values) / atr
    d = np.diff(c, prepend=c[0]); up = S(np.maximum(d, 0)).ewm(alpha=1 / 14, adjust=False).mean(); dn = S(np.maximum(-d, 0)).ewm(alpha=1 / 14, adjust=False).mean()
    f["rsi"] = (100 - 100 / (1 + up / dn.replace(0, np.nan))).values
    hh = S(h).rolling(24).max().values; ll = S(l).rolling(24).min().values; f["rpos"] = (c - ll) / np.where(hh > ll, hh - ll, np.nan)
    # last completed daily bar (day key = (NY+10h).normalize, day ends 14:00 NY): bar close time >= day end
    closeT = M.idx + M.step
    dend = (pd.DatetimeIndex(X.days) + pd.Timedelta(hours=14)).tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
    dpos = np.searchsorted(dend.values, closeT.values, side="right") - 1
    s200 = sma(X.C, 200); dd = (X.C - s200) / X.ATR
    f["d200"] = np.where(dpos >= 0, dd[np.clip(dpos, 0, None)], np.nan)
    nyc = closeT.tz_convert("America/New_York"); hr = nyc.hour.values; wd = nyc.dayofweek.values
    f["hs"] = np.sin(2 * np.pi * hr / 24); f["hc"] = np.cos(2 * np.pi * hr / 24); f["ws"] = np.sin(2 * np.pi * wd / 5); f["wc"] = np.cos(2 * np.pi * wd / 5)
    ndate = nyc.tz_localize(None).normalize()
    for nm, lag, key in (("DFII10", 2, "dry"), ("DTWEXBGS", 2, "dusd")):
        s = fred(nm); p = fred_asof(s, ndate, lag); v = s.values
        f[key] = np.where(p >= 5, v[np.clip(p, 0, None)] - v[np.clip(p - 5, 0, None)], np.nan)
    s = fred("VIXCLS"); p = fred_asof(s, ndate, 1); v = s.values
    f["vix"] = np.where(p >= 5, v[np.clip(p, 0, None)], np.nan); f["dvix"] = np.where(p >= 5, np.log(v[np.clip(p, 0, None)] / v[np.clip(p - 5, 0, None)]), np.nan)
    F = pd.DataFrame(f, index=M.idx)
    # trade outcome
    x = np.arange(n) + HOLD; ok = x < n; x = np.where(ok, x, n - 1)
    span = (M.idx[x] - M.idx) / pd.Timedelta(hours=1)
    mult = cost_mult(closeT)
    e = c; px = c[x]; g = (e - px) / e
    ca = (0.5 * 0.24 * mult / e + SLIP) + (0.5 * 0.24 * mult[x] / px + SLIP)
    elig = ok & (span.values <= HOLD + 2) & ((wd <= 3) | ((wd == 4) & (hr < 12))) & (M.idx >= pd.Timestamp("2006-02-01", tz="UTC"))
    F["y"] = (g > ca).astype(int); F["g"] = g; F["a"] = g - ca; F["b"] = g - CB; F["x"] = x; F["hr"] = hr
    F = F[elig].replace([np.inf, -np.inf], np.nan).dropna()
    return F


FEATS = ["r1", "r2", "r4", "r8", "r24", "r72", "r120", "v24", "v120", "vr", "e20", "e50", "e200", "rsi", "rpos", "d200",
         "hs", "hc", "ws", "wc", "dry", "dusd", "vix", "dvix"]


def model(): return make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))


def seq(F, sel):
    """one position at a time; returns rows taken"""
    pos = {ix: k for k, ix in enumerate(F.index)}
    rows = []; busy = -1
    idxpos = F["pos"].values
    for k in np.flatnonzero(sel):
        if idxpos[k] <= busy: continue
        rows.append(k); busy = F.x.values[k]
    return F.iloc[rows]


def st(r):
    n = len(r); m = r.mean(); t = m / (r.std(ddof=1) / np.sqrt(n)) if n > 2 else 0
    return {"n": int(n), "bp": round(m * 1e4, 3), "t": round(float(t), 2)}


def rand_base(F, T, nsim=1000, seed=3):
    rng = np.random.default_rng(seed); yrs = F.index.year.values; T_y = T.index.year.values
    groups = {}
    for i, (y, h) in enumerate(zip(yrs, F.hr.values)): groups.setdefault((y, h), []).append(i)
    groups = {k: np.array(v) for k, v in groups.items()}
    pick = [groups[(y, h)] for y, h in zip(T_y, T.hr.values)]
    res = {}
    for col in ("a", "b"):
        v = F[col].values; means = np.empty(nsim)
        for s in range(nsim): means[s] = np.mean([v[rng.choice(p)] for p in pick])
        res[col] = {"rand_bp": round(float(means.mean()) * 1e4, 3), "p": float((np.sum(means >= T[col].mean()) + 1) / (nsim + 1))}
    return res


if __name__ == "__main__":
    which = sys.argv[1]
    M = Market(); X = Ctx(M); F = build(M, X); F["pos"] = np.searchsorted(M.idx.values, F.index.values)
    out = {"n_rows": len(F), "feats": FEATS}
    if which == "disc":
        parts = []; coefs = {}
        for Y in range(2009, 2017):
            tr = F[(F.index.year < Y)]; te = F[F.index.year == Y]
            m = model().fit(tr[FEATS].values, tr.y.values)
            thr = np.quantile(m.predict_proba(tr[FEATS].values)[:, 1], 0.85)
            p = m.predict_proba(te[FEATS].values)[:, 1]; T = seq(te, p >= thr)
            parts.append(T); out[str(Y)] = {**st(T.a.values), "thr": round(float(thr), 4), "base_rate": round(float(tr.y.mean()), 3)}
            print(Y, out[str(Y)], flush=True)
        T = pd.concat(parts)
    else:
        P = {"conf": CONF, "vault": VAULT}[which]
        if which == "vault": assert OPEN_VAULT
        tr = F[F.index < DISC[1]]; m = model().fit(tr[FEATS].values, tr.y.values)
        thr = np.quantile(m.predict_proba(tr[FEATS].values)[:, 1], 0.85)
        te = F[(F.index >= P[0]) & (F.index < P[1])]; p = m.predict_proba(te[FEATS].values)[:, 1]; T = seq(te, p >= thr)
        out["thr"] = float(thr); out["coef"] = dict(zip(FEATS, np.round(m[-1].coef_[0], 3).tolist()))
    out["all_a"] = st(T.a.values); out["all_b"] = st(T.b.values); out["gross"] = st(T.g.values)
    out["random"] = rand_base(F[(F.index >= T.index.min()) & (F.index <= T.index.max())], T)
    out["by_year_a"] = {int(y): round(v * 1e4, 2) for y, v in T.groupby(T.index.year).a.mean().items()}
    print(json.dumps({k: out[k] for k in ("all_a", "all_b", "gross", "random", "by_year_a")}), flush=True)
    json.dump(out, open(f"{HERE}/results_76_{which}.json", "w"), indent=1)
