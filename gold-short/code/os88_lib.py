"""#88 open M1 search: data, condition library, per-minute trade outcomes (prereg/PREREGISTRATION_88_open_search.md)."""
import os, numpy as np, pandas as pd
os.environ.setdefault("BARS", "1m")
from numba import njit
import shortlib as sl

SLIP = 0.1e-4
NEWS = ((745, 760), (805, 820), (835, 850), (895, 910), (1075, 1090), (1135, 1150))
EXITS = {"E1": (1.0, 60, 0), "E2": (2.0, 120, 0), "E3": (3.0, 240, 0), "E4": (0.0, 240, 1), "E5": (0.0, 30, 0), "E6": (0.0, 120, 0)}
CACHE = os.environ.get("OS88_CACHE", sl.GDATA + "/os88")


# ------------------------------------------------------------------ helpers
def ema(x, n): return pd.Series(x).ewm(span=n, adjust=False).mean().values
def sma(x, n): return pd.Series(x).rolling(n, min_periods=n).mean().values
def wma(x, n):
    w = np.arange(1, n + 1, dtype=float); return pd.Series(x).rolling(n).apply(lambda a: np.dot(a, w) / w.sum(), raw=True).values
def hma(x, n):
    h = int(n / 2); s = int(np.sqrt(n))
    return wma_fast(2 * wma_fast(x, h) - wma_fast(x, n), s)
def wma_fast(x, n):
    x = np.nan_to_num(np.asarray(x, float)); w = np.arange(1, n + 1, dtype=float)
    out = np.convolve(x, w[::-1], mode="full")[:len(x)] / w.sum(); out[:n - 1] = np.nan; return out
def rmax(x, n): return pd.Series(x).rolling(n, min_periods=n).max().values
def rmin(x, n): return pd.Series(x).rolling(n, min_periods=n).min().values
def shift(x, k=1):
    out = np.empty_like(x, dtype=float); out[:k] = np.nan; out[k:] = x[:-k]; return out


@njit(cache=True)
def kama(c, n, fast, slow):
    out = np.full(len(c), np.nan); fsc = 2.0 / (fast + 1); ssc = 2.0 / (slow + 1)
    if len(c) <= n: return out
    out[n] = c[n]
    for i in range(n + 1, len(c)):
        ch = abs(c[i] - c[i - n]); vol = 0.0
        for j in range(i - n + 1, i + 1): vol += abs(c[j] - c[j - 1])
        er = ch / vol if vol > 0 else 0.0
        sc = (er * (fsc - ssc) + ssc) ** 2
        out[i] = out[i - 1] + sc * (c[i] - out[i - 1])
    return out


@njit(cache=True)
def supertrend(h, l, c, atr, mult):
    n = len(c); d = np.ones(n); ub = np.zeros(n); lb = np.zeros(n)
    for i in range(n):
        m = (h[i] + l[i]) / 2; u = m + mult * atr[i]; b = m - mult * atr[i]
        if i == 0: ub[i] = u; lb[i] = b; continue
        ub[i] = u if (u < ub[i - 1] or c[i - 1] > ub[i - 1]) else ub[i - 1]
        lb[i] = b if (b > lb[i - 1] or c[i - 1] < lb[i - 1]) else lb[i - 1]
        if d[i - 1] == 1 and c[i] < lb[i]: d[i] = -1
        elif d[i - 1] == -1 and c[i] > ub[i]: d[i] = 1
        else: d[i] = d[i - 1]
    return d


@njit(cache=True)
def dcstate(c, th):
    n = len(c); mode = np.zeros(n); osh = np.zeros(n); m = 0; hi = c[0]; lo = c[0]; px = c[0]
    for i in range(1, n):
        p = c[i]
        if m == 0:
            if p > hi: hi = p
            if p < lo: lo = p
            if p <= hi * (1 - th): m = -1; lo = p; px = p
            elif p >= lo * (1 + th): m = 1; hi = p; px = p
        elif m == 1:
            if p > hi: hi = p
            elif p <= hi * (1 - th): m = -1; lo = p; px = p
        else:
            if p < lo: lo = p
            elif p >= lo * (1 + th): m = 1; hi = p; px = p
        mode[i] = m; osh[i] = (p / px - 1) / th if px > 0 else 0.0
    return mode, osh


