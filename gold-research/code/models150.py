"""#150 walk-forward models (prereg 149_153 section 3). Sizing only.
usage: python models150.py run      -> OOS predictions 2009-2023 + final models (train 2005-2023)
       python models150.py eval     -> results/results_150.json"""
import os, sys, json, pickle, warnings
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from joblib import Parallel, delayed
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, \
    RandomForestRegressor, ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.linear_model import LogisticRegression, Lasso
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, features149 as F, metric149 as MT
warnings.filterwarnings("ignore")
CACHE = lab.CACHE; OUT = f"{CACHE}/models150"; HERE = lab.HERE
TEST_YEARS = list(range(2009, 2024)); FINAL_YEAR = 2024
MODELS = ["hgb", "rf", "l1", "et"]; TARGETS = ["cls", "reg"]


def grid(model):
    if model == "hgb":
        return [dict(learning_rate=a, max_depth=b, max_iter=c) for a in (0.03, 0.1) for b in (2, 3) for c in (100, 300)]
    if model in ("rf", "et"):
        return [dict(max_depth=a, max_features=b, min_samples_leaf=c) for a in (3, 6) for b in ("sqrt", 0.3) for c in (25, 100)]
    return [dict(C=c) for c in (0.003, 0.01, 0.03, 0.1, 0.3)]


def make(model, target, p, seed=0):
    if model == "hgb":
        K = HistGradientBoostingClassifier if target == "cls" else HistGradientBoostingRegressor
        return K(min_samples_leaf=50, l2_regularization=1.0, random_state=seed, early_stopping=False, **p)
    if model in ("rf", "et"):
        K = {("rf", "cls"): RandomForestClassifier, ("rf", "reg"): RandomForestRegressor,
             ("et", "cls"): ExtraTreesClassifier, ("et", "reg"): ExtraTreesRegressor}[(model, target)]
        return K(n_estimators=300, random_state=seed, n_jobs=1, **p)
    if target == "cls":
        return make_pipeline(StandardScaler(), LogisticRegression(penalty="l1", solver="liblinear", C=p["C"], max_iter=2000))
    alpha = {0.003: 1e-3, 0.01: 3e-4, 0.03: 1e-4, 0.1: 3e-5, 0.3: 1e-5}[p["C"]]     # same 5-point ladder, strong -> weak
    return make_pipeline(StandardScaler(), Lasso(alpha=alpha, max_iter=20000))


def predict(m, X, target):
    return m.predict_proba(X)[:, 1] if target == "cls" else m.predict(X)


def labels(D, idx, target):
    r = D.net1.values[idx]
    if target == "cls": return (r > 0).astype(int)
    lo, hi = np.percentile(r, [1, 99]); return np.clip(r, lo, hi)


def purge_idx(D, years, before_year):
    """trades in `years`, minus the last 5 trading days before Jan 1 of before_year"""
    y = D.t.dt.year.values
    sel = np.flatnonzero(np.isin(y, years))
    days = np.sort(D.t[D.t < pd.Timestamp(f"{before_year}-01-01")].unique())
    if len(days) >= 5:
        cut = days[-5]; sel = sel[D.t.values[sel] < cut]
    return sel


def ic(a, b):
    v = spearmanr(a, b).correlation
    return 0.0 if np.isnan(v) else float(v)


def fit_year(D, X, Y, model, target):
    y = D.t.dt.year.values
    vy = [Y - 3, Y - 2, Y - 1]
    best = None
    for p in grid(model):
        ics = []; preds = []
        for v in vy:
            tr = purge_idx(D, list(range(2005, v)), v); va = np.flatnonzero(y == v)
            if len(tr) < 100: continue
            m = make(model, target, p).fit(X[tr], labels(D, tr, target))
            pv = predict(m, X[va], target); ics.append(ic(pv, D.net1.values[va])); preds.append(pv)
        s = float(np.mean(ics))
        if best is None or s > best[0]: best = (s, p, np.concatenate(preds))
    tr = purge_idx(D, list(range(2005, Y)), Y)
    m = make(model, target, best[1]).fit(X[tr], labels(D, tr, target))
    return dict(year=Y, model=model, target=target, params=best[1], inner_ic=best[0], ref=best[2], fitted=m)


