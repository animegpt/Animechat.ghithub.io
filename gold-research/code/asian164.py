"""#164 Asian drift (prereg PREREGISTRATION_164_asian_drift.md). usage: python asian164.py dev|silver"""
import os, sys, json
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, lablog
WIN = {"W1": (19, 2), "W2": (20, 1)}


def trades(M, w, spread_mult=1.0):
    h0, h1 = WIN[w]; rows = []
    for t in range(len(M.days)):
        a = M.dh[t, h0]; b = M.dh[t, h1]
        if a < 0 or b < 0 or b < a: continue
        r = lab.trade_row(M, 1, a, M.o[a], b, M.c[b])
        if spread_mult != 1.0:
            ex = (spread_mult - 1) * M.spec["spread"] * (0.5 / r["ep"] + 0.5 / r["xp"]); r["net1"] -= ex
            r["net2"] -= (spread_mult - 1) * M.spec["spread"] / 4000 if M.inst == "XAUUSD" else ex
        rows.append(r)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    which = sys.argv[1]; out = {}
    if which == "dev":
        M = lab.Mkt(lab.load_hourly("XAUUSD")); P = {"disc_2004_2016": lab.DISC, "conf_2017_2023": lab.CONF}
    else:
        M = lab.Mkt(lab.load_hourly("XAGUSD", vault=True), "XAGUSD"); P = {"silver_2023_2026": (pd.Timestamp("2023-01-01"), pd.Timestamp("2026-11-01"))}
    for w in WIN:
        T = trades(M, w); T2 = trades(M, w, 2.0) if which == "dev" else None
        for pn, per in P.items():
            s = lab.summ(M, T, per, two_sided=False, nsim=2000)
            if T2 is not None:
                X = lab.period(T2, per); s["stress_x2"] = {"net1_bp": round(float(X.net1.mean() * 1e4), 2), "net2_bp": round(float(X.net2.mean() * 1e4), 2), "t2": round(lab.tstat(X.net2.values), 2)}
            out[f"{w}_{pn}"] = s
            print(w, pn, "n", s["n"], "gross", s["gross_bp"], "net1", s["net1"]["bp"], s["net1"]["t"], "net2", s["net2"]["bp"], s["net2"]["t"], "p_time", s.get("p_time"), "x2", s.get("stress_x2"), flush=True)
        if which == "dev":
            days = M.days[(M.days >= lab.DISC[0]) & (M.days < lab.CONF[1])]
            dsr = lab.deflated_sharpe(lab.daily_pnl(T, "net2", days).values, 350289, 0.0843 / 252 * 252)
            out[f"{w}_dsr"] = dsr; print(w, "DSR (prob, SR, SR0)", dsr)
    if which == "dev":
        p = [out[f"{w}_disc_2004_2016"]["net2"]["p1"] for w in WIN]
        adj = dict(zip(WIN, np.minimum(1, np.array(sorted(p)) * np.array([2, 1]))[np.argsort(np.argsort(p))]))
        out["holm_disc_net2"] = {w: float(v) for w, v in adj.items()}; print("holm", out["holm_disc_net2"])
    json.dump(out, open(f"{lab.HERE}/results/results_164_{which}.json", "w"), indent=1, default=float)
