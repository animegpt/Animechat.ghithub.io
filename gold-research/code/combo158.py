"""#158-#161 COMBO portfolio (prereg PREREGISTRATION_158_161_combo.md).
Rebuild of GoldComboAI.mq5 v1.00 (Sonic + Sonic-AI features, Overnight + 18 features) and Williams #112 on Dukascopy H1,
cost scenarios A-D, walk-forward Sonic-AI / Overnight-AI reproductions."""
import os, sys, json
import numpy as np, pandas as pd
from numba import njit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab

SLIP = 0.1e-4
SCN = ("A", "B0", "B", "C", "D")   # Amendment A: B = live swap 0.8944, B0 = old swap 0.4316
# frozen EA Overnight model (GoldComboAI.mq5 v1.00) - used only for the threshold calibration q and the silver frozen check
ON_COEF = np.array([-0.250023, -0.080665, -0.078455, 0.235973, -0.06383, 0.046993, 0.111766, -0.160775, -0.309784, 0.046821, 0.006768,
                    -0.072245, -0.009762, -0.078953, 0.163087, -0.049637, -0.006806, 0.135965])
ON_MEAN = np.array([-0.000584, 0.002488, 0.007151, 0.152932, 0.760341, 2.117146, 4.352902, 0.514995, -1.861425, 2.115013, 50.46558, 0.126375,
                    0.532942, 33.107054, 1.021883, 1.512042, 6.506617, 0.964532])
ON_SD = np.array([0.500272, 1.177253, 2.22103, 2.97785, 7.042404, 14.074703, 1.346815, 0.290832, 3.150082, 3.236626, 13.538249, 2.305856,
                  4.541134, 15.432695, 0.222628, 1.109104, 3.397766, 36.094531])
ON_ICPT = -0.337297; ON_THR = 0.410668


# ------------------------------------------------------------------ costs
def cost_frac(scn, side, ep, xp, nroll, inst="XAUUSD"):
    """fraction-of-price cost of one round trip (prereg section 2)"""
    side = np.asarray(side); ep = np.asarray(ep, float); xp = np.asarray(xp, float); nroll = np.asarray(nroll, float)
    if inst != "XAUUSD":
        return 0.0125 / ep + 0.0125 / xp + 2 * SLIP
    if scn == "A": sp = 0.12 / ep + 0.12 / xp; sw = 0.4316 / ep * nroll
    elif scn == "B0": sp = 0.24 / 4000 + 0 * ep; sw = 0.4316 / 4000 * nroll
    elif scn == "B": sp = 0.24 / 4000 + 0 * ep; sw = 0.8944 / 4000 * nroll
    elif scn == "C": sp = 0.24 / 4000 + 0 * ep; sw = 0 * ep
    else: sp = 0.12 / 4000 + 0 * ep; sw = 0 * ep
    return sp + 2 * SLIP + np.where(side > 0, sw, 0.0)


def nroll_of(M, j0, jx):
    d = M.dayof.copy()
    # bars outside kept days (weekend keys) -> nearest following kept day
    good = np.flatnonzero(d >= 0); nxt = np.searchsorted(good, np.arange(len(d)))
    nxt = np.minimum(nxt, len(good) - 1); d2 = np.where(d >= 0, d, d[good[nxt]])
    d0 = d2[np.asarray(j0)]; d1 = d2[np.asarray(jx)]
    return M.roll_cum[d1] - M.roll_cum[d0]


# ------------------------------------------------------------------ EA indicator helpers
def ema_seed(x, n):
    a = 2.0 / (n + 1); out = np.empty(len(x)); s = x[0]
    for i in range(len(x)):
        s = x[0] if i == 0 else s + a * (x[i] - s); out[i] = s
    return out


@njit(cache=True)
def _ema(x, n):
    a = 2.0 / (n + 1); out = np.empty(len(x)); s = x[0]
    for i in range(len(x)):
        s = x[0] if i == 0 else s + a * (x[i] - s); out[i] = s
    return out


