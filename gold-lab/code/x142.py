"""#142 EURUSD (dollar) -> gold cross-asset conditions (prereg/PREREGISTRATION_142_143_round4.md). Vault never loaded."""
import json, numpy as np, pandas as pd
from scipy import stats
import lab, bf
from lablog import log

CUM_BEFORE = 150172; N = 10000; NMIN = 150

M = lab.Mkt(lab.load_hourly("XAUUSD")); B = bf.build(M)
X = lab.load_hourly("EURUSD").reindex(M.idx)              # EURUSD on the gold bars
xo, xc = X.o.values, X.c.values
nd = len(M.days)
xday = pd.Series(xc).groupby(M.dayof).last(); xday = xday[xday.index >= 0].reindex(range(nd)).ffill().values
gday = M.D.c.values
er1 = np.r_[np.nan, np.log(xday[1:] / xday[:-1])]; gr1 = np.r_[np.nan, np.log(gday[1:] / gday[:-1])]
er5 = np.r_[np.full(5, np.nan), np.log(xday[5:] / xday[:-5])]
corr20 = pd.Series(gr1).rolling(20).corr(pd.Series(er1)).values
new_daily = []
for nm, x in (("e_r1", er1), ("ge_r1", gr1 - er1), ("e_r5", er5), ("ge_corr20", corr20)):
    for q, a in zip(("lo", "mid", "hi"), bf.past_terciles(x)): new_daily.append((f"{nm}_{q}", nm, bf.lag(a)))
base_n = len(B["names"])
for E in bf.ES:
    jE = M.dh[:, E]; esf = np.full(nd, np.nan); gsf = np.full(nd, np.nan)
    for t in np.flatnonzero(jE > M.s):
        a, b = M.s[t], jE[t] - 1
        sa = xo[a:b + 1]; sb = xc[a:b + 1]
        if np.isfinite(sa).any() and np.isfinite(sb).any():
            s0 = sa[np.isfinite(sa)][0]; s1 = sb[np.isfinite(sb)][-1]; esf[t] = np.log(s1 / s0); gsf[t] = np.log(M.c[b] / M.o[a]) - esf[t]
    rows = list(new_daily)
    for nm, x in (("e_sofar", esf), ("ge_sofar", gsf)):
        for q, a in zip(("lo", "mid", "hi"), bf.past_terciles(x)): rows.append((f"{nm}_{q}", nm, a))
    B["C"][E] = np.vstack([B["C"][E]] + [r[2].astype(bool) for r in rows])
    if E == bf.ES[0]:
        B["names"] += [r[0] for r in rows]; B["groups"] += [r[1] for r in rows]
newidx = list(range(base_n, len(B["names"]))); groups = np.array(B["groups"])
print("new conditions", len(newidx), "EURUSD coverage on gold bars", round(float(np.isfinite(xc).mean()), 3), flush=True)
rng = np.random.default_rng(142); no = len(B["outs"]); rules = [(oi, a, -1) for oi in range(no) for a in newidx]; seen = set(rules)
while len(rules) < N:
    oi = int(rng.integers(no)); a = int(rng.choice(newidx)); b = int(rng.integers(1, base_n))
    if groups[a] == groups[b]: continue
    r = (oi, min(a, b), max(a, b))
    if r in seen: continue
    seen.add(r); rules.append(r)
R = np.array(rules, dtype=np.int64); assert len(R) == N
disc = np.flatnonzero((M.days >= lab.DISC[0]) & (M.days < lab.DISC[1])); conf = np.flatnonzero((M.days >= lab.CONF[0]) & (M.days < lab.CONF[1]))
SR = bf.evaluate(B, R, disc); ok = SR.n >= NMIN; SR["rule"] = [bf.rule_name(B, r) for r in R]
top = SR[ok].sort_values("t1", ascending=False); print(top.head(15)[["n", "mean1", "t1", "t2", "rule"]].to_string(), flush=True)
RN = bf.gen_rules(B, CUM_BEFORE, 133)   # top-up (library rules only)
nulls = []; rr = np.random.default_rng(1420)
for k in range(20):
    sh = int(rr.integers(250, len(disc) - 250))
    a = bf.evaluate(B, R, disc, shift=sh); b = bf.evaluate(B, RN, disc, shift=sh)
    m = max(a.t1[a.n >= NMIN].max(), b.t1[b.n >= NMIN].max()); nulls.append(float(m)); print("null", k, round(m, 3), flush=True)
thr = float(np.percentile(nulls, 95)); print("threshold", thr, flush=True)
surv = top[(top.t1 > thr) & (top.t2 >= 2)]
out = {"threshold_t1": thr, "nulls": nulls, "best_real_t1": float(top.t1.iloc[0]),
       "top10": top.head(10)[["n", "mean1", "t1", "t2", "rule"]].to_dict("records"), "n_surv_t": int(len(surv)), "candidates": []}
cands = []; dd = M.days[disc]
for i in surv.index:
    T = bf.rule_trades(M, B, R[i], lab.DISC)
    pt = lab.random_time_p(M, T, lab.DISC, 2000, np.random.default_rng(142))
    if pt >= 0.05: print("placebo fail", SR.rule[i], pt); continue
    d = lab.daily_pnl(T, days=dd)
    if any(abs(np.corrcoef(d, c["d"])[0, 1]) > 0.7 for c in cands): continue
    cands.append(dict(i=int(i), rule=SR.rule[i], d=d, p_time=pt))
    if len(cands) >= 10: break
if cands:
    SC = bf.evaluate(B, R[[c["i"] for c in cands]], conf)
    p = [float(stats.t.sf(t, max(n - 1, 1))) for t, n in zip(SC.t1, SC.n)]; adj = lab.holm(p)
    for c, (_, r), a in zip(cands, SC.iterrows(), adj):
        rec = {"rule": c["rule"], "disc": SR.loc[c["i"], ["n", "mean1", "t1", "mean2", "t2"]].to_dict(), "p_time_disc": c["p_time"],
               "conf": r[["n", "mean1", "t1", "mean2", "t2"]].to_dict(), "conf_holm": float(a),
               "conf_pass": bool(r.mean1 > 0 and r.mean2 > 0 and a < 0.05)}
        out["candidates"].append(rec); print(json.dumps(rec, default=float), flush=True)
json.dump(out, open(f"{lab.HERE}/results/results_142.json", "w"), indent=1, default=float)
log({"id": "142", "test": "EURUSD->gold cross-asset conditions, 10,000 rules (prereg 142_143)", "trials_added": N, "cum_trials": CUM_BEFORE + N,
     "threshold_t1": thr, "best_real_t1": out["best_real_t1"], "n_surv_t": out["n_surv_t"], "n_cand": len(cands),
     "n_conf_pass": sum(c["conf_pass"] for c in out["candidates"]), "candidates": out["candidates"]})
