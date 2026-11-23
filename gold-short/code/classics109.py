"""#109-#112 classic strategies (prereg/PREREGISTRATION_109_112_classics.md). usage: BARS=1h GDATA=... python classics109.py <hist dir> disc|conf"""
import os, sys, json, numpy as np, pandas as pd
os.environ["BARS"] = "1h"
from scipy import stats
import shortlib as sl
import long97 as LF
import doors89_90 as DB

CA, CR = 0.24 / 4000 + 2e-5, 0.10 / 4000 + 2e-5; SWAP = 0.4316 / 4000


def daily_ohlc(m):
    ny = m.index.tz_convert("America/New_York").tz_localize(None); key = (ny + pd.Timedelta(hours=7)).normalize()
    mm = m[["o", "h", "l", "c"]].copy(); mm["k"] = key.values
    D = mm.groupby("k").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("o", "size"))
    return D[(D.n >= 10) & (D.index.dayofweek <= 4)].drop(columns="n"), mm


def rsi(c, n):
    d = np.diff(c, prepend=c[0]); up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / n, adjust=False).mean(); dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(50).values


def rec(d0, d1, side, g, swap_days):
    """returns gross and nets (A swapfree, A swap, Raw swapfree) as fractions"""
    sw = SWAP * swap_days if side == 1 else 0.0
    return dict(t=d0, side=side, gross=g, A=g - CA, A_swap=g - CA - sw, R=g - CR, days=(d1 - d0).days)


def rsi2(D, short=False):
    c = D.c.values; r = rsi(c, 2); s200 = pd.Series(c).rolling(200).mean().values; s5 = pd.Series(c).rolling(5).mean().values; d = D.index; out = []; k = 200
    while k < len(c) - 1:
        cond = (r[k] < 10 and c[k] > s200[k]) if not short else (r[k] > 90 and c[k] < s200[k])
        if cond:
            j = k + 1
            while j < len(c) - 1 and not ((c[j] > s5[j]) if not short else (c[j] < s5[j])): j += 1
            side = -1 if short else 1; g = side * (c[j] / c[k] - 1); out.append(rec(d[k], d[j], side, g, (d[j] - d[k]).days)); k = j + 1
        else: k += 1
    return pd.DataFrame(out)


def ibs(D, filt):
    o, h, l, c = (D[k].values for k in "ohlc"); s200 = pd.Series(c).rolling(200).mean().values; d = D.index; out = []
    v = np.where(h > l, (c - l) / np.where(h > l, h - l, 1), 0.5)
    for k in range(200, len(c) - 1):
        if v[k] < 0.2 and (not filt or c[k] > s200[k]):
            out.append(rec(d[k], d[k + 1], 1, c[k + 1] / c[k] - 1, (d[k + 1] - d[k]).days))
    return pd.DataFrame(out)


