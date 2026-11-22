"""#88 aggregation: null threshold, distinct top-5 of the real run (discovery only)."""
import json, glob, ast, numpy as np
import os88_lib as L
import os88_search as S

if __name__ == "__main__":
    runs = {int(f[-7:-5]): json.load(open(f)) for f in sorted(glob.glob(f"{L.CACHE}/runs/run_*.json"))}
    null = np.array([runs[k]["best_raw_t"] for k in runs if k > 0]); null_elig = np.array([runs[k]["best"] for k in runs if k > 0])
    thr = float(np.percentile(null, 95))
    real = runs[0]
    print(f"null runs {len(null)}: raw max t per run {np.round(np.sort(null), 2)}")
    print(f"null eligible max per run {np.round(np.sort(null_elig), 2)}")
    print(f"THRESHOLD (95th pct of raw null maxima) = {thr:.3f} | real best eligible {real['best']:.3f} raw {real['best_raw_t']:.3f}")
    X = S.Ctx(0)
    cands = []
    for r in real["top_rules"]:
        if not r["elig"]: continue
        cands.append(("rule", r))
    for g in real["top_gp"]:
        if g.get("elig"): cands.append(("gp", g))
    cands.sort(key=lambda z: -z[1]["t"])
    picked = []; sets = []
    for kind, r in cands:
        if kind == "rule": s, keep = S.eval_rule(X, r["rule"])
        else:
            ind = {"tree": ast.literal_eval(r["ind"]["tree"]), "k": r["ind"]["k"], "ex": r["ind"]["ex"]}; s, keep = S.eval_gp(X, ind)
        if keep is None: continue
        ks = set(keep.tolist())
        if any(len(ks & o) / len(ks | o) >= 0.5 for o in sets): continue
        sets.append(ks); picked.append({"kind": kind, **r, "gap_to_threshold": r["t"] - thr})
        if len(picked) == 5: break
    for p in picked:
        desc = (f"{'LONG' if p['rule']['side']==1 else 'SHORT'} {p['rule']['struct']} {p['rule']['cond_names']} exit {p['rule']['ex']}" if p["kind"] == "rule"
                else f"GP {p['ind']}")
        print(f"t={p['t']:.2f} (gap {p['gap_to_threshold']:+.2f}) n={p['n']} B={p['B_bp']:.2f}bp C={p['C_bp']:.2f}bp | {desc}")
    json.dump({"threshold": thr, "null_raw_max": null.tolist(), "null_elig_max": null_elig.tolist(), "real_best": real["best"], "real_best_raw": real["best_raw_t"],
               "n_evals_per_run": real["n_evals"], "top5": picked, "passes": [p for p in picked if p["t"] > thr]},
              open(f"{L.CACHE}/os88_summary.json", "w"), indent=1, default=float)
