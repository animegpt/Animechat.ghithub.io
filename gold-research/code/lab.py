"""Gold Lab core: data (Dukascopy hourly bi5), day structure (17:00 NY), realistic trade engine, costs, stats, placebos.
Vault rows (>= 2024-01-01) are excluded unless OPEN_VAULT=1. See gold-lab/prereg/PREREGISTRATION_LAB_COMMON.md."""
import os, lzma, numpy as np, pandas as pd
from numba import njit
from scipy import stats

RAW = os.environ.get("LABRAW", "/home/user/lab/raw")
CACHE = os.environ.get("LABCACHE", "/home/user/lab/cache")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPEN_VAULT = os.environ.get("OPEN_VAULT") == "1"
VAULT_START = pd.Timestamp("2024-01-01")
DISC = (pd.Timestamp("2004-01-01"), pd.Timestamp("2017-01-01"))
CONF = (pd.Timestamp("2017-01-01"), pd.Timestamp("2024-01-01"))
VAULT = (pd.Timestamp("2024-01-01"), pd.Timestamp("2026-11-01"))
SLIP = 0.1e-4
SPEC = {"XAUUSD": dict(point=1e3, spread=0.24, swap_long=0.4316),
        "XAGUSD": dict(point=1e3, spread=0.025, swap_long=0.0),
        "EURUSD": dict(point=1e5, spread=0.00010, swap_long=0.0),
        "BTCUSD": dict(point=1.0, spread=6.40, swap_long=0.0),
        "USDCNH": dict(point=1e5, spread=0.0, swap_long=0.0), "USA500IDXUSD": dict(point=1e3, spread=0.0, swap_long=0.0),
        "USDJPY": dict(point=1e3, spread=0.0, swap_long=0.0)}   # signal-only inputs (#145)


def _parse(path, t0, point):
    raw = lzma.decompress(open(path, "rb").read())
    a = np.frombuffer(raw, dtype=">i4").reshape(-1, 6).astype(np.int64)
    v = np.frombuffer(raw, dtype=">f4").reshape(-1, 6)[:, 5].astype(np.float64)
    df = pd.DataFrame({"o": a[:, 1], "c": a[:, 2], "l": a[:, 3], "h": a[:, 4]}, index=t0 + pd.to_timedelta(a[:, 0], unit="s")) / point
    df["v"] = v
    return df[df.v > 0]


def load_hourly(inst="XAUUSD", side="BID", vault=None):
    vault = OPEN_VAULT if vault is None else vault
    os.makedirs(CACHE, exist_ok=True)
    dev = f"{CACHE}/{inst}_{side}_dev.parquet"; vlt = f"{CACHE}/{inst}_{side}_vault.parquet"
    if not os.path.exists(dev):
        d = f"{RAW}/{inst}/{side}"; out = []
        for f in sorted(os.listdir(d)):
            if not f.endswith(".bi5") or os.path.getsize(f"{d}/{f}") == 0: continue
            out.append(_parse(f"{d}/{f}", pd.Timestamp(f[:7] + "-01"), SPEC[inst]["point"]))
        df = pd.concat(out).sort_index(); df = df[~df.index.duplicated()]
        df[df.index < VAULT_START].to_parquet(dev); df[df.index >= VAULT_START].to_parquet(vlt)
    df = pd.read_parquet(dev)
    if vault: df = pd.concat([df, pd.read_parquet(vlt)])
    else: assert df.index.max() < VAULT_START
    return df


