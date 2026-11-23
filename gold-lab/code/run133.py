"""#133 brute force run: real search, 20 cumulative-size circular-shift nulls, survivors -> confirmation. Vault never loaded."""
import json, sys, numpy as np, pandas as pd
import lab, bf
from lablog import log

CUM_BEFORE = 48756; N_REAL = 50000; NMIN = 150

M = lab.Mkt(lab.load_hourly("XAUUSD")); B = bf.build(M)
disc = np.flatnonzero((M.days >= lab.DISC[0]) & (M.days < lab.DISC[1]))
conf = np.flatnonzero((M.days >= lab.CONF[0]) & (M.days < lab.CONF[1]))
R = bf.gen_rules(B, N_REAL, 133)
S = bf.evaluate(B, R, disc)
ok = S.n >= NMIN
print("real: rules", len(R), "with n>=150:", int(ok.sum()), "best t1", S.t1[ok].max(), flush=True)

RN = bf.gen_rules(B, N_REAL + CUM_BEFORE, 133)
assert (RN[:N_REAL] == R).all()
rng = np.random.default_rng(1330); nulls = []
for k in range(20):
    sh = int(rng.integers(250, len(disc) - 250))
    SN = bf.evaluate(B, RN, disc, shift=sh)
    m = SN.t1[SN.n >= NMIN].max(); nulls.append(float(m)); print("null", k, sh, round(m, 3), flush=True)
thr = float(np.percentile(nulls, 95))
print("threshold", thr, flush=True)

S["rule"] = [bf.rule_name(B, r) for r in R]
top = S[ok].sort_values("t1", ascending=False).head(40)
print(top[["n", "mean1", "t1", "mean2", "t2", "rule"]].to_string(), flush=True)
surv = S[ok & (S.t1 > thr) & (S.t2 >= 2)].sort_values("t1", ascending=False)
print("survivors before placebo/cluster:", len(surv), flush=True)
cands = []; dd = M.days[disc]
for i in surv.index:
    T = bf.rule_trades(M, B, R[i], lab.DISC)
    pt = lab.random_time_p(M, T, lab.DISC, 2000, np.random.default_rng(133))
    if pt >= 0.05: print("placebo fail", S.rule[i], pt); continue
    d = lab.daily_pnl(T, days=dd)
    if any(abs(np.corrcoef(d, c["d"])[0, 1]) > 0.7 for c in cands): continue
    cands.append(dict(i=int(i), rule=S.rule[i], d=d, p_time=pt))
    if len(cands) >= 10: break
out = {"threshold_t1": thr, "nulls": nulls, "n_rules": N_REAL, "null_size": N_REAL + CUM_BEFORE, "best_real_t1": float(S.t1[ok].max()),
       "var_sr_ann": float(S.sr_ann[ok].var()), "top10": top.head(10)[["n", "mean1", "t1", "mean2", "t2", "rule"]].to_dict("records"), "candidates": []}
if cands:
    SC = bf.evaluate(B, R[[c["i"] for c in cands]], conf)
    from scipy import stats
    p = [float(stats.t.sf(t, max(n - 1, 1))) for t, n in zip(SC.t1, SC.n)]
    adj = lab.holm(p)
    for c, (_, r), a in zip(cands, SC.iterrows(), adj):
        rec = {"rule": c["rule"], "disc": S.loc[c["i"], ["n", "mean1", "t1", "mean2", "t2"]].to_dict(), "p_time_disc": c["p_time"],
               "conf": r[["n", "mean1", "t1", "mean2", "t2"]].to_dict(), "conf_holm": float(a),
               "conf_pass": bool(r.mean1 > 0 and r.mean2 > 0 and a < 0.05)}
        out["candidates"].append(rec); print(json.dumps(rec, default=float), flush=True)
json.dump(out, open(f"{lab.HERE}/results/results_133.json", "w"), indent=1, default=float)
log({"id": "133", "test": "structured brute force 50,000 same-day rules (prereg 133_134)", "trials_added": N_REAL,
     "cum_trials": CUM_BEFORE + N_REAL, "threshold_t1": thr, "best_real_t1": out["best_real_t1"],
     "n_survivors_disc": len(cands), "n_conf_pass": sum(c["conf_pass"] for c in out["candidates"]),
     "candidates": out["candidates"]})
