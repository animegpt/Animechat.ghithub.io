"""#162 Sonic v2 family (prereg PREREGISTRATION_162_sonic_v2.md). usage: python sonic162.py"""
import os, sys, json, itertools
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, combo158 as K, metric149 as MT, lablog
ENTRIES = ["E0", "E1", "E2", "E3"]; EXITS = ["X0", "X1", "X2", "X3", "X4"]; STOPS = ["S0", "S1", "S2"]
CUM_BEFORE = 350225; RISK = 0.0015


def prep(E):
    M = E.M; H, L, C = M.h, M.l, M.c
    _, _, _, _, _, chB, chS = K._structure(H, L, C, 5)
    E.chB, E.chS = chB, chS
    E.LL20 = pd.Series(L).rolling(20).min().values; E.HH20 = pd.Series(H).rolling(20).max().values
    return E


def stop_of(E, i, s, kind):
    C, A = E.M.c, E.ATR
    if kind == "S0": return min(E.LL10[i], C[i] - 0.5 * A[i]) if s == 1 else max(E.HH10[i], C[i] + 0.5 * A[i])
    if kind == "S1": return C[i] - 1.0 * A[i] if s == 1 else C[i] + 1.0 * A[i]
    return min(E.LL20[i], C[i] - 0.5 * A[i]) if s == 1 else max(E.HH20[i], C[i] + 0.5 * A[i])


def sim(E, entry, exitk, stopk):
    M = E.M; O, H, L, C = M.o, M.h, M.l, M.c; n = E.n; A = E.ATR; rows = []; pos = None; i = 600
    while i < n - 2:
        exited = False
        if pos is not None and i >= pos["jb"]:
            s, ep, stp = pos["side"], pos["ep"], pos["stop"]
            hit = (s == 1 and L[i] <= stp) or (s == -1 and H[i] >= stp)
            xp = None
            if hit:
                xp = min(stp, O[i]) if s == 1 else max(stp, O[i]); jx = i
                if i == pos["jb"] and pos.get("fill_intrabar"): xp = stp
            else:
                far = C[i] < E.EL[i] if s == 1 else C[i] > E.EH[i]
                mid = C[i] < E.EC[i] if s == 1 else C[i] > E.EC[i]
                ch = E.chS[i] if s == 1 else E.chB[i]
                cond = {"X0": far, "X1": mid, "X2": False, "X3": far or ch, "X4": far}[exitk]
                if cond or i - (pos["jb"] - 1) >= 240: xp = O[i + 1]; jx = i + 1
                else:
                    if exitk == "X2":
                        if s == 1: pos["hh"] = max(pos["hh"], H[i]); pos["stop"] = max(stp, pos["hh"] - 3 * A[i])
                        else: pos["ll"] = min(pos["ll"], L[i]); pos["stop"] = min(stp, pos["ll"] + 3 * A[i])
                    if exitk == "X4" and not pos["be"]:
                        if (s == 1 and H[i] >= ep + pos["dist"]) or (s == -1 and L[i] <= ep - pos["dist"]):
                            pos["be"] = True; pos["stop"] = max(stp, ep) if s == 1 else min(stp, ep)
            if xp is not None:
                pos.update(xp=xp, jx=jx); rows.append(pos); pos = None; exited = (jx == i + 1)
        if pos is None and not exited:
            sig = E.sonic_signal(i)
            if sig != 0 and not (entry == "E1" and E.HTF4[i] * sig <= 0):
                stp = stop_of(E, i, sig, stopk); jb = None; px = None; intrabar = False
                if entry in ("E0", "E1"): jb, px = i + 1, O[i + 1]
                elif entry == "E2":
                    if (sig == 1 and C[i + 1] > E.EH[i + 1]) or (sig == -1 and C[i + 1] < E.EL[i + 1]): jb, px = i + 2, O[i + 2]
                else:
                    lim = E.EC[i]
                    for k in range(i + 1, min(i + 6, n - 1)):
                        if (sig == 1 and L[k] <= lim) or (sig == -1 and H[k] >= lim):
                            jb = k; px = min(lim, O[k]) if sig == 1 else max(lim, O[k]); intrabar = True; break
                if jb is not None and jb < n - 1:
                    if not ((sig == 1 and stp >= px) or (sig == -1 and stp <= px)):
                        pos = dict(side=sig, ep=px, stop=stp, dist=abs(px - stp), jb=jb, hh=px, ll=px, be=False, fill_intrabar=intrabar)
        i += 1
    T = pd.DataFrame(rows)
    T["t0"] = M.idx[T.jb.values]; T["tx"] = M.idx[T.jx.values]; T["nroll"] = K.nroll_of(M, T.jb.values, T.jx.values)
    return T


def monthly_R(T, scn, P, inst="XAUUSD"):
    a, b = pd.Timestamp(P[0]), pd.Timestamp(P[1]); m = ((T.t0 >= a) & (T.t0 < b)).values
    R = (K.net_returns(T, scn, inst) * T.ep.values / T.dist.values)[m]
    ms = pd.period_range(P[0], b - pd.Timedelta(days=1), freq="M")
    s = pd.Series(RISK * R, index=pd.DatetimeIndex(T.tx.values[m]).to_period("M")).groupby(level=0).sum()
    return s.reindex(ms).fillna(0.0).values, R


