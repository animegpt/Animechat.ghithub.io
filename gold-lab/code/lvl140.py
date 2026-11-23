"""#140 level-breakout structured search (prereg/PREREGISTRATION_140_level_breakouts.md)."""
import json, numpy as np, pandas as pd
from numba import njit
import lab, bf
from lablog import log

CUM_BEFORE = 128832; NMIN = 150


@njit(cache=True)
def _leg(o, h, l, c, ja, jb, lvl, side, stopkind, opp, atr):
    """one stop entry leg -> (j0, ep, jx, xp) or j0=-1"""
    j0 = -1; ep = np.nan
    for j in range(ja, jb + 1):
        if side == 1 and h[j] >= lvl: j0 = j; ep = max(lvl, o[j]); break
        if side == -1 and l[j] <= lvl: j0 = j; ep = min(lvl, o[j]); break
    if j0 < 0: return -1, np.nan, -1, np.nan
    st = np.nan
    if stopkind == 1: st = opp
    elif stopkind == 2: st = ep - side * 0.5 * atr
    if not np.isnan(st):
        if (side == 1 and l[j0] <= st) or (side == -1 and h[j0] >= st): return j0, ep, j0, st
        for j in range(j0 + 1, jb + 1):
            if side == 1 and l[j] <= st: return j0, ep, j, min(st, o[j])
            if side == -1 and h[j] >= st: return j0, ep, j, max(st, o[j])
    return j0, ep, jb, c[jb]


@njit(cache=True)
def sim(o, h, l, c, JA, JB, UP, DN, mode, stopkind, ATR, half_spread, slip):
    nd = len(JA); out = np.full((nd, 5), np.nan)   # side, gross, net1, net2, j0
    for t in range(nd):
        ja = JA[t]; jb = JB[t]
        if ja < 0 or jb < 0 or jb < ja or np.isnan(ATR[t]): continue
        up = UP[t]; dn = DN[t]
        okL = (mode != 1) and not np.isnan(up) and o[ja] < up
        okS = (mode != 0) and not np.isnan(dn) and o[ja] > dn
        bL = (-1, np.nan, -1, np.nan); bS = (-1, np.nan, -1, np.nan)
        if okL: bL = _leg(o, h, l, c, ja, jb, up, 1, stopkind, dn, ATR[t])
        if okS: bS = _leg(o, h, l, c, ja, jb, dn, -1, stopkind, up, ATR[t])
        pick = 0
        if bL[0] >= 0 and bS[0] >= 0:
            if bL[0] < bS[0]: pick = 1
            elif bS[0] < bL[0]: pick = -1
            else:
                gl = bL[3] / bL[1] - 1; gs = -(bS[3] / bS[1] - 1); pick = 1 if gl < gs else -1
        elif bL[0] >= 0: pick = 1
        elif bS[0] >= 0: pick = -1
        if pick == 0: continue
        b = bL if pick == 1 else bS
        g = pick * (b[3] / b[1] - 1)
        out[t, 0] = pick; out[t, 1] = g; out[t, 2] = g - half_spread / b[1] - half_spread / b[3] - 2 * slip
        out[t, 3] = g - 2 * half_spread / 4000.0 - 2 * slip; out[t, 4] = b[0]
    return out


