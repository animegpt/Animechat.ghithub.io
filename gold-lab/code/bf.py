"""#133 structured brute force + shared machinery for #134 GP (prereg/PREREGISTRATION_133_134_bruteforce_gp.md).
Builds: condition library C[E] (78 x days, bool) and outcome series per (E, X, stop, dir) with net1/net2 per day."""
import numpy as np, pandas as pd
import lab
from numba import njit

ES = [19, 0, 3, 6, 8, 9, 10, 12, 14]
XS = [3, 8, 10, 12, 14, 16]
ORDER = {h: (h - 17) % 24 for h in range(24)}   # position of an NY hour inside the 17:00->17:00 day


def windows():
    return [(E, X) for E in ES for X in XS if ORDER[X] > ORDER[E]]


def past_terciles(x, w=250, minp=100):
    s = pd.Series(x)
    q1 = s.shift(1).rolling(w, min_periods=minp).quantile(1 / 3).values
    q2 = s.shift(1).rolling(w, min_periods=minp).quantile(2 / 3).values
    ok = np.isfinite(q1) & np.isfinite(x)
    return [ok & (x <= q1), ok & (x > q1) & (x <= q2), ok & (x > q2)]


def sma(x, n): return pd.Series(x).rolling(n).mean().values


def rsi(x, n):
    d = np.r_[0, np.diff(x)]
    up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / n, adjust=False).mean().values
    dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / n, adjust=False).mean().values
    return 100 - 100 / (1 + up / np.where(dn == 0, 1e-12, dn))


def lag(x, k=1):
    x = np.asarray(x); out = np.empty_like(x)
    if x.dtype == bool: out[:k] = False
    else: out = out.astype(float); out[:k] = np.nan
    out[k:] = x[:-k]; return out


def daily_conditions(M):
    """conditions for day t using only information up to the end of day t-1. returns list of (name, group, bool array)"""
    D = M.D; O, H, L, C = (D[k].values for k in "ohlc"); n = len(C)
    pc = np.r_[C[0], C[:-1]]; tr = np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))
    atr14 = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    r1 = np.r_[np.nan, np.log(C[1:] / C[:-1])]
    out = []
    add = lambda nm, g, arr: out.append((nm, g, lag(np.asarray(arr, bool))))   # all shifted: value at t uses t-1
    for nm, a in zip(("lo", "mid", "hi"), past_terciles(r1)): add(f"r1_{nm}", "r1", a)
    for nm, a in zip(("lo", "mid", "hi"), past_terciles((H - L) / atr14)): add(f"rng_{nm}", "rng", a)
    clv = (C - L) / np.where(H - L == 0, np.nan, H - L)
    add("clv_lo", "clv", clv < 0.25); add("clv_hi", "clv", clv > 0.75); add("clv_mid", "clv", (clv >= 0.25) & (clv <= 0.75))
    ins = np.r_[False, (H[1:] < H[:-1]) & (L[1:] > L[:-1])]; outd = np.r_[False, (H[1:] > H[:-1]) & (L[1:] < L[:-1])]
    add("inside", "io", ins); add("outside", "io", outd)
    add("c_gt_h2", "brk1", np.r_[False, C[1:] > H[:-1]]); add("c_lt_l2", "brk1", np.r_[False, C[1:] < L[:-1]])
    up = np.r_[False, C[1:] > C[:-1]]; dn = np.r_[False, C[1:] < C[:-1]]
    run = lambda b: pd.Series(b.astype(int)).groupby((~b).cumsum()).cumsum().values
    add("up3", "streak", run(up) >= 3); add("dn3", "streak", run(dn) >= 3)
    for k in (5, 10, 20, 50, 100, 200):
        m = sma(C, k); add(f"above_sma{k}", f"sma{k}", C > m); add(f"below_sma{k}", f"sma{k}", C < m)
    for k in (5, 10, 20, 55):
        hi = pd.Series(C).shift(1).rolling(k).max().values; lo = pd.Series(C).shift(1).rolling(k).min().values
        add(f"hiclose{k}", f"ext{k}", C > hi); add(f"loclose{k}", f"ext{k}", C < lo)
    r2 = rsi(C, 2); r14 = rsi(C, 14)
    add("rsi2_lt10", "rsi2", r2 < 10); add("rsi2_gt90", "rsi2", r2 > 90); add("rsi14_lt30", "rsi14", r14 < 30); add("rsi14_gt70", "rsi14", r14 > 70)
    for k in (5, 20):
        rk = np.r_[np.full(k, np.nan), np.log(C[k:] / C[:-k])]
        for nm, a in zip(("lo", "mid", "hi"), past_terciles(rk)): add(f"r{k}_{nm}", f"r{k}", a)
    days = M.days
    wk = days.to_period("W-FRI"); mo = days.to_period("M")
    dfw = pd.DataFrame({"h": H, "l": L, "w": wk, "m": mo})
    wh = dfw.groupby("w").h.max(); wl = dfw.groupby("w").l.min(); mh = dfw.groupby("m").h.max(); ml = dfw.groupby("m").l.min()
    pwh = wh.shift(1).reindex(wk).values; pwl = wl.shift(1).reindex(wk).values; pmh = mh.shift(1).reindex(mo).values; pml = ml.shift(1).reindex(mo).values
    # condition at t uses close(t-1) vs the week/month before day t-1's week/month -> compute on t-1 then lag
    add("gt_lastwk_h", "wk", C > pwh); add("lt_lastwk_l", "wk", C < pwl); add("gt_lastmo_h", "mo", C > pmh); add("lt_lastmo_l", "mo", C < pml)
    atr5 = pd.Series(tr).rolling(5).mean().values; atr20 = pd.Series(tr).rolling(20).mean().values
    for nm, a in zip(("lo", "mid", "hi"), past_terciles(atr5 / atr20)): add(f"atrr_{nm}", "atrr", a)
    rv = pd.Series(r1).rolling(20).std().values
    for nm, a in zip(("lo", "mid", "hi"), past_terciles(rv)): add(f"rv_{nm}", "rv", a)
    # calendar: known in advance, NOT lagged
    for d, nm in enumerate(("mon", "tue", "wed", "thu", "fri")): out.append((nm, "dow", np.asarray(days.dayofweek == d)))
    mser = pd.Series(mo)
    out.append(("first_dom", "dom", np.asarray(mser != mser.shift(1))))
    out.append(("last_dom", "dom", np.asarray(mser != mser.shift(-1))))
    return out, atr14


