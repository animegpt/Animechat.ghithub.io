"""Re-implementation (from public descriptions, NOT the original sonic_ai.features / pac.py / ind.py, which were not
available in this container) of the three indicator suites, as per-bar raw features on one timeframe.
Every value at bar t uses bars <= t only (bar t is complete when the value is used).
Sign convention: for directional values, positive = bullish. Event pairs return bars-since for the bullish and bearish
version separately; features149.py turns them into 'with trade' / 'against trade'.

1. Price Action Concepts (PAC): swing (len 50) + internal (len 5) structure with BOS / CHoCH / CHoCH+, order blocks,
   FVG, liquidity sweeps, EQH/EQL, premium/discount.
2. Oscillator Matrix (OM): HyperWave (TSI-type 0-100 wave + signal), Money Flow (MFI-type, tick volume), Confluence,
   reversal marks (wave/signal cross in OB/OS), divergences (wave vs price pivots).
3. Signals & Overlays (SO): SuperTrend AI (9 factors 1..5, k-means on factor performance, best-cluster factor),
   Reversal Bands (EMA mid +- k * RMA(TR)).
"""
import numpy as np, pandas as pd
from numba import njit

BIG = 999.0


@njit(cache=True)
def _rma(x, n):
    out = np.empty_like(x); a = 1.0 / n; s = x[0]
    for i in range(len(x)):
        s = x[i] if i == 0 else s + a * (x[i] - s); out[i] = s
    return out


@njit(cache=True)
def _ema(x, n):
    out = np.empty_like(x); a = 2.0 / (n + 1); s = x[0]
    for i in range(len(x)):
        s = x[i] if i == 0 else s + a * (x[i] - s); out[i] = s
    return out


def _tr(h, l, c):
    pc = np.r_[c[0], c[:-1]]
    return np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))


@njit(cache=True)
def _since(ev):
    """bars since last True (0 = this bar); BIG if never"""
    out = np.empty(len(ev)); last = -1
    for i in range(len(ev)):
        if ev[i]: last = i
        out[i] = BIG if last < 0 else i - last
    return out


# ------------------------------------------------------------------ PAC
@njit(cache=True)
def _structure(h, l, c, size):
    """LuxAlgo leg() pivots (confirmed `size` bars later) + close-break of last pivot.
    returns trend, events (6: bos_b, choch_b, chochp_b, bos_s, choch_s, chochp_s), last pivot hi/lo level and index"""
    n = len(c)
    trend = np.zeros(n); ev = np.zeros((n, 6), np.bool_)
    phl = np.full(n, np.nan); pll = np.full(n, np.nan); phi_ = np.full(n, -1); pli_ = np.full(n, -1)
    leg = 0; ph = np.nan; pl = np.nan; phx = True; plx = True; tr = 0
    ph_prev = np.nan; pl_prev = np.nan; phi = -1; pli = -1
    for t in range(size, n):
        hh = h[t - size + 1]; ll = l[t - size + 1]
        for k in range(t - size + 1, t + 1):
            if h[k] > hh: hh = h[k]
            if l[k] < ll: ll = l[k]
        newH = h[t - size] > hh; newL = l[t - size] < ll
        prev = leg
        if newH: leg = 0
        elif newL: leg = 1
        if leg != prev:
            if leg == 1:
                pl_prev = pl; pl = l[t - size]; plx = False; pli = t - size
            else:
                ph_prev = ph; ph = h[t - size]; phx = False; phi = t - size
        if (not np.isnan(ph)) and (not phx) and c[t] > ph:
            phx = True
            if tr == -1:
                plus = (not np.isnan(pl_prev)) and pl > pl_prev
                if plus: ev[t, 2] = True
                else: ev[t, 1] = True
            else: ev[t, 0] = True
            tr = 1
        if (not np.isnan(pl)) and (not plx) and c[t] < pl:
            plx = True
            if tr == 1:
                plus = (not np.isnan(ph_prev)) and ph < ph_prev
                if plus: ev[t, 5] = True
                else: ev[t, 4] = True
            else: ev[t, 3] = True
            tr = -1
        trend[t] = tr; phl[t] = ph; pll[t] = pl; phi_[t] = phi; pli_[t] = pli
    return trend, ev, phl, pll, phi_, pli_