@njit(cache=True)
def _structure(H, L, C, size):
    n = len(C); trend = np.zeros(n); pl_ = np.full(n, np.nan); ph_ = np.full(n, np.nan)
    bull = np.zeros(n, np.bool_); bear = np.zeros(n, np.bool_); chB = np.zeros(n, np.bool_); chS = np.zeros(n, np.bool_)
    leg = 0; ph = np.nan; pl = np.nan; phx = False; plx = False; tr = 0; cur = 0.0
    for t in range(n):
        if t >= size:
            hh = H[t - size + 1]; ll = L[t - size + 1]
            for k in range(t - size + 1, t + 1):
                if H[k] > hh: hh = H[k]
                if L[k] < ll: ll = L[k]
            newH = H[t - size] > hh; newL = L[t - size] < ll
            prev = leg
            if newH: leg = 0
            elif newL: leg = 1
            if leg != prev:
                if leg == 1: pl = L[t - size]; plx = False
                else: ph = H[t - size]; phx = False
            if (not np.isnan(ph)) and (not phx) and C[t] > ph and C[t - 1] <= ph:
                phx = True
                if tr == -1: chB[t] = True
                bull[t] = True; tr = 1
            if (not np.isnan(pl)) and (not plx) and C[t] < pl and C[t - 1] >= pl:
                plx = True
                if tr == 1: chS[t] = True
                bear[t] = True; tr = -1
        if bull[t]: cur = 1.0
        elif bear[t]: cur = -1.0
        trend[t] = cur; pl_[t] = pl; ph_[t] = ph
    return trend, pl_, ph_, bull, bear, chB, chS


@njit(cache=True)
def _since(x):
    out = np.empty(len(x)); last = -1
    for i in range(len(x)):
        if x[i]: last = i
        out[i] = (i - last) if last >= 0 else 9999.0
    return out


@njit(cache=True)
def _sweeps(H, L, C):
    n = len(C); b1 = np.zeros(n, np.bool_); b2 = np.zeros(n, np.bool_)
    lastL = np.nan; lastH = np.nan; usedL = False; usedH = False
    for t in range(n):
        j = t - 10
        if j >= 10:
            mn = L[j]; mx = H[j]
            for k in range(j - 10, j + 11):
                if L[k] < mn: mn = L[k]
                if H[k] > mx: mx = H[k]
            if L[j] == mn: lastL = L[j]; usedL = False
            if H[j] == mx: lastH = H[j]; usedH = False
        if (not usedL) and (not np.isnan(lastL)) and L[t] < lastL and C[t] > lastL: b1[t] = True; usedL = True
        elif (not np.isnan(lastL)) and C[t] < lastL: usedL = True
        if (not usedH) and (not np.isnan(lastH)) and H[t] > lastH and C[t] < lastH: b2[t] = True; usedH = True
        elif (not np.isnan(lastH)) and C[t] > lastH: usedH = True
    return b1, b2


@njit(cache=True)
def _linreg7(raw):
    n = len(raw); lr = np.zeros(n)
    for i in range(6, n):
        sx = 0.0; sy = 0.0; sxy = 0.0; sxx = 0.0; ok = True
        for k in range(i - 6, i + 1):
            if np.isnan(raw[k]): ok = False; break
            x = float(k); sx += x; sy += raw[k]; sxy += x * raw[k]; sxx += x * x
        if not ok: continue
        mx = sx / 7; my = sy / 7; cov = sxy / 7 - mx * my; var = sxx / 7 - mx * mx
        lr[i] = my + (cov / var) * (i - mx)
    return lr


@njit(cache=True)
def _htf(TUs, H, L, C, secs):
    n = len(C); out = np.zeros(n)
    bh = np.nan; bl = np.nan; bc = np.nan; eH = np.nan; eL = np.nan; eC = np.nan; sig = 0.0; prevB = -1
    for i in range(n):
        b = TUs[i] // secs
        if prevB >= 0 and b != prevB:
            eH = bh if np.isnan(eH) else eH + 2.0 / 35 * (bh - eH)
            eL = bl if np.isnan(eL) else eL + 2.0 / 35 * (bl - eL)
            eC = bc if np.isnan(eC) else eC + 2.0 / 90 * (bc - eC)
            m = (eH + eL) / 2 - eC; sig = 1.0 if m > 0 else (-1.0 if m < 0 else 0.0)
            bh = H[i]; bl = L[i]; bc = C[i]
        else:
            bh = H[i] if np.isnan(bh) else max(bh, H[i]); bl = L[i] if np.isnan(bl) else min(bl, L[i]); bc = C[i]
        prevB = b; out[i] = sig
    return out


def sma(x, n): return pd.Series(x).rolling(n).mean().values
def rmax(x, n): return pd.Series(x).rolling(n).max().values
def rmin(x, n): return pd.Series(x).rolling(n).min().values


