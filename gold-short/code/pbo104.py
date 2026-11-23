"""#104 PBO via CSCV + #105 robust plateau. Builds monthly-return matrices for Sonic grid and DC grid here;
the Overnight matrix is built by pbo104_overnight.py (research working copy). usage: BARS=1h GDATA=... python pbo104.py build|analyse"""
import os, sys, json, itertools, numpy as np, pandas as pd
from scipy import stats
os.environ["BARS"] = "1h"
import shortlib as sl
OUT = sl.HERE + "/pbo"


def sonic(m, nd, nt):
    b = m[["o", "h", "l", "c"]]; o, h, l, c = (b[k].values for k in "ohlc"); n = len(c)
    bclose = (b.index + pd.Timedelta(hours=1)).tz_convert(None)
    ema = lambda x, s: pd.Series(x).ewm(span=s, adjust=False).mean().values
    eh, el, ec, et = ema(h, nd), ema(l, nd), ema(c, nd), ema(c, nt)
    pc = np.r_[c[0], c[:-1]]; tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))); atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    mid = (eh + el) / 2; sh5 = lambda x: np.r_[np.full(5, np.nan), x[:-5]]
    up = (mid > et) & (mid > sh5(mid)) & (et > sh5(et)); dn = (mid < et) & (mid < sh5(mid)) & (et < sh5(et))
    tl = pd.Series(l <= ec).rolling(5).max().values > 0; ts = pd.Series(h >= ec).rolling(5).max().values > 0; pcl = np.r_[c[0], c[:-1]]
    L = up & tl & (c > eh) & (pcl <= np.r_[eh[0], eh[:-1]]); S = dn & ts & (c < el) & (pcl >= np.r_[el[0], el[:-1]])
    ll10 = pd.Series(l).rolling(10).min().values; hh10 = pd.Series(h).rolling(10).max().values
    ev = sorted([(k, 1) for k in np.flatnonzero(L) if k > 1300] + [(k, -1) for k in np.flatnonzero(S) if k > 1300]); rows = []; busy = -1
    for k, s in ev:
        if k <= busy: continue
        stop = min(ll10[k], c[k] - 0.5 * atr[k]) if s == 1 else max(hh10[k], c[k] + 0.5 * atr[k])
        xe = min(k + 240, n - 1); px = None; xt = xe
        for kk in range(k + 1, xe + 1):
            if s == 1 and l[kk] <= stop: px = min(stop, o[kk]); xt = kk; break
            if s == -1 and h[kk] >= stop: px = max(stop, o[kk]); xt = kk; break
            if (s == 1 and c[kk] < el[kk]) or (s == -1 and c[kk] > eh[kk]): px = c[kk]; xt = kk; break
        if px is None: px = c[xe]; xt = xe
        e = c[k]; net = s * (px / e - 1) - (0.24 / e + 2e-5)
        rows.append((bclose[xt], 0.01 * net / (abs(e - stop) / e))); busy = xt
    T = pd.Series([r for _, r in rows], index=pd.DatetimeIndex([t for t, _ in rows]))
    return T.groupby(T.index.to_period("M")).sum()


def dc_grid():
    os.environ["BARS"] = "1m"
    import importlib; importlib.reload(sl)
    import dc84
    m = sl.load_minutes(); m = m[m.index >= pd.Timestamp("2017-01-01", tz="UTC")]
    O, H, L, C = (m[k].values.astype(np.float64) for k in "ohlc")
    ny = m.index.tz_convert("America/New_York"); nyh = ny.hour.values.astype(np.int64)
    tmin = m.index.values.astype("datetime64[m]").astype(np.int64); mon = m.index.tz_convert(None).to_period("M")
    cols = {}
    for th in (0.0010, 0.0015, 0.0020, 0.0025, 0.0030):
        for k in (1.5, 2.0, 2.5):
            for sm in (2.0, 3.0, 4.0):
                ii, xx, g, sd, how, _ = dc84.run(C, O, H, L, nyh, tmin, th, k, sm, 1440, 0)
                net = g - (0.10 / O[ii] + 2e-5)
                cols[f"dc_{th*100:.2f}_{k}_{int(sm)}"] = pd.Series(net, index=mon[ii]).groupby(level=0).sum()
    return pd.DataFrame(cols).fillna(0.0)


