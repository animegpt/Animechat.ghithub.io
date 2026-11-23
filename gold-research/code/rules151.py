"""#151 brute force on simple sizing rules (prereg 149_153 section 4).
usage: python rules151.py run   -> results/results_151.json (+ cache of all rule stats)"""
import os, sys, json, time
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, features149 as F, metric149 as MT
CACHE = lab.CACHE; HERE = lab.HERE
N_RULES = 50000; N_NULL = 20; SEED = 151
SINCE_BASES = {b[:-2] if b.endswith("_b") else b for b, s, k in F.PAIRS if k == "since"}
WIN = {"H1": (6, 24), "H4": (2, 6), "D1": (1, 5)}


def atom_specs(cols):
    """deterministic list of (col, op, param). op: gt0, lt0, eq1, ge, eq, le, win, hi, lo, pos"""
    A = []
    for c in cols:
        tf = c[:2]; core = c[3:]
        base = core.replace("_with", "").replace("_against", "")
        if c.endswith(("_trend", "_zone", "_dir", "_agree", "_out")):
            A += [(c, "gt0", None), (c, "lt0", None)]
        elif "_ob_in_" in c:
            A += [(c, "eq1", None)]
        elif c.endswith("_align3") or c.endswith("_votes") or c == "mtf_align3_majority":
            A += [(c, "ge", 2), (c, "eq", 3), (c, "eq", 0)]
        elif c == "mtf_align9":
            A += [(c, "ge", 6), (c, "le", 3)]
        elif base in SINCE_BASES:
            A += [(c, "win", w) for w in WIN[tf]]
        elif "_n_" in c:
            A += [(c, "pos", None), (c, "hi", None), (c, "lo", None)]
        else:
            A += [(c, "hi", None), (c, "lo", None)]
    return A


def thresholds(Xd, specs):
    th = []
    for c, op, p in specs:
        x = Xd[c].values
        if op == "hi": th.append(np.percentile(x, 67))
        elif op == "lo": th.append(np.percentile(x, 33))
        elif op == "win": th.append(np.log1p(p))
        else: th.append(p)
    return th


def masks(X, specs, th):
    M = np.zeros((len(X), len(specs)), bool)
    for k, ((c, op, p), t) in enumerate(zip(specs, th)):
        x = X[c].values
        M[:, k] = {"gt0": lambda: x > 0, "lt0": lambda: x < 0, "eq1": lambda: x == 1, "ge": lambda: x >= t,
                   "eq": lambda: x == t, "le": lambda: x <= t, "win": lambda: x <= t + 1e-9,
                   "hi": lambda: x > t, "lo": lambda: x < t, "pos": lambda: x > 0}[op]()
    return M


def candidate_stream(n_atoms, cols_of_atom, seed):
    """deterministic stream: all singles, then alternating random pairs / triples (distinct columns)"""
    for a in range(n_atoms): yield (a,)
    rng = np.random.default_rng(seed); k = 0
    while True:
        size = 2 if k % 2 == 0 else 3; k += 1
        r = tuple(sorted(rng.choice(n_atoms, size, replace=False)))
        if len({cols_of_atom[i] for i in r}) == size: yield r


def select_rules(Md, cols_of_atom, seed=SEED, n=N_RULES):
    """rules (atom tuples) with discovery coverage in [10%, 90%]; each rule gives 2 actions -> n/2 rule bodies"""
    out = []; seen = set()
    for r in candidate_stream(Md.shape[1], cols_of_atom, seed):
        if r in seen: continue
        seen.add(r)
        cov = Md[:, list(r)].all(1).mean()
        if 0.10 <= cov <= 0.90: out.append(r)
        if len(out) >= n // 2: break
    return out


def rule_stats(t, r, Mall, rules, P, batch=4000):
    """JKM D and t for up (x1.5) and down (x0.5) action of every rule body in period P."""
    m, G, months = MT.month_matrix(t, P)
    rr = np.asarray(r)[m]; Mm = Mall[m]; base = G @ rr
    Du = np.empty(len(rules)); tu = np.empty(len(rules)); Dd = np.empty(len(rules)); td = np.empty(len(rules))
    for s in range(0, len(rules), batch):
        R = rules[s:s + batch]
        mk = np.ones((len(rr), len(R)), bool)
        L = max(len(x) for x in R)
        idx = np.array([list(x) + [x[0]] * (L - len(x)) for x in R])
        for j in range(L): mk &= Mm[:, idx[:, j]]
        Q = G @ (rr[:, None] * mk)
        Du[s:s + batch], tu[s:s + batch] = MT.jkm(base, base[:, None] + 0.5 * Q)
        Dd[s:s + batch], td[s:s + batch] = MT.jkm(base, base[:, None] - 0.5 * Q)
    return np.r_[Du, Dd], np.r_[tu, td]


