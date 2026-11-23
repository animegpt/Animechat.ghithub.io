"""Export the frozen #150 RF-regression model (trained 2005-2023, 300 trees) + percentile reference to JSON
(used by build_shadow_ea.py and shadow_compare.py). Also a pure-numpy predictor that must equal sklearn."""
import os, sys, json, pickle
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mt5", "rf_shadow_model.json")


def export(pkl="/home/user/lab/cache/models150/finals.pkl"):
    fz = pickle.load(open(pkl, "rb")); fin = fz["finals"][("rf", "reg")]; m = fin["fitted"]
    trees = []
    for e in m.estimators_:
        t = e.tree_
        trees.append({"feature": t.feature.tolist(), "threshold": [float(x) for x in t.threshold],
                      "left": t.children_left.tolist(), "right": t.children_right.tolist(), "value": [float(x) for x in t.value[:, 0, 0]]})
    J = {"model": "RF regression #150 rf_reg_A, trained 2005-2023 gold (frozen)", "params": fin["params"], "cols": fz["cols"],
         "ref_sorted": sorted(float(x) for x in fin["ref"]), "size_map": "size = 0.5 + pct, pct = #(ref <= pred)/len(ref)", "trees": trees}
    json.dump(J, open(OUT, "w"))
    return J, m


def predict(J, X):
    """X: (n, n_features) float64. sklearn compares float32 features with float64 thresholds."""
    X = np.asarray(X, np.float32).astype(np.float64); out = np.zeros(len(X))
    for t in J["trees"]:
        f = np.array(t["feature"]); th = np.array(t["threshold"]); L = np.array(t["left"]); R = np.array(t["right"]); v = np.array(t["value"])
        node = np.zeros(len(X), int)
        while True:
            leaf = L[node] < 0
            if leaf.all(): break
            go = np.where(X[np.arange(len(X)), np.maximum(f[node], 0)] <= th[node], L[node], R[node])
            node = np.where(leaf, node, go)
        out += v[node]
    return out / len(J["trees"])


def size_of(J, pred):
    ref = np.array(J["ref_sorted"]); return 0.5 + np.searchsorted(ref, pred, side="right") / len(ref)


if __name__ == "__main__":
    import pandas as pd, features149 as F
    J, m = export()
    D = pd.read_parquet("/home/user/lab/cache/feat149_XAUUSD.parquet"); X = F.make_X(D, D.side)[J["cols"]].values
    a = m.predict(X); b = predict(J, X)
    print("exported", OUT, os.path.getsize(OUT), "bytes | max |sklearn - numpy| =", float(np.abs(a - b).max()))
