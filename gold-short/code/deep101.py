"""#101 gold/silver pair, #102 flight to safety, #103 Sonic H4 add-on (prereg/PREREGISTRATION_101_103_deep_dive.md)
usage: BARS=1h GDATA=... python deep101.py <hist dir> <silver hourly dir> disc|conf"""
import os, sys, json, numpy as np, pandas as pd
os.environ["BARS"] = "1h"
from scipy import stats
import shortlib as sl
import long97 as LF
import doors89_90 as DB

SWAP = 0.4316 / 4000; SL = 0.1e-4


def silver_daily(d):
    fr = [sl._parse(f"{d}/{f}", pd.Timestamp(f[:7] + "-01", tz="UTC")) for f in sorted(os.listdir(d)) if os.path.getsize(f"{d}/{f}") > 0 and f[:7] < "2024-01"]
    m = pd.concat(fr).sort_index(); m = m[~m.index.duplicated()]
    return LF.daily_close(m)


def st(r, extra=None):
    r = np.asarray(r); n = len(r)
    if n < 3: return {"n": int(n)}
    t = r.mean() / (r.std(ddof=1) / np.sqrt(n)); eq = np.cumsum(r)
    out = {"n": int(n), "net_bp": round(float(r.mean() * 1e4), 2), "t": round(float(t), 2), "sum_pct": round(float(r.sum() * 100), 1),
           "maxdd_pct": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min() * 100), 1), "win": round(float((r > 0).mean()), 3),
           "p1": float(stats.t.sf(t, n - 1))}
    if extra: out.update(extra)
    return out


# ------------------------------------------------------------------ #101
def pair(G, S, N, swap, a, b, seed=101):
    j = pd.concat([G, S], axis=1, keys=["g", "s"]).dropna()
    r = np.log(j.g / j.s); mu = r.shift(1).rolling(N).mean(); sd = r.shift(1).rolling(N).std(); z = ((r - mu) / sd).values
    g, s, d = j.g.values, j.s.values, j.index; trades = []; pos = 0; k0 = 0
    for k in range(len(j)):
        if not np.isfinite(z[k]): continue
        if pos != 0:
            if (pos == 1 and z[k] <= 0) or (pos == -1 and z[k] >= 0) or abs(z[k]) >= 4 or k - k0 >= 60:
                sg, ss = -pos, pos                              # pos=+1 means z>=2: short gold, long silver
                rg = sg * (g[k] / g[k0] - 1); rs = ss * (s[k] / s[k0] - 1)
                cost = 0.12 / g[k0] + 0.12 / g[k] + 0.0125 / s[k0] + 0.0125 / s[k] + 4 * SL
                days = (d[k] - d[k0]).days
                sw = (SWAP * days) if swap else 0.0             # exactly one leg is long
                trades.append((d[k0], rg + rs - cost - sw, rg + rs, rg, rs)); pos = 0
        if pos == 0 and abs(z[k]) >= 2 and abs(z[k]) < 4:
            pos = 1 if z[k] >= 2 else -1; k0 = k
    T = pd.DataFrame(trades, columns=["t", "net", "gross", "rg", "rs"]).set_index("t")
    X = T[(T.index >= a) & (T.index < b)]
    if len(X) < 3: return {"n": int(len(X))}
    rng = np.random.default_rng(seed); gr = X.gross.values
    sims = np.array([(np.where(rng.random(len(gr)) < 0.5, 1, -1) * gr).mean() for _ in range(1000)])
    return st(X.net.values, {"gross_bp": round(float(gr.mean() * 1e4), 2), "p_rand": float((np.sum(sims >= gr.mean()) + 1) / 1001)})


# ------------------------------------------------------------------ #102
def nasdaq():
    s = pd.read_csv(sys.argv[1] + "/NASDAQCOM.csv", index_col=0, parse_dates=True).iloc[:, 0]; return pd.to_numeric(s, errors="coerce").dropna()