def load_btc():
    import zipfile, glob
    out = []
    for f in sorted(glob.glob(f"{RAW}/BTC/*.zip")):
        z = zipfile.ZipFile(f); x = pd.read_csv(z.open(z.namelist()[0]), header=None)
        ts = x[0].astype(np.int64); ts = np.where(ts > 1e14, ts // 1000, ts)   # 2025+ files are in microseconds
        out.append(pd.DataFrame({"o": x[1].values, "h": x[2].values, "l": x[3].values, "c": x[4].values, "v": x[5].values},
                                index=pd.to_datetime(ts, unit="ms")))
    df = pd.concat(out).sort_index(); return df[~df.index.duplicated()]


class Mkt:
    """hourly arrays + 17:00-NY trading days. idx is naive UTC."""
    def __init__(self, df, inst="XAUUSD"):
        self.inst = inst; self.spec = SPEC[inst]; self.df = df
        self.o, self.h, self.l, self.c = (df[k].values.astype(np.float64) for k in "ohlc")
        self.idx = df.index
        ny = df.index.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        self.ny = ny; self.nyh = ny.hour.values
        key = (ny + pd.Timedelta(hours=7)).normalize()
        g = pd.DataFrame({"o": self.o, "h": self.h, "l": self.l, "c": self.c, "k": key, "i": np.arange(len(df))})
        D = g.groupby("k").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("o", "size"), s=("i", "first"), e=("i", "last"))
        D = D[(D.n >= 10) & (D.index.dayofweek <= 4)].copy()
        self.D = D; self.days = D.index; self.s = D.s.values.astype(np.int64); self.e = D.e.values.astype(np.int64)
        self.dayof = np.full(len(df), -1, np.int64)
        for t, (a, b) in enumerate(zip(self.s, self.e)): self.dayof[a:b + 1] = t
        # bar index by (day, NY hour); -1 if missing
        self.dh = np.full((len(D), 24), -1, np.int64)
        for t, (a, b) in enumerate(zip(self.s, self.e)):
            for j in range(a, b + 1): self.dh[t, self.nyh[j]] = j
        # swap weight of the rollover at the END of each day key (17:00 NY on that date): Wed x3
        self.roll_w = np.where(self.days.dayofweek == 2, 3.0, 1.0)
        self.roll_cum = np.r_[0.0, np.cumsum(self.roll_w)]

    def bar_at(self, t, hour):
        return self.dh[t, hour] if 0 <= t < len(self.days) else -1

    def costs(self, side, ep, xp, d0, d1):
        sp = self.spec["spread"]
        c1 = 0.5 * sp / ep + 0.5 * sp / xp + 2 * SLIP
        c2 = (sp / 4000.0 + 2 * SLIP) if self.inst == "XAUUSD" else c1
        nroll = self.roll_cum[d1] - self.roll_cum[d0]     # rollovers at the end of days d0..d1-1
        sw = self.spec["swap_long"] / 4000.0 * nroll if side == 1 else 0.0   # Amendment A: rate-based swap = 0.4316/4000 per rollover
        return c1 + sw, c2 + sw


# ------------------------------------------------------------------ engine
@njit(cache=True)
def stop_fill(o, h, l, ja, jb, lvl, side):
    """first bar in [ja, jb] where a stop entry at lvl triggers -> (bar, price) or (-1, nan)"""
    for j in range(ja, jb + 1):
        if side == 1 and h[j] >= lvl: return j, max(lvl, o[j])
        if side == -1 and l[j] <= lvl: return j, min(lvl, o[j])
    return -1, np.nan


@njit(cache=True)
def run_exit(o, h, l, c, j0, side, stop, tgt, jx, entry_bar_check):
    """position opened during bar j0 (entry_bar_check: stop on the entry bar counts, worst case) -> (exit bar, exit price, how)
    how: 0 time, 1 stop, 2 target. stop/target nan = none. stop first if both in a bar."""
    if entry_bar_check and not np.isnan(stop):
        if (side == 1 and l[j0] <= stop) or (side == -1 and h[j0] >= stop): return j0, stop, 1
    for j in range(j0 + 1, jx + 1):
        if not np.isnan(stop):
            if side == 1 and l[j] <= stop: return j, min(stop, o[j]), 1
            if side == -1 and h[j] >= stop: return j, max(stop, o[j]), 1
        if not np.isnan(tgt):
            if side == 1 and h[j] >= tgt: return j, max(tgt, o[j]), 2
            if side == -1 and l[j] <= tgt: return j, min(tgt, o[j]), 2
    return jx, c[jx], 0


def trade_row(M, side, j0, ep, jx, xp, name="", how=0):
    d0 = M.dayof[j0]; d1 = M.dayof[jx]
    g = side * (xp / ep - 1); n1, n2 = M.costs(side, ep, xp, d0, d1)
    return dict(t=M.days[d0], tx=M.days[d1], j0=int(j0), jx=int(jx), side=int(side), ep=ep, xp=xp, gross=g, net1=g - n1, net2=g - n2, how=how)