def intraday_conditions(M, E, atr14):
    nd = len(M.days); o, h, l, c = M.o, M.h, M.l, M.c
    jE = M.dh[:, E]; ok = jE > M.s
    ret = np.full(nd, np.nan); rngs = np.full(nd, np.nan); last = np.full(nd, np.nan); pos = np.full(nd, np.nan); px = np.full(nd, np.nan)
    D = M.D; PH = lag(D.h.values.astype(float)); PL = lag(D.l.values.astype(float)); PC = lag(D.c.values.astype(float))
    for t in np.flatnonzero(ok):
        a, b = M.s[t], jE[t] - 1
        hh = h[a:b + 1].max(); ll = l[a:b + 1].min()
        ret[t] = c[b] / o[a] - 1; rngs[t] = (hh - ll) / atr14[t - 1] if t > 0 else np.nan; last[t] = c[b] / o[b] - 1
        pos[t] = (c[b] - ll) / (hh - ll) if hh > ll else 0.5; px[t] = c[b]
    out = []
    for nm, a in zip(("lo", "mid", "hi"), past_terciles(ret)): out.append((f"sofar_{nm}", "sofar", a))
    out.append(("abv_pdh", "vsprev", px > PH)); out.append(("blw_pdl", "vsprev", px < PL))
    out.append(("in_abv_pdc", "vsprev", (px <= PH) & (px >= PL) & (px > PC))); out.append(("in_blw_pdc", "vsprev", (px <= PH) & (px >= PL) & (px <= PC)))
    for nm, a in zip(("lo", "mid", "hi"), past_terciles(rngs)): out.append((f"irng_{nm}", "irng", a))
    for nm, a in zip(("lo", "mid", "hi"), past_terciles(last)): out.append((f"lasth_{nm}", "lasth", a))
    out.append(("at_dayhigh", "athl", pos >= 0.9)); out.append(("at_daylow", "athl", pos <= 0.1))
    return out


@njit(cache=True)
def _outcome(o, h, l, c, jE, jX, stopd, side, half_spread, slip):
    nd = len(jE); g = np.full(nd, np.nan); n1 = np.full(nd, np.nan); n2 = np.full(nd, np.nan)
    for t in range(nd):
        a = jE[t]; b = jX[t]
        if a < 0 or b < 0 or b < a: continue
        ep = o[a]; xp = c[b]
        if stopd[t] > 0:
            st = ep - side * stopd[t]
            for j in range(a, b + 1):
                if side == 1 and l[j] <= st:
                    xp = min(st, o[j]); break
                if side == -1 and h[j] >= st:
                    xp = max(st, o[j]); break
        gg = side * (xp / ep - 1)
        g[t] = gg; n1[t] = gg - half_spread / ep - half_spread / xp - 2 * slip; n2[t] = gg - 2 * half_spread / 4000.0 - 2 * slip
    return g, n1, n2


def build(M):
    dconds, atr14 = daily_conditions(M)
    nd = len(M.days)
    always = ("always", "always", np.ones(nd, bool))
    C = {}; names = None; groups = None
    for E in ES:
        lst = [always] + dconds + intraday_conditions(M, E, atr14)
        if names is None: names = [x[0] for x in lst]; groups = [x[1] for x in lst]
        C[E] = np.vstack([x[2] for x in lst]).astype(bool)
    outs = []  # (E, X, stopflag, side)
    Y = {}
    atr_l = lag(atr14)
    hs = M.spec["spread"] / 2
    for (E, X) in windows():
        jE = M.dh[:, E]; jX = M.dh[:, (X - 1) % 24]
        for st in (0, 1):
            sd = (0.5 * atr_l if st else np.zeros(nd)); sd = np.nan_to_num(sd, nan=-1.0) if st else sd
            for side in (1, -1):
                g, n1, n2 = _outcome(M.o, M.h, M.l, M.c, jE, jX, sd if st else np.zeros(nd), side, hs, lab.SLIP)
                if st: bad = ~np.isfinite(atr_l); n1[bad] = np.nan; n2[bad] = np.nan; g[bad] = np.nan
                outs.append((E, X, st, side)); Y[(E, X, st, side)] = (g, n1, n2)
    return dict(C=C, names=names, groups=groups, outs=outs, Y=Y, nd=nd)