def flight(P, sig_days, H, swap, a, b, nextday, seed=102):
    idx = P.index; rows = []; busy = pd.Timestamp("1900-01-01")
    ent = []
    for d in sig_days:
        k = idx.searchsorted(d, side="right" if nextday else "left")
        if k + H >= len(idx): continue
        d0 = idx[k]
        if d0 <= busy or d0 < a or d0 >= b: continue
        d1 = idx[k + H]; g = P.iloc[k + H] / P.iloc[k] - 1
        net = g - (0.24 / 4000 + 2 * SL) - (SWAP * (d1 - d0).days if swap else 0.0)
        rows.append((d0, net, g)); busy = d1; ent.append(k)
    if len(rows) < 3: return {"n": len(rows)}
    T = pd.DataFrame(rows, columns=["t", "net", "gross"])
    rng = np.random.default_rng(seed); yrs = idx.year.values; sims = []
    plan = pd.Series([idx[k].year for k in ent]).value_counts()
    pools = {y: np.flatnonzero((yrs == y) & (np.arange(len(idx)) + H < len(idx))) for y in plan.index}
    for _ in range(1000):
        ks = np.concatenate([rng.choice(pools[y], c) for y, c in plan.items()])
        gg = P.values[ks + H] / P.values[ks] - 1
        dd = (idx[ks + H] - idx[ks]).days.values
        sims.append((gg - (0.24 / 4000 + 2 * SL) - (SWAP * dd if swap else 0.0)).mean())
    sims = np.array(sims)
    return st(T.net.values, {"gross_bp": round(float(T.gross.mean() * 1e4), 2), "rand_bp": round(float(sims.mean() * 1e4), 2),
                             "p_rand": float((np.sum(sims >= T.net.mean()) + 1) / 1001)})


# ------------------------------------------------------------------ #103
def sonic_trades(m, rule, swap):
    if rule == "1h":
        b = m[["o", "h", "l", "c"]]; bclose = b.index + pd.Timedelta(hours=1)
    else:
        b = m.resample("4h", label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna(); bclose = b.index + pd.Timedelta(hours=4)
    bclose = pd.DatetimeIndex(bclose); bclose = bclose.tz_convert(None) if bclose.tz is not None else bclose
    o, h, l, c = (b[k].values for k in "ohlc"); n = len(c)
    ema = lambda x, s: pd.Series(x).ewm(span=s, adjust=False).mean().values
    eh, el, ec, e89 = ema(h, 34), ema(l, 34), ema(c, 34), ema(c, 89)
    pc = np.r_[c[0], c[:-1]]; trr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))); atr = pd.Series(trr).ewm(alpha=1 / 14, adjust=False).mean().values
    mid = (eh + el) / 2; sh5 = lambda x: np.r_[np.full(5, np.nan), x[:-5]]
    up = (mid > e89) & (mid > sh5(mid)) & (e89 > sh5(e89)); dn = (mid < e89) & (mid < sh5(mid)) & (e89 < sh5(e89))
    tl = pd.Series(l <= ec).rolling(5).max().values > 0; ts = pd.Series(h >= ec).rolling(5).max().values > 0; pcl = np.r_[c[0], c[:-1]]
    Lg = up & tl & (c > eh) & (pcl <= np.r_[eh[0], eh[:-1]]); Sg = dn & ts & (c < el) & (pcl >= np.r_[el[0], el[:-1]])
    ll10 = pd.Series(l).rolling(10).min().values; hh10 = pd.Series(h).rolling(10).max().values
    hi_, lo_, ho, ht = m.h.values, m.l.values, m.o.values, m.index.values
    hpos = np.searchsorted(ht, pd.DatetimeIndex(bclose).values)
    ev = sorted([(k, 1) for k in np.flatnonzero(Lg) if k > 300] + [(k, -1) for k in np.flatnonzero(Sg) if k > 300]); rows = []; busy = -1
    for k, s in ev:
        if k <= busy: continue
        stop = min(ll10[k], c[k] - 0.5 * atr[k]) if s == 1 else max(hh10[k], c[k] + 0.5 * atr[k])
        xe = min(k + 240, n - 1)
        for kk in range(k + 1, xe + 1):
            if (s == 1 and c[kk] < el[kk]) or (s == -1 and c[kk] > eh[kk]): xe = kk; break
        e = c[k]; px = c[xe]; xt = bclose[xe]
        for j in range(hpos[k], min(hpos[xe], len(hi_))):
            if s == 1 and lo_[j] <= stop: px = min(stop, ho[j]); xt = ht[j]; break
            if s == -1 and hi_[j] >= stop: px = max(stop, ho[j]); xt = ht[j]; break
        days = (pd.Timestamp(xt) - pd.Timestamp(bclose[k])).days
        net = s * (px / e - 1) - (0.24 / e + 2 * SL) - (SWAP * days if (swap and s == 1) else 0.0)
        rows.append((pd.Timestamp(xt), net / (abs(e - stop) / e), s)); busy = xe
    T = pd.DataFrame(rows, columns=["t", "R", "side"]).set_index("t")
    if T.index.tz is not None: T.index = T.index.tz_localize(None)
    return T


