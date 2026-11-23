"""#152 verdict (prereg 149_153 section 5) + silver clean ground (+ gold vault only with VAULT_LOOK=1 after audit).
usage: python verdict152.py verdict          -> results/results_152_verdict.json
       python verdict152.py silver NAME      -> silver test for a model variant (e.g. hgb_cls_A) or rule:<idx>
       VAULT_LOOK=1 OPEN_VAULT=1 python verdict152.py vault NAME"""
import os, sys, json, pickle
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, features149 as F, metric149 as MT, rules151 as R, models150 as MD
CACHE = lab.CACHE; HERE = lab.HERE
CUM_BEFORE = 300172


def gold():
    D = pd.read_parquet(f"{CACHE}/feat149_XAUUSD.parquet"); return D[D.t >= "2005-01-01"].reset_index(drop=True)


def verdict():
    M150 = json.load(open(f"{HERE}/results/results_150.json"))
    R151 = json.load(open(f"{HERE}/results/results_151.json"))
    st = np.load(f"{CACHE}/rules151_stats.npz")
    names = list(M150)
    pm = np.array([stats.norm.sf(M150[k]["all"]["t_jkm"]) for k in names])
    pr = stats.norm.sf(st["ta"])
    n_trials = len(names) + len(pr)
    adj = MT.holm(np.r_[pm, pr]); adj_m = adj[:len(names)]; adj_r = adj[len(names):]
    adj_models_only = MT.holm(pm)
    # overlay Sharpe of every trial (for the DSR cross-trial variance)
    D = gold(); S = R.search(D, D.side.values.astype(float))
    m, G, months = MT.month_matrix(D.t, MT.P_ALL); rr = S["r"][m]; nb = len(S["rules"])
    ov_sh = []
    for s in range(0, nb, 4000):
        Rb = S["rules"][s:s + 4000]; L = max(len(x) for x in Rb)
        idx = np.array([list(x) + [x[0]] * (L - len(x)) for x in Rb]); mk = np.ones((m.sum(), len(Rb)), bool)
        for j in range(L): mk &= S["Mall"][m][:, idx[:, j]]
        Q = G @ (rr[:, None] * mk); ov_sh.append(MT.sharpe_m(0.5 * Q) * np.sqrt(12))
    ov_rules = np.concatenate(ov_sh); ov_rules = np.r_[ov_rules, ov_rules]   # down action = -overlay, same |SR|... sign flips
    ov_rules[nb:] *= -1
    P = pd.read_parquet(f"{MD.OUT}/oos_pct.parquet"); P = P[P.t >= "2009-01-01"].reset_index(drop=True)
    ov_models = {}
    for k in names:
        mdl, tg, mp = k.split("_"); pc = P[f"pct_{mdl}_{tg}"].values
        ov_models[k] = MT.overlay_monthly(P.t, P.net1.values, MD.sizes(pc)[mp], MT.P_ALL)
    sr_models = np.array([MT.sharpe_m(ov_models[k][:, None])[0] * np.sqrt(12) for k in names])
    var_sr = float(np.var(np.r_[sr_models, ov_rules], ddof=1))
    N = CUM_BEFORE + n_trials
    rows = []
    for i, k in enumerate(names):
        r = M150[k]; dsr, sr, sr0 = MT.dsr_monthly(ov_models[k], N, var_sr)
        g = {"g1_all_D_pos_t2": r["all"]["D"] > 0 and r["all"]["t_jkm"] >= 2 and r["all"]["t_boot"] >= 2,
             "g2_both_periods_D_pos": r["disc"]["D"] > 0 and r["conf"]["D"] > 0,
             "g4_holm_all": bool(adj_m[i] < 0.05), "g5_dsr": dsr >= 0.95}
        rows.append(dict(name=k, kind="model", D_disc=r["disc"]["D"], D_conf=r["conf"]["D"], D_all=r["all"]["D"],
                         t_jkm=r["all"]["t_jkm"], t_boot=r["all"]["t_boot"], t_conf=r["conf"]["t_jkm"], holm_all=float(adj_m[i]),
                         holm_models_only=float(adj_models_only[i]), dsr=dsr, overlay_sr=sr, gates=g, passes=all(g.values())))
    thr = R151["threshold"]
    cand = np.flatnonzero((st["td"] > thr) & (st["td"] >= 2))
    cand = np.unique(np.r_[cand, np.argsort(-st["ta"])[:5], np.argsort(-st["td"])[:5]])
    for i in cand:
        body = S["rules"][i % nb]; act = "up" if i < nb else "down"
        size = np.where(S["Mall"][:, list(body)].all(1), 1.5 if act == "up" else 0.5, 1.0)
        ev = {pn: MT.evaluate(D.t, S["r"], size, per) for pn, per in (("disc", MT.P_DISC), ("conf", MT.P_CONF), ("all", MT.P_ALL))}
        dsr, sr, sr0 = MT.dsr_monthly(MT.overlay_monthly(D.t, S["r"], size, MT.P_ALL), N, var_sr)
        g = {"g1_all_D_pos_t2": ev["all"]["D"] > 0 and ev["all"]["t_jkm"] >= 2 and ev["all"]["t_boot"] >= 2,
             "g2_both_periods_D_pos": ev["disc"]["D"] > 0 and ev["conf"]["D"] > 0,
             "g3_beats_luck": bool(st["td"][i] > thr and st["td"][i] >= 2),
             "g4_holm_all": bool(adj_r[i] < 0.05), "g5_dsr": dsr >= 0.95}
        rows.append(dict(name=f"rule:{int(i)}", kind="rule", rule=R.describe(S["specs"], S["th"], body, act),
                         D_disc=ev["disc"]["D"], D_conf=ev["conf"]["D"], D_all=ev["all"]["D"], t_disc=ev["disc"]["t_jkm"],
                         t_jkm=ev["all"]["t_jkm"], t_boot=ev["all"]["t_boot"], t_conf=ev["conf"]["t_jkm"], holm_all=float(adj_r[i]),
                         dsr=dsr, overlay_sr=sr, gates=g, passes=all(g.values())))
    out = dict(n_trials_study=n_trials, N_dsr=N, var_sr_annual=var_sr, luck_threshold=thr, rows=rows,
               passers=[r["name"] for r in rows if r["passes"]])
    json.dump(out, open(f"{HERE}/results/results_152_verdict.json", "w"), indent=1, default=float)
    for r in rows:
        print(r["name"], r.get("rule", ""), "D", r["D_disc"], r["D_conf"], r["D_all"], "t", r["t_jkm"], r["t_boot"],
              "holm", round(r["holm_all"], 4), "dsr", round(r["dsr"], 3), "PASS" if r["passes"] else "")
    print("passers:", out["passers"])


