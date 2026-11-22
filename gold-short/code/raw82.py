"""#82 Raw/Zero vs Standard cost comparison (prereg/PREREGISTRATION_82_raw_account_costs.md).
Run with cwd = working copy of gold-research (code/ + raw/ with hourly files < 2024 only):  python <this> """
import sys, os, json, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0, "code")
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
import sonic_ai as SA
from sonic_pac import prepare, signals
from sonic_sl import extra, stop_level
from sonic_ai_pine import PINE_FEATS
from glib import SLIP
from bidask import mid_hourly
from brute_overnight import build_days, SLIP_
import ml_overnight

OUT = sys.argv[1] if len(sys.argv) > 1 else "results_82.json"
X_COMM = 0.07
FIXP = float(os.environ.get("FIXP", "0"))      # reported sensitivity: costs priced as if gold were at FIXP (e.g. 4000)
_P = lambda P: FIXP if FIXP else P
SC = {"A": lambda P: 0.24 / _P(P) + 2 * SLIP, "B": lambda P: (0.03 + X_COMM) / _P(P) + 2 * SLIP, "B2": lambda P: 2 * ((0.03 + X_COMM) / _P(P) + 2 * SLIP)}
SWAP = 0.4316 / 4000.0            # per night, fraction of notional (long only)
OOS0, OOS1 = pd.Timestamp("2017-01-01"), pd.Timestamp("2024-01-01")

# ---------------------------------------------------------------- Sonic R + AI
STASH = {}
def simulate_stash(A, i, s, stop, cut, maxh=240):
    """identical to sonic_sl.simulate with cut C0; also stashes entry/exit/gross for re-costing"""
    o, h, l, c, eh, el = A["o"], A["h"], A["l"], A["c"], A["eh"], A["el"]; n = len(c); e = c[i]; risk = abs(e - stop)
    for t in range(i + 1, min(n, i + maxh)):
        if (s == 1 and l[t] <= stop): px = min(stop, o[t]); break
        if (s == -1 and h[t] >= stop): px = max(stop, o[t]); break
        if (s == 1 and c[t] < el[t]) or (s == -1 and c[t] > eh[t]): px = c[t]; break
    else: t = min(n - 1, i + maxh); px = c[t]
    net = s * (px / e - 1) - (0.24 / e + 2 * SLIP)
    STASH[A["df"].index[i]] = dict(i=i, x=t, e=e, px=px, side=s, riskf=risk / e, g=s * (px / e - 1))
    return net / (risk / e), t
SA.simulate = simulate_stash

A = extra(prepare(True)); L, S, _ = signals(A); Fe = SA.features(A)
assert A["df"].index.max() < OOS1
T = SA.trades(A, L, S, Fe, "2010-01-01", "2024-01-01")
info = pd.DataFrame.from_dict(STASH, orient="index").reindex(T.index)
T = T.join(info[["x", "e", "px", "riskf", "g"]])
idx = A["df"].index
T["t_in"] = idx[T.index.map(lambda t: STASH[t]["i"])] + pd.Timedelta("1h"); T["t_out"] = idx[T.x.values] + pd.Timedelta("1h")
dev = T[T.index < OOS0]; oos = T[(T.index >= OOS0) & (T.index < OOS1)].copy()
m = SA.model().fit(dev[PINE_FEATS], (dev.R > 0).astype(int))
pt = np.sort(m.predict_proba(dev[PINE_FEATS])[:, 1])
oos["w"] = 0.5 + np.searchsorted(pt, m.predict_proba(oos[PINE_FEATS])[:, 1]) / len(pt)

def rollovers(t0, t1):
    """17:00 New York rollovers crossed in (t0, t1]; Wednesday counts 3. t in naive UTC"""
    a = pd.DatetimeIndex(t0).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
    b = pd.DatetimeIndex(t1).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
    out = np.zeros(len(a))
    for k, (x, y) in enumerate(zip(a, b)):
        d = (x - pd.Timedelta(hours=17)).normalize() + pd.Timedelta(days=1)
        while d + pd.Timedelta(hours=17) <= y:
            if d.dayofweek < 5: out[k] += 3 if d.dayofweek == 2 else 1
            d += pd.Timedelta(days=1)
    return out
oos["nights"] = rollovers(oos.t_in, oos.t_out)

# ---------------------------------------------------------------- Overnight AI (gates56 / cent_sim61 walk-forward)
jj = mid_hourly(hidden=False); jj = jj[jj.index < OOS1]
mid = (jj.c + jj.c_a) / 2; spr = (jj.c_a - jj.c) / mid
ny = (jj.index + pd.Timedelta("1h")).tz_localize("UTC").tz_convert("America/New_York")
Pp, Sp = build_days(pd.DataFrame({"mid": mid.values, "spr": spr.values, "h": ny.hour, "date": pd.to_datetime(ny.date)}))
cache = "ml_dataset_rebuilt.pkl"
if os.path.exists(cache): XD = pd.read_pickle(cache)
else: XD = ml_overnight.build_dataset(hidden=False); XD.to_pickle(cache)
XD = XD[(XD.index >= "2010-01-01") & (XD.index < OOS1)]
feats = [c_ for c_ in XD.columns if c_ != "y"]
d = XD.index; p16 = Pp[16].reindex(d); p20 = Pp[20].reindex(d)
y = (p20 / p16 - 1) - 2 * (0.12 / p16 + SLIP_); Z = XD.assign(y=y.values); sel = []
for Y in range(2012, 2024):
    tr = Z[Z.index.year < Y]; te = Z[Z.index.year == Y]
    clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.03, max_depth=3, min_samples_leaf=40, l2_regularization=1.0,
                                         random_state=0).fit(tr[feats], (tr.y > 0).astype(int))
    thr = np.median(clf.predict_proba(tr[feats])[:, 1]); sel.append(te.index[clf.predict_proba(te[feats])[:, 1] > thr])
