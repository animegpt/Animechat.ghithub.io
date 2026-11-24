"""#155-#157 fusion lab (prereg/PREREGISTRATION_155_157_fusion.md).
usage: python fusion155.py check            -> Williams engine check (gold disc n 2053, net1 +5.09bp, t 2.25)
       python fusion155.py dev              -> gold 2004-2023 (sanity / development)
       python fusion155.py silver           -> silver 2004-2022 (clean ground) + 2023-2026 descriptive
       python fusion155.py verdict          -> gates 1-4 from the json files
       OPEN_VAULT=1 VAULT_LOOK=1 python fusion155.py vault   -> ONE look, gold 2024-01..2026-10 (after the audit)"""
import os, sys, json
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, metric149 as MT
from features149 import williams

N_DSR = 350217; VAR_SR = 0.08433
OUT = f"{lab.HERE}/results"
P = {"2004_2016": ("2004-01-01", "2017-01-01"), "2017_2023": ("2017-01-01", "2024-01-01"),
     "2017_2022": ("2017-01-01", "2023-01-01"), "2004_2022": ("2004-01-01", "2023-01-01"),
     "2004_2023": ("2004-01-01", "2024-01-01"), "2023_2026": ("2023-01-01", "2026-11-01"),
     "vault": ("2024-01-01", "2026-11-01"), "nov2026": ("2026-11-01", "2027-01-01"),
     "2011_2016": ("2011-01-01", "2017-01-01"), "2011_2022": ("2011-01-01", "2023-01-01")}


def variants(M, T):
    """returns dict name -> DataFrame of trades (same rows as T, exits changed per the prereg)."""
    out = {"base": T.reset_index(drop=True)}
    for name in ("F1", "F2"):
        rows = []
        for r in T.itertuples(index=False):
            d = M.dayof[r.j0]; jx = r.jx; side = r.side; new = None
            if name == "F1":
                A = M.dh[d, 15]; B = M.dh[d, 16]
                if B >= 0 and jx == B and A == B - 1 and r.j0 <= A and side * (M.c[A] / M.o[A] - 1) > 0: new = A
            else:
                C = M.dh[d, 13]
                if C >= 0 and r.j0 <= C and C < jx: new = C
            if new is None: rows.append(r._asdict())
            else:
                x = lab.trade_row(M, side, r.j0, r.ep, new, M.c[new], how=3); rows.append(x)
        out[name] = pd.DataFrame(rows)[T.columns]
    return out


def tstat1(x):
    t = lab.tstat(x); return t, float(stats.t.sf(t, max(len(x) - 1, 1)))


def per_period(V, pn):
    a, b = (pd.Timestamp(x) for x in P[pn]); B = V["base"]; m = ((B.t >= a) & (B.t < b)).values
    res = {"n": int(m.sum())}
    if m.sum() < 10: return res
    for k, X in V.items():
        r = X.net1.values[m]; t, p = tstat1(r)
        res[k] = {"net1_bp": round(r.mean() * 1e4, 2), "t": round(t, 2), "net2_bp": round(X.net2.values[m].mean() * 1e4, 2),
                  "gross_bp": round(X.gross.values[m].mean() * 1e4, 2)}
        if k != "base":
            d = (X.net1.values - B.net1.values)[m]; td, pd_ = tstat1(d)
            res[k].update({"changed": int((X.jx.values != B.jx.values)[m].sum()), "dmean_bp": round(d.mean() * 1e4, 3),
                           "d_t": round(td, 2), "d_p1": pd_})
            ev = MT.evaluate(B.t.values[m], B.net1.values[m], np.ones(m.sum()), P[pn], boot=False)  # base monthly Sharpe
            mm, G, months = MT.month_matrix(B.t.values, P[pn])
            base_m = G @ B.net1.values[mm]; var_m = G @ X.net1.values[mm]
            D, tj = MT.jkm(base_m, var_m)
            res[k].update({"sh_base": ev["sh_base"], "sh_var": round(float(MT.sharpe_m(var_m[:, None])[0] * np.sqrt(12)), 3),
                           "D_sharpe": round(float(D), 3), "t_jkm": round(float(tj), 2)})
            ov = var_m - base_m
            if ov.std() > 0:
                dsr, sr, sr0 = MT.dsr_monthly(ov, N_DSR, VAR_SR); res[k].update({"dsr": round(dsr, 4), "ov_sr": round(sr, 3), "sr0": round(sr0, 3)})
    return res


def run(inst, vault, periods):
    M = lab.Mkt(lab.load_hourly(inst, vault=vault), inst)
    T = williams(M); V = variants(M, T)
    out = {"inst": inst, "first_day": str(M.days[0].date()), "last_day": str(M.days[-1].date())}
    for pn in periods:
        out[pn] = per_period(V, pn)
        print(inst, pn, json.dumps(out[pn], default=float), flush=True)
    return out, M, V


def daily(V, M, key, pn):
    a, b = (pd.Timestamp(x) for x in P[pn]); days = M.days[(M.days >= a) & (M.days < b)]
    return lab.daily_pnl(V[key], days=days)


