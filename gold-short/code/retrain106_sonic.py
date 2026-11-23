"""#106 Sonic AI sizing retraining policy: P0 (train 2010-2012 once) vs P1 (yearly expanding) on 2013-2023. cwd = research working copy."""
import sys, json, warnings; warnings.filterwarnings("ignore"); sys.path.insert(0, "code")
import numpy as np, pandas as pd
import sonic_ai as SA
from sonic_pac import prepare, signals
from sonic_sl import extra
from sonic_ai_pine import PINE_FEATS as F
A = extra(prepare(True)); L, S, _ = signals(A); Fe = SA.features(A)
T = SA.trades(A, L, S, Fe, "2010-01-01", "2024-01-01")
def wsize(p, pt): pt = np.sort(pt); return 0.5 + np.searchsorted(pt, p) / len(pt)
out = {}
for pol in ("P0", "P1"):
    W = []
    for Y in range(2013, 2024):
        tr = T[T.index.year < (2013 if pol == "P0" else Y)]; te = T[T.index.year == Y]
        m = SA.model().fit(tr[F], (tr.R > 0).astype(int)); W.append(pd.Series(wsize(m.predict_proba(te[F])[:, 1], m.predict_proba(tr[F])[:, 1]), index=te.index))
    w = pd.concat(W); R = T.R.reindex(w.index)
    yr = (R * w).groupby(R.index.year).sum(); yu = R.groupby(R.index.year).sum()
    out[pol] = {"trades": int(len(R)), "unsized_totR": round(float(R.sum()), 1), "ai_sized_totR": round(float((R * w).sum()), 1), "mean_w": round(float(w.mean()), 3),
                "ai_minus_unsized_per_meanw": round(float((R * w / w.mean()).sum() - R.sum()), 1), "years_ai_better": int(((R * w / w.mean()).groupby(R.index.year).sum() > yu).sum())}
print(json.dumps(out)); json.dump(out, open(sys.argv[1], "w"), indent=1)
