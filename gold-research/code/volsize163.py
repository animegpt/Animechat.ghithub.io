"""#163 Williams vol-managed sizing (prereg PREREGISTRATION_163_williams_volsize.md)"""
import os, sys, json
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, combo158 as K, metric149 as MT, lablog


def sizes(M, W):
    D = M.D.copy(); rng = (D.h - D.l) / D.c; ret = np.log(D.c).diff()
    atr20 = rng.rolling(20).mean().shift(1); rv60 = ret.rolling(60).std().shift(1)          # known before the day opens
    v1 = (atr20.rolling(252, min_periods=126).median() / atr20).clip(0.5, 2)
    v2 = (rv60.rolling(252, min_periods=126).median() / rv60).clip(0.5, 2)
    t = pd.DatetimeIndex(W.t)
    return {"V1": v1.reindex(t).fillna(1.0).values, "V2": v2.reindex(t).fillna(1.0).values}


def monthly(W, r, P):
    a, b = pd.Timestamp(P[0]), pd.Timestamp(P[1]); m = ((W.t0 >= a) & (W.t0 < b)).values
    ms = pd.period_range(P[0], b - pd.Timedelta(days=1), freq="M")
    return pd.Series(r[m], index=pd.DatetimeIndex(W.tx.values[m]).to_period("M")).groupby(level=0).sum().reindex(ms).fillna(0.0).values


def mdd(x): eq = np.cumsum(x); return float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min() * 100)


def run(inst, vault, periods, scn):
    M = lab.Mkt(lab.load_hourly(inst, vault=vault), inst); W = K.sim_williams(M); S = sizes(M, W)
    r = 0.5 * K.net_returns(W, scn, inst); out = {}
    for v, s in S.items():
        e = {}
        for pn, P in periods.items():
            b = monthly(W, r, P); z = monthly(W, r * s, P); Dv, tj = MT.jkm(b, z)
            e[pn] = {"D": round(float(Dv), 3), "t_jkm": round(float(tj), 2), "sh_base": round(float(b.mean() / b.std(ddof=1) * np.sqrt(12)), 3),
                     "sh_sized": round(float(z.mean() / z.std(ddof=1) * np.sqrt(12)), 3), "dd_base": round(mdd(b), 1), "dd_sized": round(mdd(z), 1),
                     "mean_size": round(float(s[((W.t0 >= P[0]) & (W.t0 < P[1])).values].mean()), 3)}
            if pn == "all": e[pn]["t_boot"] = round(MT.boot_t(b, z), 2); e["_overlay"] = (z - b)
        out[v] = e
    return out


if __name__ == "__main__":
    G = run("XAUUSD", False, {"disc": ("2009-01-01", "2017-01-01"), "conf": ("2017-01-01", "2024-01-01"), "all": ("2009-01-01", "2024-01-01")}, "B")
    S = run("XAGUSD", True, {"silver": ("2023-01-01", "2026-11-01")}, "A")
    p = [float(stats.norm.sf(G[v]["all"]["t_jkm"])) for v in ("V1", "V2")]; adj = MT.holm(p); res = {}
    for k, v in enumerate(("V1", "V2")):
        g = G[v]; dsr, _, _ = MT.dsr_monthly(g.pop("_overlay"), 350287, 0.0843); S[v].pop("_overlay", None)
        gates = {"g1": g["all"]["D"] > 0 and g["all"]["t_jkm"] >= 2 and g["all"]["t_boot"] >= 2, "g2": g["disc"]["D"] > 0 and g["conf"]["D"] > 0,
                 "g3_holm": bool(adj[k] < 0.05), "g4_dsr": dsr >= 0.95, "g5_silver": S[v]["silver"]["D"] > 0}
        res[v] = {**g, "silver": S[v]["silver"], "holm": float(adj[k]), "dsr": dsr, "gates": gates, "passes": all(gates.values())}
        print(v, json.dumps(res[v], default=float))
    json.dump(res, open(f"{lab.HERE}/results/results_163_volsize.json", "w"), indent=1, default=float)
    lablog.log({"id": "163", "test": "Williams vol-managed sizing V1 ATR20 / V2 RV60 (prereg 163, from external research review)", "trials_added": 2, "cum_trials": 350287,
                "results": {v: {"D_all": res[v]["all"]["D"], "t": res[v]["all"]["t_jkm"], "D_disc": res[v]["disc"]["D"], "D_conf": res[v]["conf"]["D"], "silver_D": res[v]["silver"]["D"], "dsr": res[v]["dsr"], "passes": res[v]["passes"]} for v in res}})
