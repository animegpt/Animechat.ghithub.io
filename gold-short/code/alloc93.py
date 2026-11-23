"""#93 optimal risk allocation Sonic (plain, 1% risk unit) + Overnight AI (1x unit). Estimation 2012-2020, test 2021-2023.
Run with cwd = research working copy. usage: python alloc93.py <out json>"""
import sys, json, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0, "code")
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
import sonic_plus as SP
from glib import SLIP
from bidask import mid_hourly
from brute_overnight import build_days, SLIP_

SWAP = 0.4316 / 4000
j = mid_hourly(hidden=False); j = j[j.index < "2024-01-01"]
g = pd.DataFrame({k: (j[k] + j[k + "_a"]) / 2 for k in "ohlc"})
SP.COST = 0.0; B = SP.sonic_trades(g).reset_index()
B["e"] = g.c.reindex(B.t).values; B["riskf"] = B.stopd * B.atrp / 1e4
B["nights"] = ((B.tx - B.t).dt.total_seconds() / 86400).round().clip(lower=0)
mid = (j.c + j.c_a) / 2; spr = (j.c_a - j.c) / mid
ny = (j.index + pd.Timedelta("1h")).tz_localize("UTC").tz_convert("America/New_York")
Pp, Sp = build_days(pd.DataFrame({"mid": mid.values, "spr": spr.values, "h": ny.hour, "date": pd.to_datetime(ny.date)}))
XD = pd.read_pickle("ml_dataset_rebuilt.pkl"); XD = XD[(XD.index >= "2010-01-01") & (XD.index < "2024-01-01")]
feats = [c for c in XD.columns if c != "y"]; d = XD.index; p16 = Pp[16].reindex(d); p20 = Pp[20].reindex(d)
y = (p20 / p16 - 1) - 2 * (0.12 / p16 + SLIP_); Z = XD.assign(y=y.values); sel = []
for Y in range(2012, 2024):
    tr = Z[Z.index.year < Y]; te = Z[Z.index.year == Y]
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.03, max_depth=3, min_samples_leaf=40, l2_regularization=1.0, random_state=0).fit(tr[feats], (tr.y > 0).astype(int))
    thr = np.median(clf.predict_proba(tr[feats])[:, 1]); sel.append(te.index[clf.predict_proba(te[feats])[:, 1] > thr])
ON = pd.DataFrame(index=np.concatenate(sel)); ON["p16"] = p16.reindex(ON.index).values; ON["p20"] = p20.reindex(ON.index).values; ON = ON.dropna()
ON.to_csv("overnight_wf_nights.csv")

def series(cost):
    cs = cost(B.e)
    s = 0.01 * (B.net - cs - SWAP * B.nights * (B.side == 1)) / B.riskf
    o = (ON.p20 / ON.p16 - 1) - cost(ON.p16) - SWAP * np.where(ON.index.dayofweek == 2, 3, 1)
    days = pd.bdate_range("2012-01-02", "2023-12-29")
    S = pd.Series(s.values, index=pd.DatetimeIndex(B.tx).normalize()).groupby(level=0).sum().reindex(days).fillna(0)
    O = pd.Series(o.values, index=ON.index).groupby(level=0).sum().reindex(days).fillna(0)
    return pd.DataFrame({"S": S, "O": O})
COSTS = {"A": lambda P: 0.24 / P + 2 * SLIP, "B": lambda P: 0.10 / P + 2 * SLIP}

def mc_dd95(R, w, n=2000, horizon=756, block=20, seed=93):
    rng = np.random.default_rng(seed); x = R @ w; T = len(x); dds = np.empty(n)
    for k in range(n):
        idx = np.concatenate([np.arange(s, s + block) % T for s in rng.integers(0, T, horizon // block + 1)])[:horizon]
        eq = np.cumsum(x[idx]); dds[k] = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    return -np.percentile(dds, 5)

def scale_to(R, w, target=0.15):
    lo, hi = 0.0, 1.0
    while mc_dd95(R, w * hi) < target and hi < 1e4: hi *= 2
    for _ in range(25):
        mid_ = (lo + hi) / 2
        if mc_dd95(R, w * mid_) < target: lo = mid_
        else: hi = mid_
    return w * lo

def perf(x):
    eq = x.cumsum(); return {"ann_pct": round(float(x.mean() * 252 * 100), 2), "sharpe": round(float(x.mean() / x.std() * np.sqrt(252)), 3),
                             "maxdd_pct": round(float((eq - eq.cummax()).min() * 100), 2)}
out = {}
for cn, cf in COSTS.items():
    D = series(cf); est = D[D.index < "2021-01-01"]; test = D[D.index >= "2021-01-01"]
    mu = est.mean().values; Sig = est.cov().values; se = est.std().values / np.sqrt(len(est))
    W = {"current (S 0.3%, O 2x)": np.array([0.3, 2.0]),
         "kelly_frac": scale_to(est.values, np.linalg.solve(Sig, mu)),
         "risk_parity": scale_to(est.values, 1 / est.std().values),
         "robust": scale_to(est.values, np.linalg.solve(Sig, np.maximum(mu - se, 0)) if np.any(mu - se > 0) else np.zeros(2))}
    r = {"est_mean_bp_day": (mu * 1e4).round(3).tolist(), "est_corr": round(float(est.corr().iloc[0, 1]), 3)}
    for k, w in W.items():
        r[k] = {"w_sonic_risk_pct": round(float(w[0]), 3), "w_overnight_x": round(float(w[1]), 3), "mc_dd95_est_pct": round(mc_dd95(est.values, w) * 100, 1),
                "est": perf(est.values @ w if False else pd.Series(est.values @ w)), "test": perf(pd.Series(test.values @ w))}
    out[cn] = r; print(cn, json.dumps(r, indent=0), flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