class EA:
    """all EA series on the full H1 history (EA uses the last 6000 bars; recursive values converge)"""
    def __init__(self, M):
        self.M = M; O, H, L, C = M.o, M.h, M.l, M.c; n = len(C); self.n = n
        self.TU = M.idx; self.TUs = (M.idx.values.astype("datetime64[s]").astype(np.int64))
        pc = np.r_[C[0], C[:-1]]
        self.TRV = np.maximum(H - L, np.maximum(np.abs(H - pc), np.abs(L - pc)))
        atr = np.empty(n); atr[0] = self.TRV[0]
        for i in range(1, n): atr[i] = atr[i - 1] + (self.TRV[i] - atr[i - 1]) / 14.0
        self.ATR = atr
        self.EH, self.EL, self.EC, self.E89 = _ema(H, 34), _ema(L, 34), _ema(C, 34), _ema(C, 89)
        tr, pl, ph, b, s, cb, cs = _structure(H, L, C, 5)
        self.iTrend, self.iPL, self.iPH = tr, pl, ph
        self.sinceIB, self.sinceIS, self.sinceCB, self.sinceCS = _since(b), _since(s), _since(cb), _since(cs)
        tr, pl, ph, *_ = _structure(H, L, C, 50); self.sTrend, self.sPL, self.sPH = tr, pl, ph
        h2 = np.r_[np.nan, np.nan, H[:-2]]; l2 = np.r_[np.nan, np.nan, L[:-2]]; c1 = np.r_[np.nan, C[:-1]]
        f1 = (L > h2) & (c1 > h2); f2 = (H < l2) & (c1 < l2)
        self.fvgB24 = pd.Series(f1.astype(float)).rolling(24, min_periods=1).sum().values
        self.fvgS24 = pd.Series(f2.astype(float)).rolling(24, min_periods=1).sum().values
        s1, s2 = _sweeps(H, L, C)
        self.swB24 = pd.Series(s1.astype(float)).rolling(24, min_periods=1).sum().values
        self.swS24 = pd.Series(s2.astype(float)).rolling(24, min_periods=1).sum().values
        hl2 = (H + L) / 2; hi, lo, av = rmax(H, 7), rmin(L, 7), sma(hl2, 7)
        with np.errstate(invalid="ignore", divide="ignore"):
            raw = np.where((hi - lo) == 0, np.nan, (C - (hi + lo + av) / 3) / (hi - lo) * 100)
        self.HW = _ema(_linreg7(raw), 3)
        with np.errstate(invalid="ignore", divide="ignore"):
            self.RBZ = (C - sma(C, 30)) / sma(H - L, 30)
            self.VOLR = sma(self.TRV, 120) / sma(self.TRV, 1200)
        self.HTF4 = _htf(self.TUs, H, L, C, 4 * 3600); self.HTF1 = _htf(self.TUs, H, L, C, 24 * 3600)
        # NY time of each bar CLOSE
        ny = (M.idx + pd.Timedelta(hours=1)).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        self.nyc_hour = ny.hour.values; self.nyc_dow = ny.dayofweek.values; self.nyc_mon = ny.month.values
        self.nyc_day = ny.normalize().values.astype("datetime64[D]").astype(np.int64)
        self.LL10, self.HH10, self.LL5, self.HH5 = rmin(L, 10), rmax(H, 10), rmin(L, 5), rmax(H, 5)
        self.e50, self.e200 = _ema(C, 50), _ema(C, 200)
        up = 0.0; dn = 0.0; rsi = np.full(n, np.nan)
        for k in range(1, n):
            d = C[k] - C[k - 1]; up += (max(d, 0.0) - up) / 14.0; dn += (max(-d, 0.0) - dn) / 14.0
            rsi[k] = np.nan if dn == 0 else 100 - 100 / (1 + up / dn)
        self.RSI = rsi
        with np.errstate(invalid="ignore", divide="ignore"):
            self.VR = sma(self.TRV, 481) / sma(self.TRV, 2401)

    def sonic_signal(self, i):
        EH, EL, EC, E89, H, L, C = self.EH, self.EL, self.EC, self.E89, self.M.h, self.M.l, self.M.c
        mid = (EH[i] + EL[i]) / 2; mid5 = (EH[i - 5] + EL[i - 5]) / 2
        up = mid > E89[i] and mid > mid5 and E89[i] > E89[i - 5]
        dn = mid < E89[i] and mid < mid5 and E89[i] < E89[i - 5]
        tl = np.any(L[i - 4:i + 1] <= EC[i - 4:i + 1]); ts = np.any(H[i - 4:i + 1] >= EC[i - 4:i + 1])
        if up and tl and C[i] > EH[i] and C[i - 1] <= EH[i - 1]: return 1
        if dn and ts and C[i] < EL[i] and C[i - 1] >= EL[i - 1]: return -1
        return 0

    def sonic_features(self, i, s, prevR):
        M = self.M; C, O, H, L = M.c, M.o, M.h, M.l; a = self.ATR[i]; c = C[i]
        rng = self.sPH[i] - self.sPL[i]; pd_ = (c - self.sPL[i]) / rng if rng > 0 else np.nan
        f = np.empty(38)
        f[0] = s * self.iTrend[i]; f[1] = s * self.sTrend[i]
        f[2] = (c - self.iPL[i]) / a; f[3] = (self.iPH[i] - c) / a; f[4] = (c - self.sPL[i]) / a; f[5] = (self.sPH[i] - c) / a
        f[6] = s * self.RBZ[i]; f[7] = s * self.HW[i]; f[8] = (self.EH[i] - self.EL[i]) / a; f[9] = s * (c - self.E89[i]) / a
        f[10] = s * (self.EC[i] - self.EC[i - 5]) / a; f[11] = s * (self.E89[i] - self.E89[i - 5]) / a
        f[12] = s * self.HTF4[i]; f[13] = s * self.HTF1[i]
        for k, lag in zip((14, 15, 16, 17, 18), (1, 4, 24, 120, 480)): f[k] = s * (c - C[i - lag]) / a
        f[19] = a / c * 10000; f[20] = self.VOLR[i]; f[21] = (H[i] - L[i]) / a; f[22] = s * (c - O[i]) / a
        f[23] = self.nyc_hour[i]; f[24] = self.nyc_dow[i]
        f[25] = self.sinceIB[i] if s == 1 else self.sinceIS[i]; f[26] = self.sinceIS[i] if s == 1 else self.sinceIB[i]
        f[27] = self.sinceCB[i] if s == 1 else self.sinceCS[i]; f[28] = self.sinceCS[i] if s == 1 else self.sinceCB[i]
        f[29] = f[5] if s == 1 else f[4]; f[30] = f[4] if s == 1 else f[5]
        f[31] = np.nan if np.isnan(pd_) else (pd_ if s == 1 else 1 - pd_)
        f[32] = self.fvgB24[i] if s == 1 else self.fvgS24[i]; f[33] = self.fvgS24[i] if s == 1 else self.fvgB24[i]
        f[34] = self.swB24[i] if s == 1 else self.swS24[i]
        f[35] = (self.LL5[i] - self.EC[i]) / a if s == 1 else -(self.HH5[i] - self.EC[i]) / a
        f[36] = s; f[37] = prevR
        return f

    def on_features(self, i, eur):
        M = self.M; C, H, L = M.c, M.h, M.l; a = self.ATR[i]; c = C[i]; day = self.nyc_day[i]
        k = i; dHi = -np.inf; dLo = np.inf
        while k >= 0 and self.nyc_day[k] == day: dHi = max(dHi, H[k]); dLo = min(dLo, L[k]); k -= 1
        if k < 0: return None
        pday = self.nyc_day[k]; pHi = -np.inf; pLo = np.inf
        while k >= 0 and self.nyc_day[k] == pday: pHi = max(pHi, H[k]); pLo = min(pLo, L[k]); k -= 1
        x = np.empty(18)
        for j, lag in enumerate((1, 4, 8, 24, 120, 480)): x[j] = (c - C[i - lag]) / a
        x[6] = (dHi - dLo) / a; x[7] = (c - dLo) / max(dHi - dLo, 1e-9); x[8] = (c - pHi) / a; x[9] = (c - pLo) / a
        x[10] = self.RSI[i]; x[11] = (c - self.e50[i]) / a; x[12] = (c - self.e200[i]) / a; x[13] = a / c * 10000
        x[14] = self.VR[i]; x[15] = self.nyc_dow[i]; x[16] = self.nyc_mon[i]; x[17] = eur
        return x


