"""#141 silver -> gold cross-asset conditions (prereg/PREREGISTRATION_141_cross_asset.md)."""
import json, numpy as np, pandas as pd
import lab, bf
from lablog import log

CUM_BEFORE = 140172; N = 10000; NMIN = 150

M = lab.Mkt(lab.load_hourly("XAUUSD")); B = bf.build(M)
S = lab.load_hourly("XAGUSD").reindex(M.idx)            # silver on the gold bars
so, sc = S.o.values, S.c.values
nd = len(M.days)
# silver daily close per gold day (last available silver close inside the day)
sday = pd.Series(sc).groupby(M.dayof).last(); sday = sday[sday.index >= 0].reindex(range(nd)).ffill().values
gday = M.D.c.values
sr1 = np.r_[np.nan, np.log(sday[1:] / sday[:-1])]; gr1 = np.r_[np.nan, np.log(gday[1:] / gday[:-1])]
sr5 = np.r_[np.full(5, np.nan), np.log(sday[5:] / sday[:-5])]
ratio = np.log(gday / sday); rz = (ratio - pd.Series(ratio).rolling(20).mean().values) / pd.Series(ratio).rolling(20).std().values
new_daily = []
for nm, x in (("s_r1", sr1), ("gs_r1", gr1 - sr1), ("s_r5", sr5), ("gs_ratioz", rz)):
    for q, a in zip(("lo", "mid", "hi"), bf.past_terciles(x)): new_daily.append((f"{nm}_{q}", nm, bf.lag(a)))
base_n = len(B["names"])
for E in bf.ES:
    jE = M.dh[:, E]; ssf = np.full(nd, np.nan); gsf = np.full(nd, np.nan)
    for t in np.flatnonzero(jE > M.s):
        a, b = M.s[t], jE[t] - 1
        sa = so[a:b + 1]; sb = sc[a:b + 1]
        if np.isfinite(sa).any() and np.isfinite(sb).any():
            s0 = sa[np.isfinite(sa)][0]; s1 = sb[np.isfinite(sb)][-1]; ssf[t] = np.log(s1 / s0); gsf[t] = np.log(M.c[b] / M.o[a]) - ssf[t]
    rows = list(new_daily)
    for nm, x in (("s_sofar", ssf), ("gs_sofar", gsf)):
        for q, a in zip(("lo", "mid", "hi"), bf.past_terciles(x)): rows.append((f"{nm}_{q}", nm, a))
    B["C"][E] = np.vstack([B["C"][E]] + [r[2].astype(bool) for r in rows])
    if E == bf.ES[0]:
        B["names"] += [r[0] for r in rows]; B["groups"] += [r[1] for r in rows]
newidx = list(range(base_n, len(B["names"]))); groups = np.array(B["groups"])
rng = np.random.default_rng(141); no = len(B["outs"]); rules = [(oi, a, -1) for oi in range(no) for a in newidx]; seen = set(rules)
while len(rules) < N:
    oi = int(rng.integers(no)); a = int(rng.choice(newidx)); b = int(rng.integers(1, base_n))
    if groups[a] == groups[b]: continue
    r = (oi, min(a, b), max(a, b))
    if r in seen: continue
    seen.add(r); rules.append(r)
R = np.array(rules, dtype=np.int64)
disc = np.flatnonzero((M.days >= lab.DISC[0]) & (M.days < lab.DISC[1])); conf = np.flatnonzero((M.days >= lab.CONF[0]) & (M.days < lab.CONF[1]))
SR = bf.evaluate(B, R, disc); ok = SR.n >= NMIN; SR["rule"] = [bf.rule_name(B, r) for r in R]
top = SR[ok].sort_values("t1", ascending=False); print(top.head(15)[["n", "mean1", "t1", "t2", "rule"]].to_string(), flush=True)
RN = bf.gen_rules(B, CUM_BEFORE, 133)   # top-up (library rules only)
nulls = []; rr = np.random.default_rng(1410)
for k in range(20):
    sh = int(rr.integers(250, len(disc) - 250))
    a = bf.evaluate(B, R, disc, shift=sh); b = bf.evaluate(B, RN, disc, shift=sh)
    m = max(a.t1[a.n >= NMIN].max(), b.t1[b.n >= NMIN].max()); nulls.append(float(m)); print("null", k, round(m, 3), flush=True)
thr = float(np.percentile(nulls, 95)); print("threshold", thr)
surv = top[(top.t1 > thr) & (top.t2 >= 2)]
out = {"threshold_t1": thr, "nulls": nulls, "best_real_t1": float(top.t1.iloc[0]), "top10": top.head(10)[["n", "mean1", "t1", "t2", "rule"]].to_dict("records"), "n_surv": len(surv)}
if len(surv):
    SC = bf.evaluate(B, R[surv.index.values[:10]], conf); out["conf"] = [dict(rule=r, n=float(c.n), mean1=float(c.mean1), t1=float(c.t1), t2=float(c.t2)) for r, (_, c) in zip(surv.rule[:10], SC.iterrows())]
    print(out["conf"])
json.dump(out, open(f"{lab.HERE}/results/results_141.json", "w"), indent=1, default=float)
log({"id": "141", "test": "silver->gold cross-asset conditions, 10,000 rules (prereg 141)", "trials_added": N, "cum_trials": CUM_BEFORE + N, **{k: out[k] for k in ("threshold_t1", "best_real_t1", "n_surv")}, "conf": out.get("conf")})
