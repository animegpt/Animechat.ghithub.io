"""#97-#100 long field (prereg/PREREGISTRATION_97_100_long_field.md).
usage: BARS=1h GDATA=... python long97.py <hist dir> disc|confA|confB [variants...]"""
import os, sys, json, numpy as np, pandas as pd
os.environ["BARS"] = "1h"
from scipy import stats
import shortlib as sl
import doors89_90 as DB

RT = 0.24 / 4000 + 2 * 0.1e-4; SWAP = 0.4316 / 4000
PER = {"disc": ("2004-01-01", "2017-01-01"), "confA": ("1968-01-01", "1999-01-01"), "confB": ("2017-01-01", "2024-01-01")}


def hourly():
    m = sl.load_minutes(); m = m[m.index < pd.Timestamp("2024-01-01", tz="UTC")]
    return m


def daily_close(m):
    ny = (m.index + pd.Timedelta(hours=1)).tz_convert("America/New_York").tz_localize(None)       # bar close time NY
    s = pd.Series(m.c.values, index=ny); s = s[(s.index.hour <= 17) & (s.index.dayofweek <= 4)]
    d = s.groupby(s.index.normalize()).last(); return d


def tr(side, pe, px, days, swap):
    g = side * (px / pe - 1); return g - RT - (SWAP * days if (swap and side == 1) else 0.0), g


def dc_follow(P, th, swap):
    p = P.values; d = P.index; mode = 0; hi = lo = p[0]; trades = []; pos = 0; e = 0; ei = None
    for i in range(1, len(p)):
        x = p[i]; ev = 0
        if mode == 0:
            hi = max(hi, x); lo = min(lo, x)
            if x <= hi * (1 - th): mode = -1; lo = x; ev = -1
            elif x >= lo * (1 + th): mode = 1; hi = x; ev = 1
        elif mode == 1:
            if x > hi: hi = x
            elif x <= hi * (1 - th): mode = -1; lo = x; ev = -1
        else:
            if x < lo: lo = x
            elif x >= lo * (1 + th): mode = 1; hi = x; ev = 1
        if ev != 0:
            if pos != 0: trades.append((d[ei], pos, *tr(pos, e, x, (d[i] - d[ei]).days, swap)))
            pos = ev; e = x; ei = i
    return pd.DataFrame(trades, columns=["t", "side", "net", "gross"]).set_index("t")


def tsmom(P, L, swap):
    me = P.groupby(P.index.to_period("M")).last(); dates = P.groupby(P.index.to_period("M")).apply(lambda s: s.index[-1])
    rows = []; prev = 0
    for k in range(L, len(me) - 1):
        sig = np.sign(me.iloc[k] / me.iloc[k - L] - 1); r = me.iloc[k + 1] / me.iloc[k] - 1
        days = (dates.iloc[k + 1] - dates.iloc[k]).days
        net = sig * r - 0.5 * RT * abs(sig - prev) - (SWAP * days if (swap and sig > 0) else 0.0)
        rows.append((dates.iloc[k], sig, net, sig * r)); prev = sig
    return pd.DataFrame(rows, columns=["t", "side", "net", "gross"]).set_index("t")


def realyield(P, longflat, swap):
    ry = sl.fred("DFII10")
    me = P.groupby(P.index.to_period("M")).last(); dates = P.groupby(P.index.to_period("M")).apply(lambda s: s.index[-1])
    rows = []; prev = 0
    for k in range(len(me) - 1):
        t = dates.iloc[k]; cut = t - pd.offsets.BDay(2)
        cur = ry[ry.index <= cut]
        if len(cur) < 70: continue
        dlt = cur.iloc[-1] - cur.iloc[-64]
        sig = 1.0 if dlt < 0 else (0.0 if longflat else -1.0)
        r = me.iloc[k + 1] / me.iloc[k] - 1; days = (dates.iloc[k + 1] - t).days
        net = sig * r - 0.5 * RT * abs(sig - prev) - (SWAP * days if (swap and sig > 0) else 0.0)
        rows.append((t, sig, net, sig * r)); prev = sig
    return pd.DataFrame(rows, columns=["t", "side", "net", "gross"]).set_index("t")


