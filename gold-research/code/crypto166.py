"""#166 frozen Williams on ETH/SOL/XRP/LTC (prereg PREREGISTRATION_166_btc_williams_crypto.md)"""
import os, sys, json, glob, zipfile
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, features149 as F, metric149 as MT, lablog
COINS = {"ETH": 5e-4, "SOL": 10e-4, "XRP": 8e-4, "LTC": 10e-4}


def load(c):
    out = []
    for f in sorted(glob.glob(f"{lab.RAW}/CRYPTO_{c}/*.zip")):
        z = zipfile.ZipFile(f); x = pd.read_csv(z.open(z.namelist()[0]), header=None)
        ts = x[0].astype(np.int64); ts = np.where(ts > 1e14, ts // 1000, ts)
        out.append(pd.DataFrame({"o": x[1].values, "h": x[2].values, "l": x[3].values, "c": x[4].values, "v": x[5].values}, index=pd.to_datetime(ts, unit="ms")))
    df = pd.concat(out).sort_index(); return df[~df.index.duplicated()]


res = {}; pv = []
for c, sp in COINS.items():
    df = load(c); inst = f"{c}USD"; lab.SPEC[inst] = dict(point=1.0, spread=0.0, swap_long=0.0)
    M = lab.Mkt(df, inst); T = F.williams(M)
    g = T.gross.values; r = {}
    for k, mult in (("net", 1), ("net_x2", 2)):
        T[k] = g - mult * sp - 2 * lab.SLIP
    a, b = T.t.min(), T.t.max(); mid = a + (b - a) / 2
    for pn, m in (("all", np.ones(len(T), bool)), ("half1", (T.t < mid).values), ("half2", (T.t >= mid).values)):
        x = T.net.values[m]; t = lab.tstat(x)
        from scipy import stats
        r[pn] = {"n": int(m.sum()), "gross_bp": round(float(g[m].mean() * 1e4), 2), "net_bp": round(float(x.mean() * 1e4), 2), "t": round(t, 2),
                 "p1": float(stats.t.sf(t, len(x) - 1)), "net_x2_bp": round(float(T.net_x2.values[m].mean() * 1e4), 2)}
    s = lab.summ(M, T.assign(net1=T.net, net2=T.net), (a, b + pd.Timedelta(days=1)), two_sided=True, nsim=1000)
    r["p_time"] = s.get("p_time"); r["from"] = str(a.date()); res[c] = r; pv.append(r["all"]["p1"])
    print(c, r["from"], r["all"], "| half1", r["half1"]["net_bp"], "half2", r["half2"]["net_bp"], "| p_time", r["p_time"], flush=True)
adj = MT.holm(pv); n_ok = 0
for (c, r), h in zip(res.items(), adj):
    r["holm"] = float(h); r["confirms"] = bool(h < 0.05 and r["half1"]["net_bp"] > 0 and r["half2"]["net_bp"] > 0); n_ok += r["confirms"]
verdict = "crypto phenomenon" if n_ok >= 2 else ("BTC-only / luck" if n_ok == 0 else "weak support")
print({c: (round(r["holm"], 4), r["confirms"]) for c, r in res.items()}, "->", verdict)
json.dump({"coins": res, "n_confirm": n_ok, "verdict": verdict}, open(f"{lab.HERE}/results/results_166_crypto.json", "w"), indent=1, default=float)
lablog.log({"id": "166", "test": "frozen Williams on ETH/SOL/XRP/LTC (BTC clean ground, prereg 166)", "trials_added": 4, "cum_trials": 350301,
            "results": {c: {"net_bp": r["all"]["net_bp"], "t": r["all"]["t"], "holm": r["holm"], "h1": r["half1"]["net_bp"], "h2": r["half2"]["net_bp"], "confirms": r["confirms"]} for c, r in res.items()}, "verdict": verdict})
