"""#88 search run: 47,000 random rules + GP (60 x 25) on discovery 2017-2020.
usage: python os88_search.py <run_id>   (0 = real target, 1..16 = random-direction null)"""
import os, sys, json, time, numpy as np, pandas as pd
from numba import njit
import os88_lib as L

N_RULES, POP, GENS, MIN_TRADES = int(os.environ.get("OS88_N", 47000)), 60, int(os.environ.get("OS88_G", 25)), 300
EX = list(L.EXITS)


@njit(cache=True)
def nonoverlap(sig, xi):
    keep = np.empty(len(sig), np.int64); m = 0; busy = -1
    for s in sig:
        if s + 1 <= busy: continue
        keep[m] = s; m += 1; busy = xi[s]
    return keep[:m]


@njit(cache=True)
def nonoverlap2(sigL, sigS, xiL, xiS):
    """merge long & short signal lists; returns (index, side)"""
    out = np.empty(len(sigL) + len(sigS), np.int64); sd = np.empty(len(sigL) + len(sigS), np.int64)
    a = 0; b = 0; m = 0; busy = -1
    while a < len(sigL) or b < len(sigS):
        if b >= len(sigS) or (a < len(sigL) and sigL[a] <= sigS[b]): s = sigL[a]; side = 1; a += 1
        else: s = sigS[b]; side = -1; b += 1
        if s + 1 <= busy: continue
        out[m] = s; sd[m] = side; m += 1; busy = xiL[s] if side == 1 else xiS[s]
    return out[:m], sd[:m]


class Ctx:
    def __init__(self, run_id, end_key="disc_end"):
        C = L.CACHE; self.meta = json.load(open(f"{C}/meta.json")); de = self.meta[end_key]; self.de = de
        self.names = self.meta["names"]
        self.CL = np.load(f"{C}/condL.npy", mmap_mode="r")[:, :de]; self.CS = np.load(f"{C}/condS.npy", mmap_mode="r")[:, :de]
        self.dayid = np.load(f"{C}/dayid.npy")[:de]; self.nd = int(self.dayid.max()) + 1
        self.out = {}
        flip = None
        if run_id > 0:
            rng = np.random.default_rng(10_000 + run_id); flip = (rng.random(self.nd) < 0.5)[self.dayid]
        for side in (1, -1):
            for ex in EX:
                d = {f: np.load(f"{C}/out_{side}_{ex}_{f}.npy", mmap_mode="r")[:de] for f in ("B", "C", "xi", "ok")}
                self.out[(side, ex)] = d
        if flip is not None:                                  # swap long/short outcome series on flipped days
            for ex in EX:
                a, b = self.out[(1, ex)], self.out[(-1, ex)]
                na = {f: np.where(flip, b[f], a[f]) for f in a}; nb = {f: np.where(flip, a[f], b[f]) for f in a}
                self.out[(1, ex)], self.out[(-1, ex)] = na, nb
        else:
            for k in self.out: self.out[k] = {f: np.asarray(v) for f, v in self.out[k].items()}
        S = np.load(f"{C}/series.npy", mmap_mode="r")[:, :de]
        self.ser = {"o": np.asarray(S[0]), "h": np.asarray(S[1]), "l": np.asarray(S[2]), "c": np.asarray(S[3]), "v": np.asarray(S[4])}
        self.ser["tp"] = (self.ser["h"] + self.ser["l"] + self.ser["c"]) / 3
        self.ser["r"] = np.r_[0.0, np.diff(np.log(self.ser["c"]))]


def score_trades(X, idx, side_arr, ex):
    """idx: kept signal minutes; side_arr: +1/-1 per trade"""
    n = len(idx)
    if n < MIN_TRADES: return None
    B = np.where(side_arr == 1, X.out[(1, ex)]["B"][idx], X.out[(-1, ex)]["B"][idx])
    Cc = np.where(side_arr == 1, X.out[(1, ex)]["C"][idx], X.out[(-1, ex)]["C"][idx])
    dB = np.bincount(X.dayid[idx], weights=B, minlength=X.nd); has = np.bincount(X.dayid[idx], minlength=X.nd) > 0
    x = dB[has]; sd = x.std(ddof=1)
    t = float(x.mean() / (sd / np.sqrt(len(x)))) if sd > 0 else 0.0
    return {"n": int(n), "B_bp": float(B.mean() * 1e4), "C_bp": float(Cc.mean() * 1e4), "t": t, "elig": bool(B.mean() > 0 and Cc.mean() > 0)}


