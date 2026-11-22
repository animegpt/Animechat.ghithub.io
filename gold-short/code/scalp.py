"""#78-#81 SHORT scalping on 1-minute bars (prereg/PREREGISTRATION_78_81_scalp.md).
usage: BARS=1m GDATA=<dir containing raw/> python scalp.py disc|conf|vault [variant ...]"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("BARS", "1m")
from numba import njit
from scipy import stats
import shortlib as sl

DISC = (pd.Timestamp("2017-01-01", tz="UTC"), pd.Timestamp("2021-01-01", tz="UTC"))
CONF = (pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC"))
VAULT = (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2026-11-01", tz="UTC"))
SLIP = 0.1e-4
SCEN = {"A": (0.24, 0.0), "B": (0.03, 0.07), "C": (0.06, 0.14)}   # spread USD, commission USD/oz round trip
NEWS = ((745, 760), (805, 820), (835, 850), (895, 910), (1075, 1090), (1135, 1150))


class Data:
    def __init__(self):
        df = sl.load_minutes()
        df = df[df.index >= DISC[0]]
        self.idx = df.index; self.o, self.h, self.l, self.c = (df[k].values.astype(np.float64) for k in "ohlc")
        self.n = len(self.c)
        tm = self.idx.hour * 60 + self.idx.minute; self.tm = tm.values
        self.dow = self.idx.dayofweek.values
        news = np.zeros(self.n, bool)
        for a, b in NEWS: news |= (tm >= a) & (tm < b)
        self.news = news
        self.noentry = news | ((tm >= 1245) & (tm <= 1395)) | ((self.dow == 4) & (tm >= 1170))
        # session key: session starts 23:00 UTC
        self.sess = (self.idx + pd.Timedelta(hours=1)).normalize().values.astype("datetime64[D]").astype(np.int64)
        lc = np.log(self.c); r = np.r_[0.0, np.diff(lc)]
        self.sig1 = pd.Series(r).rolling(1440).std().values
        pc = np.r_[self.c[0], self.c[:-1]]
        tr = np.maximum(self.h - self.l, np.maximum(abs(self.h - pc), abs(self.l - pc)))
        self.atr = pd.Series(tr).ewm(alpha=1 / 60, adjust=False).mean().values
        self.tns = self.idx.values.astype("datetime64[ns]").astype(np.int64)   # explicit ns (parquet index is us)
        # force-close index: last minute <= 20:44 UTC of the same UTC date
        d = self.idx.normalize().values.astype("datetime64[ns]").astype(np.int64) + (20 * 60 + 44) * 60 * 10 ** 9
        d = d + np.where(self.tm >= 1245, 86400 * 10 ** 9, 0)        # entries after 20:45 UTC -> next day 20:44
        self.fc = np.searchsorted(self.tns, d, side="right") - 1


@njit(cache=True)
def _sim(o, h, l, c, sig, stop, tgtR, rel_stop, rel_tgt, tns, Hns, fc):
    """sig = signal minute; entry = open of sig+1. If rel_stop>0: stop = e*(1+rel_stop), target = e*(1-rel_tgt).
    else stop absolute, target = e - tgtR*(stop-e). Returns entry idx, exit idx, entry px, exit px, valid, outcome."""
    n = len(sig); out = np.zeros((n, 6)); N = len(c)
    for k in range(n):
        i = sig[k] + 1
        if i >= N: continue
        e = o[i]
        if rel_stop[k] > 0:
            s = e * (1 + rel_stop[k]); tg = e * (1 - rel_tgt[k])
        else:
            s = stop[k]
            if s <= e: out[k, 4] = 0; continue
            tg = e - tgtR[k] * (s - e)
        # time limit
        lim = tns[sig[k]] + Hns
        x = i
        while x + 1 < N and tns[x + 1] <= lim: x += 1
        if fc[i] < x: x = fc[i]
        if x < i: x = i
        px = c[x]; xi = x; outc = 0.0
        for j in range(i, x + 1):
            if j > i and o[j] >= s: px = o[j]; xi = j; outc = -1.0; break
            if h[j] >= s: px = s; xi = j; outc = -1.0; break
            if l[j] <= tg: px = tg; xi = j; outc = 1.0; break
        out[k, 0] = i; out[k, 1] = xi; out[k, 2] = e; out[k, 3] = px; out[k, 4] = 1; out[k, 5] = outc
    return out


def costs(D, e, px, xi, scen, fixedP=None):
    s, com = SCEN[scen]; Pe = e if fixedP is None else fixedP; Px = px if fixedP is None else fixedP
    mx = np.where(D.news[xi], 3.0, 1.0)
    return 0.5 * s / Pe + 0.5 * s * mx / Px + com / ((Pe + Px) / 2) + 2 * SLIP


def run(D, cand, H, rearm=None):
    """cand: DataFrame with sig, stop, tgtR, rel_stop, rel_tgt (+ meta). Sequential, one position at a time."""
    if len(cand) == 0: return pd.DataFrame()
    cand = cand[~D.noentry[np.minimum(cand.sig.values + 1, D.n - 1)]].sort_values("sig").reset_index(drop=True)
    r = _sim(D.o, D.h, D.l, D.c, cand.sig.values.astype(np.int64), cand.stop.values.astype(float), cand.tgtR.values.astype(float),
             cand.rel_stop.values.astype(float), cand.rel_tgt.values.astype(float), D.tns, np.int64(H * 60 * 10 ** 9), D.fc)
    keep = []; busy = -1; last_sig = -10 ** 9
    for k in range(len(cand)):
        if r[k, 4] == 0: continue
        if r[k, 0] <= busy: continue
        if rearm is not None and not rearm(last_sig, int(cand.sig.values[k])): continue
        keep.append(k); busy = r[k, 1]; last_sig = int(cand.sig.values[k])
    t = cand.iloc[keep].copy(); rr = r[keep]
    t["ent"] = rr[:, 0].astype(np.int64); t["xi"] = rr[:, 1].astype(np.int64); t["e"] = rr[:, 2]; t["px"] = rr[:, 3]; t["outc"] = rr[:, 5]
    t["gross"] = (t.e - t.px) / t.e
    for sc in SCEN:
        t[sc] = t.gross - costs(D, t.e.values, t.px.values, t.xi.values, sc)
        t[sc + "4000"] = t.gross - costs(D, t.e.values, t.px.values, t.xi.values, sc, 4000.0)
    t["mins"] = (D.tns[t.xi.values] - D.tns[t.ent.values]) / 6e10 + 1
    t["sess"] = D.sess[t.ent.values]
    t.index = D.idx[t.ent.values]
    return t


def period(t, P): return t[(t.index >= P[0]) & (t.index < P[1])] if len(t) else t


def dayt(t, col):
    d = t.groupby("sess")[col].sum(); n = len(d)
    return float(d.mean() / (d.std(ddof=1) / np.sqrt(n))) if n > 2 and d.std() > 0 else 0.0, n


def summary(t, P):
    if len(t) == 0: return {"n": 0}
    out = {"n": int(len(t)), "win": round(float((t.B > 0).mean()), 3), "mins": round(float(t.mins.mean()), 1)}
    tdays = np.busday_count(P[0].date(), min(P[1], pd.Timestamp("2024-01-01", tz="UTC") if P[1] <= CONF[1] else P[1]).date())
    out["per_day"] = round(len(t) / tdays, 2)
    for col in ["gross", "A", "B", "C", "A4000", "B4000", "C4000"]:
        tt, nd = dayt(t, col)
        out[col] = {"bp": round(float(t[col].mean() * 1e4), 3), "day_t": round(tt, 2)}
    out["days"] = nd; out["p1_B"] = float(stats.t.sf(out["B"]["day_t"], max(nd - 1, 1)))
    return out


# ------------------------------------------------------------------ signals
def C(sig, stop=None, tgtR=1.0, rel_stop=0.0, rel_tgt=0.0, **meta):
    sig = np.asarray(sig, np.int64); n = len(sig)
    df = pd.DataFrame({"sig": sig, "stop": np.full(n, np.nan) if stop is None else stop, "tgtR": np.full(n, tgtR),
                       "rel_stop": np.full(n, rel_stop), "rel_tgt": np.full(n, rel_tgt)})
    for k, v in meta.items(): df[k] = v
    return df


def exh(D, Z=3.0, look=30, tgtR=1.0, H=60):
    lc = np.log(D.c); sh = np.r_[np.full(look, np.nan), lc[:-look]]
    dt = np.r_[np.full(look, np.inf), (D.tns[look:] - D.tns[:-look]) / 6e10]
    z = np.where(dt <= look + 10, (lc - sh) / (D.sig1 * np.sqrt(look)), np.nan)
    zmax = pd.Series(z).rolling(10, min_periods=1).max().values
    low3 = pd.Series(D.l).shift(1).rolling(3).min().values
    sig = np.flatnonzero((zmax >= Z) & (D.c < low3))
    hh = pd.Series(D.h).rolling(30).max().values
    lowz = np.where(np.nan_to_num(z, nan=9) < 1, np.arange(D.n), -1); lastlow = np.maximum.accumulate(lowz)
    rearm = lambda last, s: lastlow[s] > last
    return C(sig, stop=hh[sig] + 0.1 * D.atr[sig], tgtR=tgtR), H, rearm


@njit(cache=True)
def _failhi(h, l, c, sess, tm, mode, win, minage):
    n = len(c); sig = np.zeros(n, np.int64); brk = np.zeros(n, np.int64); k = 0
    cur = -1; shigh = -1.0; age = 0; prevfull = -1.0; today_full = -1.0
    level = -1.0; lastbreak = -10 ** 9; used = False; peak = -1.0
    for i in range(n):
        if sess[i] != cur:
            prevfull = today_full; today_full = -1.0; cur = sess[i]; shigh = -1.0; age = 0
            level = -1.0; lastbreak = -10 ** 9; used = False
        age += 1
        if mode == 0:
            if shigh > 0 and age > minage and h[i] > shigh:
                level = shigh; lastbreak = i; used = False; peak = h[i]
        else:
            if prevfull > 0 and not used and h[i] > prevfull:
                level = prevfull; lastbreak = i; peak = max(peak, h[i]) if lastbreak == i else h[i]
        if lastbreak >= 0 and i - lastbreak <= win and not used and level > 0:
            if h[i] > peak: peak = h[i]
            if c[i] < level:
                sig[k] = i; brk[k] = lastbreak; k += 1; used = True
        if tm[i] < 1245 or tm[i] >= 1380:          # session high excludes roll minutes
            shigh = max(shigh, h[i]) if shigh > 0 else h[i]
        if tm[i] < 1245 or tm[i] >= 1380:
            today_full = max(today_full, h[i]) if today_full > 0 else h[i]
    return sig[:k], brk[:k]


def failhi(D, mode="SESS", tgtR=1.0, H=60, win=15):
    sig, brk = _failhi(D.h, D.l, D.c, D.sess, D.tm, 0 if mode == "SESS" else 1, win, 120)
    stop = np.array([D.h[b:s + 1].max() for b, s in zip(brk, sig)]) + 0.1 * D.atr[sig]
    return C(sig, stop=stop, tgtR=tgtR), H, None


@njit(cache=True)
def _dc(c, theta):
    n = len(c); sig = np.zeros(n, np.int64); k = 0
    mode = -1; ext = c[0]; pdc = 0.0; trig = True
    for i in range(1, n):
        if mode == -1:
            if c[i] < ext: ext = c[i]
            if c[i] >= ext * (1 + theta):
                mode = 1; pdc = c[i]; ext = c[i]; trig = False
        else:
            if c[i] > ext: ext = c[i]
            if not trig and c[i] >= pdc * (1 + 2 * theta):
                sig[k] = i; k += 1; trig = True
            if c[i] <= ext * (1 - theta):
                mode = -1; ext = c[i]
    return sig[:k]


def dcos(D, theta=0.001, H=120, tgt=None):
    sig = _dc(D.c, theta)
    return C(sig, rel_stop=theta, rel_tgt=theta if tgt is None else tgt * theta), H, None


def trendpb(D, tgtR=1.0, H=90, f=8, s=20, nb=6):
    m = pd.DataFrame({"o": D.o, "h": D.h, "l": D.l, "c": D.c}, index=D.idx)
    pos = pd.Series(np.arange(D.n), index=D.idx)
    b5 = m.resample("5min", label="left", closed="left").agg({"h": "max", "c": "last"}).dropna()
    last5 = pos.resample("5min", label="left", closed="left").last().reindex(b5.index).values.astype(np.int64)
    e8 = b5.c.ewm(span=f, adjust=False).mean().values; e20 = b5.c.ewm(span=s, adjust=False).mean().values
    cross = (e8 < e20) & (np.r_[np.nan, e8[:-1]] >= np.r_[np.nan, e20[:-1]]) & (b5.c.values < e20)
    hh6 = b5.h.rolling(nb).max().values
    H1 = m.resample("1h", label="left", closed="left").agg({"h": "max", "l": "min", "c": "last"}).dropna()
    ema = lambda x, sp: pd.Series(x).ewm(span=sp, adjust=False).mean().values
    eh, el, e89 = ema(H1.h.values, 34), ema(H1.l.values, 34), ema(H1.c.values, 89); mid = (eh + el) / 2
    sh5 = lambda x: np.r_[np.full(5, np.nan), x[:-5]]
    up = (mid > e89) & (mid > sh5(mid)) & (e89 > sh5(e89))
    h1close = (H1.index + pd.Timedelta(hours=1)).values.astype(np.int64)
    t5close = (b5.index + pd.Timedelta(minutes=5)).values.astype(np.int64)
    p = np.searchsorted(h1close, t5close, side="right") - 1
    okh = np.where(p >= 0, up[np.clip(p, 0, None)], False)
    k = np.flatnonzero(cross & okh)
    sig = last5[k]
    return C(sig, stop=hh6[k], tgtR=tgtR), H, None


VARIANTS = {
    "EXH_Z3": (exh, dict(Z=3.0)), "EXH_Z4": (exh, dict(Z=4.0)),
    "FAILHI_SESS": (failhi, dict(mode="SESS")), "FAILHI_PREVDAY": (failhi, dict(mode="PREV")),
    "DCOS_010": (dcos, dict(theta=0.001)), "DCOS_020": (dcos, dict(theta=0.002)),
    "TRENDPB_1R": (trendpb, dict(tgtR=1.0)), "TRENDPB_2R": (trendpb, dict(tgtR=2.0)),
}


def random_base(D, t, H, nsim=500, seed=9):
    """same year, same minute-of-day, same stop/target geometry in ATRm units, same H, short"""
    if len(t) < 5: return {}
    rng = np.random.default_rng(seed)
    yrs = D.idx.year.values
    elig = ~D.noentry
    key = {}
    sigs = np.flatnonzero(elig[1:]) # signal minute s where entry s+1 eligible
    kk = yrs[sigs] * 10000 + D.tm[sigs + 1]
    order = np.argsort(kk, kind="stable"); ks = kk[order]
    tk = D.idx.year.values[t.ent.values] * 10000 + D.tm[t.ent.values]
    lo = np.searchsorted(ks, tk, "left"); hi = np.searchsorted(ks, tk, "right")
    rel = t.rel_stop.values > 0
    sd_atr = np.where(rel, 0, (t.stop.values - t.e.values) / D.atr[t.sig.values])
    allsig = []; stops = []; tg = []; rs = []; rt = []
    for s in range(nsim):
        pick = sigs[order[(lo + (rng.random(len(t)) * np.maximum(hi - lo, 1)).astype(np.int64)).clip(0, len(ks) - 1)]]
        allsig.append(pick)
        stops.append(np.where(rel, np.nan, D.o[np.minimum(pick + 1, D.n - 1)] + sd_atr * D.atr[pick]))
        tg.append(t.tgtR.values); rs.append(t.rel_stop.values); rt.append(t.rel_tgt.values)
    sig = np.concatenate(allsig)
    r = _sim(D.o, D.h, D.l, D.c, sig, np.concatenate(stops), np.concatenate(tg), np.concatenate(rs), np.concatenate(rt),
             D.tns, np.int64(H * 60 * 10 ** 9), D.fc)
    e = r[:, 2]; px = r[:, 3]; ok = r[:, 4] > 0
    g = np.where(ok, (e - px) / np.where(e > 0, e, 1), np.nan)
    net = g - costs(D, np.where(ok, e, 1), np.where(ok, px, 1), r[:, 1].astype(np.int64), "B")
    means = np.nanmean(net.reshape(nsim, -1), 1)
    return {"rand_B_bp": round(float(np.mean(means)) * 1e4, 3), "p_rand": float((np.sum(means >= t.B.mean()) + 1) / (nsim + 1))}


def evaluate(D, name, kw=None, P=DISC, nsim=500):
    fn, kw0 = VARIANTS[name]; kw = kw0 if kw is None else kw
    cand, H, rearm = fn(D, **kw)
    t = period(run(D, cand, H, rearm), P)
    s = summary(t, P)
    if nsim and len(t) >= 5: s.update(random_base(D, t, H, nsim))
    return s, t


if __name__ == "__main__":
    which = sys.argv[1]; P = {"disc": DISC, "conf": CONF, "vault": VAULT}[which]
    if which == "vault": assert sl.OPEN_VAULT
    D = Data(); print("minutes", D.n, D.idx.min(), D.idx.max(), flush=True)
    names = sys.argv[2:] or list(VARIANTS); res = {}
    for nm in names:
        s, t = evaluate(D, nm, P=P); res[nm] = s
        print(f"{which} {nm:15s} n={s['n']:6d} /day={s.get('per_day')} win={s.get('win')} mins={s.get('mins')} "
              f"gross={s['gross']['bp']:6.2f} A={s['A']['bp']:6.2f}({s['A']['day_t']}) B={s['B']['bp']:6.2f}({s['B']['day_t']}) "
              f"C={s['C']['bp']:6.2f}({s['C']['day_t']}) B4000={s['B4000']['bp']:6.2f} rand_B={s.get('rand_B_bp')} p_rand={s.get('p_rand')}", flush=True)
    if len(names) == len(VARIANTS):
        adj = sl.holm([res[k]["p1_B"] for k in names])
        for k, a in zip(names, adj): res[k]["holm_B"] = float(a)
        print({k: round(res[k]["holm_B"], 4) for k in names})
    json.dump(res, open(f"{sl.HERE}/results_78_81_{which}.json", "w"), indent=1, default=float)