ON = pd.DataFrame(index=np.concatenate(sel)); ON["p16"] = p16.reindex(ON.index).values; ON["p20"] = p20.reindex(ON.index).values
ON = ON.dropna(); ON["g"] = ON.p20 / ON.p16 - 1; ON["nights"] = np.where(ON.index.dayofweek == 2, 3.0, 1.0)
ON["t_in"] = [pd.Timestamp(dd) + pd.Timedelta(hours=16) for dd in ON.index]          # NY local -> UTC below
ON["t_in"] = pd.DatetimeIndex(ON.t_in).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
ON["t_out"] = ON.t_in + pd.Timedelta(hours=4)

# ---------------------------------------------------------------- per-trade stats
tstat = lambda z: float(np.mean(z) / (np.std(z, ddof=1) / np.sqrt(len(z))))
res = {"sonic_oos_trades": len(oos), "overnight_oos_nights": len(ON), "commission_estimate": X_COMM, "swap_per_night": SWAP}
for sc, f in SC.items():
    for sw in (False, True):
        k = f"{sc}{'_swap' if sw else ''}"
        sn = oos.g - f(oos.e) - (sw * SWAP * oos.nights * (oos.side == 1))
        R = sn / oos.riskf; Rw = R * oos.w
        on = ON.g - f(ON.p16) - sw * SWAP * ON.nights
        res[k] = {"sonic_bp": round(sn.mean() * 1e4, 2), "sonic_R": round(R.mean(), 4), "sonic_t": round(tstat(R), 2),
                  "sonic_AI_R": round(Rw.mean(), 4), "sonic_AI_t": round(tstat(Rw), 2),
                  "on_bp": round(on.mean() * 1e4, 2), "on_t": round(tstat(on), 2)}

# ---------------------------------------------------------------- money simulation (event driven)
def money(sc, sw, legs=("S", "O"), start=OOS0, end=OOS1, eq0=10000.0):
    f = SC[sc]; ev = []
    if "S" in legs:
        for r in oos.itertuples(): ev.append((r.t_in, 0, "S", r)); ev.append((r.t_out, 1, "S", r))
    if "O" in legs:
        for r in ON.itertuples(): ev.append((r.t_in, 0, "O", r)); ev.append((r.t_out, 1, "O", r))
    ev = [z for z in ev if start <= z[3].t_in < end]
    ev.sort(key=lambda z: (z[0], -z[1]))       # exits before entries at the same time
    eq = eq0; peak = eq; open_ = {}; curve = []
    for t, kind, leg, r in ev:
        key = (leg, r.Index)
        if kind == 0:
            guard = 0.5 if eq < 0.85 * peak else 1.0
            if leg == "S":
                dist = r.riskf * r.e
                oz = np.floor(eq * 0.003 * r.w * guard / dist)
                if oz < 1 and dist <= 0.01 * eq: oz = 1
            else:
                oz = np.floor(eq * 2.0 * guard / r.p16)
            if oz >= 1: open_[key] = oz
        else:
            oz = open_.pop(key, 0)
            if not oz: continue
            if leg == "S":
                pnl = oz * (r.e * (r.g - f(r.e)) - (sw and r.side == 1) * SWAP * r.e * r.nights)
            else:
                pnl = oz * (r.p16 * (r.g - f(r.p16)) - sw * SWAP * r.p16 * r.nights)
            eq += pnl; peak = max(peak, eq); curve.append((t, eq))
    c = pd.Series([e for _, e in curve], index=[t for t, _ in curve])
    yrs = (end - start).days / 365.25
    yearly = c.groupby(c.index.year).last(); yearly = (yearly / yearly.shift(1).fillna(eq0) - 1) * 100
    return {"final": round(float(c.iloc[-1]), 0), "cagr_pct": round(((c.iloc[-1] / eq0) ** (1 / yrs) - 1) * 100, 2),
            "maxdd_pct": round(float((c / c.cummax() - 1).min() * 100), 2), "by_year_pct": yearly.round(1).to_dict()}

res["money"] = {}
for legs, nm in ((("S", "O"), "combo"), (("S",), "sonic_only"), (("O",), "overnight_only")):
    for sc in SC:
        for sw in (False, True):
            res["money"][f"{nm}_{sc}{'_swap' if sw else ''}"] = money(sc, sw, legs)
print(json.dumps(res, indent=1, default=str))
json.dump(res, open(OUT, "w"), indent=1, default=str)