def apply(name, D_new):
    """frozen model / rule on a new feature table -> size vector"""
    X = F.make_X(D_new, D_new.side.values.astype(float))
    if name.startswith("rule:"):
        Dg = gold(); S = R.search(Dg, Dg.side.values.astype(float)); i = int(name[5:]); nb = len(S["rules"])
        body = S["rules"][i % nb]; act = "up" if i < nb else "down"
        Mk = R.masks(X, S["specs"], S["th"])
        return np.where(Mk[:, list(body)].all(1), 1.5 if act == "up" else 0.5, 1.0)
    mdl, tg, mp = name.split("_")
    fz = pickle.load(open(f"{MD.OUT}/finals.pkl", "rb")); fin = fz["finals"]; Xv = X[fz["cols"]].values
    if mdl == "ens":
        pcs = [MD.pct_of(MD.predict(fin[(m, tg)]["fitted"], Xv, tg), fin[(m, tg)]["ref"]) for m in MD.MODELS]
        pc = MD.pct_of(np.mean(pcs, axis=0), fin[("ens", tg)]["ref"])
    else:
        pc = MD.pct_of(MD.predict(fin[(mdl, tg)]["fitted"], Xv, tg), fin[(mdl, tg)]["ref"])
    return MD.sizes(pc)[mp]


def clean(name, which):
    if which == "silver":
        p = f"{CACHE}/feat149_XAGUSD_vault.parquet"; P = ("2023-01-01", "2026-11-01")
    else:
        assert os.environ.get("VAULT_LOOK") == "1" and os.environ.get("OPEN_VAULT") == "1"
        p = f"{CACHE}/feat149_XAUUSD_vault.parquet"; P = ("2024-01-01", "2026-11-01")
    D = pd.read_parquet(p); size = apply(name, D)
    res = {"name": name, "market": which, "period": P, "net1": MT.evaluate(D.t, D.net1.values, size, P),
           "net2": MT.evaluate(D.t, D.net2.values, size, P, boot=False)}
    m = (D.t >= P[0]) & (D.t < P[1]); r = D.net1.values[m]
    res["plain_williams"] = {"n": int(m.sum()), "mean_bp": round(float(r.mean() * 1e4), 2), "t": round(lab.tstat(r), 2)}
    tag = name.replace(":", "")
    json.dump(res, open(f"{HERE}/results/results_152_{which}_{tag}.json", "w"), indent=1, default=float)
    print(json.dumps(res, default=float))


if __name__ == "__main__":
    if sys.argv[1] == "verdict": verdict()
    else: clean(sys.argv[2], sys.argv[1])
