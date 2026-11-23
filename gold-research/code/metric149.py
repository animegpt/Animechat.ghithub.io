"""Metric of prereg 149-153: monthly portfolio Sharpe of sized vs plain Williams, D, JKM-Memmel t, block bootstrap t,
Holm, deflated Sharpe of the overlay."""
import numpy as np, pandas as pd
from scipy import stats

P_DISC = ("2009-01-01", "2017-01-01"); P_CONF = ("2017-01-01", "2024-01-01"); P_ALL = ("2009-01-01", "2024-01-01")


def month_matrix(t, P):
    """t: trade days (DatetimeIndex-like). Returns (mask of trades in P, G: months x trades 0/1 matrix, months)"""
    t = pd.DatetimeIndex(t); a, b = pd.Timestamp(P[0]), pd.Timestamp(P[1])
    m = (t >= a) & (t < b)
    months = pd.period_range(a, b - pd.Timedelta(days=1), freq="M")
    code = (t[m].to_period("M") - months[0]).map(lambda x: x.n).values.astype(int)
    G = np.zeros((len(months), m.sum())); G[code, np.arange(m.sum())] = 1.0
    return m, G, months


def sharpe_m(X):
    X = np.asarray(X, float); sd = X.std(0, ddof=1)
    return np.where(sd > 0, X.mean(0) / np.where(sd > 0, sd, 1), 0.0)


def jkm(base, sized):
    """base (T,), sized (T,) or (T,K) monthly. returns D (annualised), t (JKM-Memmel)"""
    b = np.asarray(base, float); S = np.asarray(sized, float)
    one = S.ndim == 1
    if one: S = S[:, None]
    T = len(b)
    s1 = sharpe_m(S); s2 = sharpe_m(b[:, None])[0]
    bc = b - b.mean(); Sc = S - S.mean(0)
    rho = (Sc * bc[:, None]).sum(0) / np.sqrt((Sc ** 2).sum(0) * (bc ** 2).sum()) if (bc ** 2).sum() > 0 else np.zeros(S.shape[1])
    var = (2 * (1 - rho) + 0.5 * (s1 ** 2 + s2 ** 2 - 2 * s1 * s2 * rho ** 2)) / T
    d = s1 - s2
    t = np.where(var > 0, d / np.sqrt(np.maximum(var, 1e-300)), 0.0)
    D = d * np.sqrt(12)
    return (D[0], t[0]) if one else (D, t)


def boot_t(base, sized, block=6, n=5000, seed=7):
    b = np.asarray(base, float); s = np.asarray(sized, float); T = len(b)
    rng = np.random.default_rng(seed); nb = int(np.ceil(T / block))
    st = rng.integers(0, T, (n, nb)); idx = ((st[:, :, None] + np.arange(block)) % T).reshape(n, -1)[:, :T]
    B = b[idx]; S = s[idx]
    def sh(X):
        sd = X.std(1, ddof=1); return np.where(sd > 0, X.mean(1) / np.where(sd > 0, sd, 1), 0)
    Db = (sh(S) - sh(B)) * np.sqrt(12)
    D = (sharpe_m(s[:, None])[0] - sharpe_m(b[:, None])[0]) * np.sqrt(12)
    se = Db.std(ddof=1)
    return float(D / se) if se > 0 else 0.0


def evaluate(t, r, size, P, boot=True):
    """t trade days, r per-trade return, size per-trade size -> dict"""
    m, G, months = month_matrix(t, P)
    base = G @ np.asarray(r)[m]; sized = G @ (np.asarray(r)[m] * np.asarray(size)[m])
    D, tj = jkm(base, sized)
    out = {"n": int(m.sum()), "months": len(months), "sh_base": round(float(sharpe_m(base[:, None])[0] * np.sqrt(12)), 3),
           "sh_sized": round(float(sharpe_m(sized[:, None])[0] * np.sqrt(12)), 3), "D": round(float(D), 3),
           "t_jkm": round(float(tj), 2), "mean_size": round(float(np.asarray(size)[m].mean()), 3)}
    if boot: out["t_boot"] = round(boot_t(base, sized), 2)
    return out


def overlay_monthly(t, r, size, P):
    m, G, months = month_matrix(t, P)
    return G @ (np.asarray(r)[m] * (np.asarray(size)[m] - 1.0))


def holm(p):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p); adj = np.empty(m); run = 0.0
    for r, i in enumerate(o):
        run = max(run, (m - r) * p[i]); adj[i] = min(1.0, run)
    return adj


def dsr_monthly(x, n_trials, var_sr_annual):
    """Bailey & Lopez de Prado deflated Sharpe on monthly returns. SRs annualised with sqrt(12)."""
    r = np.asarray(x, float); T = len(r)
    if r.std(ddof=1) == 0: return 0.0, 0.0, 0.0
    sr = r.mean() / r.std(ddof=1); sk = stats.skew(r); ku = stats.kurtosis(r, fisher=False)
    g = 0.5772156649
    sr0_a = np.sqrt(var_sr_annual) * ((1 - g) * stats.norm.ppf(1 - 1 / n_trials) + g * stats.norm.ppf(1 - 1 / (n_trials * np.e)))
    sr0 = sr0_a / np.sqrt(12)
    z = (sr - sr0) * np.sqrt(T - 1) / np.sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr ** 2, 1e-12))
    return float(stats.norm.cdf(z)), float(sr * np.sqrt(12)), float(sr0_a)
