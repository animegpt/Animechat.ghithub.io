"""#165 Williams Everywhere (prereg PREREGISTRATION_165_williams_everywhere.md). usage: python everywhere165.py [final]"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, features149 as F, metric149 as MT
MK = {"US500": ("USA500IDXUSD", 0.6, 1e3), "NASDAQ": ("USATECHIDXUSD", 2.0, 1e3), "DAX": ("DEUIDXEUR", 2.0, 1e3),
      "WTI": ("LIGHTCMDUSD", 0.04, 1e3), "USDJPY": ("USDJPY", 0.012, 1e3), "EURUSD": ("EURUSD", 0.00010, 1e5), "BTC": ("BTCUSD", 6.40, 1.0)}
P_ALL = (pd.Timestamp("2012-01-01"), pd.Timestamp("2026-11-01")); H1 = (P_ALL[0], pd.Timestamp("2019-01-01")); H2 = (pd.Timestamp("2019-01-01"), P_ALL[1])


def market(name):
    inst, spread, point = MK[name]
    lab.SPEC[inst] = dict(point=point, spread=spread, swap_long=0.0)
    if name == "BTC":
        df = lab.load_btc()
    else:
        d = f"{lab.RAW}/{inst}/BID"
        if not os.path.isdir(d) or len([f for f in os.listdir(d) if f.endswith(".bi5")]) < 60: return None
        for f in (f"{lab.CACHE}/{inst}_BID_dev.parquet", f"{lab.CACHE}/{inst}_BID_vault.parquet"):
            if os.path.exists(f): os.remove(f)                    # rebuild: downloads may have grown since last run
        df = lab.load_hourly(inst, vault=True)
        df = df[df.index >= "2011-06-01"]                           # study window 2012+ (old partial files ignored)
    M = lab.Mkt(df, inst); T = F.williams(M)
    return M, T


def gold():
    M = lab.Mkt(lab.load_hourly("XAUUSD", vault=True)); T = F.williams(M); T["net1"] = T["net2"]   # gold at 0.24/4000
    return M, T


def summ(M, T):
    out = {}
    for pn, P in (("all", P_ALL), ("2012_2018", H1), ("2019_2026", H2)):
        s = lab.summ(M, T, P, two_sided=True, nsim=1000)
        if s.get("n", 0) >= 10: out[pn] = {"n": s["n"], "gross_bp": s["gross_bp"], "net_bp": s["net1"]["bp"], "t": s["net1"]["t"], "p1": s["net1"]["p1"],
                                           "p_rand": s.get("p_rand"), "p_time": s.get("p_time")}
        else: out[pn] = {"n": s.get("n", 0)}
    return out


if __name__ == "__main__":
    final = len(sys.argv) > 1 and sys.argv[1] == "final"; res = {}; daily = {}
    for name in MK:
        r = market(name)
        if r is None: print(name, "no data yet"); continue
        M, T = r; res[name] = summ(M, T); res[name]["data_from"] = str(M.days[0].date())
        daily[name] = lab.daily_pnl(T, "net1"); print(name, json.dumps(res[name], default=float), flush=True)
    Mg, Tg = gold(); res["GOLD"] = summ(Mg, Tg); daily["GOLD"] = lab.daily_pnl(Tg, "net1"); print("GOLD", json.dumps(res["GOLD"], default=float))
    if final:
        names = [k for k in res if k != "GOLD"]; p = [res[k]["all"].get("p1", 1.0) for k in names]; adj = MT.holm(p)
        for k, a in zip(names, adj):
            r = res[k]; r["holm"] = float(a)
            r["confirms"] = bool(a < 0.05 and r["2012_2018"].get("net_bp", -1) > 0 and r["2019_2026"].get("net_bp", -1) > 0)
        mo = pd.DataFrame({k: v.groupby(pd.DatetimeIndex(v.index).to_period("M")).sum() for k, v in daily.items()})
        mo = mo[(mo.index >= "2012-01") & (mo.index <= "2026-10")]
        keep = [k for k in mo if mo[k].notna().sum() >= 60]; mo = mo[keep].fillna(0.0)
        w = 1 / mo.std(); bask = (mo * w).sum(1) / w.sum(); g = mo["GOLD"]
        def st(x): x = np.asarray(x); eq = np.cumsum(x); return {"sharpe": round(float(x.mean() / x.std(ddof=1) * np.sqrt(12)), 2), "maxdd_over_sd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min() / x.std()), 1)}
        h1 = mo.index < pd.Period("2019-01", "M")
        gs = g / g.std() * bask.std()
        res["basket"] = {"markets": keep, "all": st(bask), "gold_alone": st(g), "D_all": round(st(bask)["sharpe"] - st(g)["sharpe"], 2),
                         "D_2012_2018": round(st(bask[h1])["sharpe"] - st(g[h1])["sharpe"], 2), "D_2019_2026": round(st(bask[~h1])["sharpe"] - st(g[~h1])["sharpe"], 2),
                         "corr": mo.corr().round(2).to_dict()}
        nconf = sum(res[k].get("confirms", False) for k in names)
        res["verdict"] = "general" if nconf >= 3 else ("gold-specific" if nconf <= 1 else "mixed"); res["n_confirm"] = nconf
        print(json.dumps({k: res[k] for k in ("basket", "verdict", "n_confirm")}, default=float, indent=1))
    json.dump(res, open(f"{lab.HERE}/results/results_165{'_final' if final else '_partial'}.json", "w"), indent=1, default=float)