def search(D, side, P=MT.P_DISC):
    """full search for a side vector. returns dict with specs, th, rules, disc D/t arrays, returns r"""
    move = D.xp.values / D.ep.values - 1
    cost = D.side.values * move - D.net1.values
    r = side * move - cost
    X = F.make_X(D, side)
    cols = list(X.columns); specs = atom_specs(cols)
    dm = (D.t >= P[0]) & (D.t < P[1])
    th = thresholds(X[dm.values], specs)
    Mall = masks(X, specs, th)
    rules = select_rules(Mall[dm.values], [s[0] for s in specs])
    Dv, tv = rule_stats(D.t, r, Mall, rules, P)
    return dict(specs=specs, th=th, rules=rules, D=Dv, t=tv, r=r, Mall=Mall, X=X)


def describe(specs, th, rule, action):
    parts = []
    for a in rule:
        c, op, p = specs[a]; t = th[a]
        if op in ("gt0", "pos"): sym = "> 0"
        elif op == "lt0": sym = "< 0"
        elif op == "eq1": sym = "= 1"
        elif op == "ge": sym = f">= {t}"
        elif op == "eq": sym = f"= {t}"
        elif op == "le": sym = f"<= {t}"
        elif op == "win": sym = f"within {p} bars"
        elif op == "hi": sym = f"> {t:.4g} (p67)"
        else: sym = f"< {t:.4g} (p33)"
        parts.append(f"{c} {sym}")
    return (" & ".join(parts)) + (" -> x1.5" if action == "up" else " -> x0.5")


def run():
    D = pd.read_parquet(f"{CACHE}/feat149_XAUUSD.parquet"); D = D[D.t >= "2005-01-01"].reset_index(drop=True)
    t0 = time.time()
    S = search(D, D.side.values.astype(float))
    nb = len(S["rules"]); n_tot = 2 * nb
    print("real search", n_tot, "rules", "atoms", len(S["specs"]), "best t", S["t"].max(), round(time.time() - t0), "s", flush=True)
    rng = np.random.default_rng(SEED + 1000); null_max = []
    for k in range(N_NULL):
        flip = np.where(rng.random(len(D)) < 0.5, -1.0, 1.0)
        Sn = search(D, D.side.values * flip)
        null_max.append(float(Sn["t"].max())); print("null", k, null_max[-1], flush=True)
    thr = float(np.percentile(null_max, 95))
    # confirmation + combined for all rules (thresholds fixed from discovery)
    Dc, tc = rule_stats(D.t, S["r"], S["Mall"], S["rules"], MT.P_CONF)
    Da, ta = rule_stats(D.t, S["r"], S["Mall"], S["rules"], MT.P_ALL)
    np.savez(f"{CACHE}/rules151_stats.npz", Dd=S["D"], td=S["t"], Dc=Dc, tc=tc, Da=Da, ta=ta)
    order = np.argsort(-S["t"])
    def info(i):
        body = S["rules"][i % nb]; act = "up" if i < nb else "down"
        size = np.where(S["Mall"][:, list(body)].all(1), 1.5 if act == "up" else 0.5, 1.0)
        ev = {pn: MT.evaluate(D.t, S["r"], size, per) for pn, per in (("disc", MT.P_DISC), ("conf", MT.P_CONF), ("all", MT.P_ALL))}
        return dict(idx=int(i), rule=describe(S["specs"], S["th"], body, act), n_atoms=len(body),
                    coverage_disc=round(float(S["Mall"][(D.t < "2017-01-01").values & (D.t >= "2009-01-01").values][:, list(body)].all(1).mean()), 3),
                    disc=ev["disc"], conf=ev["conf"], all=ev["all"])
    top = [info(i) for i in order[:30]]
    surv = [int(i) for i in np.flatnonzero((S["t"] > thr) & (S["t"] >= 2))]
    res = dict(n_rules=n_tot, n_atoms=len(S["specs"]), null_max=null_max, threshold=thr, best_disc_t=float(S["t"].max()),
               n_beat_threshold=len(surv), survivors=[info(i) for i in surv],
               top30_disc=top,
               best_all=[info(i) for i in np.argsort(-ta)[:10]],
               frac_conf_pos_among_top100=float((Dc[order[:100]] > 0).mean()),
               summary_all=dict(n_D_pos=int((Da > 0).sum()), n_t_ge2=int((ta >= 2).sum()), max_t=float(ta.max())))
    json.dump(res, open(f"{HERE}/results/results_151.json", "w"), indent=1, default=float)
    print("threshold", thr, "best", S["t"].max(), "beat", len(surv), flush=True)


if __name__ == "__main__":
    run()