def sonic_big(m, rule, swap):
    if rule == "4h":
        b = m.resample("4h", label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
        bclose = b.index + pd.Timedelta(hours=4)
    else:
        ny = m.index.tz_convert("America/New_York").tz_localize(None); key = (ny + pd.Timedelta(hours=7)).normalize()   # day ends 17:00 NY
        mm = m.copy(); mm["k"] = key.values
        b = mm.groupby("k").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("o", "size"))
        b = b[b.n >= 10]; last = pd.Series(m.index, index=key).groupby(level=0).last().reindex(b.index)
        bclose = pd.DatetimeIndex(last.values) + pd.Timedelta(hours=1)
    o, h, l, c = (b[k].values for k in "ohlc"); n = len(c)
    ema = lambda x, s: pd.Series(x).ewm(span=s, adjust=False).mean().values
    eh, el, ec, e89 = ema(h, 34), ema(l, 34), ema(c, 34), ema(c, 89)
    pc = np.r_[c[0], c[:-1]]; trr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))); atr = pd.Series(trr).ewm(alpha=1 / 14, adjust=False).mean().values
    mid = (eh + el) / 2; sh5 = lambda x: np.r_[np.full(5, np.nan), x[:-5]]
    up = (mid > e89) & (mid > sh5(mid)) & (e89 > sh5(e89)); dn = (mid < e89) & (mid < sh5(mid)) & (e89 < sh5(e89))
    tl = pd.Series(l <= ec).rolling(5).max().values > 0; ts = pd.Series(h >= ec).rolling(5).max().values > 0; pcl = np.r_[c[0], c[:-1]]
    Lg = up & tl & (c > eh) & (pcl <= np.r_[eh[0], eh[:-1]]); Sg = dn & ts & (c < el) & (pcl >= np.r_[el[0], el[:-1]])
    ll10 = pd.Series(l).rolling(10).min().values; hh10 = pd.Series(h).rolling(10).max().values
    hi_ = m.h.values; lo_ = m.l.values; ho = m.o.values; ht = m.index.values
    hpos = np.searchsorted(ht, pd.DatetimeIndex(bclose).values)             # first hourly bar after bar close
    ev = sorted([(k, 1) for k in np.flatnonzero(Lg) if k > 100] + [(k, -1) for k in np.flatnonzero(Sg) if k > 100]); rows = []; busy = -1
    for k, s in ev:
        if k <= busy: continue
        stop = min(ll10[k], c[k] - 0.5 * atr[k]) if s == 1 else max(hh10[k], c[k] + 0.5 * atr[k])
        xe = min(k + 240, n - 1)
        for kk in range(k + 1, xe + 1):
            if (s == 1 and c[kk] < el[kk]) or (s == -1 and c[kk] > eh[kk]): xe = kk; break
        e = c[k]; px = c[xe]; a, z = hpos[k], hpos[xe]
        for j in range(a, min(z, len(hi_))):
            if s == 1 and lo_[j] <= stop: px = min(stop, ho[j]); break
            if s == -1 and hi_[j] >= stop: px = max(stop, ho[j]); break
        days = (pd.Timestamp(bclose[xe]) - pd.Timestamp(bclose[k])).days
        rows.append((pd.Timestamp(bclose[k]).tz_localize(None) if pd.Timestamp(bclose[k]).tzinfo else pd.Timestamp(bclose[k]), s, *tr(s, e, px, days, swap)))
        busy = xe
    return pd.DataFrame(rows, columns=["t", "side", "net", "gross"]).set_index("t")


def summ(T, a, b, nsim=1000, seed=97):
    X = T[(T.index >= a) & (T.index < b)]
    X = X[X.side != 0]
    if len(X) < 5: return {"n": int(len(X))}
    r = X.net.values; n = len(r); t = r.mean() / (r.std(ddof=1) / np.sqrt(n))
    eq = np.cumsum(r); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
    rng = np.random.default_rng(seed); g = X.gross.values
    sims = np.array([(np.where(rng.random(n) < 0.5, 1, -1) * np.abs(np.sign(X.side.values)) * g * np.sign(X.side.values)).mean() for _ in range(nsim)])
    return {"n": int(n), "net_bp": round(float(r.mean() * 1e4), 2), "t": round(float(t), 2), "sum_pct": round(float(r.sum() * 100), 1),
            "maxdd_pct": round(dd * 100, 1), "win": round(float((r > 0).mean()), 3), "p1": float(stats.t.sf(t, n - 1)),
            "p_rand": float((np.sum(sims >= g.mean()) + 1) / (nsim + 1)),
            "long_net_bp": round(float(X[X.side > 0].net.mean() * 1e4), 2) if (X.side > 0).any() else None,
            "short_net_bp": round(float(X[X.side < 0].net.mean() * 1e4), 2) if (X.side < 0).any() else None}


VARS = ["DC_2", "DC_3", "DC_5", "TSM_3", "TSM_6", "TSM_12", "RY_LS", "RY_LF", "SONIC_H4", "SONIC_D1"]

if __name__ == "__main__":
    H = sys.argv[1]; stage = sys.argv[2]; names = sys.argv[3:] or VARS
    a, b = PER[stage]
    if stage == "confA": P = DB.gold_usd(H); m = None
    else: m = hourly(); P = daily_close(m)
    res = {}
    for nm in names:
        if stage == "confA" and nm.split("_")[0] in ("RY", "SONIC"): continue
        res[nm] = {}
        for swap in (False, True):
            if nm.startswith("DC"): T = dc_follow(P, int(nm[3:]) / 100, swap)
            elif nm.startswith("TSM"): T = tsmom(P, int(nm[4:]), swap)
            elif nm.startswith("RY"): T = realyield(P, nm == "RY_LF", swap)
            else: T = sonic_big(m, "4h" if nm == "SONIC_H4" else "1d", swap)
            if T.index.tz is not None: T.index = T.index.tz_localize(None)
            res[nm]["swapfree" if not swap else "swap"] = summ(T, pd.Timestamp(a), pd.Timestamp(b))
        print(stage, nm, json.dumps(res[nm]), flush=True)
    if stage == "disc":
        adj = sl.holm([res[k]["swapfree"].get("p1", 1) for k in names])
        for k, h in zip(names, adj): res[k]["holm"] = round(float(h), 4)
        print({k: res[k]["holm"] for k in names})
    json.dump(res, open(f"{sl.HERE}/results_97_100_{stage}.json", "w"), indent=1, default=float)