@njit(cache=True)
def ha_runs(o, h, l, c):
    n = len(c); hao = np.empty(n); hac = (o + h + l + c) / 4; run = np.zeros(n)
    hao[0] = (o[0] + c[0]) / 2
    for i in range(1, n): hao[i] = (hao[i - 1] + hac[i - 1]) / 2
    for i in range(n):
        s = 1.0 if hac[i] > hao[i] else -1.0
        run[i] = s if i == 0 or np.sign(run[i - 1]) != s else run[i - 1] + s
    return run


@njit(cache=True)
def anchored(tp, v, anchor):
    out = np.empty(len(tp)); s1 = 0.0; s2 = 0.0
    for i in range(len(tp)):
        if anchor[i]: s1 = 0.0; s2 = 0.0
        s1 += tp[i] * v[i]; s2 += v[i]; out[i] = s1 / s2 if s2 > 0 else tp[i]
    return out


@njit(cache=True)
def running_extreme(h, l, newp):
    """running high/low of the current period BEFORE bar i, and the full previous period's high/low"""
    n = len(h); rh = np.full(n, np.nan); rl = np.full(n, np.nan); ph = np.full(n, np.nan); pl = np.full(n, np.nan)
    ch = -1e18; cl = 1e18; lh = np.nan; ll = np.nan
    for i in range(n):
        if newp[i]:
            if ch > -1e17: lh = ch; ll = cl
            ch = -1e18; cl = 1e18
        rh[i] = ch if ch > -1e17 else np.nan; rl[i] = cl if cl < 1e17 else np.nan; ph[i] = lh; pl[i] = ll
        if h[i] > ch: ch = h[i]
        if l[i] < cl: cl = l[i]
    return rh, rl, ph, pl


# ------------------------------------------------------------------ data
class Data:
    def __init__(self):
        df = sl.load_minutes(); df = df[df.index >= pd.Timestamp("2017-01-01", tz="UTC")]
        self.idx = df.index; self.o, self.h, self.l, self.c, self.v = (df[k].values.astype(np.float64) for k in "ohlcv")
        self.n = len(self.c)
        utc = self.idx; self.tm = (utc.hour * 60 + utc.minute).values; self.dow = utc.dayofweek.values
        news = np.zeros(self.n, bool)
        for a, b in NEWS: news |= (self.tm >= a) & (self.tm < b)
        self.news = news
        self.noentry = news | ((self.tm >= 1245) & (self.tm <= 1395)) | ((self.dow == 4) & (self.tm >= 1170))
        ny = utc.tz_convert("America/New_York").tz_localize(None); self.ny = ny
        self.nym = (ny.hour * 60 + ny.minute).values; self.nydow = ny.dayofweek.values
        tday = (ny + pd.Timedelta(hours=6)).normalize()
        self.days, self.dayid = np.unique(tday.values, return_inverse=True); self.dayid = self.dayid.astype(np.int64)
        self.daydate = pd.DatetimeIndex(self.days)
        self.newday = np.r_[True, self.dayid[1:] != self.dayid[:-1]]
        wk = np.asarray((ny + pd.Timedelta(hours=6)).to_period("W-SUN").asi8); self.newweek = np.r_[True, wk[1:] != wk[:-1]]
        pc = np.r_[self.c[0], self.c[:-1]]
        tr = np.maximum(self.h - self.l, np.maximum(abs(self.h - pc), abs(self.l - pc)))
        self.tr = tr; self.atr = pd.Series(tr).ewm(alpha=1 / 60, adjust=False).mean().values
        tns = self.idx.values.astype("datetime64[ns]").astype(np.int64); self.tns = tns
        d = self.idx.normalize().values.astype("datetime64[ns]").astype(np.int64) + (20 * 60 + 44) * 60 * 10 ** 9
        d = d + np.where(self.tm >= 1245, 86400 * 10 ** 9, 0)
        self.fc = (np.searchsorted(tns, d, side="right") - 1).astype(np.int64)
        self.disc_end = int(np.searchsorted(tns, pd.Timestamp("2021-01-01", tz="UTC").value))
        self.conf_end = int(np.searchsorted(tns, pd.Timestamp("2024-01-01", tz="UTC").value))


