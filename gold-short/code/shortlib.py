"""Short-only gold engine (tests #65+). Minute data, intrabar stops on minute HIGH with gap fill at the open,
price-relative Exness costs. Rows >= 2024-01-01 are physically dropped unless OPEN_VAULT=1."""
import os, json, lzma, numpy as np, pandas as pd
from numba import njit
from scipy import stats

GDATA = os.environ.get("GDATA", "/tmp/claude-0/-home-user-Animechat-ghithub-io/560e5906-91d7-5a21-85d3-2f8e486ee3fc/scratchpad/data")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRED = os.environ.get("FRED_DIR", HERE + "/raw/fred")
LOG = HERE + "/test_log_short.jsonl"
VAULT_START = pd.Timestamp("2024-01-01", tz="UTC")
VAULT_END = pd.Timestamp("2026-11-01", tz="UTC")
OPEN_VAULT = os.environ.get("OPEN_VAULT") == "1"
SPREAD_USD = 0.24
SLIP = 0.10 / 1e4
NEWS_MULT, OPEN_MULT = 3.0, 5.0
DISC = (pd.Timestamp("2004-01-01", tz="UTC"), pd.Timestamp("2017-01-01", tz="UTC"))
CONF = (pd.Timestamp("2017-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC"))
VAULT = (VAULT_START, VAULT_END)


# ------------------------------------------------------------------ data
def _parse(path, t0):
    raw = lzma.decompress(open(path, "rb").read())
    a = np.frombuffer(raw, dtype=">i4").reshape(-1, 6).astype(np.int64)
    v = np.frombuffer(raw, dtype=">f4").reshape(-1, 6)[:, 5].astype(np.float64)
    df = pd.DataFrame({"o": a[:, 1], "c": a[:, 2], "l": a[:, 3], "h": a[:, 4]},
                      index=t0 + pd.to_timedelta(a[:, 0], unit="s")) / 1000.0
    df["v"] = v
    return df[df.v > 0]


def load_minutes():
    dev = f"{GDATA}/xau_1m_dev.parquet"; vlt = f"{GDATA}/xau_1m_vault.parquet"
    if not os.path.exists(dev):
        d = f"{GDATA}/raw/cache_XAUUSD"; out = []
        for f in sorted(os.listdir(d)):
            if os.path.getsize(f"{d}/{f}") == 0: continue
            out.append(_parse(f"{d}/{f}", pd.Timestamp(f[:10], tz="UTC")))
        df = pd.concat(out).sort_index(); df = df[~df.index.duplicated()]
        df[df.index < VAULT_START].to_parquet(dev); df[df.index >= VAULT_START].to_parquet(vlt)
    df = pd.read_parquet(dev)
    if OPEN_VAULT:
        df = pd.concat([df, pd.read_parquet(vlt)])
    else:
        assert df.index.max() < VAULT_START
    return df[df.index < VAULT_END]


def cost_mult(idx):
    m = idx.hour * 60 + idx.minute
    mult = np.ones(len(idx))
    for a, b in ((745, 760), (805, 820), (835, 850), (895, 910), (1075, 1090), (1135, 1150)):
        mult[(m >= a) & (m < b)] = NEWS_MULT
    roll = (m >= 1255) | (m < 15)
    mult[roll] = np.maximum(mult[roll], OPEN_MULT)
    return mult


