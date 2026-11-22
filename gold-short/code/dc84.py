"""#84 DC overshoot fade on silver (+ gold comparison, same window). prereg/PREREGISTRATION_84_dc_fade_silver.md
usage: python dc84.py <silver raw dir> <gold raw dir> <out json>"""
import sys, os, json, lzma, numpy as np, pandas as pd
from numba import njit

SLIP = 0.1e-4
W0, W1 = pd.Timestamp("2023-11-01"), pd.Timestamp("2026-11-01")


def parse(path, t0):
    raw = lzma.decompress(open(path, "rb").read())
    a = np.frombuffer(raw, dtype=">i4").reshape(-1, 6).astype(np.int64)
    v = np.frombuffer(raw, dtype=">f4").reshape(-1, 6)[:, 5]
    df = pd.DataFrame({"o": a[:, 1], "c": a[:, 2], "l": a[:, 3], "h": a[:, 4]}, index=t0 + pd.to_timedelta(a[:, 0], unit="s")) / 1000.0
    return df[v > 0]


def load(d):
    out = [parse(f"{d}/{f}", pd.Timestamp(f[:10])) for f in sorted(os.listdir(d))
           if os.path.getsize(f"{d}/{f}") > 0 and W0 <= pd.Timestamp(f[:10]) < W1]
    df = pd.concat(out).sort_index(); return df[~df.index.duplicated()]


@njit(cache=True)
def run(C, O, H, L, nyh, tmin, th, k, stopm, cap, sidef):
    """port of code/dcfade58.run (gross returns) + side filter (0 both, 1 long only, -1 short only)"""
    n = len(C); oi = np.empty(n, np.int64); ox = np.empty(n, np.int64); og = np.empty(n); os_ = np.empty(n, np.int64); ohow = np.empty(n, np.int64); m_ = 0
    dcf = np.zeros(n, np.int8)
    mode = 0; hi = C[0]; lo = C[0]; dcpx = C[0]; ddir = 0; faded = False
    pos = 0; e = 0.0; stop = 0.0; ei = 0
    for i in range(1, n):
        p = C[i]; dc_now = False
        if mode == 0:
            if p > hi: hi = p
            if p < lo: lo = p
            if p <= hi * (1 - th): mode = -1; lo = p; dc_now = True; ddir = -1; dcpx = p
            elif p >= lo * (1 + th): mode = 1; hi = p; dc_now = True; ddir = 1; dcpx = p
        elif mode == 1:
            if p > hi: hi = p
            elif p <= hi * (1 - th): mode = -1; lo = p; dc_now = True; ddir = -1; dcpx = p
        else:
            if p < lo: lo = p
            elif p >= lo * (1 + th): mode = 1; hi = p; dc_now = True; ddir = 1; dcpx = p
        if dc_now: dcf[i] = 1
        if pos != 0 and i > ei:
            xp = -1.0; how = 0
            if pos == 1 and L[i] <= stop: xp = min(stop, O[i]); how = 1
            elif pos == -1 and H[i] >= stop: xp = max(stop, O[i]); how = 1
            elif dc_now: xp = p; how = 2
            elif cap > 0 and tmin[i] - tmin[ei] >= cap: xp = p; how = 3
            if xp > 0:
                oi[m_] = ei; ox[m_] = i; og[m_] = pos * (xp / e - 1); os_[m_] = pos; ohow[m_] = how; m_ += 1; pos = 0
        if dc_now: faded = False
        if pos == 0 and not faded and not dc_now and ddir != 0 and i + 1 < n:
            hh = nyh[i]
            if (ddir == 1 and p >= dcpx * (1 + k * th)) or (ddir == -1 and p <= dcpx * (1 - k * th)):
                faded = True
                if not (hh <= 2 or hh == 16 or hh == 17) and (sidef == 0 or sidef == -ddir):
                    pos = -ddir; ei = i + 1; e = O[i + 1]; stop = e * (1 - pos * stopm * th)
                    if (pos == 1 and L[i + 1] <= stop) or (pos == -1 and H[i + 1] >= stop):
                        oi[m_] = ei; ox[m_] = ei; og[m_] = pos * (stop / e - 1); os_[m_] = pos; ohow[m_] = 1; m_ += 1; pos = 0
    return oi[:m_], ox[:m_], og[:m_], os_[:m_], ohow[:m_], dcf


