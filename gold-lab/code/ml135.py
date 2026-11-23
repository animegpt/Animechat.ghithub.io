"""#135 ML walk-forward ridge over the #133 library (prereg/PREREGISTRATION_135_138_round2.md)."""
import json, numpy as np, pandas as pd
import lab, bf
from lablog import log

CUM_BEFORE = 128756; NMIN = 150


def continuous(M, B):
    D = M.D; O, H, L, C = (D[k].values for k in "ohlc")
    pc = np.r_[C[0], C[:-1]]; tr = np.maximum(H - L, np.maximum(abs(H - pc), abs(L - pc)))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    r1 = np.r_[np.nan, np.log(C[1:] / C[:-1])]
    cols = [r1, (H - L) / atr, (C - L) / np.where(H - L == 0, np.nan, H - L)]
    cols += [(C - bf.sma(C, k)) / atr for k in (5, 10, 20, 50, 100, 200)]
    cols += [bf.rsi(C, 2), bf.rsi(C, 14)]
    cols += [np.r_[np.full(k, np.nan), np.log(C[k:] / C[:-k])] for k in (5, 20)]
    cols += [pd.Series(tr).rolling(5).mean().values / pd.Series(tr).rolling(20).mean().values, pd.Series(r1).rolling(20).std().values]
    daily = np.vstack([bf.lag(x.astype(float)) for x in cols])            # known at t from t-1
    atr_l = bf.lag(atr)
    F = {}
    o, h, l, c = M.o, M.h, M.l, M.c
    for E in bf.ES:
        jE = M.dh[:, E]; nd = len(M.days); x = np.full((3, nd), np.nan)
        for t in np.flatnonzero(jE > M.s):
            a, b = M.s[t], jE[t] - 1
            x[0, t] = (c[b] - o[a]) / atr_l[t]; x[1, t] = (h[a:b + 1].max() - l[a:b + 1].min()) / atr_l[t]; x[2, t] = (c[b] - o[b]) / atr_l[t]
        F[E] = np.vstack([B["C"][E][1:].astype(float), daily, x]).T          # drop 'always'
    return F


def ridge_fit_predict(Xtr, ytr, Xte):
    mu = np.nanmean(Xtr, 0); sd = np.nanstd(Xtr, 0); sd[~np.isfinite(sd) | (sd == 0)] = 1; mu[~np.isfinite(mu)] = 0
    A = np.nan_to_num((Xtr - mu) / sd); T = np.nan_to_num((Xte - mu) / sd)
    ym = ytr.mean(); lam = 0.1 * len(ytr)
    w = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ (ytr - ym))
    return T @ w + ym


def run(M, B, F, years, shift=0, dsel_all=None):
    """returns per config arrays of per-trade (net1, net2) over the predicted years, and the trade masks"""
    nd = len(M.days); yr = M.days.year.values; res = {}
    cost = np.full(nd, np.nan)
    for (E, X) in bf.windows():
        jE = M.dh[:, E]
        cost = np.where(jE >= 0, 0.24 / M.o[np.maximum(jE, 0)] + 2 * lab.SLIP, np.nan)
        for st in (0, 1):
            gL, n1L, n2L = B["Y"][(E, X, st, 1)]; gS, n1S, n2S = B["Y"][(E, X, st, -1)]
            tgt = gL.copy()
            if shift:  # circular shift of the target (and its realised outcomes) inside the usable range
                idx = np.arange(nd); sh = np.roll(idx, shift)
                tgt = tgt[sh]; n1L, n2L, n1S, n2S, gL = n1L[sh], n2L[sh], n1S[sh], n2S[sh], gL[sh]
            out1 = []; out2 = []; sides = []; tdays = []
            for Y in years:
                tr = np.flatnonzero((yr < Y) & np.isfinite(tgt)); te = np.flatnonzero((yr == Y) & np.isfinite(tgt))
                if len(tr) < 500 or len(te) == 0: continue
                p = ridge_fit_predict(F[E][tr], tgt[tr], F[E][te])
                lg = p > cost[te]; sh_ = p < -cost[te]
                out1 += list(n1L[te][lg]) + list(n1S[te][sh_]); out2 += list(n2L[te][lg]) + list(n2S[te][sh_])
                sides += [1] * int(lg.sum()) + [-1] * int(sh_.sum()); tdays += list(te[lg]) + list(te[sh_])
            res[(E, X, st)] = (np.array(out1), np.array(out2), np.array(sides), np.array(tdays, int))
    return res


def score(res):
    rows = []
    for k, (a, b, s, d) in res.items():
        n = len(a); t1 = lab.tstat(a) if n >= NMIN else -np.inf; t2 = lab.tstat(b) if n >= NMIN else -np.inf
        rows.append(dict(cfg=k, n=n, mean1=a.mean() if n else np.nan, t1=t1, t2=t2, long_frac=(s == 1).mean() if n else np.nan))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    M = lab.Mkt(lab.load_hourly("XAUUSD")); B = bf.build(M); F = continuous(M, B)
    disc_years = range(2008, 2017); conf_years = range(2017, 2024)
    real = score(run(M, B, F, disc_years)); real = real.sort_values("t1", ascending=False)
    print(real.head(15).to_string(), flush=True)
    disc = np.flatnonzero((M.days >= lab.DISC[0]) & (M.days < lab.DISC[1]))
    RN = bf.gen_rules(B, CUM_BEFORE + 72, 133)
    rng = np.random.default_rng(1350); nulls = []
    for k in range(20):
        sh = int(rng.integers(250, len(M.days) - 250))
        sn = score(run(M, B, F, disc_years, shift=sh)); m1 = sn.t1.max()
        shd = int(sh % len(disc)) if sh % len(disc) >= 250 else 250
        SN = bf.evaluate(B, RN, disc, shift=shd); m2 = SN.t1[SN.n >= NMIN].max()
        nulls.append(float(max(m1, m2))); print("null", k, round(m1, 3), round(m2, 3), flush=True)
    thr = float(np.percentile(nulls, 95)); print("threshold", thr, flush=True)
    surv = real[(real.t1 > thr) & (real.t2 >= 2)]
    out = {"threshold_t1": thr, "nulls": nulls, "top": real.head(10).astype({"cfg": str}).to_dict("records"), "n_surv": len(surv)}
    if len(surv):
        cr = score(run(M, B, F, conf_years)); out["conf_of_survivors"] = cr[cr.cfg.isin(surv.cfg)].astype({"cfg": str}).to_dict("records")
        print(out["conf_of_survivors"])
    json.dump(out, open(f"{lab.HERE}/results/results_135.json", "w"), indent=1, default=float)
    log({"id": "135", "test": "ML walk-forward ridge, 72 same-day targets, OOS 2008-2016 (prereg 135_138)", "trials_added": 72, "cum_trials": CUM_BEFORE + 72,
         "threshold_t1": thr, "best_real_t1": float(real.t1.max()), "best_cfg": str(real.iloc[0].cfg), "n_survivors_disc": len(surv),
         "conf_of_survivors": out.get("conf_of_survivors")})
