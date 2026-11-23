"""#154 short reversal after an up-hour into 16:00 NY (prereg PREREGISTRATION_154_reversal_short.md).
usage: python rev154.py dev | silver | vault (vault needs OPEN_VAULT=1 VAULT_LOOK=1)"""
import os, sys, json
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab


def trades(M, variant, spread_mult=1.0):
    rows = []
    for t in range(len(M.days)):
        a = M.dh[t, 15]; j0 = M.dh[t, 16]
        if a < 0 or j0 < 0 or j0 != a + 1: continue
        if not (M.c[a] / M.o[a] - 1 > 0): continue
        cal = M.days[t]
        if variant == "A":
            jx = j0
        else:
            if cal.dayofweek > 3 or t + 1 >= len(M.days) or (M.days[t + 1] - cal).days != 1: continue
            jx = M.dh[t + 1, 19]
            if jx < 0 or jx < j0: continue
        r = lab.trade_row(M, -1, j0, M.o[j0], jx, M.c[jx])
        if spread_mult != 1.0:
            extra = (spread_mult - 1) * M.spec["spread"] * (0.5 / r["ep"] + 0.5 / r["xp"]); r["net1"] -= extra
        rows.append(r)
    return pd.DataFrame(rows)


def stats_(M, T, P):
    s = lab.summ(M, T, P, two_sided=False, nsim=2000)
    X = lab.period(T, P)
    s["net1"]["p1_t"] = s["net1"]["p1"]
    return s


if __name__ == "__main__":
    which = sys.argv[1]; out = {"which": which}
    if which == "dev":
        M = lab.Mkt(lab.load_hourly("XAUUSD")); periods = {"dev_2004_2023": (pd.Timestamp("2004-01-01"), pd.Timestamp("2024-01-01")),
                                                          "2004_2016": lab.DISC, "2017_2023": lab.CONF}
    elif which == "silver":
        M = lab.Mkt(lab.load_hourly("XAGUSD", vault=True), "XAGUSD"); periods = {"silver_2023_2026": (pd.Timestamp("2023-01-01"), pd.Timestamp("2026-11-01"))}
    else:
        assert os.environ.get("VAULT_LOOK") == "1" and os.environ.get("OPEN_VAULT") == "1"
        M = lab.Mkt(lab.load_hourly("XAUUSD", vault=True)); periods = {"vault_2024_2026": lab.VAULT}
    for v in ("A", "B"):
        T = trades(M, v); Ts = trades(M, v, 2.0) if M.inst == "XAUUSD" else None
        for pn, P in periods.items():
            r = stats_(M, T, P)
            if Ts is not None:
                X = lab.period(Ts, P); r["net1_spread_x2"] = {"bp": round(float(X.net1.mean() * 1e4), 2), "t": round(lab.tstat(X.net1.values), 2)}
            out[f"{v}_{pn}"] = r
            print(v, pn, "n", r.get("n"), "gross", r.get("gross_bp"), "net1", r["net1"], "net2", r["net2"]["bp"], "p_time", r.get("p_time"),
                  "x2", r.get("net1_spread_x2"), flush=True)
    json.dump(out, open(f"{lab.HERE}/results/results_154_{which}.json", "w"), indent=1, default=float)