def evaluate(trades, inst="XAUUSD", periods=None, scns=("A", "B", "C")):
    periods = periods or {"disc": ("2009-01-01", "2017-01-01"), "conf": ("2017-01-01", "2024-01-01"), "all": ("2009-01-01", "2024-01-01")}
    base = trades["E0X0S0"]; out = {}
    for name, T in trades.items():
        r = {}
        for scn in scns:
            for pn, P in periods.items():
                mb, _ = monthly_R(base, scn, P, inst); mv, R = monthly_R(T, scn, P, inst)
                Dv, tj = MT.jkm(mb, mv)
                e = {"n": int(len(R)), "mean_R": round(float(R.mean()), 3), "t_R": round(lab.tstat(R), 2),
                     "sharpe": round(float(mv.mean() / mv.std(ddof=1) * np.sqrt(12)), 3) if mv.std() > 0 else 0.0, "D": round(float(Dv), 3), "t_jkm": round(float(tj), 2)}
                if pn == "all" and scn == "B": e["t_boot"] = round(MT.boot_t(mb, mv), 2); e["monthly"] = mv.tolist()
                r[f"{scn}_{pn}"] = e
        out[name] = r
    return out


def main():
    M = lab.Mkt(lab.load_hourly("XAUUSD")); E = prep(K.EA(M))
    names = [e + x + s for e, x, s in itertools.product(ENTRIES, EXITS, STOPS)]
    trades = {nm: sim(E, nm[:2], nm[2:4], nm[4:]) for nm in names}
    print("base trades", len(trades["E0X0S0"]), "(combo158 sim_sonic: 1917)", flush=True)
    R = evaluate(trades)
    var_sr = float(np.var([R[nm]["B_all"]["sharpe"] for nm in names], ddof=1))
    N = CUM_BEFORE + len(names)
    p_disc = {nm: float(stats.norm.sf(R[nm]["B_disc"]["t_jkm"])) for nm in names if nm != "E0X0S0"}
    adj = dict(zip(p_disc, MT.holm(list(p_disc.values()))))
    # silver
    Ms = lab.Mkt(lab.load_hourly("XAGUSD", vault=True), "XAGUSD"); Es = prep(K.EA(Ms))
    tr_s = {nm: sim(Es, nm[:2], nm[2:4], nm[4:]) for nm in names}
    RS = evaluate(tr_s, inst="XAGUSD", periods={"silver": ("2023-01-01", "2026-11-01")}, scns=("A",))
    rows = []
    for nm in names:
        r = R[nm]
        if nm == "E0X0S0": continue
        dsr, sr, _ = MT.dsr_monthly(np.array(r["B_all"]["monthly"]), N, var_sr)
        g = {"g1_disc": r["B_disc"]["D"] > 0 and r["B_disc"]["t_jkm"] >= 2 and adj[nm] < 0.05 and r["B_disc"]["mean_R"] > 0,
             "g2_conf": r["B_conf"]["D"] > 0,
             "g3_all": r["B_all"]["D"] > 0 and r["B_all"]["t_jkm"] >= 2 and r["B_all"]["t_boot"] >= 2 and r["A_all"]["D"] > 0,
             "g4_dsr": dsr >= 0.95, "g5_silver": RS[nm]["A_silver"]["D"] > 0}
        rows.append(dict(name=nm, B_disc=r["B_disc"], B_conf=r["B_conf"], B_all={k: v for k, v in r["B_all"].items() if k != "monthly"},
                         A_all=r["A_all"], C_all=r["C_all"], holm_disc=adj[nm], dsr=dsr, silver=RS[nm]["A_silver"], gates=g,
                         passes=all(g.values()), probable=all(v for k, v in g.items() if k != "g4_dsr") and not g["g4_dsr"]))
    rows.sort(key=lambda x: -x["B_all"]["D"])
    base = {k: {kk: vv for kk, vv in v.items() if kk != "monthly"} for k, v in R["E0X0S0"].items()}
    res = dict(base=base, base_silver=RS["E0X0S0"]["A_silver"], N_dsr=N, var_sr=var_sr, rows=rows,
               passers=[r["name"] for r in rows if r["passes"]], probable=[r["name"] for r in rows if r["probable"]])
    json.dump(res, open(f"{lab.HERE}/results/results_162_sonic_v2.json", "w"), indent=1, default=float)
    print("BASE", base["B_disc"], base["B_conf"], base["B_all"])
    for r in rows[:15]:
        print(r["name"], "disc", r["B_disc"]["D"], r["B_disc"]["t_jkm"], "conf", r["B_conf"]["D"], "all", r["B_all"]["D"], r["B_all"]["t_jkm"],
              "meanR", r["B_all"]["mean_R"], "n", r["B_all"]["n"], "holm", round(r["holm_disc"], 3), "dsr", round(r["dsr"], 3), "silverD", r["silver"]["D"], "PASS" if r["passes"] else ("prob" if r["probable"] else ""))
    print("passers", res["passers"], "probable", res["probable"])
    lablog.log({"id": "162", "test": "Sonic v2 family 4 entries x 5 exits x 3 stops (60), cost B primary (prereg 162)", "trials_added": 60,
                "cum_trials": N, "passers": res["passers"], "probable": res["probable"],
                "top5": [{"name": r["name"], "D_disc": r["B_disc"]["D"], "D_conf": r["B_conf"]["D"], "D_all": r["B_all"]["D"], "t_all": r["B_all"]["t_jkm"], "dsr": r["dsr"], "silver_D": r["silver"]["D"]} for r in rows[:5]]})


if __name__ == "__main__":
    main()