def eur_returns(E, eur_df):
    """EA EURRet: EUR close of the bar opening at the same UTC hour as gold bar i, vs the bar 7 hours earlier"""
    if eur_df is None: return np.zeros(E.n), 0.0
    ec = eur_df.c; out = np.zeros(E.n)
    t16 = E.TU; t9 = E.TU - pd.Timedelta(hours=7)
    c16 = ec.reindex(t16).values; c9 = ec.reindex(t9).values
    ok = np.isfinite(c16) & np.isfinite(c9) & (c9 > 0)
    out[ok] = (c16[ok] / c9[ok] - 1) * 1e4
    return out, float(ok.mean())


# ------------------------------------------------------------------ strategy simulations
def sim_sonic(E, inst="XAUUSD", ai_mult=None):
    """EA Sonic rules. Returns trades with features (prevR uses cost-A R of the previous trade)."""
    M = E.M; O, H, L, C = M.o, M.h, M.l, M.c; n = E.n; rows = []; pos = None; prevR = 0.0
    i = 600
    while i < n - 1:
        exited = False
        if pos is not None:
            # stop inside bar i (bars from entry bar onward)
            s, ep, stp, jb = pos["side"], pos["ep"], pos["stop"], pos["jb"]
            hit = (s == 1 and L[i] <= stp) or (s == -1 and H[i] >= stp)
            if hit:
                xp = min(stp, O[i]) if s == 1 else max(stp, O[i]); jx = i
            else:
                trail = C[i] < E.EL[i] if s == 1 else C[i] > E.EH[i]
                age = i - (jb - 1)
                if trail or age >= 240: xp = O[i + 1]; jx = i + 1
                else: xp = None
            if xp is not None:
                pos.update(xp=xp, jx=jx); rows.append(pos)
                nr = nroll_of(M, [pos["jb"]], [jx])[0]
                net = s * (xp / ep - 1) - cost_frac("A", s, ep, xp, nr, inst)
                prevR = net * ep / pos["dist"]; pos = None; exited = (jx == i + 1)
                if jx == i: exited = False
        if pos is None and not exited and i >= 600:
            sig = E.sonic_signal(i)
            if sig != 0:
                px = O[i + 1]
                stp = min(E.LL10[i], C[i] - 0.5 * E.ATR[i]) if sig == 1 else max(E.HH10[i], C[i] + 0.5 * E.ATR[i])
                dist = abs(px - stp)
                if dist > 0 and not ((sig == 1 and stp >= px) or (sig == -1 and stp <= px)):
                    pos = dict(side=sig, ep=px, stop=stp, dist=dist, jb=i + 1, js=i, feats=E.sonic_features(i, sig, prevR), prevR=prevR)
                    # stop can also be hit inside the entry bar i+1: handled when the loop reaches i+1
        i += 1
    T = pd.DataFrame(rows)
    T["t0"] = M.idx[T.jb.values]; T["tx"] = M.idx[np.minimum(T.jx.values, n - 1)]
    T["nroll"] = nroll_of(M, T.jb.values, T.jx.values)
    return T