def pct_of(x, ref):
    ref = np.sort(ref); return np.searchsorted(ref, x, side="right") / len(ref)


def run():
    os.makedirs(OUT, exist_ok=True)
    D = pd.read_parquet(f"{CACHE}/feat149_XAUUSD.parquet")
    Xdf = F.make_X(D, D.side); X = Xdf.values; cols = list(Xdf.columns)
    jobs = [(Y, m, tg) for Y in TEST_YEARS + [FINAL_YEAR] for m in MODELS for tg in TARGETS]
    res = Parallel(n_jobs=4, verbose=5)(delayed(fit_year)(D, X, Y, m, tg) for Y, m, tg in jobs)
    y = D.t.dt.year.values
    P = pd.DataFrame({"t": D.t, "net1": D.net1, "net2": D.net2, "side": D.side})
    meta = []
    for tg in TARGETS:
        for m in MODELS: P[f"pct_{m}_{tg}"] = np.nan
        P[f"pct_ens_{tg}"] = np.nan
    finals = {}
    for tg in TARGETS:
        for Y in TEST_YEARS + [FINAL_YEAR]:
            te = np.flatnonzero(y == Y); refs_e = []; pcts = []
            for m in MODELS:
                R = [r for r in res if r["year"] == Y and r["model"] == m and r["target"] == tg][0]
                meta.append({k: R[k] for k in ("year", "model", "target", "params", "inner_ic")})
                refs_e.append(pct_of(R["ref"], R["ref"]))
                if Y == FINAL_YEAR: finals[(m, tg)] = R; continue
                pc = pct_of(predict(R["fitted"], X[te], tg), R["ref"]); P.loc[te, f"pct_{m}_{tg}"] = pc; pcts.append(pc)
            ens_ref = np.mean(refs_e, axis=0)
            if Y == FINAL_YEAR: finals[("ens", tg)] = dict(ref=ens_ref); continue
            P.loc[te, f"pct_ens_{tg}"] = pct_of(np.mean(pcts, axis=0), ens_ref)
    P.to_parquet(f"{OUT}/oos_pct.parquet")
    pickle.dump({"finals": finals, "cols": cols}, open(f"{OUT}/finals.pkl", "wb"))
    json.dump(meta, open(f"{HERE}/results/results_150_params.json", "w"), indent=0, default=str)
    print("saved", P.shape)


def sizes(pct):
    return {"A": 0.5 + pct, "B": 0.25 + 1.75 * pct}


def evaluate_all():
    P = pd.read_parquet(f"{OUT}/oos_pct.parquet"); P = P[P.t >= "2009-01-01"]
    out = {}
    for tg in TARGETS:
        for m in MODELS + ["ens"]:
            pc = P[f"pct_{m}_{tg}"].values
            for mp, s in sizes(pc).items():
                name = f"{m}_{tg}_{mp}"; r = {}
                for pn, per in (("disc", MT.P_DISC), ("conf", MT.P_CONF), ("all", MT.P_ALL)):
                    r[pn] = MT.evaluate(P.t, P.net1.values, s, per)
                r["all_net2"] = MT.evaluate(P.t, P.net2.values, s, MT.P_ALL, boot=False)
                r["ic_all"] = round(ic(pc, P.net1.values), 4)
                out[name] = r
                print(name, "D disc/conf/all", r["disc"]["D"], r["conf"]["D"], r["all"]["D"], "t", r["all"]["t_jkm"], r["all"]["t_boot"], flush=True)
    json.dump(out, open(f"{HERE}/results/results_150.json", "w"), indent=1, default=float)
    return out


if __name__ == "__main__":
    {"run": run, "eval": evaluate_all}[sys.argv[1]]()