def portfolio(H1, H4, a, b):
    mon = lambda T, w: (T.R * w).groupby(T.index.to_period("M")).sum()
    months = pd.period_range(a, pd.Timestamp(b) - pd.Timedelta(days=1), freq="M")
    s1 = mon(H1, 0.003).reindex(months).fillna(0); s4 = mon(H4, 0.0015).reindex(months).fillna(0)
    def p(x):
        eq = x.cumsum(); return {"ann_pct": round(float(x.mean() * 12 * 100), 2), "sharpe_m": round(float(x.mean() / x.std() * np.sqrt(12)), 3),
                                 "maxdd_pct": round(float((eq - eq.cummax()).min() * 100), 2)}
    a1, c = p(s1), p(s1 + s4)
    return {"H1_alone": a1, "H1_plus_H4": c, "H4_alone_0.15": p(s4), "corr_monthly": round(float(np.corrcoef(s1, s4)[0, 1]), 3),
            "pass": bool(c["sharpe_m"] > a1["sharpe_m"] and c["maxdd_pct"] >= 1.1 * a1["maxdd_pct"])}


if __name__ == "__main__":
    H, SD, stage = sys.argv[1], sys.argv[2], sys.argv[3]
    m = LF.hourly(); G = LF.daily_close(m); S = silver_daily(SD)
    res = {}
    if stage == "disc":
        A, B = pd.Timestamp("2018-01-01"), pd.Timestamp("2022-01-01")
        for N in (60, 250):
            res[f"PAIR_{N}"] = {"swapfree": pair(G, S, N, False, A, B), "swap": pair(G, S, N, True, A, B)}
        nq = nasdaq(); nr = nq.pct_change(); vix = sl.fred("VIXCLS"); vr = vix.pct_change()
        sigN = nr[nr <= -0.02].index; sigV = vr[vr >= 0.20].index
        A, B = pd.Timestamp("2004-01-01"), pd.Timestamp("2017-01-01")
        for nm, sd_ in (("N2_H5", sigN), ("V20_H5", sigV)):
            res[nm] = {"swap": flight(G, sd_, 5, True, A, B, False), "swapfree": flight(G, sd_, 5, False, A, B, False),
                       "desc_H1": flight(G, sd_, 1, True, A, B, False), "desc_H10": flight(G, sd_, 10, True, A, B, False)}
        names = ["PAIR_60", "PAIR_250", "N2_H5", "V20_H5"]
        prim = {"PAIR_60": "swapfree", "PAIR_250": "swapfree", "N2_H5": "swap", "V20_H5": "swap"}
        adj = sl.holm([res[k][prim[k]].get("p1", 1) for k in names])
        for k, h_ in zip(names, adj): res[k]["holm"] = round(float(h_), 4)
        h1 = sonic_trades(m, "1h", False); h4 = sonic_trades(m, "4h", False)
        res["SONIC_H1H4_swapfree"] = portfolio(h1, h4, "2004-01", "2017-01")
        h1s = sonic_trades(m, "1h", True); h4s = sonic_trades(m, "4h", True)
        res["SONIC_H1H4_swap"] = portfolio(h1s, h4s, "2004-01", "2017-01")
    for k, v in res.items(): print(stage, k, json.dumps(v), flush=True)
    json.dump(res, open(f"{sl.HERE}/results_101_103_{stage}.json", "w"), indent=1, default=float)


def confirm103():
    m = LF.hourly(); res = {}
    for swap in (False, True):
        h1 = sonic_trades(m, "1h", swap); h4 = sonic_trades(m, "4h", swap)
        res["SONIC_H1H4_" + ("swap" if swap else "swapfree")] = portfolio(h1, h4, "2017-01", "2024-01")
    for k, v in res.items(): print("conf", k, json.dumps(v), flush=True)
    json.dump(res, open(f"{sl.HERE}/results_103_conf.json", "w"), indent=1)