def base_rules(M):
    D = M.D; O, H, L, C = (D[k].values for k in "ohlc"); nd = len(C)
    pc = np.r_[C[0], C[:-1]]; tr = np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))
    atr = bf.lag(pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values)
    R1 = bf.lag((H - L).astype(float)); PH = bf.lag(H.astype(float)); PL = bf.lag(L.astype(float))
    asia_h = np.full(nd, np.nan); asia_l = np.full(nd, np.nan)
    for t in range(nd):
        a = M.dh[t, 19]; b = M.dh[t, 2]
        if a >= 0 and b > a: asia_h[t] = M.h[a:b + 1].max(); asia_l[t] = M.l[a:b + 1].min()
    wk = M.days.to_period("W-FRI"); dfw = pd.DataFrame({"h": H, "l": L, "w": wk})
    WH = dfw.groupby("w").h.max().shift(1).reindex(wk).values; WL = dfw.groupby("w").l.min().shift(1).reindex(wk).values
    lv = []
    for k in (0.2, 0.4, 0.6, 0.8, 1.0, 1.2): lv.append((f"WIL{k}", O + k * R1, O - k * R1, (17, 3, 8)))
    for k in (0.25, 0.5, 0.75, 1.0, 1.25): lv.append((f"ATR{k}", O + k * atr, O - k * atr, (17, 3, 8)))
    for k in (0, 0.1, 0.25): lv.append((f"PD{k}", PH + k * atr, PL - k * atr, (17, 3, 8)))
    for k in (0, 0.1, 0.25): lv.append((f"ASIA{k}", asia_h + k * atr, asia_l - k * atr, (3, 8)))
    lv.append(("WEEK", WH, WL, (17, 3, 8)))
    for N in (5, 10, 20): lv.append((f"NDAY{N}", pd.Series(H).shift(1).rolling(N).max().values, pd.Series(L).shift(1).rolling(N).min().values, (17, 3, 8)))
    JB = M.dh[:, 15]; rules = []; outs = []
    for name, up, dn, wins in lv:
        for W in wins:
            JA = M.s.copy() if W == 17 else M.dh[:, W]
            for mode, mname in ((0, "long"), (1, "short"), (2, "oco")):
                for sk, sname in ((0, "nostop"), (1, "oppstop"), (2, "stop0.5ATR")):
                    o = sim(M.o, M.h, M.l, M.c, JA, JB, up.astype(float), dn.astype(float), mode, sk, atr, M.spec["spread"] / 2, lab.SLIP)
                    rules.append(f"{name} W{W} {mname} {sname}"); outs.append(o)
    return rules, outs


FILTERS = ["always", "above_sma20", "below_sma20", "above_sma50", "below_sma50", "above_sma200", "below_sma200", "rng_lo", "rng_hi", "r1_lo", "r1_hi",
           "atrr_lo", "atrr_hi", "rv_lo", "rv_hi", "inside", "outside", "clv_lo", "clv_hi", "r20_lo", "r20_hi"]


def stats_mat(G1, G2, V, Fm):
    """G1,G2: (nb, nd) net arrays (0 where no trade), V valid (nb, nd) float; Fm (nf, nd) float -> t1,t2,n (nb, nf)"""
    n = V @ Fm.T; s1 = G1 @ Fm.T; q1 = (G1 * G1) @ Fm.T; s2 = G2 @ Fm.T; q2 = (G2 * G2) @ Fm.T
    m1 = s1 / np.maximum(n, 1); v1 = (q1 - n * m1 ** 2) / np.maximum(n - 1, 1); m2 = s2 / np.maximum(n, 1); v2 = (q2 - n * m2 ** 2) / np.maximum(n - 1, 1)
    t1 = m1 / np.sqrt(np.maximum(v1, 1e-30) / np.maximum(n, 1)); t2 = m2 / np.sqrt(np.maximum(v2, 1e-30) / np.maximum(n, 1))
    t1[n < NMIN] = -np.inf; t2[n < NMIN] = -np.inf
    return t1, t2, n, m1


