"""#145 MODERN cross-asset conditions (USDCNH, US500, USDJPY) -> gold, disc 2017-2021 (prereg 144_146).
Also exports build_modern(M) for #146."""
import json, numpy as np, pandas as pd
import lab, bf
from lablog import log

CUM_BEFORE = 260172; N = 10000; NMIN = 100
MD = (pd.Timestamp("2017-01-01"), pd.Timestamp("2022-01-01")); MC = (pd.Timestamp("2022-01-01"), pd.Timestamp("2024-01-01"))


def build_modern(M, B):
    nd = len(M.days); base_n = len(B["names"]); new_names = []; new_groups = []
    rows_by_E = {E: [] for E in bf.ES}
    for inst, tag, five in (("USDCNH", "cnh", True), ("USA500IDXUSD", "spx", False), ("USDJPY", "jpy", False)):
        S = lab.load_hourly(inst).reindex(M.idx); so, sc = S.o.values, S.c.values
        sday = pd.Series(sc).groupby(M.dayof).last(); sday = sday[sday.index >= 0].reindex(range(nd)).ffill().values
        r1 = np.r_[np.nan, np.log(sday[1:] / sday[:-1])]
        daily = [(f"{tag}_r1", r1)]
        if five: daily.append((f"{tag}_r5", np.r_[np.full(5, np.nan), np.log(sday[5:] / sday[:-5])]))
        dl = []
        for nm, x in daily:
            for q, a in zip(("lo", "mid", "hi"), bf.past_terciles(x)): dl.append((f"{nm}_{q}", nm, bf.lag(a)))
        for E in bf.ES:
            jE = M.dh[:, E]; sf = np.full(nd, np.nan)
            for t in np.flatnonzero(jE > M.s):
                a, b = M.s[t], jE[t] - 1; sa = so[a:b + 1]; sb = sc[a:b + 1]
                fa = sa[np.isfinite(sa)]; fb = sb[np.isfinite(sb)]
                if len(fa) and len(fb): sf[t] = np.log(fb[-1] / fa[0])
            rows = list(dl) + [(f"{tag}_sofar_{q}", f"{tag}_sofar", a) for q, a in zip(("lo", "mid", "hi"), bf.past_terciles(sf))]
            rows_by_E[E] += rows
    for E in bf.ES:
        rows = rows_by_E[E]
        B["C"][E] = np.vstack([B["C"][E]] + [r[2].astype(bool) for r in rows])
    B["names"] += [r[0] for r in rows_by_E[bf.ES[0]]]; B["groups"] += [r[1] for r in rows_by_E[bf.ES[0]]]
    return list(range(base_n, len(B["names"]))), base_n


if __name__ == "__main__":
    M = lab.Mkt(lab.load_hourly("XAUUSD")); B = bf.build(M)
    newidx, base_n = build_modern(M, B); print("new conditions", len(newidx), flush=True)
    groups = np.array(B["groups"]); rng = np.random.default_rng(145); no = len(B["outs"])
    rules = [(oi, a, -1) for oi in range(no) for a in newidx]; seen = set(rules)
    while len(rules) < N:
        oi = int(rng.integers(no)); a = int(rng.choice(newidx)); b = int(rng.integers(1, base_n))
        if groups[a] == groups[b]: continue
        r = (oi, min(a, b), max(a, b))
        if r in seen: continue
        seen.add(r); rules.append(r)
    R = np.array(rules, dtype=np.int64)
    disc = np.flatnonzero((M.days >= MD[0]) & (M.days < MD[1])); conf = np.flatnonzero((M.days >= MC[0]) & (M.days < MC[1]))
    SR = bf.evaluate(B, R, disc); ok = SR.n >= NMIN; SR["rule"] = [bf.rule_name(B, r) for r in R]
    top = SR[ok].sort_values("t1", ascending=False); print(top.head(15)[["n", "mean1", "t1", "t2", "rule"]].to_string(), flush=True)
    RN = bf.gen_rules(B, CUM_BEFORE, 144)
    nulls = []; rr = np.random.default_rng(1450)
    for k in range(20):
        sh = int(rr.integers(120, len(disc) - 120))
        a = bf.evaluate(B, R, disc, shift=sh); b = bf.evaluate(B, RN, disc, shift=sh)
        m = max(a.t1[a.n >= NMIN].max(), b.t1[b.n >= NMIN].max()); nulls.append(float(m)); print("null", k, round(m, 3), flush=True)
    thr = float(np.percentile(nulls, 95)); print("threshold", thr)
    surv = top[(top.t1 > thr) & (top.t2 >= 2)]
    out = {"threshold_t1": thr, "nulls": nulls, "best_real_t1": float(top.t1.iloc[0]), "top10": top.head(10)[["n", "mean1", "t1", "t2", "rule"]].to_dict("records"), "n_surv": len(surv)}
    if len(surv):
        SC = bf.evaluate(B, R[surv.index.values[:10]], conf)
        out["conf"] = [dict(rule=r, n=float(c.n), mean1=float(c.mean1), t1=float(c.t1), t2=float(c.t2)) for r, (_, c) in zip(surv.rule[:10], SC.iterrows())]
        print(out["conf"])
    json.dump(out, open(f"{lab.HERE}/results/results_145.json", "w"), indent=1, default=float)
    log({"id": "145", "test": "MODERN cross-asset (USDCNH, US500, USDJPY) -> gold, 10,000 rules, disc 2017-2021 (prereg 144_146)", "trials_added": N,
         "cum_trials": CUM_BEFORE + N, **{k: out[k] for k in ("threshold_t1", "best_real_t1", "n_surv")}, "conf": out.get("conf")})