def eval_rule(X, rule):
    side, conds, struct, ex = rule["side"], rule["conds"], rule["struct"], rule["ex"]
    M = X.CL if side == 1 else X.CS
    if struct == "and":
        m = np.logical_and.reduce([M[k] for k in conds])
    else:
        m = M[conds[0]] & (M[conds[1]] | M[conds[2]])
        for k in conds[3:]: m &= M[k]
    e = m.copy(); e[1:] &= ~m[:-1]
    o = X.out[(side, ex)]
    sig = np.flatnonzero(e & o["ok"])
    if len(sig) < MIN_TRADES: return None, None
    keep = nonoverlap(sig, o["xi"])
    return score_trades(X, keep, np.full(len(keep), side), ex), keep


def gen_rules(nc, seed=88):
    rng = np.random.default_rng(seed); R = []
    for _ in range(N_RULES):
        k = int(rng.integers(1, 5)); struct = "andor" if (k >= 3 and rng.random() < 0.25) else "and"
        R.append({"side": int(rng.choice([1, -1])), "conds": [int(c) for c in rng.choice(nc, size=k, replace=False)],
                  "struct": struct, "ex": EX[int(rng.integers(0, 6))]})
    return R


# ------------------------------------------------------------------ GP
TERMS = ["c", "o", "h", "l", "v", "tp", "r"]; UN = ["ema", "std", "diff", "max", "min", "abs", "sign"]; BIN = ["+", "-", "*", "/"]; NS = [5, 15, 60, 240]


def rand_tree(rng, depth):
    if depth == 0 or rng.random() < 0.3: return ("t", TERMS[int(rng.integers(len(TERMS)))])
    if rng.random() < 0.5: return ("u", UN[int(rng.integers(len(UN)))], int(NS[int(rng.integers(4))]), rand_tree(rng, depth - 1))
    return ("b", BIN[int(rng.integers(4))], rand_tree(rng, depth - 1), rand_tree(rng, depth - 1))


def ev_tree(X, t):
    if t[0] == "t": return X.ser[t[1]]
    if t[0] == "u":
        a = ev_tree(X, t[3]); n = t[2]; s = pd.Series(a)
        if t[1] == "ema": return s.ewm(span=n, adjust=False).mean().values
        if t[1] == "std": return s.rolling(n).std().values
        if t[1] == "diff": return a - np.r_[np.full(n, np.nan), a[:-n]]
        if t[1] == "max": return s.rolling(n).max().values
        if t[1] == "min": return s.rolling(n).min().values
        if t[1] == "abs": return np.abs(a)
        return np.sign(a)
    a, b = ev_tree(X, t[2]), ev_tree(X, t[3])
    with np.errstate(all="ignore"):
        if t[1] == "+": return a + b
        if t[1] == "-": return a - b
        if t[1] == "*": return a * b
        return np.where(np.abs(b) > 1e-12, a / np.where(np.abs(b) > 1e-12, b, 1), 0.0)


def depth(t): return 0 if t[0] == "t" else 1 + (depth(t[3]) if t[0] == "u" else max(depth(t[2]), depth(t[3])))


def subtrees(t, path=()):
    yield path, t
    if t[0] == "u": yield from subtrees(t[3], path + (3,))
    elif t[0] == "b": yield from subtrees(t[2], path + (2,)); yield from subtrees(t[3], path + (3,))


def replace(t, path, new):
    if not path: return new
    l = list(t); l[path[0]] = replace(t[path[0]], path[1:], new); return tuple(l)


def eval_gp(X, ind):
    try:
        z = ev_tree(X, ind["tree"])
        if not np.all(np.isfinite(z[np.isfinite(z)])) or np.nanstd(z) == 0: return None, None
        s = pd.Series(z); zz = ((s - s.rolling(1440, min_periods=500).mean()) / s.rolling(1440, min_periods=500).std()).values
    except Exception:
        return None, None
    k = ind["k"]; ex = ind["ex"]
    prev = np.r_[np.nan, zz[:-1]]
    with np.errstate(invalid="ignore"):
        eL = (zz > k) & (prev <= k); eS = (zz < -k) & (prev >= -k)
    oL, oS = X.out[(1, ex)], X.out[(-1, ex)]
    sL = np.flatnonzero(eL & oL["ok"]); sS = np.flatnonzero(eS & oS["ok"])
    if len(sL) + len(sS) < MIN_TRADES: return None, None
    idx, sd = nonoverlap2(sL, sS, oL["xi"], oS["xi"])
    return score_trades(X, idx, sd, ex), idx