def turtle(D, entry_n, exit_n, s1filter):
    """unit = 1% equity per N; results in % equity (as fraction). Daily OHLC; close-only data have o=h=l=c."""
    o, h, l, c = (D[k].values for k in "ohlc"); d = D.index; n_ = len(c)
    pc = np.r_[c[0], c[:-1]]; tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    N = pd.Series(tr).ewm(alpha=1 / 20, adjust=False).mean().values
    hiE = pd.Series(h).shift(1).rolling(entry_n).max().values; loE = pd.Series(l).shift(1).rolling(entry_n).min().values
    hiX = pd.Series(h).shift(1).rolling(exit_n).max().values; loX = pd.Series(l).shift(1).rolling(exit_n).min().values
    hi55 = pd.Series(h).shift(1).rolling(55).max().values; lo55 = pd.Series(l).shift(1).rolling(55).min().values

    def sim_single(k0, side, px):          # hypothetical 1-unit outcome for the S1 filter
        Nk = N[k0 - 1]; stop = px - side * 2 * Nk
        for j in range(k0 + 1, n_):
            lev = max(stop, loX[j]) if side == 1 else min(stop, hiX[j])
            if (side == 1 and l[j] <= lev) or (side == -1 and h[j] >= lev):
                x = min(lev, o[j]) if side == 1 else max(lev, o[j]); return side * (x - px) > 0, j
        return side * (c[-1] - px) > 0, n_ - 1

    trades = []; k = max(entry_n, 60) + 1; last_win = False; pending_skip = None
    while k < n_:
        side = 0
        if h[k] > hiE[k] and not (l[k] < loE[k]): side, lvl = 1, hiE[k]
        elif l[k] < loE[k] and not (h[k] > hiE[k]): side, lvl = -1, loE[k]
        failsafe = False
        if side == 0 and pending_skip is not None:
            ps, pend_end = pending_skip
            if k <= pend_end and ((ps == 1 and h[k] > hi55[k]) or (ps == -1 and l[k] < lo55[k])): side, lvl, failsafe = ps, (hi55[k] if ps == 1 else lo55[k]), True
            elif k > pend_end: pending_skip = None
        if side == 0: k += 1; continue
        px0 = max(lvl, o[k]) if side == 1 else min(lvl, o[k])
        if s1filter and not failsafe:
            win, jend = sim_single(k, side, px0)
            if last_win:
                last_win = win; pending_skip = (side, jend); k += 1; continue
            last_win = win
        pending_skip = None
        Nk = N[k - 1]; units = [(px0, Nk)]; stop = px0 - side * 2 * Nk; nxt = px0 + side * 0.5 * Nk; k0 = k; exitpx = None; j = k
        while j < n_:
            if j > k0:
                lev = max(stop, loX[j]) if side == 1 else min(stop, hiX[j])
                if (side == 1 and l[j] <= lev) or (side == -1 and h[j] >= lev):
                    exitpx = min(lev, o[j]) if side == 1 else max(lev, o[j]); break
            while len(units) < 4 and ((side == 1 and h[j] >= nxt) or (side == -1 and l[j] <= nxt)):
                ep = max(nxt, o[j]) if side == 1 else min(nxt, o[j]); units.append((ep, Nk)); stop = ep - side * 2 * Nk; nxt = ep + side * 0.5 * Nk
            j += 1
        if exitpx is None: j = n_ - 1; exitpx = c[j]
        g = sum(0.01 * side * (exitpx - ep) / Nu for ep, Nu in units)
        cost_a = sum(0.01 * CA * ep / Nu for ep, Nu in units); cost_r = sum(0.01 * CR * ep / Nu for ep, Nu in units)
        days = (d[j] - d[k0]).days; sw = sum(0.01 * SWAP * days * ep / Nu for ep, Nu in units) if side == 1 else 0.0
        trades.append(dict(t=d[k0], side=side, gross=g, A=g - cost_a, A_swap=g - cost_a - sw, R=g - cost_r, days=days, units=len(units)))
        k = j + 1
    return pd.DataFrame(trades)


def williams(D, mm):
    o, h, l, c = (D[k].values for k in "ohlc"); d = D.index; out = []
    groups = {k: g for k, g in mm.groupby("k")}
    for t in range(1, len(c)):
        rng_ = h[t - 1] - l[t - 1]; bu, sd = o[t] + 0.6 * rng_, o[t] - 0.6 * rng_
        g = groups.get(d[t]);
        if g is None or rng_ <= 0: continue
        side = 0; ep = None; amb = False
        for _, b in g.iterrows():
            hb, lb = b.h >= bu, b.l <= sd
            if hb and lb: amb = True; break
            if hb: side, ep = 1, max(bu, b.o); break
            if lb: side, ep = -1, min(sd, b.o); break
        if amb:
            ga = (c[t] - bu) / bu; gb = (sd - c[t]) / sd
            gr = min(ga, gb); out.append(dict(t=d[t], side=1 if ga <= gb else -1, gross=gr, A=gr - CA, A_swap=gr - CA, R=gr - CR, days=0)); continue
        if side == 0: continue
        gr = side * (c[t] / ep - 1); out.append(dict(t=d[t], side=side, gross=gr, A=gr - CA, A_swap=gr - CA, R=gr - CR, days=0))
    return pd.DataFrame(out)


