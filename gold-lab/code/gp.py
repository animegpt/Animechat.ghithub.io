"""#134 genetic programming over the #133 condition library (prereg 133_134). usage: python gp.py"""
import json, numpy as np, pandas as pd
import lab, bf
from lablog import log

CUM_BEFORE = 98756; N_EVAL = 30000; POP = 1000; GEN = 30; NMIN = 150


def stats_of(B, oi, mask, dsel, shift):
    g, n1, n2 = B["Y"][B["outs"][oi]]
    y1 = n1[dsel]; y2 = n2[dsel]
    if shift: y1 = np.roll(y1, shift); y2 = np.roll(y2, shift)
    m = mask & np.isfinite(y1); n = m.sum()
    if n < NMIN: return n, -np.inf, -np.inf, 0.0
    a = y1[m]; b = y2[m]
    t1 = a.mean() / (a.std(ddof=1) / np.sqrt(n)); t2 = b.mean() / (b.std(ddof=1) / np.sqrt(n))
    return n, t1, t2, a.mean()


def mask_of(B, ind, dsel):
    oi, lits = ind; E = B["outs"][oi][0]; Cm = B["C"][E]
    m = np.ones(len(dsel), bool)
    for c, neg in lits:
        x = Cm[c, dsel]; m &= (~x if neg else x)
    return m


def run(B, dsel, seed, shift=0, verbose=False):
    rng = np.random.default_rng(seed); nc = len(B["names"]); no = len(B["outs"])
    def rand_ind():
        k = int(rng.integers(1, 5)); return (int(rng.integers(no)), tuple(sorted({(int(rng.integers(1, nc)), bool(rng.random() < 0.3)) for _ in range(k)})))
    def fit(ind):
        n, t1, t2, m = stats_of(B, ind[0], mask_of(B, ind, dsel), dsel, shift)
        return t1, t1 - 0.1 * max(0, len(ind[1]) - 2), t2, n
    pop = [rand_ind() for _ in range(POP)]; evals = 0; best = (-np.inf, None, None, None); hist = []
    cache = {}
    for g in range(GEN):
        F = []
        for ind in pop:
            r = fit(ind); evals += 1; F.append(r)
            if r[0] > best[0]: best = (r[0], ind, r[2], r[3])
        fp = np.array([f[1] for f in F])
        order = np.argsort(-fp); elite = [pop[i] for i in order[:20]]
        def tour():
            idx = rng.integers(0, POP, 5); return pop[idx[np.argmax(fp[idx])]]
        new = list(elite)
        while len(new) < POP:
            a = tour()
            if rng.random() < 0.7:
                b = tour(); lits = list(set(a[1]) | set(b[1])); rng.shuffle(lits)
                k = int(rng.integers(1, min(4, len(lits)) + 1)); child = (a[0] if rng.random() < 0.5 else b[0], tuple(sorted(lits[:k])))
            else: child = a
            if rng.random() < 0.3:
                oi, lits = child; lits = list(lits); op = rng.integers(4)
                if op == 0 and lits: lits[int(rng.integers(len(lits)))] = (int(rng.integers(1, nc)), bool(rng.random() < 0.3))
                elif op == 1 and lits: i = int(rng.integers(len(lits))); lits[i] = (lits[i][0], not lits[i][1])
                elif op == 2: oi = int(rng.integers(no))
                else:
                    if len(lits) < 4 and rng.random() < 0.5: lits.append((int(rng.integers(1, nc)), bool(rng.random() < 0.3)))
                    elif len(lits) > 1: lits.pop(int(rng.integers(len(lits))))
                child = (oi, tuple(sorted(set(lits))))
            if not child[1]: continue
            new.append(child)
        pop = new; hist.append(float(np.max([f[0] for f in F])))
        if verbose: print("gen", g, "best t1", round(best[0], 3), flush=True)
    return best, evals, hist, pop, F


def ind_name(B, ind):
    oi, lits = ind; E, X, st, side = B["outs"][oi]
    return f"{'LONG' if side == 1 else 'SHORT'} {E:02d}->{X:02d}NY{' stop0.5ATR' if st else ''} | " + " & ".join(("NOT " if n else "") + B["names"][c] for c, n in lits)


if __name__ == "__main__":
    M = lab.Mkt(lab.load_hourly("XAUUSD")); B = bf.build(M)
    disc = np.flatnonzero((M.days >= lab.DISC[0]) & (M.days < lab.DISC[1]))
    conf = np.flatnonzero((M.days >= lab.CONF[0]) & (M.days < lab.CONF[1]))
    best, ev, hist, pop, F = run(B, disc, 134, verbose=True)
    print("REAL best", best[0], ind_name(B, best[1]), "evals", ev, flush=True)
    # top distinct finals
    fin = sorted(set(pop), key=lambda ind: -stats_of(B, ind[0], mask_of(B, ind, disc), disc, 0)[1])[:200]
    # nulls: GP on shifted outcomes + random top-up to cumulative size
    RN = bf.gen_rules(B, CUM_BEFORE + N_EVAL - N_EVAL, 133)   # random top-up = cumulative before (98,756 rules)
    rng = np.random.default_rng(1340); nulls = []
    for k in range(10):
        sh = int(rng.integers(250, len(disc) - 250))
        bn, _, _, _, _ = run(B, disc, 2000 + k, shift=sh)
        SN = bf.evaluate(B, RN, disc, shift=sh); m2 = SN.t1[SN.n >= NMIN].max()
        nulls.append(float(max(bn[0], m2))); print("null", k, round(bn[0], 3), round(m2, 3), flush=True)
    thr = float(np.percentile(nulls, 95)); print("threshold", thr, flush=True)
    cands = []; dd = M.days[disc]
    for ind in fin:
        n, t1, t2, m = stats_of(B, ind[0], mask_of(B, ind, disc), disc, 0)
        if not (t1 > thr and t2 >= 2): continue
        cands.append(ind)
    out = {"threshold_t1": thr, "nulls": nulls, "best_real_t1": float(best[0]), "best_rule": ind_name(B, best[1]), "evals": ev,
           "hist": hist, "n_cands": len(cands), "candidates": [ind_name(B, c) for c in cands[:10]]}
    json.dump(out, open(f"{lab.HERE}/results/results_134.json", "w"), indent=1, default=float)
    log({"id": "134", "test": "genetic programming 30,000 evaluations (prereg 133_134)", "trials_added": N_EVAL, "cum_trials": CUM_BEFORE + N_EVAL,
         "threshold_t1": thr, "best_real_t1": float(best[0]), "best_rule": out["best_rule"], "n_survivors_disc": len(cands)})