# ------------------------------------------------------------------ outcomes
@njit(cache=True)
def _outcomes(o, h, l, c, atr, tns, fc, news, noentry, side, tgtR, Hmin, trail, wide):
    """trade for a signal at every minute t (entry open t+1). Returns gross, costA, costB, exit idx, valid."""
    n = len(c); g = np.zeros(n, np.float32); cA = np.zeros(n, np.float32); cB = np.zeros(n, np.float32)
    xi = np.zeros(n, np.int32); ok = np.zeros(n, np.bool_)
    for t in range(n - 1):
        i = t + 1
        if noentry[i] or fc[i] <= i: continue
        e = o[i]
        minD = 3.0 * (0.10 + 2 * 0.1e-4 * e)
        if wide > 0: s = e - side * wide * atr[t]
        else: s = (l[t] - 0.1 * atr[t]) if side == 1 else (h[t] + 0.1 * atr[t])
        if side * (e - s) < minD: s = e - side * minD
        if side * (e - s) <= 0: continue
        R = side * (e - s); tg = e + side * tgtR * R if tgtR > 0 else 0.0
        lim = tns[t] + Hmin * 60 * 1000000000
        x = i
        while x + 1 < n and tns[x + 1] <= lim: x += 1
        if fc[i] < x: x = fc[i]
        px = c[x]; xx = x; best = c[i] if trail else 0.0
        for j in range(i, x + 1):
            if side == 1:
                if j > i and o[j] <= s: px = o[j]; xx = j; break
                if l[j] <= s: px = s; xx = j; break
                if tgtR > 0 and h[j] >= tg: px = tg; xx = j; break
            else:
                if j > i and o[j] >= s: px = o[j]; xx = j; break
                if h[j] >= s: px = s; xx = j; break
                if tgtR > 0 and l[j] <= tg: px = tg; xx = j; break
            if trail:
                if side == 1:
                    if c[j] > best: best = c[j]
                    if c[j] < best - 2 * atr[j]: px = c[j]; xx = j; break
                else:
                    if c[j] < best or best == 0.0: best = c[j]
                    if c[j] > best + 2 * atr[j]: px = c[j]; xx = j; break
        gr = side * (px - e) / e
        mx = 3.0 if news[xx] else 1.0
        g[t] = gr; xi[t] = xx; ok[t] = True
        cA[t] = 0.12 / e + 0.12 * mx / px + 2 * 0.1e-4
        cB[t] = 0.015 / e + 0.015 * mx / px + 0.035 / e + 0.035 / px + 2 * 0.1e-4
    return g, cA, cB, xi, ok


def outcomes(D, wide=0.0):
    out = {}
    for side in (1, -1):
        for nm, (tg, H, tr) in EXITS.items():
            g, cA, cB, xi, ok = _outcomes(D.o, D.h, D.l, D.c, D.atr, D.tns, D.fc, D.news, D.noentry, side, tg, H, tr, wide)
            out[(side, nm)] = dict(g=g, A=g - cA, B=g - cB, C=g - 2 * cB, xi=xi, ok=ok)
    return out