def summ(T, a, b, kind, D=None, seed=109):
    if len(T) == 0: return {"n": 0}
    T = T[(T.t >= a) & (T.t < b)]
    if len(T) < 5: return {"n": int(len(T))}
    out = {"n": int(len(T))}
    for col in ("A", "A_swap", "R"):
        r = T[col].values; t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))); eq = np.cumsum(r)
        out[col] = {"bp": round(float(r.mean() * 1e4), 2), "t": round(float(t), 2), "sum_pct": round(float(r.sum() * 100), 1),
                    "maxdd_pct": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min() * 100), 1), "p1": float(stats.t.sf(t, len(r) - 1))}
    out["win"] = round(float((T.A > 0).mean()), 3); out["avg_days"] = round(float(T.days.mean()), 1)
    rng = np.random.default_rng(seed); g = T.gross.values
    if kind == "dir":
        sims = np.array([(np.where(rng.random(len(g)) < 0.5, 1, -1) * g).mean() for _ in range(1000)])
    else:                                                                     # random long entries, same holding lengths
        c = D.c.values; idx = D.index; hold = np.maximum(1, np.round(T.days.values * 5 / 7).astype(int)); sims = []
        pool = np.flatnonzero((idx >= a) & (idx < b))
        for _ in range(1000):
            k = rng.choice(pool[pool + hold.max() < len(c)], len(g)); sims.append(np.mean(c[k + hold] / c[k] - 1))
        sims = np.array(sims)
    out["rand_gross_bp"] = round(float(sims.mean() * 1e4), 2); out["p_rand"] = float((np.sum(sims >= g.mean()) + 1) / 1001); out["gross_bp"] = round(float(g.mean() * 1e4), 2)
    return out


if __name__ == "__main__":
    H, stage = sys.argv[1], sys.argv[2]
    m = LF.hourly(); D, mm = daily_ohlc(m)
    S = {"RSI2_LONG": (rsi2(D), "long"), "RSI2_SHORT_desc": (rsi2(D, True), "dir"), "TURTLE_S1": (turtle(D, 20, 10, True), "dir"),
         "TURTLE_S2": (turtle(D, 55, 20, False), "dir"), "IBS": (ibs(D, False), "long"), "IBS_SMA200": (ibs(D, True), "long"), "WILLIAMS_06": (williams(D, mm), "dir")}
    res = {}
    P = {"disc": [("2004-01-01", "2017-01-01")], "conf": [("2017-01-01", "2024-01-01")]}[stage]
    for nm, (T, kind) in S.items():
        for a, b in P: res[nm] = summ(T, pd.Timestamp(a), pd.Timestamp(b), kind, D)
        print(stage, nm, json.dumps({k: (v if not isinstance(v, dict) else {kk: v[kk] for kk in ("bp", "t", "maxdd_pct")}) for k, v in res[nm].items()}), flush=True)
    if stage == "disc":
        prim = ["RSI2_LONG", "TURTLE_S1", "TURTLE_S2", "IBS", "IBS_SMA200", "WILLIAMS_06"]
        adj = sl.holm([res[k]["A"]["p1"] if "A" in res[k] else 1 for k in prim])
        for k, h_ in zip(prim, adj): res[k]["holm"] = round(float(h_), 4)
        print({k: res[k]["holm"] for k in prim})
    else:
        Pb = DB.gold_usd(H); Db = pd.DataFrame({"o": Pb, "h": Pb, "l": Pb, "c": Pb})
        for nm, T, kind in (("RSI2_LONG_1968_1998", rsi2(Db), "long"), ("TURTLE_S1_1968_1998", turtle(Db, 20, 10, True), "dir"), ("TURTLE_S2_1968_1998", turtle(Db, 55, 20, False), "dir")):
            res[nm] = summ(T, pd.Timestamp("1968-01-01"), pd.Timestamp("1999-01-01"), kind, Db)
            print("confA", nm, json.dumps({k: (v if not isinstance(v, dict) else {kk: v[kk] for kk in ("bp", "t", "maxdd_pct")}) for k, v in res[nm].items()}), flush=True)
    json.dump(res, open(f"{sl.HERE}/results_109_112_{stage}.json", "w"), indent=1, default=float)
