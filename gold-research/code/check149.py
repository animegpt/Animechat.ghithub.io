"""#149 look-ahead check: for random bars b of each timeframe, indicator features recomputed on the series truncated at b
must equal the full-series features at b. (The as-of join itself asserts avail <= entry time in features149.build.)"""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, ind3, features149 as F

M = lab.Mkt(lab.load_hourly("XAUUSD"))
bars = F.tf_bars(M); rng = np.random.default_rng(1); out = {}
for tf, B in bars.items():
    full = ind3.all_features(B); n = len(B); bad = 0; worst = None
    picks = rng.integers(min(300, n // 2), n, 15)
    for b in picks:
        tr = ind3.all_features(B.iloc[:b + 1]).iloc[-1]
        d = (tr - full.iloc[b]).abs()
        rel = d / (full.iloc[b].abs() + 1e-6)
        mism = rel[(d > 1e-6) & (rel > 1e-6)]
        if len(mism): bad += 1; worst = mism.index.tolist()[:5]
    out[tf] = {"bars_tested": len(picks), "mismatching_bars": bad, "example_cols": worst}
print(json.dumps(out))