class Market:
    """minute arrays + daily bars (day ends 15:30 NY) + entry minute per day (bar starting 15:31 NY)"""
    def __init__(self, df=None):
        df = load_minutes() if df is None else df
        self.m = df; self.idx = df.index
        self.o, self.h, self.l, self.c = (df[k].values.astype(np.float64) for k in "ohlc")
        end = self.idx + pd.Timedelta(minutes=1)              # fills happen at minute CLOSE
        self.side_cost_frac = 0.5 * SPREAD_USD * cost_mult(end) + 0.0   # USD; divided by price at use
        ny = self.idx.tz_convert("America/New_York")
        self.ny = ny
        key = (ny.tz_localize(None) + pd.Timedelta(hours=8, minutes=30)).normalize()
        g = pd.DataFrame({"o": self.o, "h": self.h, "l": self.l, "c": self.c, "k": key, "pos": np.arange(len(df))})
        d = g.groupby("k").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("o", "size"),
                               last=("pos", "last"))
        d = d[d.n >= 600].copy()
        # entry minute: first minute starting >= 15:31 NY on calendar date d, within 30 minutes
        nyl = ny.tz_localize(None)
        mins = nyl.hour * 60 + nyl.minute
        cand = np.flatnonzero((mins >= 931) & (mins <= 960))
        cdate = nyl[cand].normalize()
        first = pd.Series(cand, index=cdate).groupby(level=0).first()
        d["entry"] = first.reindex(d.index).values
        d = d.dropna(subset=["entry"]); d["entry"] = d["entry"].astype(np.int64)
        pc = d.c.shift(1)
        tr = np.maximum(d.h - d.l, np.maximum((d.h - pc).abs(), (d.l - pc).abs()))
        d["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
        d["r"] = np.log(d.c / pc)
        self.d = d
        self.year_of_min = self.idx.year.values

    def cost(self, i):
        """per-side cost fraction at minute i"""
        return self.side_cost_frac[i] / self.c[i] + SLIP


# ------------------------------------------------------------------ trade simulation
@njit(cache=True)
def _sim(o, h, c, ent, stp, xmax, sidecost_usd, slip, cmult):
    n = len(ent); out = np.zeros((n, 5))
    for k in range(n):
        i = ent[k]; e = c[i]; s = stp[k]; x = xmax[k]; px = c[x]; xi = x; stopped = 0.0
        for j in range(i + 1, x + 1):
            if h[j] >= s:
                px = o[j] if o[j] >= s else s; xi = j; stopped = 1.0; break
        gross = (e - px) / e
        ce = sidecost_usd[i] / e + slip; cx = sidecost_usd[xi] / px + slip
        out[k, 0] = xi; out[k, 1] = gross; out[k, 2] = gross - cmult * (ce + cx); out[k, 3] = stopped
        out[k, 4] = gross - 2.0 * cmult * (ce + cx)
    return out


def simulate(M, ent, stp, xmax, cmult=1.0):
    ent = np.asarray(ent, np.int64); stp = np.asarray(stp, np.float64); xmax = np.asarray(xmax, np.int64)
    if len(ent) == 0:
        return pd.DataFrame(columns=["i", "x", "gross", "net", "stopped", "net2"])
    r = _sim(M.o, M.h, M.c, ent, stp, xmax, M.side_cost_frac, SLIP, cmult)
    t = pd.DataFrame({"i": ent, "x": r[:, 0].astype(np.int64), "gross": r[:, 1], "net": r[:, 2],
                      "stopped": r[:, 3], "net2": r[:, 4]})
    t.index = M.idx[t.i]
    return t


def nonoverlap(cands):
    """cands: list of (entry_min, stop, xmax, meta) sorted by entry; keep a trade only after the previous planned exit.
    Because stops can end a trade earlier, we resolve sequentially with the real exit."""
    return cands


def run_sequential(M, cands, cmult=1.0):
    """cands sorted list of dicts {i, stop, xmax}; one position at a time using the REAL exit (stop may end early)."""
    keep = []; busy = -1
    if not cands: return simulate(M, [], [], [])
    ent = np.array([c["i"] for c in cands]); stp = np.array([c["stop"] for c in cands]); xm = np.array([c["xmax"] for c in cands])
    full = simulate(M, ent, stp, xm, cmult)
    rows = []
    for k in range(len(cands)):
        if ent[k] <= busy: continue
        rows.append(k); busy = full.x.values[k]
    t = full.iloc[rows].copy()
    for key in cands[0]:
        if key not in ("i", "stop", "xmax"):
            t[key] = [cands[k][key] for k in rows]
    return t


def period(t, P):
    return t[(t.index >= P[0]) & (t.index < P[1])]


def summ(t, col="net"):
    r = t[col].values if len(t) else np.array([])
    n = len(r)
    if n < 3: return {"n": int(n), "mean_bp": float(np.mean(r) * 1e4) if n else 0.0, "t": 0.0}
    sd = r.std(ddof=1); tt = r.mean() / (sd / np.sqrt(n)) if sd > 0 else 0.0
    pos = r[r > 0].sum(); neg = -r[r < 0].sum()
    eq = np.cumsum(r); dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    return {"n": int(n), "mean_bp": round(float(r.mean() * 1e4), 2), "t": round(float(tt), 2),
            "win": round(float((r > 0).mean()), 3), "pf": round(float(pos / neg), 2) if neg > 0 else None,
            "sum_pct": round(float(r.sum() * 100), 1), "maxdd_pct": round(float(dd * 100), 1),
            "gross_bp": round(float(t["gross"].mean() * 1e4), 2), "net2_bp": round(float(t["net2"].mean() * 1e4), 2),
            "p1": float(stats.t.sf(tt, n - 1))}


def holm(pvals):
    p = np.asarray(pvals, float); m = len(p); order = np.argsort(p); adj = np.empty(m); run = 0.0
    for r, k in enumerate(order):
        run = max(run, (m - r) * p[k]); adj[k] = min(1.0, run)
    return adj


def deflated_sharpe(r, n_trials, var_trial_sr):
    """Bailey & Lopez de Prado (2014). r = per-trade returns; SR per trade."""
    r = np.asarray(r); n = len(r); sr = r.mean() / r.std(ddof=1)
    sk = stats.skew(r); ku = stats.kurtosis(r, fisher=False)
    g = 0.5772156649
    sr0 = np.sqrt(var_trial_sr) * ((1 - g) * stats.norm.ppf(1 - 1 / n_trials) + g * stats.norm.ppf(1 - 1 / (n_trials * np.e)))
    z = (sr - sr0) * np.sqrt(n - 1) / np.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2)
    return float(stats.norm.cdf(z)), float(sr), float(sr0)


def bootstrap_p(r, nb=10000, seed=7):
    rng = np.random.default_rng(seed); r = np.asarray(r)
    means = r[rng.integers(0, len(r), (nb, len(r)))].mean(1)
    return float((means <= 0).mean())


def log(rec):
    with open(LOG, "a") as f: f.write(json.dumps(rec, default=float) + "\n")


# ------------------------------------------------------------------ FRED
def fred(name):
    s = pd.read_csv(f"{FRED}/{name}.csv", index_col=0, parse_dates=True).iloc[:, 0]
    return pd.to_numeric(s, errors="coerce").dropna()


def fred_asof(s, days, lag_bd):
    """value of series as known at decision dates `days` (naive dates) using obs dated <= day - lag_bd business days.
    returns positional index (into s) of the latest usable observation."""
    cutoff = pd.DatetimeIndex(days) - pd.offsets.BDay(lag_bd)
    pos = np.searchsorted(s.index.values, cutoff.values, side="right") - 1
    return pos