def oco_stop_trade(M, ja, jb, orders, jx_of, entry_check=True):
    """orders: list of (side, lvl, stop, tgt). First triggered wins; both in one bar -> worse outcome.
    jx_of(j0) -> exit bar. Returns row dict or None."""
    o, h, l, c = M.o, M.h, M.l, M.c
    fills = []
    for (side, lvl, stop, tgt) in orders:
        if not np.isfinite(lvl): continue
        j, p = stop_fill(o, h, l, ja, jb, lvl, side)
        if j >= 0: fills.append((j, p, side, stop, tgt))
    if not fills: return None
    jmin = min(f[0] for f in fills); cand = [f for f in fills if f[0] == jmin]
    rows = []
    for (j, p, side, stop, tgt) in cand:
        jx = jx_of(j)
        if jx < j: continue
        stop_ = np.nan if stop is None else float(stop); tgt_ = np.nan if tgt is None else float(tgt)
        xj, xp, how = run_exit(o, h, l, c, j, side, stop_, tgt_, jx, entry_check)
        rows.append(trade_row(M, side, j, p, xj, xp, how=how))
    if not rows: return None
    if len(rows) > 1: return min(rows, key=lambda r: r["net1"])
    return rows[0]


# ------------------------------------------------------------------ stats
def tstat(r):
    r = np.asarray(r, float)
    if len(r) < 3 or r.std(ddof=1) == 0: return 0.0
    return float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r))))


def period(T, P):
    if T is None or len(T) == 0: return T
    return T[(T.t >= P[0]) & (T.t < P[1])]


def summ(M, T, P, two_sided=True, nsim=2000, seed=123):
    X = period(T, P)
    if X is None or len(X) < 10: return {"n": 0 if X is None else int(len(X))}
    out = {"n": int(len(X)), "gross_bp": round(float(X.gross.mean() * 1e4), 2), "win": round(float((X.net1 > 0).mean()), 3),
           "long_frac": round(float((X.side == 1).mean()), 2)}
    for col in ("net1", "net2"):
        r = X[col].values; t = tstat(r); eq = np.cumsum(r)
        out[col] = {"bp": round(float(r.mean() * 1e4), 2), "t": round(t, 2), "p1": float(stats.t.sf(t, len(r) - 1)),
                    "maxdd_pct": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min() * 100), 1)}
    rng = np.random.default_rng(seed); g = X.gross.values
    if two_sided:
        sims = (np.where(rng.random((nsim, len(g))) < 0.5, 1, -1) * g).mean(1)
        out["p_rand"] = float((np.sum(sims >= g.mean()) + 1) / (nsim + 1))
    out["p_time"] = random_time_p(M, X, P, nsim, rng)
    return out


def random_time_p(M, X, P, nsim, rng):
    """same side, same entry NY hour, same holding length (bars), random day in the period; gross from bar open to bar close."""
    dsel = np.flatnonzero((M.days >= P[0]) & (M.days < P[1]))
    hr = M.nyh[X.j0.values]; hold = (X.jx.values - X.j0.values); side = X.side.values
    n = len(X); acc = np.zeros(nsim)
    o, c = M.o, M.c; N = len(c)
    for k in range(n):
        days = dsel[rng.integers(0, len(dsel), nsim)]
        j = M.dh[days, hr[k]]
        bad = j < 0
        j = np.where(bad, M.s[days], j)
        jx = np.minimum(j + hold[k], N - 1)
        acc += side[k] * (c[jx] / o[j] - 1)
    sims = acc / n
    return float((np.sum(sims >= X.gross.mean()) + 1) / (nsim + 1))


def holm(p):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p); adj = np.empty(m); run = 0.0
    for r, i in enumerate(o):
        run = max(run, (m - r) * p[i]); adj[i] = min(1.0, run)
    return adj


def daily_pnl(T, col="net1", days=None):
    s = T.groupby("tx")[col].sum()
    return s.reindex(days).fillna(0.0) if days is not None else s


def deflated_sharpe(daily, n_trials, var_sr_annual):
    """Bailey & Lopez de Prado 2014. daily returns; SRs annualized (252); var_sr_annual = cross-trial variance of annual SR."""
    r = np.asarray(daily, float); T = len(r)
    sr_d = r.mean() / r.std(ddof=1); sk = stats.skew(r); ku = stats.kurtosis(r, fisher=False)
    g = 0.5772156649
    sr0_a = np.sqrt(var_sr_annual) * ((1 - g) * stats.norm.ppf(1 - 1 / n_trials) + g * stats.norm.ppf(1 - 1 / (n_trials * np.e)))
    sr0_d = sr0_a / np.sqrt(252)
    z = (sr_d - sr0_d) * np.sqrt(T - 1) / np.sqrt(1 - sk * sr_d + (ku - 1) / 4 * sr_d ** 2)
    return float(stats.norm.cdf(z)), float(sr_d * np.sqrt(252)), float(sr0_a)