if __name__ == "__main__":
    M = lab.Mkt(lab.load_hourly("XAUUSD")); B = bf.build(M)
    names, outs = base_rules(M); print("base rules", len(names), flush=True)
    disc = np.flatnonzero((M.days >= lab.DISC[0]) & (M.days < lab.DISC[1])); conf = np.flatnonzero((M.days >= lab.CONF[0]) & (M.days < lab.CONF[1]))
    Fall = np.vstack([B["C"][19][B["names"].index(f)] for f in FILTERS]).astype(float)   # daily filters identical for every E
    def mats(dsel, flip=None):
        O = np.stack([o[dsel] for o in outs])   # nb, nd, 5
        V = np.isfinite(O[:, :, 2]).astype(float); side = np.nan_to_num(O[:, :, 0]); g = np.nan_to_num(O[:, :, 1])
        c1 = np.nan_to_num(O[:, :, 1] - O[:, :, 2]); c2 = np.nan_to_num(O[:, :, 1] - O[:, :, 3])
        if flip is not None: g = g * flip[None, :]
        return (g - c1) * V, (g - c2) * V, V
    G1, G2, V = mats(disc); F = Fall[:, disc]
    t1, t2, n, m1 = stats_mat(G1, G2, V, F)
    ntot = t1.size; print("rules", ntot, flush=True)
    order = np.dstack(np.unravel_index(np.argsort(-t1, axis=None), t1.shape))[0]
    for b, f in order[:20]: print(round(t1[b, f], 2), round(t2[b, f], 2), int(n[b, f]), round(m1[b, f] * 1e4, 2), names[b], "|", FILTERS[f])
    RN = bf.gen_rules(B, CUM_BEFORE + ntot - ntot, 133)    # top-up = cumulative before
    rng = np.random.default_rng(1400); nulls = []
    for k in range(20):
        flip = np.where(rng.random(len(disc)) < 0.5, 1.0, -1.0)   # same random sign per day across rules
        a1, _, _, _ = stats_mat(*mats(disc, flip), F)
        sh = int(rng.integers(250, len(disc) - 250)); SN = bf.evaluate(B, RN, disc, shift=sh); m2 = SN.t1[SN.n >= NMIN].max()
        nulls.append(float(max(a1.max(), m2))); print("null", k, round(a1.max(), 3), round(m2, 3), flush=True)
    thr = float(np.percentile(nulls, 95)); print("threshold", thr, flush=True)
    W = lab.daily_pnl(__import__("refs").williams(M), days=M.days[disc])
    cands = []
    for b, f in order:
        if t1[b, f] <= thr: break
        if t2[b, f] < 2: continue
        sel = disc[(V[b] > 0) & (F[f] > 0)]
        T = pd.DataFrame({"t": M.days[sel], "tx": M.days[sel], "j0": outs[b][sel, 4].astype(int), "jx": M.dh[sel, 15], "side": outs[b][sel, 0].astype(int),
                          "gross": outs[b][sel, 1], "net1": outs[b][sel, 2], "net2": outs[b][sel, 3]})
        pt = lab.random_time_p(M, T, lab.DISC, 2000, np.random.default_rng(140))
        d = lab.daily_pnl(T, days=M.days[disc]); cw = float(np.corrcoef(d, W)[0, 1])
        rec = dict(rule=names[b] + " | " + FILTERS[f], b=int(b), f=int(f), t1=float(t1[b, f]), t2=float(t2[b, f]), n=int(n[b, f]), p_time=pt, corr_W112=cw)
        print("cand", rec, flush=True)
        if pt >= 0.05 or cw > 0.7: continue
        if any(abs(np.corrcoef(d, c["d"])[0, 1]) > 0.7 for c in cands): continue
        rec["d"] = d; cands.append(rec)
        if len(cands) >= 10: break
    res = {"n_rules": int(ntot), "threshold_t1": thr, "nulls": nulls, "best_real_t1": float(t1.max()),
           "top10": [dict(rule=names[b] + " | " + FILTERS[f], t1=float(t1[b, f]), t2=float(t2[b, f]), n=int(n[b, f]), mean1_bp=float(m1[b, f] * 1e4)) for b, f in order[:10]],
           "candidates": []}
    if cands:
        from scipy import stats
        G1c, G2c, Vc = mats(conf); Fc = Fall[:, conf]; c1, c2, cn, cm = stats_mat(G1c, G2c, Vc, Fc)
        ps = [float(stats.t.sf(c1[c["b"], c["f"]], max(cn[c["b"], c["f"]] - 1, 1))) for c in cands]; adj = lab.holm(ps)
        for c, a in zip(cands, adj):
            b, f = c["b"], c["f"]; c.pop("d")
            c.update(conf_t1=float(c1[b, f]), conf_t2=float(c2[b, f]), conf_n=int(cn[b, f]), conf_mean1_bp=float(cm[b, f] * 1e4), conf_holm=float(a),
                     conf_pass=bool(cm[b, f] > 0 and c2[b, f] > 0 and a < 0.05))
            res["candidates"].append(c); print("conf", c, flush=True)
    json.dump(res, open(f"{lab.HERE}/results/results_140.json", "w"), indent=1, default=float)
    log({"id": "140", "test": "level-breakout structured search (prereg 140)", "trials_added": int(ntot), "cum_trials": CUM_BEFORE + int(ntot),
         "threshold_t1": thr, "best_real_t1": float(t1.max()), "top10": res["top10"], "candidates": res["candidates"]})