# ------------------------------------------------------------------ condition library
def conditions(D):
    o, h, l, c, v, atr = D.o, D.h, D.l, D.c, D.v, D.atr
    L = {}; S = {}
    def add(name, lo, sh=None):
        L[name] = np.nan_to_num(lo).astype(bool) if lo.dtype != bool else lo
        S[name] = (L[name] if sh is None else (np.nan_to_num(sh).astype(bool) if sh.dtype != bool else sh))
    with np.errstate(invalid="ignore"):
        for n in (9, 21, 50, 100, 200, 500):
            e = ema(c, n); add(f"c>ema{n}", c > e, c < e)
            sl_ = e - shift(e, 5); add(f"ema{n}_up", sl_ > 0, sl_ < 0)
        for f, s_ in ((9, 21), (21, 50), (50, 200), (20, 100)):
            ef, es = ema(c, f), ema(c, s_); add(f"ema{f}>{s_}", ef > es, ef < es)
            add(f"ema{f}x{s_}", (ef > es) & (shift(ef) <= shift(es)), (ef < es) & (shift(ef) >= shift(es)))
        for n in (50, 200):
            s_ = sma(c, n); add(f"c>sma{n}", c > s_, c < s_)
        for n in (21, 55):
            hm = hma(c, n); add(f"hma{n}_up", hm > shift(hm), hm < shift(hm)); add(f"c>hma{n}", c > hm, c < hm)
        for n in (10, 30):
            k = kama(c, n, 2, 30); add(f"c>kama{n}", c > k, c < k); add(f"kama{n}_up", k > shift(k, 3), k < shift(k, 3))
        tp = (h + l + c) / 3
        sv = anchored(tp, v, D.newday); wv = anchored(tp, v, D.newweek)
        add("c>sessvwap", c > sv, c < sv); add("c>weekvwap", c > wv, c < wv)
        add("sessvwap_x", (c > sv) & (shift(c) <= shift(sv)), (c < sv) & (shift(c) >= shift(sv)))
        for n in (15, 30, 60, 120, 240):
            hh, ll = shift(rmax(h, n)), shift(rmin(l, n))
            add(f"donch{n}_brk", c > hh, c < ll)
        for n in (20, 60):
            m_, sd = sma(c, n), pd.Series(c).rolling(n).std().values
            add(f"bb{n}_brk", c > m_ + 2 * sd, c < m_ - 2 * sd)
            add(f"bb{n}_dip", c < m_ - 2 * sd, c > m_ + 2 * sd)                 # mean-reversion version
            add(f"c>bbmid{n}", c > m_, c < m_)
        for n in (20, 60):
            m_ = ema(c, n); add(f"kelt{n}_brk", c > m_ + 2 * atr, c < m_ - 2 * atr)
        a1440 = pd.Series(D.tr).ewm(alpha=1 / 1440, adjust=False).mean().values
        add("vol_expand", atr / a1440 > 1.5); add("vol_quiet", atr / a1440 < 0.7)
        d = np.diff(c, prepend=c[0])
        for n in (7, 14, 50):
            up = pd.Series(np.maximum(d, 0)).ewm(alpha=1 / n, adjust=False).mean().values
            dn = pd.Series(np.maximum(-d, 0)).ewm(alpha=1 / n, adjust=False).mean().values
            rsi = 100 - 100 / (1 + up / np.where(dn > 0, dn, np.nan))
            add(f"rsi{n}>70", rsi > 70, rsi < 30); add(f"rsi{n}>50", rsi > 50, rsi < 50); add(f"rsi{n}<30", rsi < 30, rsi > 70)
        for f, s_, g_ in ((12, 26, 9), (60, 130, 45)):
            mac = ema(c, f) - ema(c, s_); sig = ema(mac, g_); hist = mac - sig
            add(f"macd{f}_pos", hist > 0, hist < 0); add(f"macd{f}_x", (hist > 0) & (shift(hist) <= 0), (hist < 0) & (shift(hist) >= 0))
        for n in (14, 60):
            k = (c - rmin(l, n)) / np.where(rmax(h, n) > rmin(l, n), rmax(h, n) - rmin(l, n), np.nan) * 100
            add(f"stoch{n}>80", k > 80, k < 20); add(f"stoch{n}<20", k < 20, k > 80)
        upm = np.r_[0, np.diff(h)]; dnm = np.r_[0, -np.diff(l)]
        pdm = np.where((upm > dnm) & (upm > 0), upm, 0.0); ndm = np.where((dnm > upm) & (dnm > 0), dnm, 0.0)
        a14 = pd.Series(D.tr).ewm(alpha=1 / 14, adjust=False).mean().values
        r_ = lambda x: pd.Series(x).ewm(alpha=1 / 14, adjust=False).mean().values
        pdi = 100 * r_(pdm) / a14; ndi = 100 * r_(ndm) / a14
        adx = r_(np.nan_to_num(100 * abs(pdi - ndi) / np.where(pdi + ndi == 0, np.nan, pdi + ndi)))
        add("adx>25", adx > 25); add("di+>di-", pdi > ndi, ndi > pdi)
        for n, m in ((10, 3.0), (20, 2.0)):
            stv = supertrend(h, l, c, pd.Series(D.tr).ewm(alpha=1 / n, adjust=False).mean().values, m)
            add(f"st{n}_up", stv > 0, stv < 0); add(f"st{n}_flip", (stv > 0) & (shift(stv) < 0), (stv < 0) & (shift(stv) > 0))
        ten = (rmax(h, 9) + rmin(l, 9)) / 2; kij = (rmax(h, 26) + rmin(l, 26)) / 2
        sa = shift((ten + kij) / 2, 26); sb = shift((rmax(h, 52) + rmin(l, 52)) / 2, 26)
        add("ichi_above", c > np.fmax(sa, sb), c < np.fmin(sa, sb)); add("ichi_tk", ten > kij, ten < kij)
        run = ha_runs(o, h, l, c)
        for k in (3, 5, 8): add(f"ha{k}", run >= k, run <= -k)
        for th in (0.001, 0.002, 0.005):
            mo, osh = dcstate(c, th)
            add(f"dc{th}_up", mo > 0, mo < 0)
            add(f"dc{th}_os1", (mo > 0) & (osh >= 1), (mo < 0) & (osh <= -1))
            add(f"dc{th}_os2", (mo > 0) & (osh >= 2), (mo < 0) & (osh <= -2))
            add(f"dc{th}_new", (mo > 0) & (shift(mo) <= 0), (mo < 0) & (shift(mo) >= 0))
        vz = v / np.where(sma(v, 60) > 0, sma(v, 60), np.nan)
        add("tickvol>2", vz > 2); add("tickvol<0.5", vz < 0.5)
        nym = D.nym
        add("t_asia", (nym >= 1080) | (nym < 180)); add("t_london", (nym >= 180) & (nym < 480))
        add("t_nyopen", (nym >= 480) & (nym < 660)); add("t_nyafter", (nym >= 660) & (nym < 960))
        rh, rl, ph, pl = running_extreme(h, l, D.newday)
        add("new_dayhigh", c > rh, c < rl); add("near_dayhigh", (rh - c) < 0.5 * atr, (c - rl) < 0.5 * atr)
        add("brk_prevday", (c > ph) & (shift(c) <= shift(ph)), (c < pl) & (shift(c) >= shift(pl)))
        add("above_prevday", c > ph, c < pl)
        wh, wl, pwh, pwl = running_extreme(h, l, D.newweek)
        add("new_weekhigh", c > wh, c < wl); add("above_prevweek", c > pwh, c < pwl)
        for rule, lab in (("1h", "h1"), ("4h", "h4")):
            m = pd.DataFrame({"h": h, "l": l, "c": c}, index=D.idx).resample(rule, label="left", closed="left").agg({"h": "max", "l": "min", "c": "last"}).dropna()
            eh, el, e89 = ema(m.h.values, 34), ema(m.l.values, 34), ema(m.c.values, 89); mid = (eh + el) / 2
            up = (mid > e89) & (mid > shift(mid, 5)) & (e89 > shift(e89, 5)); dn = (mid < e89) & (mid < shift(mid, 5)) & (e89 < shift(e89, 5))
            close_t = (m.index + pd.Timedelta(rule)).values.astype("datetime64[ns]").astype(np.int64)
            p = np.searchsorted(close_t, D.tns + 60 * 10 ** 9, side="right") - 1
            add(f"sonic_{lab}", np.where(p >= 0, up[np.clip(p, 0, None)], False), np.where(p >= 0, dn[np.clip(p, 0, None)], False))
        rng_ = h - l
        add("strong_bar", ((c - o) > 0.6 * rng_) & ((h - c) < 0.2 * rng_), ((o - c) > 0.6 * rng_) & ((c - l) < 0.2 * rng_))
        add("big_bar", rng_ > 2 * atr)
        add("ret15_up", c > shift(c, 15) + atr, c < shift(c, 15) - atr)
        add("ret60_up", c > shift(c, 60) + 2 * atr, c < shift(c, 60) - 2 * atr)
    names = list(L)
    return names, L, S
