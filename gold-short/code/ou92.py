"""#92 Optimal mean-reversion stopping (Bertram 2010) for the DC-fade family. prereg/PREREGISTRATION_92_94_juicer.md
usage: BARS=1m GDATA=... python ou92.py <silver minute dir>"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("BARS", "1m")
from numba import njit
from scipy import stats, integrate
import shortlib as sl

NEWS = ((745, 760), (805, 820), (835, 850), (895, 910), (1075, 1090), (1135, 1150))
SC = {"A": (0.24, 0.0, 1.0), "B": (0.03, 0.07, 1.0), "C": (0.06, 0.14, 2.0)}   # spread, commission, slippage mult


def arrays(df):
    A = {}
    A["idx"] = df.index; A["o"], A["h"], A["l"], A["c"] = (df[k].values.astype(np.float64) for k in "ohlc")
    tm = (df.index.hour * 60 + df.index.minute).values; dow = df.index.dayofweek.values
    news = np.zeros(len(df), bool)
    for a, b in NEWS: news |= (tm >= a) & (tm < b)
    A["news"] = news; A["noentry"] = news | ((tm >= 1245) & (tm <= 1395)) | ((dow == 4) & (tm >= 1170))
    tns = df.index.values.astype("datetime64[ns]").astype(np.int64); A["tns"] = tns
    d = df.index.normalize().values.astype("datetime64[ns]").astype(np.int64) + (20 * 60 + 44) * 60 * 10 ** 9
    d = d + np.where(tm >= 1245, 86400 * 10 ** 9, 0); A["fc"] = (np.searchsorted(tns, d, side="right") - 1).astype(np.int64)
    ny = df.index.tz_convert("America/New_York").tz_localize(None)
    A["nyh"] = ny.hour.values.astype(np.int64)
    A["dayid"] = np.unique((ny + pd.Timedelta(hours=6)).normalize().values, return_inverse=True)[1].astype(np.int64)
    c = A["c"]; e = pd.Series(c).ewm(span=60, adjust=False).mean().values
    A["X"] = np.log(c) - np.log(e)
    A["s"] = pd.Series(A["X"]).rolling(1440, min_periods=720).std().values
    return A


def fit_ou(X):
    x0, x1 = X[:-1], X[1:]; ok = np.isfinite(x0) & np.isfinite(x1)
    b, a = np.polyfit(x0[ok], x1[ok], 1); res = x1[ok] - (a + b * x0[ok])
    kappa = -np.log(b); mu = a / (1 - b); sigma = res.std() * np.sqrt(2 * kappa / (1 - b * b))
    return dict(kappa=float(kappa), mu=float(mu), sigma=float(sigma), s=float(sigma / np.sqrt(2 * kappa)), beta=float(b))


def bertram(kappa, s, c, grid=np.linspace(-4, 4, 161)):
    """maximise (m-a-c)/(E[T a->m]+E[T m->a]) ; a,m in units of s; c in log units"""
    f = lambda u: np.exp(u * u / 2) * np.sqrt(2 * np.pi) * stats.norm.cdf(u)
    # cumulative integral of f on a fine grid for fast lookup
    U = np.linspace(-6, 6, 12001); F = np.r_[0, np.cumsum((f(U[1:]) + f(U[:-1])) / 2 * np.diff(U))]
    I = lambda lo, hi: np.interp(hi, U, F) - np.interp(lo, U, F)
    best = (-1e9, None, None)
    for a in grid:
        for m in grid[grid > a]:
            ET = (I(a, m) + I(-m, -a)) / kappa
            val = ((m - a) * s - c) / ET
            if val > best[0]: best = (val, float(a), float(m))
    return {"rate_per_min": best[0], "a": best[1], "m": best[2]}


@njit(cache=True)
def sim(o, h, l, c, X, s, noentry, fc, tns, mode, a, m, allow_long, allow_short, th, nyh, stopk):
    """mode 0: OU bands; mode 1: DC entries + OU exit; mode 2: DC entries + next-DC exit (baseline).
    returns entry idx, exit idx, side, entry px, exit px"""
    n = len(c); ei = np.empty(n, np.int64); xi = np.empty(n, np.int64); sd = np.empty(n, np.int64); ep = np.empty(n); xp = np.empty(n); k = 0
    pos = 0; e = 0.0; stop = 0.0; ent = 0; pend = 0; pend_exit = False
    dmode = 0; hi = c[0]; lo = c[0]; dcpx = c[0]; ddir = 0; faded = False
    for t in range(1, n):
        # 1) execute pending orders at this minute's open
        if pend_exit and pos != 0:
            ei[k] = ent; xi[k] = t; sd[k] = pos; ep[k] = e; xp[k] = o[t]; k += 1; pos = 0; pend_exit = False
        if pend != 0 and pos == 0:
            if not noentry[t] and fc[t] > t:
                pos = pend; e = o[t]; ent = t
                if mode == 0: stop = e * (1 - pos * stopk * s[t - 1])
                else: stop = e * (1 - pos * 3.0 * th)
            pend = 0
        # 2) intrabar stop
        if pos != 0:
            if (pos == 1 and l[t] <= stop) or (pos == -1 and h[t] >= stop):
                px = stop
                if t > ent and ((pos == 1 and o[t] <= stop) or (pos == -1 and o[t] >= stop)): px = o[t]
                ei[k] = ent; xi[k] = t; sd[k] = pos; ep[k] = e; xp[k] = px; k += 1; pos = 0; pend_exit = False
        # 3) DC state on close
        p = c[t]; dc_now = False
        if dmode == 0:
            if p > hi: hi = p
            if p < lo: lo = p
            if p <= hi * (1 - th): dmode = -1; lo = p; dc_now = True; ddir = -1; dcpx = p
            elif p >= lo * (1 + th): dmode = 1; hi = p; dc_now = True; ddir = 1; dcpx = p
        elif dmode == 1:
            if p > hi: hi = p
            elif p <= hi * (1 - th): dmode = -1; lo = p; dc_now = True; ddir = -1; dcpx = p
        else:
            if p < lo: lo = p
            elif p >= lo * (1 + th): dmode = 1; hi = p; dc_now = True; ddir = 1; dcpx = p
        if dc_now: faded = False
        # 4) exits decided at close (filled next open)
        if pos != 0:
            if t >= fc[ent]:
                ei[k] = ent; xi[k] = t; sd[k] = pos; ep[k] = e; xp[k] = c[t]; k += 1; pos = 0
            elif tns[t] - tns[ent] >= 1440 * 60 * 1000000000: pend_exit = True
            elif mode == 2 and dc_now: pend_exit = True
            elif mode <= 1 and np.isfinite(s[t]) and ((pos == 1 and X[t] >= m * s[t]) or (pos == -1 and X[t] <= -m * s[t])): pend_exit = True
        # 5) entries decided at close
        if pos == 0 and pend == 0 and not pend_exit:
            if mode == 0:
                if np.isfinite(s[t]) and s[t] > 0:
                    if allow_long and X[t] <= a * s[t]: pend = 1
                    elif allow_short and X[t] >= -a * s[t]: pend = -1
            else:
                if not faded and not dc_now and ddir != 0:
                    if (ddir == 1 and p >= dcpx * (1 + 2 * th)) or (ddir == -1 and p <= dcpx * (1 - 2 * th)):
                        faded = True
                        hh = nyh[t]
                        if not (hh <= 2 or hh == 16 or hh == 17):
                            if (-ddir == 1 and allow_long) or (-ddir == -1 and allow_short): pend = -ddir
    return ei[:k], xi[:k], sd[:k], ep[:k], xp[:k]


def evaluate(A, lo, hi, mode, a, m, al, ash, spread_usd_override=None):
    sl_ = slice(lo, hi)
    args = [A[k][sl_] for k in ("o", "h", "l", "c", "X", "s", "noentry", "fc")]
    args[7] = args[7] - lo
    ei, xi, sd, ep, xp = sim(*args, A["tns"][sl_], mode, a, m, al, ash, 0.002, A["nyh"][sl_], 6.0)
    g = sd * (xp / ep - 1); news = A["news"][sl_][xi]; out = {"n": int(len(g))}
    dayid = A["dayid"][sl_][ei]; ndays = len(np.unique(A["dayid"][sl_]))
    if len(g) < 5: return out, None
    holds = (A["tns"][sl_][xi] - A["tns"][sl_][ei]) / 6e10
    out["gross_bp"] = round(float(g.mean() * 1e4), 3); out["hold_min"] = round(float(holds.mean()), 1); out["per_day"] = round(len(g) / ndays, 2)
    for k, (sp, cm, sm) in SC.items():
        if spread_usd_override is not None and k != "B": continue
        sp_ = spread_usd_override if spread_usd_override is not None else sp
        cost = 0.5 * sp_ / ep + 0.5 * sp_ * np.where(news, 3, 1) / xp + 0.5 * cm / ep + 0.5 * cm / xp + 2 * sm * 0.1e-4
        net = g - cost; dd = pd.Series(net).groupby(dayid).sum()
        t = float(dd.mean() / (dd.std(ddof=1) / np.sqrt(len(dd)))) if len(dd) > 2 else 0.0
        out[k] = {"bp": round(float(net.mean() * 1e4), 3), "day_t": round(t, 2), "per_day_bp": round(float(net.sum() / ndays * 1e4), 3),
                  "p1": float(stats.t.sf(t, max(len(dd) - 1, 1)))}
    dg = pd.Series(g).groupby(dayid).sum(); out["gross_day_t"] = round(float(dg.mean() / (dg.std(ddof=1) / np.sqrt(len(dg)))), 2)
    return out, g


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "disc"
    G = arrays(sl.load_minutes()[lambda d: d.index >= pd.Timestamp("2017-01-01", tz="UTC")])
    de = int(np.searchsorted(G["tns"], pd.Timestamp("2021-01-01", tz="UTC").value)); n = len(G["c"])
    par = fit_ou(G["X"][:de]); pm = float(G["c"][:de].mean())
    mnews = 1.0 + 2.0 * G["news"][:de].mean()
    cB = (0.03 * (1 + mnews) / 2 + 0.07) / pm + 2e-5
    bands = bertram(par["kappa"], par["s"], cB)
    print("OU fit (disc):", par, "| mean price", round(pm, 1), "| cost B log", round(cB * 1e4, 3), "bp | bands", bands, flush=True)
    V = {"OU_BOTH": (0, True, True), "OU_LONG": (0, True, False), "DC_OUEXIT": (1, True, True), "BASELINE_DC": (2, True, True)}
    res = {"ou": par, "bands": bands, "cost_B_logbp": cB * 1e4}
    rng = {"disc": (0, de), "conf": (de, n)}[which]
    for nm, (mode, al, ash) in V.items():
        r, _ = evaluate(G, rng[0], rng[1], mode, bands["a"], bands["m"], al, ash); res[nm] = r
        print(which, nm, json.dumps(r), flush=True)
    names = ["OU_BOTH", "OU_LONG", "DC_OUEXIT"]
    if which == "disc":
        adj = sl.holm([res[k]["B"]["p1"] if "B" in res[k] else 1 for k in names])
        for k, a_ in zip(names, adj): res[k]["holm_B"] = round(float(a_), 4)
        print({k: res[k].get("holm_B") for k in names})
    if which == "silver":
        pass
    json.dump(res, open(f"{sl.HERE}/results_92_{which}.json", "w"), indent=1, default=float)
