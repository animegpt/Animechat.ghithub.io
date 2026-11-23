"""Descriptive cross-market check of the user's TradingView test: Williams #112 rule on BTCUSDT (Binance spot hourly), 24/7 market.
Day = 17:00->17:00 New York (all 7 days). Costs: (a) TradingView setting 0.12 USD/BTC per side; (b) Exness BTCUSDc measured spread 6.40 USD
round trip (#54) + 0.1bp/side; (c) 2x (b). Exit at the day close. Not a pre-registered test (no decision taken from it)."""
import sys, glob, json, numpy as np, pandas as pd
fr = []
for f in sorted(glob.glob(sys.argv[1] + "/BTCUSDT-1h-*.csv")):
    x = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4]); x.columns = ["t", "o", "h", "l", "c"]; fr.append(x)
d = pd.concat(fr); d["t"] = np.where(d.t > 1e14, d.t // 1000, d.t)
d.index = pd.to_datetime(d.t, unit="ms", utc=True); d = d[~d.index.duplicated()].sort_index()[["o", "h", "l", "c"]].astype(float)
ny = d.index.tz_convert("America/New_York").tz_localize(None); d["k"] = (ny + pd.Timedelta(hours=7)).normalize()
D = d.groupby("k").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("o", "size")); D = D[D.n >= 20]
G = {k: g for k, g in d.groupby("k")}
rows = []
for t in range(1, len(D)):
    r = D.h.iloc[t - 1] - D.l.iloc[t - 1]; O = D.o.iloc[t]; bu, sd = O + 0.6 * r, O - 0.6 * r; C = D.c.iloc[t]; g = G[D.index[t]]
    side = 0
    for _, b in g.iterrows():
        hb, lb = b.h >= bu, b.l <= sd
        if hb and lb: side = 9; break
        if hb: side, ep = 1, max(bu, b.o); break
        if lb: side, ep = -1, min(sd, b.o); break
    if side == 0: continue
    if side == 9: gr = min((C - bu) / bu, (sd - C) / sd); ep = bu
    else: gr = side * (C / ep - 1)
    rows.append((D.index[t], gr, ep))
T = pd.DataFrame(rows, columns=["t", "g", "ep"]).set_index("t")
T["tv"] = T.g - 2 * 0.12 / T.ep
T["exness"] = T.g - 6.40 / T.ep - 2e-5
T["exness_x2"] = T.g - 2 * (6.40 / T.ep + 2e-5)
out = {}
for lab, a, b in (("2017-08..2020", "2017", "2021"), ("2021-2023", "2021", "2024"), ("2024-2026-10", "2024", "2027"), ("all", "2017", "2027")):
    X = T[(T.index >= a) & (T.index < b)]; o = {"n": len(X), "gross_bp": round(X.g.mean() * 1e4, 2)}
    for col in ("tv", "exness", "exness_x2"):
        r = X[col]; pf = r[r > 0].sum() / -r[r < 0].sum()
        o[col] = {"bp": round(r.mean() * 1e4, 2), "t": round(r.mean() / (r.std() / np.sqrt(len(r))), 2), "PF": round(pf, 3)}
    out[lab] = o; print(lab, json.dumps(o))
print("mean cost per trade bp: tv", round((2 * 0.12 / T.ep).mean() * 1e4, 3), "| exness", round((6.40 / T.ep + 2e-5).mean() * 1e4, 2))
json.dump(out, open(sys.argv[2], "w"), indent=1)