def run_gp(X, seed=888):
    rng = np.random.default_rng(seed)
    pop = [{"tree": rand_tree(rng, 4), "k": float(rng.choice([1.0, 2.0])), "ex": EX[int(rng.integers(6))]} for _ in range(POP)]
    hist = []; fit = lambda r: (r["t"] if (r is not None and r["elig"]) else -99.0)
    scores = []
    for ind in pop:
        r, _ = eval_gp(X, ind); scores.append(fit(r)); hist.append((ind, r))
    for g in range(GENS - 1):
        new = []
        best = int(np.argmax(scores)); new.append(pop[best])
        while len(new) < POP:
            a, b = [pop[max(rng.choice(POP, 3, replace=False), key=lambda i: scores[i])] for _ in range(2)]
            child = dict(a)
            if rng.random() < 0.7:
                pa = list(subtrees(a["tree"])); pb = list(subtrees(b["tree"]))
                pth, _ = pa[int(rng.integers(len(pa)))]; _, sub = pb[int(rng.integers(len(pb)))]
                child = {**a, "tree": replace(a["tree"], pth, sub)}
            if rng.random() < 0.3:
                pa = list(subtrees(child["tree"])); pth, _ = pa[int(rng.integers(len(pa)))]
                child = {**child, "tree": replace(child["tree"], pth, rand_tree(rng, 2))}
            if rng.random() < 0.1: child = {**child, "k": float(rng.choice([1.0, 2.0]))}
            if rng.random() < 0.1: child = {**child, "ex": EX[int(rng.integers(6))]}
            if depth(child["tree"]) > 5: child = {**child, "tree": rand_tree(rng, 3)}
            new.append(child)
        pop = new; scores = []
        for ind in pop:
            r, _ = eval_gp(X, ind); scores.append(fit(r)); hist.append((ind, r))
    return hist


if __name__ == "__main__":
    run_id = int(sys.argv[1]); t0 = time.time()
    X = Ctx(run_id)
    rules = gen_rules(len(X.names))
    res = []
    for i, r in enumerate(rules):
        s, _ = eval_rule(X, r)
        if s is not None: res.append((s["t"] if s["elig"] else -99.0, i, s))
    print(f"run {run_id}: random rules done {time.time()-t0:.0f}s, scored {len(res)}", flush=True)
    gp = run_gp(X)
    print(f"run {run_id}: GP done {time.time()-t0:.0f}s, evals {len(gp)}", flush=True)
    res.sort(key=lambda z: -z[0])
    top = [{"kind": "rule", "rule": {**rules[i], "cond_names": [X.names[k] for k in rules[i]["conds"]]}, **s} for _, i, s in res[:300]]
    gps = sorted([(r["t"] if (r is not None and r["elig"]) else -99.0, ind, r) for ind, r in gp], key=lambda z: -z[0])
    topgp = [{"kind": "gp", "ind": {"tree": repr(ind["tree"]), "k": ind["k"], "ex": ind["ex"]}, **r} for f, ind, r in gps[:50] if r is not None]
    best_rule = res[0][0] if res else -99; best_gp = gps[0][0] if gps else -99
    raw_rule = max([z[2]["t"] for z in res], default=-99); raw_gp = max([r["t"] for _, _, r in gps if r is not None], default=-99)
    out = {"run": run_id, "best": max(best_rule, best_gp), "best_raw_t": max(raw_rule, raw_gp), "best_rule": best_rule, "best_gp": best_gp, "n_rules_scored": len(res),
           "n_evals": len(rules) + len(gp), "secs": round(time.time() - t0), "top_rules": top, "top_gp": topgp}
    os.makedirs(f"{L.CACHE}/runs", exist_ok=True)
    json.dump(out, open(f"{L.CACHE}/runs/run_{run_id:02d}.json", "w"), default=float)
    print(f"run {run_id}: best {out['best']:.3f} (rule {best_rule:.3f}, gp {best_gp:.3f}) {out['secs']}s", flush=True)