@njit(cache=True)
def _order_blocks(h, l, c, atr, brk_b, brk_s, phi_, pli_, max_keep):
    """bull OB on bullish break: bar with lowest low between last pivot high and break; mitigated when close < btm.
    returns n_active_bull, n_active_bear, dist to nearest bull OB top below/at price (ATR), dist to nearest bear OB btm
    above (ATR), inside-bull, inside-bear"""
    n = len(c)
    bt = np.full(max_keep, np.nan); bb = np.full(max_keep, np.nan); st_ = np.full(max_keep, np.nan); sb = np.full(max_keep, np.nan)
    nb = np.zeros(n); ns = np.zeros(n); db = np.full(n, 10.0); ds = np.full(n, 10.0); ib = np.zeros(n); is_ = np.zeros(n)
    kb = 0; ks = 0
    for t in range(n):
        if brk_b[t] and phi_[t] >= 0 and t - phi_[t] >= 2:
            s = phi_[t]; j = s
            for k in range(s, t):
                if l[k] < l[j]: j = k
            bt[kb % max_keep] = h[j]; bb[kb % max_keep] = l[j]; kb += 1
        if brk_s[t] and pli_[t] >= 0 and t - pli_[t] >= 2:
            s = pli_[t]; j = s
            for k in range(s, t):
                if h[k] > h[j]: j = k
            st_[ks % max_keep] = h[j]; sb[ks % max_keep] = l[j]; ks += 1
        a = atr[t] if atr[t] > 0 else 1e-9
        cb = 0; cs = 0
        for q in range(max_keep):
            if not np.isnan(bb[q]):
                if c[t] < bb[q]: bb[q] = np.nan; bt[q] = np.nan
                else:
                    cb += 1
                    d = (c[t] - bt[q]) / a
                    if d < 0: d = 0.0; ib[t] = 1
                    if d < db[t]: db[t] = d
            if not np.isnan(st_[q]):
                if c[t] > st_[q]: st_[q] = np.nan; sb[q] = np.nan
                else:
                    cs += 1
                    d = (sb[q] - c[t]) / a
                    if d < 0: d = 0.0; is_[t] = 1
                    if d < ds[t]: ds[t] = d
        nb[t] = cb; ns[t] = cs
    return nb, ns, db, ds, ib, is_


@njit(cache=True)
def _fvg(h, l, c, atr, max_keep):
    """bull FVG at t: l[t] > h[t-2] and c[t-1] > h[t-2]; zone [h[t-2], l[t]] filled when low <= bottom. bear symmetric."""
    n = len(c)
    evb = np.zeros(n, np.bool_); evs = np.zeros(n, np.bool_)
    zb = np.full(max_keep, np.nan); zbt = np.full(max_keep, np.nan); zs = np.full(max_keep, np.nan); zsb = np.full(max_keep, np.nan)
    nb = np.zeros(n); ns = np.zeros(n); db = np.full(n, 10.0); ds = np.full(n, 10.0)
    kb = 0; ks = 0
    for t in range(2, n):
        if l[t] > h[t - 2] and c[t - 1] > h[t - 2]:
            evb[t] = True; zb[kb % max_keep] = h[t - 2]; zbt[kb % max_keep] = l[t]; kb += 1
        if h[t] < l[t - 2] and c[t - 1] < l[t - 2]:
            evs[t] = True; zs[ks % max_keep] = l[t - 2]; zsb[ks % max_keep] = h[t]; ks += 1
        a = atr[t] if atr[t] > 0 else 1e-9
        cb = 0; cs = 0
        for q in range(max_keep):
            if not np.isnan(zb[q]):
                if l[t] <= zb[q]: zb[q] = np.nan
                else:
                    cb += 1; d = (c[t] - zbt[q]) / a
                    if d < 0: d = 0.0
                    if d < db[t]: db[t] = d
            if not np.isnan(zs[q]):
                if h[t] >= zs[q]: zs[q] = np.nan
                else:
                    cs += 1; d = (zsb[q] - c[t]) / a
                    if d < 0: d = 0.0
                    if d < ds[t]: ds[t] = d
        nb[t] = cb; ns[t] = cs
    return evb, evs, nb, ns, db, ds


