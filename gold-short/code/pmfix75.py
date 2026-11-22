"""#75 PMFIX (prereg/PREREGISTRATION_75_77_phase2.md). usage: python pmfix75.py disc|conf|vault [V]"""
import sys, json, numpy as np, pandas as pd
from shortlib import *

CB, CC = 0.24 / 4000 + 0.2e-4, 2 * (0.24 / 4000 + 0.2e-4)
VARS = {"E14_X15": (14, 15), "E13_X15": (13, 15), "E14_X16": (14, 16)}


class Fix:
    def __init__(self, M):
        self.M = M
        lon = M.idx.tz_convert("Europe/London").tz_localize(None)
        self.endh = (lon + pd.Timedelta(hours=1)).hour.values       # bar CLOSE hour (London)
        self.date = lon.normalize(); self.dow = lon.dayofweek.values
        self.mult = cost_mult(M.idx + M.step)

    def trades(self, E, X, days=(0, 1, 2, 3, 4)):
        M = self.M
        ei = np.flatnonzero(self.endh == E); xi = np.flatnonzero(self.endh == X)
        j = pd.Series(ei, index=self.date[ei]).to_frame("e").join(pd.Series(xi, index=self.date[xi]).to_frame("x"), how="inner")
        j = j[(j.x > j.e) & pd.Index(j.index.dayofweek).isin(days)]
        return self.make(j.e.values, j.x.values)

    def make(self, i, x):
        M = self.M; e = M.c[i]; px = M.c[x]
        g = (e - px) / e
        ca = (0.5 * 0.24 * self.mult[i] / e + SLIP) + (0.5 * 0.24 * self.mult[x] / px + SLIP)
        cbp = (0.5 * 0.24 / 4000) * (self.mult[i] + self.mult[x]) + 2 * SLIP
        return pd.DataFrame({"i": i, "x": x, "gross": g, "a": g - ca, "b": g - CB, "c": g - CC, "bnews": g - cbp},
                            index=M.idx[i])


def st(r):
    n = len(r); m = r.mean(); t = m / (r.std(ddof=1) / np.sqrt(n))
    return {"n": int(n), "bp": round(m * 1e4, 3), "t": round(float(t), 2), "p1": float(stats.t.sf(t, n - 1))}


def report(t):
    return {k: st(t[k].values) for k in ("gross", "a", "b", "c", "bnews")}


def random_base(F, t, nsim=1000, seed=5):
    """same n per year, random London business day, random entry hour outside 12-16 London, same hold hours"""
    rng = np.random.default_rng(seed); M = F.M
    hold = int(np.median(t.x - t.i)) if len(t) else 1
    ok = ~np.isin(F.endh, [12, 13, 14, 15, 16]) & (F.dow <= 4)
    yrs = M.idx.year.values; out = {k: [] for k in ("b", "a")}
    plan = t.groupby(t.index.year).size()
    I = []
    for s in range(nsim):
        for y, cnt in plan.items():
            pool = np.flatnonzero(ok & (yrs == y)); pool = pool[pool + hold < len(M.c)]
            I.append(rng.choice(pool, cnt))
    I = np.concatenate(I); X = I + hold
    # require same calendar day / contiguous hours: drop pairs spanning > hold+2 hours
    r = F.make(I, X)
    span = (M.idx[X] - M.idx[I]) / pd.Timedelta(hours=1)
    r.loc[span.values > hold + 2, ["a", "b"]] = np.nan
    res = {}
    N = len(t)
    for k in ("a", "b"):
        v = r[k].values.reshape(nsim, N); means = np.nanmean(v, 1)
        res[k] = {"rand_bp": round(float(np.mean(means)) * 1e4, 3), "p": float((np.sum(means >= t[k].mean()) + 1) / (nsim + 1))}
    return res


if __name__ == "__main__":
    which = sys.argv[1]; P = {"disc": DISC, "conf": CONF, "vault": VAULT}[which]
    if which == "vault": assert OPEN_VAULT
    M = Market(); F = Fix(M); out = {}
    names = [sys.argv[2]] if len(sys.argv) > 2 else list(VARS)
    for nm in names:
        t = period(F.trades(*VARS[nm]), P); out[nm] = report(t)
        print(which, nm, json.dumps({k: (v["n"], v["bp"], v["t"]) for k, v in out[nm].items()}), flush=True)
    if len(names) == 3:
        adj = holm([out[k]["b"]["p1"] for k in names])
        for k, a in zip(names, adj): out[k]["holm_b"] = float(a)
        print({k: round(out[k]["holm_b"], 5) for k in names})
    json.dump(out, open(f"{HERE}/results_75_{which}.json", "w"), indent=1)
