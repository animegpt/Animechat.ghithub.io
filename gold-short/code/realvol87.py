"""#87 descriptive: real-volume VWAP (PAXG/USDT, Binance) vs TWAP; same measures on Dukascopy XAUUSD tick volume.
usage: BARS=1m GDATA=... python realvol87.py <paxg csv dir> <out json>"""
import os, sys, glob, json, numpy as np, pandas as pd
os.environ.setdefault("BARS", "1m")
import vwap85 as V

def measures(df, label):
    o, h, l, c, v = (df[k].values.astype(float) for k in "ohlcv"); tp = (h + l + c) / 3
    ny = df.index.tz_convert("America/New_York").tz_localize(None); nym = (ny.hour * 60 + ny.minute).values; d = ny.normalize().values
    sess = (nym >= 570) & (nym < 960); first = sess & np.r_[True, (d[1:] != d[:-1]) | ~sess[:-1]]
    vw = V.line(tp, v, first, True); tw = V.line(tp, v, first, False); vw[~sess] = np.nan; tw[~sess] = np.nan
    m = sess & (nym >= 600) & ~np.isnan(vw)                  # from 10:00 NY (30 min into the session)
    gap = np.abs(vw[m] - tw[m]) / c[m] * 1e4
    agree = np.mean(np.sign(c[m] - vw[m]) == np.sign(c[m] - tw[m]))
    # ZA 1m rule zero cost, VWAP vs TWAP (descriptive)
    tday = (ny + pd.Timedelta(hours=6)).normalize(); days, dayid = np.unique(tday.values, return_inverse=True)
    news = np.zeros(len(c), bool); last = sess & np.r_[(d[1:] != d[:-1]) | ~sess[1:], True]
    dec = sess & (nym >= 574) & (nym <= 958); ok = np.ones(len(c), np.bool_)
    r = {}
    for lab, ln in (("VWAP", vw), ("TWAP", tw)):
        pnl, fl = V.backtest(o, c, ln, dec, last, ok, dayid.astype(np.int64), len(days), 0.0, 0.0, news)
        x = pnl[fl > 0]; r[lab] = {"gross_bp_day": round(float(x.mean() * 1e4), 3), "day_t": round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2), "flips_day": round(float(fl[fl > 0].mean()), 1)}
    out = {"minutes": int(m.sum()), "median_abs_vwap_minus_twap_bp": round(float(np.median(gap)), 2), "p90_abs_gap_bp": round(float(np.percentile(gap, 90)), 2),
           "sign_agreement": round(float(agree), 4), "ZA_zero_cost": r, "median_minute_volume": float(np.median(v[sess]))}
    print(label, json.dumps(out), flush=True); return out

if __name__ == "__main__":
    pdir, outp = sys.argv[1:3]
    rows = []
    for f in sorted(glob.glob(f"{pdir}/PAXGUSDT-1m-*.csv")):
        x = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4, 5]); x.columns = ["t", "o", "h", "l", "c", "v"]; rows.append(x)
    p = pd.concat(rows); unit = "us" if p.t.max() > 1e14 else "ms"
    p.index = pd.to_datetime(p.t, unit=unit, utc=True); p = p[["o", "h", "l", "c", "v"]].astype(float); p = p[~p.index.duplicated()].sort_index()
    p = p[p.index < pd.Timestamp("2024-01-01", tz="UTC")]
    res = {"PAXG_real_volume": measures(p, "PAXG")}
    D = V.D(); g = D.df[(D.df.index >= p.index.min()) & (D.df.index < pd.Timestamp("2024-01-01", tz="UTC"))]
    res["XAU_dukascopy_tick_volume"] = measures(g, "XAU")
    # agreement of the two VWAP decisions on common minutes: does PAXG-volume weighting move the XAU line?
    g = g.copy(); g.index = pd.DatetimeIndex(g.index).as_unit("ns"); pv = p[["v"]].rename(columns={"v": "pv"}); pv.index = pd.DatetimeIndex(pv.index).as_unit("ns")
    j = g.join(pv, how="inner")
    j = j[j.pv > 0]
    res["XAU_prices_weighted_by_PAXG_volume"] = measures(j.assign(v=j.pv)[["o", "h", "l", "c", "v"]], "XAU_w_PAXGvol")
    json.dump(res, open(outp, "w"), indent=1)
