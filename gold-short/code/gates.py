"""7-gate evaluation for a variant that passed discovery+confirmation. usage: python gates.py NAME"""
import sys, json, numpy as np
from short_batch import *

NEIGH = {
    "CRASH": lambda kw: [dict(kw, k=kw["k"] - .25), dict(kw, k=kw["k"] + .25), dict(kw, H=max(1, kw["H"] - 1)), dict(kw, H=kw["H"] + 2),
                         dict(kw, stop=.75), dict(kw, stop=1.5), dict(kw, clv=.15), dict(kw, clv=.35)],
    "EXHAUST": lambda kw: [dict(kw, Z=kw["Z"] - .5), dict(kw, Z=kw["Z"] + .5), dict(kw, hold=10), dict(kw, hold=20),
                           dict(kw, buf=.25), dict(kw, buf=1.0), dict(kw, n=40), dict(kw, n=60)],
    "MACRO": lambda kw: [dict(kw, L=3), dict(kw, L=10), dict(kw, L=40), dict(kw, hold=10), dict(kw, hold=40),
                         dict(kw, mode="ry"), dict(kw, mode="usd")],
    "FIX": lambda kw: [dict(ent=(12, 0)), dict(ext=(15, 0)), dict(days=(1, 2, 3))],
    "SONICDN": lambda kw: [dict(n=150), dict(n=250), dict(slope=10), dict(slope=40), dict(mode="level")],
    "VIX": lambda kw: [dict(ratio=1.3), dict(ratio=1.5), dict(H=3), dict(H=10), dict(floor=15.0), dict(floor=25.0)],
}

if __name__ == "__main__":
    name = sys.argv[1]; fn, kw = VARIANTS[name]
    M = Market(); X = Ctx(M); out = {"name": name}
    d, td = evaluate(X, name, fn, kw, DISC); c, tc = evaluate(X, name, fn, kw, CONF)
    out["disc"] = d; out["conf"] = c
    out["G2_costs2x"] = bool(d["net2_bp"] > 0 and c["net2_bp"] > 0)
    nb = []
    for k2 in NEIGH[name.split("_")[0]](kw):
        a, _ = evaluate(X, name, fn, k2, DISC, nsim=0); b, _ = evaluate(X, name, fn, k2, CONF, nsim=0)
        nb.append({"kw": str(k2), "disc_bp": a["mean_bp"], "disc_n": a["n"], "conf_bp": b["mean_bp"], "conf_n": b["n"]})
    out["neighbours"] = nb
    out["G4_robust"] = bool(np.mean([x["disc_bp"] > 0 and x["conf_bp"] > 0 for x in nb]) >= 0.75)
    disc_sr = [r["mean_bp"] / 1e4 for r in []]
    allr = np.r_[td.net.values, tc.net.values]
    res = json.load(open(f"{HERE}/results_65_70_disc.json"))
    # trial-Sharpe variance from the 11 discovery variants (per-trade SR = t/sqrt(n))
    srs = [v["t"] / np.sqrt(v["n"]) for v in res.values() if v["n"] > 2]
    dsr, sr, sr0 = deflated_sharpe(allr, 75, float(np.var(srs, ddof=1)))
    out["G5"] = {"boot_p_conf": bootstrap_p(tc.net.values), "dsr": dsr, "sr_trade": sr, "sr0": sr0}
    out["G5_luck"] = bool(out["G5"]["boot_p_conf"] < 0.05 and dsr >= 0.95)
    out["G6_random"] = bool(d.get("p_rand", 1) < 0.05 and c.get("p_rand", 1) < 0.05)
    out["G7_sample"] = bool(d["n"] + c["n"] >= 100)
    print(json.dumps(out, indent=1, default=float))
    json.dump(out, open(f"{HERE}/gates_{name}.json", "w"), indent=1, default=float)
