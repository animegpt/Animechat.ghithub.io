"""#96 weekend / daily-break oracle: PAXG/USDT (24/7) vs spot gold reopen. prereg/PREREGISTRATION_95_96_machine.md
usage: BARS=1m GDATA=... python weekend96.py <paxg csv dir>"""
import os, sys, glob, json, numpy as np, pandas as pd
os.environ.setdefault("BARS", "1m")
from scipy import stats
import shortlib as sl

COM, SLIP = 0.07, 0.1e-4
D0, D1, C1 = pd.Timestamp("2020-08-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC")


def paxg(pdir):
    fr = []
    for f in sorted(glob.glob(f"{pdir}/PAXGUSDT-1m-*.csv")):
        x = pd.read_csv(f, header=None, usecols=[0, 4]); x.columns = ["t", "c"]; fr.append(x)
    p = pd.concat(fr); unit = "us" if p.t.max() > 1e14 else "ms"
    s = pd.Series(p.c.values.astype(float), index=pd.to_datetime(p.t, unit=unit, utc=True)); s = s[~s.index.duplicated()].sort_index()
    s.index = s.index.as_unit("ns"); return s


def hourly_spread():
    out = {}
    for side in ("", "_ASK"):
        d = f"{sl.GDATA}/raw/cache_XAUUSD{side}_h"; fr = []
        for f in sorted(os.listdir(d)):
            if os.path.getsize(f"{d}/{f}") == 0 or f[:7] >= "2024-01": continue
            fr.append(sl._parse(f"{d}/{f}", pd.Timestamp(f[:7] + "-01", tz="UTC")))
        out[side] = pd.concat(fr).c
    j = pd.concat([out[""], out["_ASK"]], axis=1, keys=["b", "a"]).dropna()
    t = j.index; return pd.DataFrame({"y": t.year, "h": t.hour, "s": (j.a - j.b).values}).groupby(["y", "h"]).s.median()


def asof(s, times):
    p = np.searchsorted(s.index.values, pd.DatetimeIndex(times).as_unit("ns").values, side="right") - 1
    return np.where(p >= 0, s.values[np.clip(p, 0, None)], np.nan)


