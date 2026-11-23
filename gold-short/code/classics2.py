"""#113-#122 classic day-horizon strategies part 2 (prereg/PREREGISTRATION_113_122_classics2.md).
usage: BARS=1h GDATA=... python classics2.py disc|conf     (vault: OPEN_VAULT=1 ... vault NAME1,NAME2 — once, after audit)"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("BARS", "1h")
from scipy import stats
import shortlib as sl

SWAP = 0.4316 / 4000; SL = 0.1e-4


def load(end="2024-01-01", start="2003-06-01"):
    m = sl.load_minutes(); m = m[(m.index >= pd.Timestamp(start, tz="UTC")) & (m.index < pd.Timestamp(end, tz="UTC"))]
    ny = m.index.tz_convert("America/New_York").tz_localize(None); key = (ny + pd.Timedelta(hours=7)).normalize()
    df = pd.DataFrame({"o": m.o.values, "h": m.h.values, "l": m.l.values, "c": m.c.values, "k": key.values})
    g = df.groupby("k"); D = g.agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("o", "size"))
    D = D[(D.n >= 10) & (D.index.dayofweek <= 4)]
    pos = df.reset_index(drop=True); pos["i"] = np.arange(len(pos))
    se = pos.groupby("k").i.agg(["first", "last"]).reindex(D.index)
    return dict(o=df.o.values, h=df.h.values, l=df.l.values, c=df.c.values), D, se["first"].values.astype(int), se["last"].values.astype(int)


def simulate(Hb, D, s, e, specs, name):
    """specs: dict t -> list of order dicts {side, lvl, arm(optional), stop('daylow'|float|None), tgt(float|None), days}"""
    o, h, l, c = Hb["o"], Hb["h"], Hb["l"], Hb["c"]; days = D.index; nd = len(days); rows = []; busy = -1
    for t in sorted(specs):
        if t <= busy: continue
        orders = specs[t]; armed = [od.get("arm") is None for od in orders]; entry = None
        for j in range(s[t], e[t] + 1):
            hits = []
            for q, od in enumerate(orders):
                if not armed[q]:
                    if (od["side"] == 1 and l[j] < od["arm"]) or (od["side"] == -1 and h[j] > od["arm"]): armed[q] = True
                    continue                                   # arming bar cannot also trigger (order unknown)
                if (od["side"] == 1 and h[j] >= od["lvl"]) or (od["side"] == -1 and l[j] <= od["lvl"]): hits.append(q)
            if len(hits) > 1:                                  # both sides in the same hour -> worse outcome
                rs = [orders[q]["side"] * (c[e[t]] / orders[q]["lvl"] - 1) for q in hits]; q = hits[int(np.argmin(rs))]
                entry = (q, j, orders[q]["lvl"], True); break
            if hits:
                q = hits[0]; od = orders[q]; px = max(od["lvl"], o[j]) if od["side"] == 1 else min(od["lvl"], o[j]); entry = (q, j, px, False); break
        if entry is None: continue
        q, j0, ep, amb = entry; od = orders[q]; side = od["side"]
        last_day = min(t + od["days"] - 1, nd - 1); jend = e[last_day]
        if od["stop"] == "daylow": stop = (l[s[t]:j0 + 1].min() - 0.0) if side == 1 else h[s[t]:j0 + 1].max()
        else: stop = od["stop"]
        tgt = od.get("tgt"); xp = c[jend]; xj = jend
        if amb: xp = c[e[t]]; xj = e[t]
        else:
            for j in range(j0 + 1, jend + 1):
                if stop is not None and ((side == 1 and l[j] <= stop) or (side == -1 and h[j] >= stop)):
                    xp = min(stop, o[j]) if side == 1 else max(stop, o[j]); xj = j; break
                if tgt is not None and ((side == 1 and h[j] >= tgt) or (side == -1 and l[j] <= tgt)):
                    xp = max(tgt, o[j]) if side == 1 else min(tgt, o[j]); xj = j; break
        xd = int(np.searchsorted(e, xj)); cal = (days[xd] - days[t]).days
        g = side * (xp / ep - 1)
        c1 = 0.12 / ep + 0.12 / xp + 2 * SL; c2 = 0.24 / 4000 + 2 * SL; sw = SWAP * cal if (side == 1 and cal > 0) else 0.0
        rows.append(dict(t=days[t], side=side, gross=g, net1=g - c1 - sw, net2=g - c2 - sw)); busy = xd
    return pd.DataFrame(rows)


def build(D):
    O, H, L, C = (D[k].values for k in "ohlc"); n = len(C); S = {k: {} for k in
        ["TSOUP", "TSOUP1", "HOLYGRAIL", "EIGHTY20", "OOPS", "SMASH", "STRETCH", "NR7", "GSV", "W_NR", "W112_ref"]}
    rng = H - L
    pc = np.r_[C[0], C[:-1]]; tr = np.maximum(rng, np.maximum(abs(H - pc), abs(L - pc)))
    upm = np.r_[0, np.diff(H)]; dnm = np.r_[0, -np.diff(L)]
    pdm = np.where((upm > dnm) & (upm > 0), upm, 0.0); ndm = np.where((dnm > upm) & (dnm > 0), dnm, 0.0)
    w = lambda x: pd.Series(x).ewm(alpha=1 / 14, adjust=False).mean().values
    atr = w(tr); pdi = 100 * w(pdm) / atr; ndi = 100 * w(ndm) / atr; adx = w(np.nan_to_num(100 * abs(pdi - ndi) / np.where(pdi + ndi == 0, np.nan, pdi + ndi)))
    e20 = pd.Series(C).ewm(span=20, adjust=False).mean().values
    stretch = pd.Series(np.minimum(H - O, O - L)).rolling(10).mean().values
    for t in range(30, n):
        p = slice(t - 20, t)
        lo20 = L[p].min(); ilo = t - 20 + int(np.argmin(L[p])); hi20 = H[p].max(); ihi = t - 20 + int(np.argmax(H[p]))
        od = []
        if t - ilo >= 4: od.append(dict(side=1, arm=lo20, lvl=lo20 + 0.5, stop="daylow", days=3))
        if t - ihi >= 4: od.append(dict(side=-1, arm=hi20, lvl=hi20 - 0.5, stop="daylow", days=3))
        if od: S["TSOUP"][t] = od
        q = slice(t - 21, t - 1); plo = L[q].min(); iplo = t - 21 + int(np.argmin(L[q])); phi = H[q].max(); iphi = t - 21 + int(np.argmax(H[q]))
        od = []
        if L[t - 1] < plo and C[t - 1] <= plo and (t - 1) - iplo >= 3: od.append(dict(side=1, lvl=plo, stop=None, days=3, stop_min=L[t - 1]))
        if H[t - 1] > phi and C[t - 1] >= phi and (t - 1) - iphi >= 3: od.append(dict(side=-1, lvl=phi, stop=None, days=3, stop_min=H[t - 1]))
        for x in od: x["stop"] = x.pop("stop_min")
        if od: S["TSOUP1"][t] = od
        if adx[t - 1] > 30:
            sw_hi = H[t - 21:t - 1].max(); sw_lo = L[t - 21:t - 1].min()
            if pdi[t - 1] > ndi[t - 1] and L[t - 1] <= e20[t - 1]: S["HOLYGRAIL"][t] = [dict(side=1, lvl=H[t - 1], stop=L[t - 1], tgt=sw_hi if sw_hi > H[t - 1] else None, days=10)]
            if ndi[t - 1] > pdi[t - 1] and H[t - 1] >= e20[t - 1]: S["HOLYGRAIL"][t] = [dict(side=-1, lvl=L[t - 1], stop=H[t - 1], tgt=sw_lo if sw_lo < L[t - 1] else None, days=10)]
        r1 = rng[t - 1]
        if r1 > 0:
            od = []
            if (O[t - 1] - L[t - 1]) >= 0.8 * r1 and (C[t - 1] - L[t - 1]) <= 0.2 * r1: od.append(dict(side=1, arm=L[t - 1] - 1.0, lvl=L[t - 1], stop="daylow", days=1))
            if (H[t - 1] - O[t - 1]) >= 0.8 * r1 and (H[t - 1] - C[t - 1]) <= 0.2 * r1: od.append(dict(side=-1, arm=H[t - 1] + 1.0, lvl=H[t - 1], stop="daylow", days=1))
            if od: S["EIGHTY20"][t] = od
        if O[t] < L[t - 1]: S["OOPS"][t] = [dict(side=1, lvl=L[t - 1], stop=None, days=1)]
        elif O[t] > H[t - 1]: S["OOPS"][t] = [dict(side=-1, lvl=H[t - 1], stop=None, days=1)]
        if C[t - 1] < L[t - 2]: S["SMASH"][t] = [dict(side=1, lvl=H[t - 1], stop=None, days=1)]
        elif C[t - 1] > H[t - 2]: S["SMASH"][t] = [dict(side=-1, lvl=L[t - 1], stop=None, days=1)]
        stv = stretch[t - 1]
        if stv > 0: S["STRETCH"][t] = [dict(side=1, lvl=O[t] + stv, stop=None, days=1), dict(side=-1, lvl=O[t] - stv, stop=None, days=1)]
        if rng[t - 1] <= rng[t - 7:t].min(): S["NR7"][t] = [dict(side=1, lvl=H[t - 1], stop=None, days=1), dict(side=-1, lvl=L[t - 1], stop=None, days=1)]
        k4 = slice(t - 4, t); dnd = C[k4] < O[k4]; upd = C[k4] > O[k4]
        bg = (H[k4] - O[k4])[dnd].mean() if dnd.any() else np.nan; sg = (O[k4] - L[k4])[upd].mean() if upd.any() else np.nan
        od = []
        if np.isfinite(bg) and bg > 0: od.append(dict(side=1, lvl=O[t] + 1.8 * bg, stop=None, days=1))
        if np.isfinite(sg) and sg > 0: od.append(dict(side=-1, lvl=O[t] - 1.8 * sg, stop=None, days=1))
        if od: S["GSV"][t] = od
        if r1 > 0:
            w112 = [dict(side=1, lvl=O[t] + 0.6 * r1, stop=None, days=1), dict(side=-1, lvl=O[t] - 0.6 * r1, stop=None, days=1)]
            S["W112_ref"][t] = w112
            if r1 < rng[t - 10:t].mean(): S["W_NR"][t] = w112
    return S


def summ(T, a, b, seed=113):
    if len(T) == 0: return {"n": 0}
    X = T[(T.t >= a) & (T.t < b)]
    if len(X) < 10: return {"n": int(len(X))}
    out = {"n": int(len(X)), "gross_bp": round(float(X.gross.mean() * 1e4), 2), "win": round(float((X.net1 > 0).mean()), 3)}
    for col in ("net1", "net2"):
        r = X[col].values; t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))); eq = np.cumsum(r)
        out[col] = {"bp": round(float(r.mean() * 1e4), 2), "t": round(float(t), 2), "maxdd_pct": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min() * 100), 1),
                    "p1": float(stats.t.sf(t, len(r) - 1))}
    rng = np.random.default_rng(seed); g = X.gross.values
    sims = np.array([(np.where(rng.random(len(g)) < 0.5, 1, -1) * g).mean() for _ in range(1000)]); out["p_rand"] = float((np.sum(sims >= g.mean()) + 1) / 1001)
    return out


NAMES = ["TSOUP", "TSOUP1", "HOLYGRAIL", "EIGHTY20", "OOPS", "SMASH", "STRETCH", "NR7", "GSV", "W_NR"]

if __name__ == "__main__":
    stage = sys.argv[1]
    if stage == "vault":
        assert sl.OPEN_VAULT; Hb, D, s, e = load(end="2026-11-01"); P = ("2024-01-01", "2026-11-01")
        names = sys.argv[2].split(",")
    else:
        Hb, D, s, e = load(); P = {"disc": ("2004-01-01", "2017-01-01"), "conf": ("2017-01-01", "2024-01-01")}[stage]; names = NAMES + ["W112_ref"]
    S = build(D); res = {}; trades = {}
    for nm in names:
        T = simulate(Hb, D, s, e, S[nm], nm); trades[nm] = T; res[nm] = summ(T, pd.Timestamp(P[0]), pd.Timestamp(P[1]))
        r = res[nm]; print(stage, nm, r.get("n"), "gross", r.get("gross_bp"), "net1", r.get("net1"), "net2", r.get("net2", {}).get("bp"), "p_rand", r.get("p_rand"), flush=True)
    if stage == "disc":
        adj = sl.holm([res[k]["net1"]["p1"] if "net1" in res[k] else 1 for k in NAMES])
        for k, h_ in zip(NAMES, adj): res[k]["holm"] = round(float(h_), 4)
        print({k: res[k]["holm"] for k in NAMES})
    # daily pnl correlations with W112_ref
    if "W112_ref" in trades:
        days = pd.bdate_range(P[0], pd.Timestamp(P[1]) - pd.Timedelta(days=1)); ser = lambda T: T.set_index("t").net1.groupby(level=0).sum().reindex(days).fillna(0)
        w = ser(trades["W112_ref"])
        for nm in names:
            if nm != "W112_ref" and len(trades[nm]): res[nm]["corr_W112"] = round(float(np.corrcoef(ser(trades[nm]), w)[0, 1]), 3)
    json.dump(res, open(f"{sl.HERE}/results_113_122_{stage}.json", "w"), indent=1, default=float)