@njit(cache=True)
def _eq_levels(h, l, atr, size, thr):
    """pivots of `size` both sides (confirmed size bars later); EQH when new pivot high within thr*ATR of previous one."""
    n = len(h)
    eqh = np.zeros(n, np.bool_); eql = np.zeros(n, np.bool_); lvh = np.full(n, np.nan); lvl = np.full(n, np.nan)
    lastph = np.nan; lastpl = np.nan; curh = np.nan; curl = np.nan
    for t in range(2 * size, n):
        p = t - size; isph = True; ispl = True
        for k in range(p - size, p + size + 1):
            if k == p: continue
            if h[k] >= h[p]: isph = False
            if l[k] <= l[p]: ispl = False
        if isph:
            if (not np.isnan(lastph)) and abs(h[p] - lastph) < thr * atr[t]:
                eqh[t] = True; curh = max(h[p], lastph)
            lastph = h[p]
        if ispl:
            if (not np.isnan(lastpl)) and abs(l[p] - lastpl) < thr * atr[t]:
                eql[t] = True; curl = min(l[p], lastpl)
            lastpl = l[p]
        lvh[t] = curh; lvl[t] = curl
    return eqh, eql, lvh, lvl


def pac(o, h, l, c, v):
    n = len(c); F = {}
    atr = _rma(_tr(h, l, c), 200)
    atr14 = _rma(_tr(h, l, c), 14)
    for nm, size in (("sw", 50), ("in", 5)):
        tr, ev, phl, pll, phi_, pli_ = _structure(h, l, c, size)
        F[f"pac_{nm}_trend"] = tr
        F[f"pac_{nm}_bos_b"] = _since(ev[:, 0]); F[f"pac_{nm}_bos_s"] = _since(ev[:, 3])
        F[f"pac_{nm}_choch_b"] = _since(ev[:, 1] | ev[:, 2]); F[f"pac_{nm}_choch_s"] = _since(ev[:, 4] | ev[:, 5])
        F[f"pac_{nm}_chochp_b"] = _since(ev[:, 2]); F[f"pac_{nm}_chochp_s"] = _since(ev[:, 5])
        brk_b = ev[:, 0] | ev[:, 1] | ev[:, 2]; brk_s = ev[:, 3] | ev[:, 4] | ev[:, 5]
        nb, ns, db, ds, ib, is_ = _order_blocks(h, l, c, atr14, brk_b, brk_s, phi_, pli_, 10 if nm == "sw" else 5)
        F[f"pac_{nm}_ob_n_b"] = nb; F[f"pac_{nm}_ob_n_s"] = ns
        F[f"pac_{nm}_ob_d_b"] = db; F[f"pac_{nm}_ob_d_s"] = ds
        F[f"pac_{nm}_ob_in_b"] = ib; F[f"pac_{nm}_ob_in_s"] = is_
        # liquidity sweep of the last pivot: wick through, close back
        phs = np.r_[np.nan, phl[:-1]]; pls = np.r_[np.nan, pll[:-1]]
        sw_s = (h > phs) & (c < phs); sw_b = (l < pls) & (c > pls)
        F[f"pac_{nm}_sweep_b"] = _since(sw_b); F[f"pac_{nm}_sweep_s"] = _since(sw_s)
        if nm == "sw":
            rng = phl - pll
            pos = np.where(rng > 0, (c - pll) / np.where(rng > 0, rng, 1), 0.5)
            pos = np.clip(np.nan_to_num(pos, nan=0.5), -0.5, 1.5)
            F["pac_pd_pos"] = pos - 0.5                                       # + = premium
            F["pac_pd_zone"] = np.where(pos > 0.525, 1.0, np.where(pos < 0.475, -1.0, 0.0))
    evb, evs, nb, ns, db, ds = _fvg(h, l, c, atr14, 20)
    F["pac_fvg_b"] = _since(evb); F["pac_fvg_s"] = _since(evs)
    F["pac_fvg_n_b"] = nb; F["pac_fvg_n_s"] = ns; F["pac_fvg_d_b"] = db; F["pac_fvg_d_s"] = ds
    eqh, eql, lvh, lvl = _eq_levels(h, l, atr, 3, 0.1)
    F["pac_eqh"] = _since(eqh); F["pac_eql"] = _since(eql)
    F["pac_eqh_d"] = np.clip(np.nan_to_num((lvh - c) / atr14, nan=10.0), -10, 10)   # + = EQH above price (liquidity above)
    F["pac_eql_d"] = np.clip(np.nan_to_num((c - lvl) / atr14, nan=10.0), -10, 10)
    return F


# ------------------------------------------------------------------ Oscillator Matrix
def _sma(x, n): return pd.Series(x).rolling(n, min_periods=1).mean().values