if __name__ == "__main__":
    P = paxg(sys.argv[1]); sp = hourly_spread()
    m = sl.load_minutes(); m = m[(m.index >= D0 - pd.Timedelta(days=7)) & (m.index < C1)]
    idx = m.index.as_unit("ns"); o = m.o.values; c = m.c.values; tns = idx.values.astype(np.int64)
    gap = np.diff(tns) / 6e10                                    # minutes between consecutive gold bars
    ev = []
    for k in np.flatnonzero(gap > 30):
        f, r = k, k + 1; tf = idx[f]
        weekend = gap[k] > 24 * 60
        daily = (40 <= gap[k] <= 150) and (tf.hour * 60 + tf.minute >= 20 * 60 + 40) and (tf.hour < 22) and not weekend
        if not (weekend or daily): continue
        e = r + 5
        if e + 1 >= len(o) or (tns[e] - tns[r]) / 6e10 > 15: continue
        te = idx[e]
        if te < D0: continue
        QF = asof(P, [tf])[0]; Qe = asof(P, [te - pd.Timedelta(minutes=1)])[0]
        if not (np.isfinite(QF) and np.isfinite(Qe)): continue
        d = np.log(Qe / QF) - np.log(o[e] / c[f]); mm = np.log(Qe / QF)
        ev.append(dict(kind="W" if weekend else "D", e=e, te=te, d=d, m=mm))
    E = pd.DataFrame(ev)
    def spr(t): return float(sp.get((t.year, t.hour), np.nan))
    def trade(e, side, Hmin, mult):
        te = idx[e]; x = np.searchsorted(tns, (te + pd.Timedelta(minutes=Hmin)).value)
        if x >= len(o): return np.nan, np.nan
        tx = idx[x]; se, sx = spr(te) * mult, spr(tx) * mult
        if side == 1: buy, sell = o[e] + se, o[x]
        else: sell, buy = o[e], o[x] + sx
        g = side * (o[x] / o[e] - 1)
        net = (sell - buy) / o[e] - COM / o[e] - 2 * SLIP
        return g, net
    V = {"B1_1h": ("W", "d", 0.0010, 60), "B1_4h": ("W", "d", 0.0010, 240), "B2_8h": ("W", "m", 0.010, 480), "B3_1h": ("D", "d", 0.0005, 60)}
    res = {"events": E.kind.value_counts().to_dict()}
    rng = np.random.default_rng(96)
    for lab, a, b in (("disc", D0, D1), ("conf", D1, C1)):
        res[lab] = {}
        for nm, (kind, var, thr, Hm) in V.items():
            X = E[(E.kind == kind) & (E.te >= a) & (E.te < b) & (E[var].abs() >= thr)]
            rows = [(trade(int(r.e), int(np.sign(r[var])), Hm, 1.0), trade(int(r.e), int(np.sign(r[var])), Hm, 2.0)) for _, r in X.iterrows()]
            rows = [(g1, n1, n2) for (g1, n1), (g2, n2) in rows if np.isfinite(n1)]
            if len(rows) < 5: res[lab][nm] = {"n": len(rows)}; continue
            g, n1, n2 = map(np.array, zip(*rows))
            t = n1.mean() / (n1.std(ddof=1) / np.sqrt(len(n1)))
            # random direction baseline on the same events
            gabs = np.array([trade(int(r.e), 1, Hm, 1.0)[1] for _, r in X.iterrows()]); gsh = np.array([trade(int(r.e), -1, Hm, 1.0)[1] for _, r in X.iterrows()])
            ok = np.isfinite(gabs) & np.isfinite(gsh); gabs, gsh = gabs[ok], gsh[ok]
            sims = np.array([np.where(rng.random(len(gabs)) < 0.5, gabs, gsh).mean() for _ in range(1000)])
            res[lab][nm] = {"n": int(len(n1)), "gross_bp": round(float(g.mean() * 1e4), 2), "net_bp": round(float(n1.mean() * 1e4), 2), "t": round(float(t), 2),
                            "net_x2_bp": round(float(n2.mean() * 1e4), 2), "win": round(float((n1 > 0).mean()), 3), "p1": float(stats.t.sf(t, len(n1) - 1)),
                            "rand_bp": round(float(sims.mean() * 1e4), 2), "p_rand": float((np.sum(sims >= n1.mean()) + 1) / 1001)}
            print(lab, nm, json.dumps(res[lab][nm]), flush=True)
    names = [k for k in V if "p1" in res["disc"].get(k, {})]
    adj = sl.holm([res["disc"][k]["p1"] for k in names])
    for k, a_ in zip(names, adj): res["disc"][k]["holm"] = round(float(a_), 4)
    # descriptive: |m| vs Monday realised vol (first 8h after entry)
    W = E[(E.kind == "W") & (E.te < C1)].copy(); rv = []
    lr = np.r_[0, np.diff(np.log(c))]
    for _, r in W.iterrows():
        x = np.searchsorted(tns, (r.te + pd.Timedelta(hours=8)).value); rv.append(lr[int(r.e):x].std() * np.sqrt(max(x - int(r.e), 1)))
    W["rv"] = rv; res["corr_abs_m_vs_rv8h"] = round(float(W[["rv"]].assign(am=W.m.abs()).corr().iloc[0, 1]), 3)
    res["d_stats_bp"] = {k: {"mean": round(float(E[E.kind == k].d.mean() * 1e4), 2), "sd": round(float(E[E.kind == k].d.std() * 1e4), 2)} for k in ("W", "D")}
    print({k: res["disc"][k].get("holm") for k in names}, "corr", res["corr_abs_m_vs_rv8h"], res["events"], res["d_stats_bp"])
    json.dump(res, open(f"{sl.HERE}/results_96.json", "w"), indent=1, default=float)
