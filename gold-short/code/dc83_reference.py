"""Reference simulation of the GoldDCFade EA rules (prereg #83 + amendment A) on historical gold minutes.
Only for checking the EA's behaviour (trades/day, exit mix, trade list to compare with the MT5 tester), never as evidence.
usage: python dc83_reference.py <gold raw minute dir> <start> <end> <out csv>"""
import sys, numpy as np, pandas as pd
from numba import njit
import dc84

@njit(cache=True)
def run(C, O, H, L, nyh, nymin, tmin, th, k, stopm, cap):
    n = len(C); oi = np.empty(n, np.int64); ox = np.empty(n, np.int64); og = np.empty(n); os_ = np.empty(n, np.int64); ohow = np.empty(n, np.int64)
    osig = np.empty(n, np.int64); m_ = 0
    mode = 0; hi = C[0]; lo = C[0]; dcpx = C[0]; ddir = 0; faded = False; pos = 0; e = 0.0; stop = 0.0; ei = 0; si = 0
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
        if pos != 0 and i > ei:
            xp = -1.0; how = 0
            if pos == 1 and L[i] <= stop: xp = min(stop, O[i]); how = 1
            elif pos == -1 and H[i] >= stop: xp = max(stop, O[i]); how = 1
            elif dc_now: xp = p; how = 2
            elif cap > 0 and tmin[i] - tmin[ei] >= cap: xp = p; how = 3
            elif nymin[i] >= 1005 and nymin[i] < 1080: xp = p; how = 4          # 16:45-17:59 New York force close (amendment A)
            if xp > 0:
                oi[m_] = ei; ox[m_] = i; og[m_] = pos * (xp / e - 1); os_[m_] = pos; ohow[m_] = how; osig[m_] = si; m_ += 1; pos = 0
        if dc_now: faded = False
        if pos == 0 and not faded and not dc_now and ddir != 0 and i + 1 < n:
            hh = nyh[i]
            if (ddir == 1 and p >= dcpx * (1 + k * th)) or (ddir == -1 and p <= dcpx * (1 - k * th)):
                faded = True
                if not (hh <= 2 or hh == 16 or hh == 17):
                    pos = -ddir; ei = i + 1; si = i; e = O[i + 1]; stop = e * (1 - pos * stopm * th)
                    if (pos == 1 and L[i + 1] <= stop) or (pos == -1 and H[i + 1] >= stop):
                        oi[m_] = ei; ox[m_] = ei; og[m_] = pos * (stop / e - 1); os_[m_] = pos; ohow[m_] = 1; osig[m_] = si; m_ += 1; pos = 0
    return oi[:m_], ox[:m_], og[:m_], os_[:m_], ohow[:m_], osig[:m_]

if __name__ == "__main__":
    d, a, b, out = sys.argv[1:5]
    dc84.W0 = pd.Timestamp(a) - pd.Timedelta(days=10); dc84.W1 = pd.Timestamp(b)     # 10 days warm-up for the DC state
    df = dc84.load(d)
    O, H, L, C = (df[k].values.astype(np.float64) for k in "ohlc")
    ny = df.index.tz_localize("UTC").tz_convert("America/New_York")
    nyh = ny.hour.values.astype(np.int64); nymin = (ny.hour * 60 + ny.minute).values.astype(np.int64)
    tmin = df.index.values.astype("datetime64[m]").astype(np.int64)
    ii, xx, g, sd, how, si = run(C, O, H, L, nyh, nymin, tmin, 0.002, 2.0, 3.0, 1440)
    T = pd.DataFrame({"signal_time_utc": df.index[si], "entry_time_utc": df.index[ii], "side": np.where(sd == 1, "BUY", "SELL"),
                      "signal_price": C[si], "entry_open": O[ii], "exit_time_utc": df.index[xx],
                      "exit_reason": pd.Series(how).map({1: "SL", 2: "DC", 3: "24h", 4: "EOD"}).values,
                      "gross_bp": np.round(g * 1e4, 3), "hold_min": tmin[xx] - tmin[ii]})
    T = T[T.entry_time_utc >= pd.Timestamp(a)]
    T.to_csv(out, index=False)
    days = len(np.unique((ny[ny >= pd.Timestamp(a, tz="UTC")] + pd.Timedelta("6h")).normalize()))
    raw_bp = (0.03 + 0.07) / T.entry_open + 2 * 0.1e-4
    print(f"{a}..{b}: trades {len(T)} | per trading day {len(T)/days:.2f} | exits {T.exit_reason.value_counts().to_dict()} | "
          f"mean gross {T.gross_bp.mean():.2f} bp | Raw-est net {(T.gross_bp - raw_bp*1e4).mean():.2f} bp | hold {T.hold_min.mean():.0f} min | "
          f"buys {int((T.side=='BUY').sum())} sells {int((T.side=='SELL').sum())}")
