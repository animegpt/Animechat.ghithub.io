"""#104/#106: Overnight AI config grid (threshold quantile x depth) and retraining policies, research walk-forward.
Run with cwd = research working copy. usage: python pbo104_overnight.py <out dir>"""
import sys, json, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0, "code")
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from bidask import mid_hourly
from brute_overnight import build_days, SLIP_

out = sys.argv[1]
j = mid_hourly(hidden=False); j = j[j.index < "2024-01-01"]
mid = (j.c + j.c_a) / 2; spr = (j.c_a - j.c) / mid
ny = (j.index + pd.Timedelta("1h")).tz_localize("UTC").tz_convert("America/New_York")
Pp, Sp = build_days(pd.DataFrame({"mid": mid.values, "spr": spr.values, "h": ny.hour, "date": pd.to_datetime(ny.date)}))
XD = pd.read_pickle("ml_dataset_rebuilt.pkl"); XD = XD[(XD.index >= "2010-01-01") & (XD.index < "2024-01-01")]
feats = [c for c in XD.columns if c != "y"]; d = XD.index; p16 = Pp[16].reindex(d); p20 = Pp[20].reindex(d)
y = (p20 / p16 - 1) - 2 * (0.12 / p16 + SLIP_); Z = XD.assign(y=y.values).dropna(subset=["y"])
clf = lambda depth: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.03, max_depth=depth, min_samples_leaf=40, l2_regularization=1.0, random_state=0)

def wf(q=0.5, depth=3, policy="P1"):
    sel = []
    periods = [(pd.Timestamp(f"{Y}-01-01"), pd.Timestamp(f"{Y+1}-01-01")) for Y in range(2012, 2024)]
    if policy == "P4": periods = [(pd.Timestamp(f"{Y}-{m:02d}-01"), pd.Timestamp(f"{Y}-{m:02d}-01") + pd.DateOffset(months=6)) for Y in range(2012, 2024) for m in (1, 7)]
    model = None
    for a, b in periods:
        if policy == "P0" and model is not None: pass
        else:
            tr = Z[Z.index < a]
            if policy == "P2": tr = tr[tr.index >= a - pd.DateOffset(years=5)]
            if policy == "P3": tr = tr[tr.index >= a - pd.DateOffset(years=8)]
            model = clf(depth).fit(tr[feats], (tr.y > 0).astype(int)); thr = np.quantile(model.predict_proba(tr[feats])[:, 1], q)
        te = Z[(Z.index >= a) & (Z.index < b)]
        if len(te): sel.append(te.y[model.predict_proba(te[feats])[:, 1] > thr])
    r = pd.concat(sel); return r

cols = {}
for q in (0.3, 0.4, 0.5, 0.6, 0.7):
    for dpt in (2, 3, 4):
        r = wf(q, dpt); cols[f"on_q{q}_d{dpt}"] = r.groupby(r.index.to_period("M")).sum(); print("cfg", q, dpt, round(r.mean() * 1e4, 2), flush=True)
M = pd.DataFrame(cols).fillna(0.0); M.to_csv(f"{out}/overnight_grid_monthly.csv")
pol = {}
for p in ("P0", "P1", "P2", "P3", "P4"):
    r = wf(0.5, 3, p); mm = r.groupby(r.index.to_period("M")).sum()
    pol[p] = {"nights": int(len(r)), "net_bp": round(float(r.mean() * 1e4), 3), "t": round(float(r.mean() / (r.std() / np.sqrt(len(r)))), 2),
              "ann_sharpe_monthly": round(float(mm.mean() / mm.std() * np.sqrt(12)), 3)}
    print(p, pol[p], flush=True)
json.dump(pol, open(f"{out}/overnight_retrain_policies.json", "w"), indent=1)
