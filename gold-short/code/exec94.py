"""#94 Overnight execution variants on minute BID + hourly-ask spread proxy. prereg/PREREGISTRATION_92_94_juicer.md
usage: BARS=1m GDATA=... python exec94.py <overnight_wf_nights.csv> <research working copy dir> <out json>"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("BARS", "1m")
import shortlib as sl

nights = pd.read_csv(sys.argv[1], index_col=0, parse_dates=True).index
W = sys.argv[2]; sys.path.insert(0, W + "/code"); os.chdir(W)
from bidask import mid_hourly
jh = mid_hourly(hidden=False); jh = jh[jh.index < "2024-01-01"]
nyc = (jh.index + pd.Timedelta("1h")).tz_localize("UTC").tz_convert("America/New_York")
sp = pd.DataFrame({"y": nyc.year, "h": nyc.hour, "s": (jh.c_a - jh.c).values}).groupby(["y", "h"]).s.median()

m = sl.load_minutes(); m = m[m.index >= pd.Timestamp("2017-01-01", tz="UTC")]
ny = m.index.tz_convert("America/New_York").tz_localize(None)
o = m.o.values; l = m.l.values
key = pd.Series(np.arange(len(m)), index=ny)
key = key[~key.index.duplicated()]

def at(dt):
    return key.get(dt, None)
def spread(dt):
    h = (dt + pd.Timedelta(minutes=30)).hour
    return float(sp.get((dt.year, h), np.nan))

COM, SLIP = 0.07, 0.1e-4
rows = []
for D in nights:
    if D < pd.Timestamp("2017-01-01") or D >= pd.Timestamp("2024-01-01"): continue
    t16 = D + pd.Timedelta(hours=16); t20 = D + pd.Timedelta(hours=20)
    def mkt(t, side):         # side +1 buy at ask, -1 sell at bid
        i = at(t)
        if i is None: return None
        return o[i] + (spread(t) if side == 1 else 0.0)
    r = {"date": D}
    b0, s0 = mkt(t16, 1), mkt(t20, -1)
    if b0 is None or s0 is None: continue
    net = lambda b, s, slips=2: (s - b) / b - COM / b - slips * SLIP
    r["E0"] = net(b0, s0)
    for d in range(1, 6):
        b, s = mkt(t16 + pd.Timedelta(minutes=d), 1), mkt(t20 + pd.Timedelta(minutes=d), -1)
        r[f"delay{d}"] = net(b, s) if (b and s) else np.nan
    bs = [mkt(t16 + pd.Timedelta(minutes=k), 1) for k in range(-5, 5)]; ss = [mkt(t20 + pd.Timedelta(minutes=k), -1) for k in range(-5, 5)]
    bs = [x for x in bs if x]; ss = [x for x in ss if x]
    r["E_TWAP"] = net(np.mean(bs), np.mean(ss)) if len(bs) >= 8 and len(ss) >= 8 else np.nan
    i16 = at(t16); L = o[i16] - 0.10; spr = spread(t16); fill = None
    for k in range(5):
        i = at(t16 + pd.Timedelta(minutes=k))
        if i is not None and l[i] <= L - spr: fill = L; break
    if fill is None:
        fb = mkt(t16 + pd.Timedelta(minutes=5), 1); r["E_LIMIT"] = net(fb, s0) if fb else np.nan; r["limit_filled"] = 0
    else:
        r["E_LIMIT"] = (s0 - fill) / fill - COM / fill - 1 * SLIP; r["limit_filled"] = 1
    be, se = mkt(t16 - pd.Timedelta(minutes=2), 1), mkt(t20 - pd.Timedelta(minutes=2), -1)
    r["E_EARLY"] = net(be, se) if (be and se) else np.nan
    r["spread16"] = spr; r["spread20"] = spread(t20)
    rows.append(r)
R = pd.DataFrame(rows).set_index("date")
out = {"nights": len(R), "spread_by_NYhour_median_usd": {int(h): round(float(v), 3) for h, v in sp.groupby(level=1).median().items()}}
for lab, a, b in (("disc", "2017", "2021"), ("conf", "2021", "2024")):
    X = R[(R.index >= a) & (R.index < b)]; res = {"n": len(X), "E0_bp": round(float(X.E0.mean() * 1e4), 3)}
    for v in ["E_TWAP", "E_LIMIT", "E_EARLY"] + [f"delay{d}" for d in range(1, 6)]:
        dlt = (X[v] - X.E0).dropna(); t = dlt.mean() / (dlt.std(ddof=1) / np.sqrt(len(dlt)))
        res[v] = {"bp": round(float(X[v].mean() * 1e4), 3), "diff_vs_E0_bp": round(float(dlt.mean() * 1e4), 3), "diff_t": round(float(t), 2)}
    res["limit_fill_rate"] = round(float(X.limit_filled.mean()), 3)
    out[lab] = res; print(lab, json.dumps(res), flush=True)
out["pass"] = {v: bool(out["disc"][v]["diff_vs_E0_bp"] > 0 and out["disc"][v]["diff_t"] >= 2 and out["conf"][v]["diff_vs_E0_bp"] > 0) for v in ("E_TWAP", "E_LIMIT", "E_EARLY")}
print(out["pass"], out["spread_by_NYhour_median_usd"])
json.dump(out, open(sys.argv[3], "w"), indent=1, default=float)
