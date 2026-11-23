"""retrain.py: rebuild the GoldComboAI models up to a cutoff date and regenerate GoldComboAI.mq5 (policy from #106: retrain
yearly on ALL data up to the cutoff, expanding window). Uses the research scripts unchanged (export_sonic_ai_pine.py,
export_pine_model.py, build_mt5_ea.py) inside a temporary copy whose raw/ only links data files up to the cutoff.

usage:
  python retrain.py --research ~/gold-research --cutoff 2026-12-31 --out ./retrained
The research dir must contain code/ and raw/ (cache_XAUUSD_h, cache_XAUUSD_ASK_h, cache_EURUSD_h, ...).
Outputs: <out>/GoldComboAI.mq5, <out>/sonic_ai_model_arrays.json, <out>/pine_model_params.json, <out>/retrain_report.json
The run FAILS (exit code 1) if any parity check fails."""
import argparse, os, re, sys, json, shutil, subprocess, tempfile
import numpy as np


def link_raw(src_raw, dst_raw, cutoff):
    """link monthly (YYYY-MM.bi5) and daily (YYYY-MM-DD.bi5) cache files with dates <= cutoff; copy small dirs (fred) as-is"""
    n = 0
    for d in sorted(os.listdir(src_raw)):
        s = os.path.join(src_raw, d); t = os.path.join(dst_raw, d)
        if not os.path.isdir(s): continue
        os.makedirs(t, exist_ok=True)
        for f in os.listdir(s):
            m = re.match(r"(\d{4}-\d{2})(-\d{2})?\.bi5$", f)
            if m:
                key = m.group(1) + (m.group(2) or "-01")
                if key > cutoff: continue
            os.symlink(os.path.join(s, f), os.path.join(t, f)); n += 1
    return n


def run(script, cwd, subs):
    src = open(os.path.join(cwd, "code", script), encoding="utf-8").read()
    for a, b in subs: src = src.replace(a, b)
    p = os.path.join(cwd, "code", "_rt_" + script); open(p, "w", encoding="utf-8").write(src)
    r = subprocess.run([sys.executable, p], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:]); raise SystemExit(f"{script} failed")
    return r.stdout


def parse_arr(src, name, cast=float):
    m = re.search(rf"{name}\[(\d+)\]\s*=\s*\{{(.*?)\}};", src, re.S)
    return [cast(x) for x in m.group(2).replace("\n", "").split(",") if x.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--research", required=True); ap.add_argument("--cutoff", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args(); res = os.path.abspath(os.path.expanduser(a.research)); os.makedirs(a.out, exist_ok=True)
    W = tempfile.mkdtemp(prefix="retrain_"); shutil.copytree(os.path.join(res, "code"), os.path.join(W, "code"))
    os.makedirs(os.path.join(W, "raw")); nlinks = link_raw(os.path.join(res, "raw"), os.path.join(W, "raw"), a.cutoff)
    os.makedirs(os.path.join(W, "mt5"), exist_ok=True); os.makedirs(os.path.join(W, "pine"), exist_ok=True)
    end = (np.datetime64(a.cutoff) + np.timedelta64(1, "D")).astype(str)
    report = {"cutoff": a.cutoff, "raw_files_linked": nlinks, "policy": "yearly retrain on all data up to cutoff (#106)"}
    # 1) Sonic AI sizing model (300 HistGB trees) -> sonic_ai_model_arrays.json (+ Pine)
    out1 = run("export_sonic_ai_pine.py", W, [('"2026-11-01"', f'"{end}"')])
    m = re.search(r"max \|pine-sklearn\| prob diff:\s*([0-9.eE+-]+)", out1); d1 = float(m.group(1)) if m else np.inf
    report["sonic_trades"] = re.search(r"training trades (\d+)", out1).group(1) if "training trades" in out1 else None
    report["parity_sonic_arrays_vs_sklearn_maxdiff"] = d1
    # 2) Overnight logistic model (18 features) -> pine_model_params.json + Gold_Overnight_AI.pine
    run("export_pine_model.py", W, [])
    P = json.load(open(os.path.join(W, "pine_model_params.json"))); report["overnight_threshold"] = P["threshold"]; report["overnight_trained_on"] = P["trained_on"]
    # 3) EA generation
    run("build_mt5_ea.py", W, [("/home/user/gold-research", W)])
    ea = open(os.path.join(W, "mt5", "GoldComboAI.mq5"), encoding="utf-8").read()
    ea = re.sub(r"(input double InpOnThr\s*=\s*)[0-9.]+", lambda mm: mm.group(1) + f"{P['threshold']:.6f}", ea)
    ea = ea.replace("//| Research: gold-research (walk-forward, out-of-sample 2012-2025)  |", f"//| Retrained on data up to {a.cutoff} (retrain.py)                    |")
    # 4) parity checks: EA arrays == JSON arrays ; EA overnight coefficients reproduce sklearn probabilities
    M = json.load(open(os.path.join(W, "sonic_ai_model_arrays.json")))
    ok_len = all(len(parse_arr(ea, nm, float)) == len(M[k]) for nm, k in (("T_FEAT", "feat"), ("T_THR", "thr"), ("T_RIGHT", "right"), ("T_LEAF", "leaf"), ("T_VAL", "val"), ("T_ROOT", "roots"), ("T_Q", "q")))
    d_thr = float(np.max(np.abs(np.array(parse_arr(ea, "T_THR")) - np.array(M["thr"])))); d_val = float(np.max(np.abs(np.array(parse_arr(ea, "T_VAL")) - np.array(M["val"]))))
    coef = np.array(parse_arr(ea, "ON_COEF")); mean = np.array(parse_arr(ea, "ON_MEAN")); sd = np.array(parse_arr(ea, "ON_SD"))
    import pandas as pd
    X = pd.read_pickle(os.path.join(W, "ml_dataset_all.pkl"))[P["features"]].fillna(0).values
    z_sk = P["intercept"] + ((X - np.array(P["mean"])) / np.array(P["std"])) @ np.array(P["coef"])
    icpt = float(re.search(r"float s = ([-\d.]+)", open(os.path.join(W, "pine", "Gold_Overnight_AI.pine")).read()).group(1))
    z_ea = icpt + ((X - mean) / sd) @ coef
    p_sk, p_ea = 1 / (1 + np.exp(-z_sk)), 1 / (1 + np.exp(-z_ea))
    report.update({"parity_ea_array_lengths": bool(ok_len), "parity_ea_thr_maxdiff": d_thr, "parity_ea_val_maxdiff": d_val,
                   "parity_overnight_prob_maxdiff": float(np.max(np.abs(p_sk - p_ea))),
                   "parity_overnight_decision_agreement": float(np.mean((p_sk > P["threshold"]) == (p_ea > P["threshold"])))})
    passed = (report["parity_sonic_arrays_vs_sklearn_maxdiff"] < 1e-6 and ok_len and d_thr < 1e-9 and d_val < 1e-6
              and report["parity_overnight_prob_maxdiff"] < 1e-4 and report["parity_overnight_decision_agreement"] > 0.999)
    report["PASS"] = bool(passed)
    open(os.path.join(a.out, "GoldComboAI.mq5"), "w", encoding="utf-8").write(ea)
    for f in ("sonic_ai_model_arrays.json", "pine_model_params.json"): shutil.copy(os.path.join(W, f), a.out)
    json.dump(report, open(os.path.join(a.out, "retrain_report.json"), "w"), indent=1, default=float)
    print(json.dumps(report, indent=1, default=float))
    if not a.keep: shutil.rmtree(W, ignore_errors=True)
    sys.exit(0 if passed else 1)
