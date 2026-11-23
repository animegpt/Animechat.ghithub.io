"""#143 two-market agreement search: S = min(t_gold, t_silver) on the #133 universe (prereg/PREREGISTRATION_142_143_round4.md).
Each market's conditions/outcomes are built from its own data with bf.build. Vault never loaded."""
import json, time, numpy as np, pandas as pd
from scipy import stats
import lab, bf
from lablog import log

CUM_BEFORE = 160172; N = 50000; CUM = CUM_BEFORE + N; NMIN = 150; NNULL = 20

G = lab.Mkt(lab.load_hourly("XAUUSD"), "XAUUSD"); BG = bf.build(G)
S_ = lab.Mkt(lab.load_hourly("XAGUSD"), "XAGUSD"); BS = bf.build(S_)
for k, (g, n1, n2) in BS["Y"].items(): BS["Y"][k] = (g, n1, n1.copy())      # silver: second cost scenario = primary
assert BG["names"] == BS["names"] and BG["outs"] == BS["outs"]
dg = np.flatnonzero((G.days >= lab.DISC[0]) & (G.days < lab.DISC[1])); cg = np.flatnonzero((G.days >= lab.CONF[0]) & (G.days < lab.CONF[1]))
ds = np.flatnonzero((S_.days >= lab.DISC[0]) & (S_.days < lab.DISC[1])); cs = np.flatnonzero((S_.days >= lab.CONF[0]) & (S_.days < lab.CONF[1]))
print("days disc gold/silver", len(dg), len(ds), flush=True)


def score(R, shift=0):
    a = bf.evaluate(BG, R, dg, shift=shift); b = bf.evaluate(BS, R, ds, shift=shift)
    ok = (a.n >= NMIN) & (b.n >= NMIN)
    s = np.where(ok, np.minimum(a.t1, b.t1), -np.inf)
    return a, b, s, ok


R = bf.gen_rules(BG, N, 143)
t0 = time.time(); A, Bs, Sc, ok = score(R); print("real eval s", round(time.time() - t0, 1), "scored", int(ok.sum()), flush=True)
names = [bf.rule_name(BG, r) for r in R]
real = pd.DataFrame({"rule": names, "n_g": A.n, "t1_g": A.t1, "t2_g": A.t2, "mean1_g": A.mean1, "n_s": Bs.n, "t1_s": Bs.t1, "mean1_s": Bs.mean1, "S": Sc})
top = real[ok].sort_values("S", ascending=False)
print(top.head(15).to_string(), flush=True)
print("best gold-only t1 among these rules", float(A.t1[A.n >= NMIN].max()), flush=True)

RN = bf.gen_rules(BG, CUM, 143)       # null search at cumulative size; first N rows == R
assert (RN[:N] == R).all()
nulls = []; nulls_g = []; rr = np.random.default_rng(1430)
for k in range(NNULL):
    sh = int(rr.integers(250, min(len(dg), len(ds)) - 250)); t0 = time.time()
    a, b, s, okn = score(RN, sh)
    nulls.append(float(s.max())); nulls_g.append(float(a.t1[a.n >= NMIN].max()))
    print("null", k, sh, round(nulls[-1], 3), "gold-only", round(nulls_g[-1], 3), f"{time.time() - t0:.0f}s", flush=True)
thr = float(np.percentile(nulls, 95)); thr_g = float(np.percentile(nulls_g, 95))
print("threshold S", thr, "gold-only info", thr_g, flush=True)

surv = top[(top.S > thr) & (top.t2_g >= 2)]
out = {"threshold_S": thr, "nulls_S": nulls, "threshold_goldonly_info": thr_g, "nulls_goldonly": nulls_g, "best_real_S": float(top.S.iloc[0]),
       "var_sr_ann_gold": float(A.sr_ann[ok].var()), "top10": top.head(10).to_dict("records"), "n_surv_t": int(len(surv)), "candidates": []}
cands = []; ddg = G.days[dg]
for i in surv.index:
    Tg = bf.rule_trades(G, BG, R[i], lab.DISC); Ts = bf.rule_trades(S_, BS, R[i], lab.DISC)
    pg = lab.random_time_p(G, Tg, lab.DISC, 2000, np.random.default_rng(143)); ps = lab.random_time_p(S_, Ts, lab.DISC, 2000, np.random.default_rng(143))
    if pg >= 0.05 or ps >= 0.05: print("placebo fail", names[i], pg, ps); continue
    d = lab.daily_pnl(Tg, days=ddg)
    if any(abs(np.corrcoef(d, c["d"])[0, 1]) > 0.7 for c in cands): continue
    cands.append(dict(i=int(i), rule=names[i], d=d, p_time_g=pg, p_time_s=ps))
    if len(cands) >= 10: break
if cands:
    ix = [c["i"] for c in cands]
    CGr = bf.evaluate(BG, R[ix], cg); CSr = bf.evaluate(BS, R[ix], cs)
    p = [float(stats.t.sf(t, max(n - 1, 1))) for t, n in zip(CGr.t1, CGr.n)]; adj = lab.holm(p)
    for c, (_, rg), (_, rs), a in zip(cands, CGr.iterrows(), CSr.iterrows(), adj):
        rec = {"rule": c["rule"], "disc": real.loc[c["i"]].drop("rule").to_dict(), "p_time_g": c["p_time_g"], "p_time_s": c["p_time_s"],
               "conf_gold": rg[["n", "mean1", "t1", "mean2", "t2"]].to_dict(), "conf_silver": rs[["n", "mean1", "t1"]].to_dict(), "conf_holm": float(a),
               "conf_pass": bool(rg.mean1 > 0 and rg.mean2 > 0 and a < 0.05 and rs.mean1 > 0)}
        out["candidates"].append(rec); print(json.dumps(rec, default=float), flush=True)
json.dump(out, open(f"{lab.HERE}/results/results_143.json", "w"), indent=1, default=float)
log({"id": "143", "test": "gold+silver agreement search, S=min(t_gold,t_silver), 50,000 rules (prereg 142_143)", "trials_added": N, "cum_trials": CUM,
     "threshold_S": thr, "threshold_goldonly_info": thr_g, "best_real_S": out["best_real_S"], "n_surv_t": out["n_surv_t"], "n_cand": len(cands),
     "n_conf_pass": sum(c["conf_pass"] for c in out["candidates"]), "candidates": out["candidates"]})