@njit(cache=True)
def _pivots(x, size):
    """pivot high/low of series x confirmed size bars later: arrays (is_ph at confirm bar, idx of pivot)"""
    n = len(x); ph = np.zeros(n, np.bool_); pl = np.zeros(n, np.bool_)
    for t in range(2 * size, n):
        p = t - size; a = True; b = True
        for k in range(p - size, p + size + 1):
            if k == p: continue
            if x[k] >= x[p]: a = False
            if x[k] <= x[p]: b = False
        ph[t] = a; pl[t] = b
    return ph, pl


@njit(cache=True)
def _divergence(h, l, w, size):
    n = len(h); bull = np.zeros(n, np.bool_); bear = np.zeros(n, np.bool_)
    lph = np.nan; lphw = np.nan; lpl = np.nan; lplw = np.nan
    for t in range(2 * size, n):
        p = t - size; isph = True; ispl = True
        for k in range(p - size, p + size + 1):
            if k == p: continue
            if h[k] >= h[p]: isph = False
            if l[k] <= l[p]: ispl = False
        if isph:
            if (not np.isnan(lph)) and h[p] > lph and w[p] < lphw: bear[t] = True
            lph = h[p]; lphw = w[p]
        if ispl:
            if (not np.isnan(lpl)) and l[p] < lpl and w[p] > lplw: bull[t] = True
            lpl = l[p]; lplw = w[p]
    return bull, bear


def osc(o, h, l, c, v):
    F = {}
    d = np.r_[0.0, np.diff(c)]
    m = _ema(_ema(d, 14), 7); a = _ema(_ema(np.abs(d), 14), 7)
    hw = 50 + 50 * np.where(a > 0, m / np.where(a > 0, a, 1), 0)
    sig = _sma(hw, 3)
    F["om_hw"] = hw - 50
    F["om_hw_sig"] = hw - sig
    F["om_hw_slope"] = hw - np.r_[hw[0], hw[:-1]]
    F["om_hw_zone"] = np.where(hw > 80, 1.0, np.where(hw < 20, -1.0, 0.0))
    up50 = (hw > 50) & (np.r_[50.0, hw[:-1]] <= 50); dn50 = (hw < 50) & (np.r_[50.0, hw[:-1]] >= 50)
    F["om_x50_b"] = _since(up50); F["om_x50_s"] = _since(dn50)
    xu = (hw > sig) & (np.r_[hw[0], hw[:-1]] <= np.r_[sig[0], sig[:-1]]); xd = (hw < sig) & (np.r_[hw[0], hw[:-1]] >= np.r_[sig[0], sig[:-1]])
    F["om_rev_b"] = _since(xu & (hw < 30)); F["om_rev_s"] = _since(xd & (hw > 70))
    tp = (h + l + c) / 3; dtp = np.r_[0.0, np.diff(tp)]
    vv = np.maximum(v, 1e-9)
    pos = pd.Series(np.where(dtp > 0, tp * vv, 0)).rolling(14, min_periods=1).sum().values
    neg = pd.Series(np.where(dtp < 0, tp * vv, 0)).rolling(14, min_periods=1).sum().values
    mfi = 100 * pos / np.maximum(pos + neg, 1e-12)
    mf = _sma(mfi, 6)
    F["om_mf"] = mf - 50
    F["om_mf_slope"] = mf - np.r_[mf[0], mf[:-1]]
    conf = ((hw - 50) / 50 + (mf - 50) / 50) / 2
    F["om_conf"] = conf
    F["om_conf_agree"] = np.where((hw > 50) & (mf > 50), 1.0, np.where((hw < 50) & (mf < 50), -1.0, 0.0))
    bull, bear = _divergence(h, l, hw, 5)
    F["om_div_b"] = _since(bull); F["om_div_s"] = _since(bear)
    return F


# ------------------------------------------------------------------ Signals & Overlays
@njit(cache=True)
def _st_one(hl2, c, atr, f):
    n = len(c); st = np.empty(n); tr = np.zeros(n)
    up = hl2[0] - f * atr[0]; dn = hl2[0] + f * atr[0]; t_ = 1
    for i in range(n):
        u = hl2[i] - f * atr[i]; d = hl2[i] + f * atr[i]
        if i > 0:
            u = max(u, up) if c[i - 1] > up else u
            d = min(d, dn) if c[i - 1] < dn else d
            if t_ == 1 and c[i] < up: t_ = -1
            elif t_ == -1 and c[i] > dn: t_ = 1
        up = u; dn = d
        st[i] = up if t_ == 1 else dn; tr[i] = t_
    return st, tr