if __name__ == "__main__":
    w = sys.argv[1]
    if w == "check":
        M = lab.Mkt(lab.load_hourly("XAUUSD")); T = williams(M)
        print(lab.summ(M, T, lab.DISC, nsim=200)); print(lab.summ(M, T, lab.CONF, nsim=200))
    elif w == "dev":
        out, M, V = run("XAUUSD", False, ["2004_2016", "2017_2023", "2004_2023"])
        json.dump(out, open(f"{OUT}/results_155_dev.json", "w"), indent=1, default=float)
    elif w == "silver":
        out, M, V = run("XAGUSD", True, ["2004_2016", "2017_2022", "2004_2022", "2023_2026"])
        # F3 silver net1 tests + portfolio with gold (gold dev only, vault closed)
        Mg = lab.Mkt(lab.load_hourly("XAUUSD")); Tg = williams(Mg)
        f3 = {}
        for pn in ("2004_2016", "2017_2022", "2004_2022"):
            a, b = (pd.Timestamp(x) for x in P[pn]); X = V["base"]; r = X.net1.values[((X.t >= a) & (X.t < b)).values]
            t, p = tstat1(r); f3[pn] = {"n": len(r), "net1_bp": round(r.mean() * 1e4, 2), "t": round(t, 2), "p1": p}
        for pn in ("2004_2016", "2017_2023"):
            a, b = (pd.Timestamp(x) for x in P[pn])
            g = lab.daily_pnl(Tg, days=Mg.days[(Mg.days >= a) & (Mg.days < b)])
            s = lab.daily_pnl(V["base"]).reindex(g.index).fillna(0.0)
            sh = lambda x: float(x.mean() / x.std() * np.sqrt(252))
            port = g / g.std() + s / s.std()
            f3["port_" + pn] = {"sh_gold": round(sh(g), 3), "sh_silver": round(sh(s), 3), "sh_port": round(sh(port), 3),
                                "corr": round(float(g.corr(s)), 3)}
        sd = lab.daily_pnl(V["base"], days=M.days[(M.days >= pd.Timestamp("2004-01-01")) & (M.days < pd.Timestamp("2023-01-01"))])
        mm, G, months = MT.month_matrix(V["base"].t.values, P["2004_2022"])
        f3["dsr_monthly"] = MT.dsr_monthly(G @ V["base"].net1.values[mm], N_DSR, VAR_SR)
        out["F3"] = f3; print("F3", json.dumps(f3, default=float))
        json.dump(out, open(f"{OUT}/results_155_silver.json", "w"), indent=1, default=float)
    elif w == "silverA":   # Amendment A: valid silver years only
        out, M, V = run("XAGUSD", True, ["2011_2016", "2017_2022", "2011_2022"])
        Mg = lab.Mkt(lab.load_hourly("XAUUSD")); Tg = williams(Mg); f3 = {}
        for pn in ("2011_2016", "2017_2022", "2011_2022"):
            a, b = (pd.Timestamp(x) for x in P[pn]); X = V["base"]; r = X.net1.values[((X.t >= a) & (X.t < b)).values]
            t, p = tstat1(r); f3[pn] = {"n": len(r), "net1_bp": round(r.mean() * 1e4, 2), "gross_bp": round(X.gross.values[((X.t >= a) & (X.t < b)).values].mean() * 1e4, 2), "t": round(t, 2), "p1": p}
        for pn in ("2011_2016", "2017_2022"):
            a, b = (pd.Timestamp(x) for x in P[pn])
            g = lab.daily_pnl(Tg, days=Mg.days[(Mg.days >= a) & (Mg.days < b)]); s = lab.daily_pnl(V["base"]).reindex(g.index).fillna(0.0)
            sh = lambda x: float(x.mean() / x.std() * np.sqrt(252)); port = g / g.std() + s / s.std()
            f3["port_" + pn] = {"sh_gold": round(sh(g), 3), "sh_silver": round(sh(s), 3), "sh_port": round(sh(port), 3), "corr": round(float(g.corr(s)), 3)}
        mm, G, months = MT.month_matrix(V["base"].t.values, P["2011_2022"])
        f3["dsr_monthly"] = MT.dsr_monthly(G @ V["base"].net1.values[mm], N_DSR, VAR_SR)
        out["F3"] = f3; print("F3", json.dumps(f3, default=float))
        json.dump(out, open(f"{OUT}/results_155_silverA.json", "w"), indent=1, default=float)
    elif w == "nov":   # gold after 2026-10, descriptive; uses ONLY November bars (no vault rows loaded)
        df = pd.read_parquet(f"{lab.CACHE}/XAUUSD_BID_nov2026.parquet"); M = lab.Mkt(df, "XAUUSD")
        T = williams(M); V = variants(M, T); out = {"nov2026": per_period(V, "nov2026"),
              "trades": V["base"].assign(F1=V["F1"].net1, F2=V["F2"].net1)[["t", "side", "net1", "F1", "F2"]].astype({"t": str}).to_dict("records")}
        print(json.dumps(out, default=float)); json.dump(out, open(f"{OUT}/results_155_nov2026.json", "w"), indent=1, default=float)
    elif w == "vault":
        assert os.environ.get("VAULT_LOOK") == "1" and lab.OPEN_VAULT
        out, M, V = run("XAUUSD", True, ["vault"])
        json.dump(out, open(f"{OUT}/results_155_vault.json", "w"), indent=1, default=float)