def sim_overnight(E, eur, sonic=None):
    """EA Overnight: bar closing 16:00 NY (Mon-Thu) -> buy open of next bar; exit at open of the bar after the bar
    closing 20:00 NY. Skipped if a Sonic short is open at entry; closed early at a Sonic short entry."""
    M = E.M; O = M.o; n = E.n; rows = []
    short_iv = []
    if sonic is not None and len(sonic):
        S = sonic[sonic.side == -1]; short_iv = list(zip(S.jb.values, S.jx.values))
    sh_start = np.array([a for a, b in short_iv]) if short_iv else np.array([], int)
    sh_end = np.array([b for a, b in short_iv]) if short_iv else np.array([], int)
    idx16 = np.flatnonzero((E.nyc_hour == 16) & (E.nyc_dow <= 3))
    for i in idx16:
        if i < 2401 or i + 1 >= n: continue
        jb = i + 1
        if len(sh_start) and np.any((sh_start <= jb) & (sh_end > jb)): continue
        x = E.on_features(i, eur[i])
        if x is None: continue
        k = i + 1; jx = None
        while k < n and k <= i + 30:
            if E.nyc_hour[k] == 20: jx = k + 1; break
            k += 1
        if jx is None or jx >= n: continue
        if len(sh_start):
            early = sh_start[(sh_start > jb) & (sh_start < jx)]
            if len(early): jx = int(early.min())
        rows.append(dict(side=1, ep=O[jb], xp=O[jx], jb=jb, jx=jx, js=i, feats=x))
    T = pd.DataFrame(rows)
    T["t0"] = M.idx[T.jb.values]; T["tx"] = M.idx[T.jx.values]; T["nroll"] = nroll_of(M, T.jb.values, T.jx.values)
    return T


def sim_williams(M):
    import features149 as F
    T = F.williams(M).rename(columns={"j0": "jb"})
    T["t0"] = M.idx[T.jb.values]; T["tx"] = M.idx[T.jx.values]; T["nroll"] = 0.0
    return T


def net_returns(T, scn, inst="XAUUSD"):
    return T.side.values * (T.xp.values / T.ep.values - 1) - cost_frac(scn, T.side.values, T.ep.values, T.xp.values, T.nroll.values, inst)