@njit(cache=True)
def _st_ai(h, l, c, atr, factors, perf_alpha):
    n = len(c); K = len(factors)
    hl2 = (h + l) / 2
    sts = np.empty((K, n))
    for k in range(K):
        s, _ = _st_one(hl2, c, atr, factors[k]); sts[k] = s
    perf = np.zeros(K); a = 2.0 / (perf_alpha + 1)
    den = 0.0
    fac = np.full(n, np.nan); strength = np.zeros(n); stf = np.empty(n); trf = np.zeros(n)
    up = hl2[0] - 3 * atr[0]; dn = hl2[0] + 3 * atr[0]; t_ = 1; f = 3.0
    for i in range(n):
        if i > 0:
            dc = c[i] - c[i - 1]
            for k in range(K):
                perf[k] += a * (dc * np.sign(c[i - 1] - sts[k, i - 1]) - perf[k])
            den += a * (abs(dc) - den)
            # 1-D k-means, 3 clusters, init at 25/50/75 percentiles
            srt = np.sort(perf.copy())
            cen = np.array([srt[int(0.25 * (K - 1))], srt[int(0.5 * (K - 1))], srt[int(0.75 * (K - 1))]])
            lab = np.zeros(K, np.int64)
            for it in range(20):
                for k in range(K):
                    b = 0; bd = abs(perf[k] - cen[0])
                    for q in range(1, 3):
                        dd = abs(perf[k] - cen[q])
                        if dd < bd: bd = dd; b = q
                    lab[k] = b
                newc = cen.copy()
                for q in range(3):
                    s = 0.0; m = 0
                    for k in range(K):
                        if lab[k] == q: s += perf[k]; m += 1
                    if m > 0: newc[q] = s / m
                if np.all(np.abs(newc - cen) < 1e-12): break
                cen = newc
            best = 0
            for q in range(1, 3):
                if cen[q] > cen[best]: best = q
            s = 0.0; m = 0
            for k in range(K):
                if lab[k] == best: s += factors[k]; m += 1
            if m > 0: f = s / m
            strength[i] = max(cen[best], 0.0) / den if den > 0 else 0.0
        u = hl2[i] - f * atr[i]; d = hl2[i] + f * atr[i]
        if i > 0:
            u = max(u, up) if c[i - 1] > up else u
            d = min(d, dn) if c[i - 1] < dn else d
            if t_ == 1 and c[i] < up: t_ = -1
            elif t_ == -1 and c[i] > dn: t_ = 1
        up = u; dn = d
        stf[i] = up if t_ == 1 else dn; trf[i] = t_; fac[i] = f
    return stf, trf, fac, strength


def sig(o, h, l, c, v):
    F = {}
    atr10 = _rma(_tr(h, l, c), 10)
    st, tr, fac, strength = _st_ai(h, l, c, atr10, np.arange(1.0, 5.01, 0.5), 10.0)
    F["so_st_dir"] = tr
    F["so_st_dist"] = np.clip((c - st) / np.maximum(atr10, 1e-9), -20, 20)
    flipb = (tr == 1) & (np.r_[1.0, tr[:-1]] == -1); flips = (tr == -1) & (np.r_[-1.0, tr[:-1]] == 1)
    F["so_st_flip_b"] = _since(flipb); F["so_st_flip_s"] = _since(flips)
    F["so_st_strength"] = np.clip(strength * 10, 0, 10)       # non-directional
    F["so_st_factor"] = fac                                     # non-directional
    mid = _ema(c, 20); ra = _rma(_tr(h, l, c), 20)
    z = (c - mid) / np.maximum(ra, 1e-9)
    F["so_rb_z"] = np.clip(z, -10, 10)
    F["so_rb_out"] = np.where(z > 2, 1.0, np.where(z < -2, -1.0, 0.0))
    F["so_rb_touch_up"] = _since(h >= mid + 3 * ra)       # bearish reversal zone
    F["so_rb_touch_dn"] = _since(l <= mid - 3 * ra)       # bullish reversal zone
    return F


def all_features(df):
    o, h, l, c, v = (df[k].values.astype(np.float64) for k in ("o", "h", "l", "c", "v"))
    F = {}
    F.update(pac(o, h, l, c, v)); F.update(osc(o, h, l, c, v)); F.update(sig(o, h, l, c, v))
    return pd.DataFrame(F, index=df.index)
