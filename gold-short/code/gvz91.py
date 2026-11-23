"""#91 GVZ vol targeting for Sonic R (plain) + Overnight AI (walk-forward). Run with cwd = research working copy (code/ + raw/ < 2024).
usage: python gvz91.py <GVZCLS.csv> <out json>"""
import sys, os, json, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0, "code")
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
import sonic_plus as SP
from glib import SLIP
from bidask import mid_hourly
from brute_overnight import build_days, SLIP_
import ml_overnight

SWAP = 0.4316 / 4000
gvz = pd.read_csv(sys.argv[1], index_col=0, parse_dates=True).iloc[:, 0]; gvz = pd.to_numeric(gvz, errors="coerce").dropna()
j = mid_hourly(hidden=False); j = j[j.index < "2024-01-01"]
g = pd.DataFrame({k: (j[k] + j[k + "_a"]) / 2 for k in "ohlc"})
SP.COST = 0.0
B = SP.sonic_trades(g).reset_index()
B["e"] = g.c.reindex(B.t).values; B["riskf"] = B.stopd * B.atrp / 1e4
B["nights"] = ((B.tx - B.t).dt.total_seconds() / 86400).round().clip(lower=0)
B["net"] = B.net - (0.24 / B.e + 2 * SLIP) - SWAP * B.nights * (B.side == 1)
B["pnl"] = 0.003 * B.net / B.riskf                                  # fraction of equity at 0.3% risk
# Overnight AI walk-forward (raw82 / gates56)
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
ON["net"] = ON.p20 / ON.p16 - 1 - (0.24 / ON.p16 + 2 * SLIP_) - SWAP * np.where(ON.index.dayofweek == 2, 3, 1)
ON["pnl"] = 2.0 * ON.net

# multipliers
gmed = gvz.rolling(252, min_periods=120).median()
def asof(s, dates):
    s = s[~s.index.duplicated()].sort_index(); p = np.searchsorted(s.index.values, pd.DatetimeIndex(dates).values, side="right") - 1
    return np.where(p >= 0, s.values[np.clip(p, 0, None)], np.nan)
def gvz_mult(dates):
    prev = pd.DatetimeIndex(dates).normalize() - pd.offsets.BDay(1)
    return np.clip(asof(gmed, prev) / asof(gvz, prev), 0.5, 2.0)
dd_ = g.resample("1D").agg({"h": "max", "l": "min", "c": "last"}).dropna()
pc = dd_.c.shift(1); trd = np.maximum(dd_.h - dd_.l, np.maximum((dd_.h - pc).abs(), (dd_.l - pc).abs()))
atr = trd.ewm(alpha=1 / 14, adjust=False).mean(); amed = atr.rolling(252, min_periods=120).median()
def atr_mult(dates):
    prev = pd.DatetimeIndex(dates).normalize() - pd.Timedelta(days=1)
    return np.clip(asof(amed, prev) / asof(atr, prev), 0.5, 2.0)
B["mg"] = gvz_mult(B.t); B["ma"] = atr_mult(B.t); ON["mg"] = gvz_mult(ON.index); ON["ma"] = atr_mult(ON.index)

def stats_(x):
    eq = x.cumsum(); return {"sharpe": round(float(x.mean() / x.std() * np.sqrt(252)), 3), "maxdd_pct": round(float((eq - eq.cummax()).min() * 100), 2),
                             "total_pct": round(float(x.sum() * 100), 2)}
res = {}
for lab, a, b in (("disc", "2008-06-04", "2017-01-01"), ("conf", "2017-01-01", "2024-01-01")):
    days = pd.bdate_range(a, pd.Timestamp(b) - pd.Timedelta(days=1))
    bs = B[(B.t >= a) & (B.t < b)].dropna(subset=["mg", "ma"]); os_ = ON[(ON.index >= a) & (ON.index < b)].dropna(subset=["mg", "ma"])
    def daily(ms, mo):
        s = pd.Series(bs.pnl.values * ms, index=pd.DatetimeIndex(bs.tx).normalize()).groupby(level=0).sum()
        o = pd.Series(os_.pnl.values * mo, index=os_.index).groupby(level=0).sum()
        return s.reindex(days).fillna(0) + o.reindex(days).fillna(0)
    fixed = daily(1.0, 1.0); gv = daily(bs.mg.values, os_.mg.values); at = daily(bs.ma.values, os_.ma.values)
    r = {"fixed": stats_(fixed), "gvz": stats_(gv), "atr_compare": stats_(at), "sonic_trades": len(bs), "overnight_nights": len(os_),
         "mean_mult_gvz": round(float(np.r_[bs.mg.values, os_.mg.values].mean()), 3)}
    # scale-neutral check: GVZ sizing renormalised to the same average multiplier as fixed
    k = 1 / r["mean_mult_gvz"]; r["gvz_renorm"] = stats_(gv * k)
    r["pass"] = bool(r["gvz"]["sharpe"] > r["fixed"]["sharpe"] and r["gvz"]["maxdd_pct"] >= r["fixed"]["maxdd_pct"])
    res[lab] = r; print(lab, json.dumps(r), flush=True)
json.dump(res, open(sys.argv[2], "w"), indent=1)