def cscv(M, S=16, embargo=False):
    M = M.dropna(); T = len(M) - len(M) % S; X = M.values[-T:]; blocks = np.array_split(np.arange(T), S); N = X.shape[1]
    lam = []; oos_best = []; is_best = []
    for comb in itertools.combinations(range(S), S // 2):
        isb = set(comb); oob = [b for b in range(S) if b not in isb]
        if embargo: oob = [b for b in oob if (b - 1) not in isb and (b + 1) not in isb]
        if len(oob) < 2: continue
        I = np.concatenate([blocks[b] for b in sorted(isb)]); O_ = np.concatenate([blocks[b] for b in oob])
        sr_i = X[I].mean(0) / X[I].std(0, ddof=1); sr_o = X[O_].mean(0) / X[O_].std(0, ddof=1)
        best = int(np.nanargmax(sr_i)); rank = (stats.rankdata(sr_o)[best]) / (N + 1)
        lam.append(np.log(rank / (1 - rank))); oos_best.append(sr_o[best]); is_best.append(sr_i[best])
    lam = np.array(lam); oos_best = np.array(oos_best); is_best = np.array(is_best)
    slope = float(np.polyfit(is_best, oos_best, 1)[0]) if len(lam) > 2 else np.nan
    return {"splits": int(len(lam)), "PBO": round(float((lam <= 0).mean()), 3), "P_oos_best_negative": round(float((oos_best < 0).mean()), 3),
            "median_oos_sharpe_of_is_best_monthly": round(float(np.median(oos_best)), 3), "degradation_slope": round(slope, 3)}


def dsr(series, family, n_trials=48730):
    r = series.values; srs = (family.mean() / family.std()).values
    p, sr, sr0 = sl.deflated_sharpe(r, n_trials, float(np.var(srs, ddof=1)))
    return {"DSR": round(p, 4), "SR_monthly": round(sr, 3), "SR0_hurdle": round(sr0, 3), "ann_sharpe": round(sr * np.sqrt(12), 2), "months": int(len(r))}


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if sys.argv[1] == "build":
        import long97 as LF
        m = LF.hourly(); cols = {}
        for nd in (21, 28, 34, 40, 48, 55):
            for nt in (55, 75, 89, 105, 144, 200):
                cols[f"s_{nd}_{nt}"] = sonic(m, nd, nt); print("sonic", nd, nt, flush=True)
        S = pd.DataFrame(cols); S = S[(S.index >= pd.Period("2004-01", "M")) & (S.index <= pd.Period("2023-12", "M"))].fillna(0.0)
        S.to_csv(f"{OUT}/sonic_grid_monthly.csv")
        D = dc_grid(); D = D[D.index <= pd.Period("2023-12", "M")]; D.to_csv(f"{OUT}/dc_grid_monthly.csv"); print("dc grid", D.shape)
    else:
        res = {}
        S = pd.read_csv(f"{OUT}/sonic_grid_monthly.csv", index_col=0); D = pd.read_csv(f"{OUT}/dc_grid_monthly.csv", index_col=0)
        O = pd.read_csv(f"{OUT}/overnight_grid_monthly.csv", index_col=0)
        res["sonic"] = {**cscv(S, 16, embargo=True), "no_embargo": cscv(S, 16), **dsr(S["s_34_89"], S)}
        res["overnight"] = {**cscv(O, 16), **dsr(O["on_q0.5_d3"], O)}
        res["dc"] = {**cscv(D, 12), **dsr(D["dc_0.20_2.0_3"], D)}
        # module 2: plateau
        win = {"2004-08": ("2004", "2008"), "2009-13": ("2009", "2013"), "2014-18": ("2014", "2018"), "2019-23": ("2019", "2023")}
        S.index = pd.PeriodIndex(S.index, freq="M"); heat = {}
        for w, (a, b) in win.items():
            X = S[(S.index.year >= int(a)) & (S.index.year <= int(b))]; heat[w] = (X.mean() / X.std() * np.sqrt(12))
        H = pd.DataFrame(heat)
        nds, nts = [21, 28, 34, 40, 48, 55], [55, 75, 89, 105, 144, 200]
        def grid(col): return np.array([[H.loc[f"s_{a}_{b}", col] for b in nts] for a in nds])
        smooth = {}
        for w in win:
            g = grid(w); pad = np.pad(g, 1, mode="edge")
            smooth[w] = np.array([[pad[i:i + 3, j:j + 3].mean() for j in range(6)] for i in range(6)])
        minw = np.min(np.stack(list(smooth.values())), axis=0); raw_min = np.min(np.stack([grid(w) for w in win]), axis=0)
        bi, bj = np.unravel_index(np.argmax(minw), minw.shape)
        res["plateau"] = {"heat_annual_sharpe_by_window": {w: pd.DataFrame(grid(w), index=nds, columns=nts).round(2).to_dict() for w in win},
                          "min_over_windows_smoothed": pd.DataFrame(minw, index=nds, columns=nts).round(2).to_dict(),
                          "live_34_89_min_smoothed": round(float(minw[2, 2]), 3), "live_rank_of_36": int((minw > minw[2, 2]).sum()) + 1,
                          "robust_centre": f"{nds[bi]}/{nts[bj]}", "robust_centre_min_smoothed": round(float(minw[bi, bj]), 3),
                          "live_raw_min_over_windows": round(float(raw_min[2, 2]), 3), "share_configs_positive_all_windows": round(float((raw_min > 0).mean()), 3)}
        O.index = pd.PeriodIndex(O.index, freq="M"); ow = {}
        for w, (a, b) in {"2012-15": (2012, 2015), "2016-19": (2016, 2019), "2020-23": (2020, 2023)}.items():
            X = O[(O.index.year >= a) & (O.index.year <= b)]; ow[w] = (X.mean() / X.std() * np.sqrt(12)).round(2).to_dict()
        res["overnight_threshold_by_window"] = ow
        print(json.dumps({k: v for k, v in res.items() if k != "plateau"}, indent=1)); print(json.dumps({k: v for k, v in res["plateau"].items() if not k.startswith("heat")}, indent=1))
        json.dump(res, open(f"{sl.HERE}/results_104_105.json", "w"), indent=1, default=float)