def gen_rules(B, n_total, seed, exclude=None, n_singles=True):
    """returns array of rules (out_index, a, b) ; b = -1 for singles. Singles first (all), then random distinct pairs."""
    rng = np.random.default_rng(seed); nc = len(B["names"]); no = len(B["outs"]); groups = np.array(B["groups"])
    rules = []; seen = set() if exclude is None else set(exclude)
    if n_singles:
        for oi in range(no):
            for a in range(nc):
                rules.append((oi, a, -1)); seen.add((oi, a, -1))
    while len(rules) < n_total:
        oi = int(rng.integers(no)); a, b = sorted(int(x) for x in rng.integers(1, nc, 2))
        if a == b or groups[a] == groups[b] or (oi, a, b) in seen: continue
        seen.add((oi, a, b)); rules.append((oi, a, b))
    return np.array(rules[:n_total], dtype=np.int64)


def evaluate(B, rules, dsel, shift=0):
    """vectorised stats of rules over day indices dsel. shift: circular shift of outcomes within dsel (null).
    returns DataFrame n, mean1, t1, mean2, t2, sr_ann (daily pnl incl. zero days, net1)"""
    nr = len(rules); res = np.zeros((nr, 6))
    outs = B["outs"]; nd = len(dsel)
    by_E = {}
    for k, (oi, a, b) in enumerate(rules): by_E.setdefault(outs[oi][0], []).append(k)
    for E, ks in by_E.items():
        Cm = B["C"][E][:, dsel]
        ks = np.array(ks); r = rules[ks]
        # masks for unique (a,b) pairs
        pairs, inv = np.unique(r[:, 1:], axis=0, return_inverse=True)
        inv = inv.ravel()
        A = Cm[pairs[:, 0]] & np.where(pairs[:, 1:2] >= 0, Cm[np.maximum(pairs[:, 1], 0)], True)
        A = A.astype(np.float32)
        ois = np.unique(r[:, 0])
        for oi in ois:
            g, n1, n2 = B["Y"][outs[oi]]
            y1 = n1[dsel]; y2 = n2[dsel]
            if shift: y1 = np.roll(y1, shift); y2 = np.roll(y2, shift)
            v = np.isfinite(y1); y1 = np.where(v, y1, 0); y2 = np.where(v, y2, 0)
            Ym = np.stack([v.astype(np.float32), y1, y1 * y1, y2, y2 * y2], 1).astype(np.float64)
            sel = np.flatnonzero(r[:, 0] == oi)
            S = A[inv[sel]].astype(np.float64) @ Ym
            n = S[:, 0]; m1 = S[:, 1] / np.maximum(n, 1); v1 = (S[:, 2] - n * m1 ** 2) / np.maximum(n - 1, 1)
            m2 = S[:, 3] / np.maximum(n, 1); v2 = (S[:, 4] - n * m2 ** 2) / np.maximum(n - 1, 1)
            t1 = m1 / np.sqrt(np.maximum(v1, 1e-30) / np.maximum(n, 1)); t2 = m2 / np.sqrt(np.maximum(v2, 1e-30) / np.maximum(n, 1))
            md = S[:, 1] / nd; vd = S[:, 2] / nd - md ** 2; sr = md / np.sqrt(np.maximum(vd, 1e-30)) * np.sqrt(252)
            res[ks[sel]] = np.stack([n, m1, t1, m2, t2, sr], 1)
    return pd.DataFrame(res, columns=["n", "mean1", "t1", "mean2", "t2", "sr_ann"])


def rule_name(B, rule):
    oi, a, b = rule; E, X, st, side = B["outs"][oi]
    c = B["names"][a] + ("" if b < 0 else " & " + B["names"][b])
    return f"{'LONG' if side == 1 else 'SHORT'} {E:02d}->{X:02d}NY{' stop0.5ATR' if st else ''} | {c}"


def rule_trades(M, B, rule, P):
    """per-trade DataFrame (lab format) for a rule within period P, for placebo/portfolio."""
    oi, a, b = rule; E, X, st, side = B["outs"][oi]
    m = B["C"][E][a] & (B["C"][E][b] if b >= 0 else True)
    g, n1, n2 = B["Y"][(E, X, st, side)]
    sel = np.flatnonzero(m & np.isfinite(n1) & (M.days >= P[0]) & (M.days < P[1]))
    jE = M.dh[sel, E]; jX = M.dh[sel, (X - 1) % 24]
    return pd.DataFrame({"t": M.days[sel], "tx": M.days[sel], "j0": jE, "jx": jX, "side": side, "gross": g[sel], "net1": n1[sel], "net2": n2[sel]})