@njit(cache=True)
def rand_exit(ent, side, C, O, H, L, tmin, dcf, th, stopm, cap):
    n = len(C); g = np.empty(len(ent)); xi = np.empty(len(ent), np.int64)
    for k in range(len(ent)):
        ei = ent[k]; s = side[k]; e = O[ei]; stop = e * (1 - s * stopm * th); xp = C[n - 1]; x = n - 1
        if (s == 1 and L[ei] <= stop) or (s == -1 and H[ei] >= stop):
            xp = stop; x = ei
        else:
            for i in range(ei + 1, n):
                if s == 1 and L[i] <= stop: xp = min(stop, O[i]); x = i; break
                if s == -1 and H[i] >= stop: xp = max(stop, O[i]); x = i; break
                if dcf[i] == 1: xp = C[i]; x = i; break
                if cap > 0 and tmin[i] - tmin[ei] >= cap: xp = C[i]; x = i; break
        g[k] = s * (xp / e - 1); xi[k] = x
    return g, xi


def analyse(df, spread_usd, label, nsim=500, seed=84):
    O, H, L, C = (df[k].values.astype(np.float64) for k in "ohlc")
    ny = df.index.tz_localize("UTC").tz_convert("America/New_York")
    nyh = ny.hour.values.astype(np.int64); tmin = df.index.values.astype("datetime64[m]").astype(np.int64)
    tday = (ny + pd.Timedelta("6h")).normalize().tz_localize(None).values
    ym = (ny.year * 100 + ny.month).values; mod = (ny.hour * 60 + ny.minute).values
    key = ym.astype(np.int64) * 10000 + mod
    order = np.argsort(key, kind="stable"); ks = key[order]
    out = {"bars": int(len(C)), "price_min": round(float(C.min()), 3), "price_max": round(float(C.max()), 3)}
    rng = np.random.default_rng(seed)
    for th in (0.002, 0.003):
        for sidef, sn in ((0, "both"), (1, "long"), (-1, "short")):
            ii, xx, g, sd, how, dcf = run(C, O, H, L, nyh, tmin, th, 2.0, 3.0, 1440, sidef)
            net = g - (spread_usd / O[ii] + 2 * SLIP)
            dg = pd.Series(g).groupby(tday[ii]).sum(); dn = pd.Series(net).groupby(tday[ii]).sum()
            tt = lambda s: float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))) if len(s) > 10 else 0.0
            # random baseline: same month, same NY minute of day, same side & exit rule
            lo = np.searchsorted(ks, key[ii], "left"); hi = np.searchsorted(ks, key[ii], "right")
            means = np.empty(nsim)
            for s_ in range(nsim):
                pick = order[np.minimum(lo + (rng.random(len(ii)) * (hi - lo)).astype(np.int64), len(ks) - 1)]
                pick = np.minimum(pick, len(C) - 2)
                rg, _ = rand_exit(pick, sd, C, O, H, L, tmin, dcf, th, 3.0, 1440)
                means[s_] = rg.mean()
            days = len(np.unique(tday))
            out[f"th{th*100:.1f}_{sn}"] = {
                "n": int(len(g)), "per_day": round(len(g) / days, 2), "gross_bp": round(float(g.mean() * 1e4), 3), "gross_day_t": round(tt(dg), 2),
                "net_bp": round(float(net.mean() * 1e4), 3), "net_day_t": round(tt(dn), 2), "win_gross": round(float((g > 0).mean()), 3),
                "stop_share": round(float((how == 1).mean()), 3), "hold_min": round(float((tmin[xx] - tmin[ii]).mean()), 1),
                "rand_gross_bp": round(float(means.mean() * 1e4), 3), "p_rand": float((np.sum(means >= g.mean()) + 1) / (nsim + 1)),
                "by_year_gross_bp": {int(y): round(float(v * 1e4), 2) for y, v in pd.Series(g, index=df.index[ii]).groupby(df.index[ii].year).mean().items()}}
            r = out[f"th{th*100:.1f}_{sn}"]
            print(f"{label} th={th*100:.1f}% {sn:5s} n={r['n']:5d} /day={r['per_day']} gross={r['gross_bp']:6.2f}bp t={r['gross_day_t']:5.2f} "
                  f"net={r['net_bp']:6.2f} (t {r['net_day_t']}) win={r['win_gross']} stop={r['stop_share']} hold={r['hold_min']}m "
                  f"rand={r['rand_gross_bp']} p={r['p_rand']:.4f} years={r['by_year_gross_bp']}", flush=True)
    return out


if __name__ == "__main__":
    sdir, gdir, outp = sys.argv[1:4]
    res = {}
    s = load(sdir); print("silver", len(s), s.index.min(), s.index.max(), "price", s.c.min(), s.c.max(), flush=True)
    assert 15 < s.c.median() < 80, "silver price scale looks wrong"
    res["XAGUSD"] = analyse(s, 0.025, "XAG")
    g = load(gdir); print("gold", len(g), g.index.min(), g.index.max(), flush=True)
    res["XAUUSD"] = analyse(g, 0.24, "XAU")
    json.dump(res, open(outp, "w"), indent=1)
