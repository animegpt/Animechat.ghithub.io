"""Reference strategies of the current portfolio for correlation/portfolio checks (hourly approximations of the earlier lab's
portfolio_check.py): Sonic R H1 (EMA34/89, both sides, unsized), Overnight (long 16:00->20:00 NY Mon-Thu), Williams #112."""
import numpy as np, pandas as pd
import lab
from lab import trade_row, run_exit


def sonic(M):
    o, h, l, c = M.o, M.h, M.l, M.c
    ema = lambda x, s: pd.Series(x).ewm(span=s, adjust=False).mean().values
    eh, el, ec, e89 = ema(h, 34), ema(l, 34), ema(c, 34), ema(c, 89)
    pc = np.r_[c[0], c[:-1]]; tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    mid = (eh + el) / 2; sh5 = lambda x: np.r_[np.full(5, np.nan), x[:-5]]
    up = (mid > e89) & (mid > sh5(mid)) & (e89 > sh5(e89)); dn = (mid < e89) & (mid < sh5(mid)) & (e89 < sh5(e89))
    tl = pd.Series(l <= ec).rolling(5).max().values > 0; ts = pd.Series(h >= ec).rolling(5).max().values > 0
    pcl = np.r_[c[0], c[:-1]]
    Lg = up & tl & (c > eh) & (pcl <= np.r_[eh[0], eh[:-1]]); Sg = dn & ts & (c < el) & (pcl >= np.r_[el[0], el[:-1]])
    ll10 = pd.Series(l).rolling(10).min().values; hh10 = pd.Series(h).rolling(10).max().values
    rows = []; busy = -1; N = len(c)
    ev = sorted([(k, 1) for k in np.flatnonzero(Lg) if k > 300] + [(k, -1) for k in np.flatnonzero(Sg) if k > 300])
    for k, s in ev:
        if k <= busy or k + 1 >= N or M.dayof[k + 1] < 0: continue
        stop = min(ll10[k], c[k] - 0.5 * atr[k]) if s == 1 else max(hh10[k], c[k] + 0.5 * atr[k])
        xe = min(k + 240, N - 1)
        for kk in range(k + 1, xe + 1):
            if (s == 1 and c[kk] < el[kk]) or (s == -1 and c[kk] > eh[kk]): xe = kk; break
        j0 = k + 1
        xj, xp, how = run_exit(o, h, l, c, j0, s, stop, np.nan, xe, True)
        if M.dayof[xj] < 0: continue
        rows.append(trade_row(M, s, j0, o[j0], xj, xp, how=how)); busy = xj
    return pd.DataFrame(rows)


def overnight(M):
    rows = []
    for t in range(len(M.days) - 1):
        # 16:00 NY on calendar date d belongs to day key d (day runs 17:00 d-1 -> 17:00 d); 20:00 NY belongs to key d+1
        cal = M.days[t]
        if cal.dayofweek > 3: continue
        a = M.dh[t, 15]; b = M.dh[t + 1, 19] if (M.days[t + 1] - cal).days == 1 else -1
        if a < 0 or b < 0: continue
        j0 = a + 1  # entry at the open of the 16:00 bar == close of the 15:00 bar
        if j0 > b: continue
        rows.append(trade_row(M, 1, j0, M.o[j0], b, M.c[b]))
    return pd.DataFrame(rows)


def williams(M):
    import classics3
    return classics3.build_trades(M, "W112")


def portfolio(M, cand, P, w_cand=1.0):
    days = M.days[(M.days >= P[0]) & (M.days < P[1])]
    refs = {"sonic": sonic(M), "overnight": overnight(M), "williams": williams(M)}
    df = pd.DataFrame({k: lab.daily_pnl(v, days=days) for k, v in refs.items()})
    df["cand"] = lab.daily_pnl(cand, days=days)
    vol = df.std()
    base = sum(df[k] / vol[k] for k in refs); withc = base + w_cand * df.cand / vol.cand
    def st(x):
        eq = x.cumsum(); dd = (eq - eq.cummax()).min()
        return {"sharpe": round(float(x.mean() / x.std() * np.sqrt(252)), 2), "maxdd_over_vol": round(float(dd / x.std()), 1)}
    return {"corr": df.corr().round(3)["cand"].to_dict(), "base": st(base), "with_cand": st(withc), "cand_alone": st(df.cand),
            "refs_alone": {k: st(df[k]) for k in refs}}
