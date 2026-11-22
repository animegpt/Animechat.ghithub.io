"""#85 ZA session-VWAP trend, #86 weekly anchored VWAP, with TWAP placebo (prereg/PREREGISTRATION_85_87_vwap.md).
usage: BARS=1m GDATA=<dir with raw/> python vwap85.py disc|conf|vault"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("BARS", "1m")
from numba import njit
from scipy import stats
import shortlib as sl

P = {"disc": (pd.Timestamp("2017-01-01"), pd.Timestamp("2021-01-01")), "conf": (pd.Timestamp("2021-01-01"), pd.Timestamp("2024-01-01")),
     "vault": (pd.Timestamp("2024-01-01"), pd.Timestamp("2026-11-01"))}
SLIP = 0.1e-4
COST = {"A": (0.24, 0.0), "B": (0.03, 0.07), "G": (0.0, 0.0)}
NEWS = ((745, 760), (805, 820), (835, 850), (895, 910), (1075, 1090), (1135, 1150))


@njit(cache=True)
def line(tp, v, anchor, weighted):
    n = len(tp); out = np.full(n, np.nan); s1 = 0.0; s2 = 0.0; active = False
    for i in range(n):
        if anchor[i]: s1 = 0.0; s2 = 0.0; active = True
        if not active: continue
        w = v[i] if weighted else 1.0
        s1 += tp[i] * w; s2 += w
        out[i] = s1 / s2 if s2 > 0 else np.nan
    return out


@njit(cache=True)
def backtest(o, c, ln, decide, flat_end, start_ok, dayid, ndays, spread, comm, news):
    """decide[t]: decision at close of t -> fill at open of t+1. flat_end[t]: close everything at close of t.
    start_ok[t]: decisions allowed. Returns daily pnl (fraction of notional, 1x) and flips per day."""
    n = len(c); pnl = np.zeros(ndays); flips = np.zeros(ndays); pos = 0.0; lastF = 0.0; pend = np.nan
    for t in range(n):
        d = dayid[t]
        if not np.isnan(pend):
            F = o[t]
            if pos != 0.0: pnl[d] += pos * (F / lastF - 1.0)
            ch = abs(pend - pos)
            if ch > 0:
                m = 3.0 if news[t] else 1.0
                pnl[d] -= ch * (0.5 * spread * m / F + 0.5 * comm / F + SLIP); flips[d] += ch
            pos = pend; lastF = F; pend = np.nan
        if flat_end[t]:
            if pos != 0.0:
                F = c[t]; m = 3.0 if news[t] else 1.0
                pnl[d] += pos * (F / lastF - 1.0) - abs(pos) * (0.5 * spread * m / F + 0.5 * comm / F + SLIP); flips[d] += abs(pos)
            pos = 0.0; continue
        if decide[t] and start_ok[t] and not np.isnan(ln[t]):
            q = 1.0 if c[t] > ln[t] else (-1.0 if c[t] < ln[t] else pos)
            if q != pos: pend = q
    return pnl, flips


class D:
    def __init__(self):
        df = sl.load_minutes(); df = df[df.index >= pd.Timestamp("2017-01-01", tz="UTC")]
        self.df = df; self.o, self.h, self.l, self.c, self.v = (df[k].values.astype(np.float64) for k in "ohlcv")
        self.tp = (self.h + self.l + self.c) / 3
        ny = df.index.tz_convert("America/New_York").tz_localize(None); self.ny = ny
        self.nym = (ny.hour * 60 + ny.minute).values; self.dow = ny.dayofweek.values
        utc = df.index; um = (utc.hour * 60 + utc.minute).values
        news = np.zeros(len(df), bool)
        for a, b in NEWS: news |= (um >= a) & (um < b)
        self.news = news
        tday = (ny + pd.Timedelta(hours=6)).normalize()       # trading day starts 18:00 NY
        self.days, self.dayid = np.unique(tday.values, return_inverse=True)
        self.dayid = self.dayid.astype(np.int64)
        self.date = ny.normalize().values


def za(Dd, bar, weighted, sc):
    nym = Dd.nym; d = Dd.date
    sess = (nym >= 570) & (nym < 960)
    first = sess & np.r_[True, (d[1:] != d[:-1]) | ~sess[:-1]]              # first session minute of the date
    anchor = first.copy()
    ln = line(Dd.tp, Dd.v, anchor, weighted); ln[~sess] = np.nan
    if bar == 1: decide = sess & (nym >= 574) & (nym <= 958)
    else: decide = sess & (nym >= 574) & (nym <= 954) & ((nym + 1) % 5 == 0)
    # flat at close of the last session minute of each date
    last = sess & np.r_[(d[1:] != d[:-1]) | ~sess[1:], True]
    sp, cm = COST[sc]
    return backtest(Dd.o, Dd.c, ln, decide, last, np.ones(len(nym), np.bool_), Dd.dayid, len(Dd.days), sp, cm, Dd.news)


def avwap(Dd, weighted, sc, shift_h=None, rng=None):
    ny = Dd.ny; nym = Dd.nym; dow = Dd.dow
    wk = ((ny + pd.Timedelta(hours=6)).to_period("W-SUN")).asi8     # trading week (Sun 18:00 NY ->)
    wk = np.asarray(wk)
    newwk = np.r_[True, wk[1:] != wk[:-1]]
    tns = ny.values.astype("datetime64[m]").astype(np.int64)
    if shift_h is None:
        anchor = newwk; start_ok = dow != 6                                      # decisions from Mon 00:00 NY
    else:
        starts = np.flatnonzero(newwk); anchor = np.zeros(len(nym), np.bool_); start_ok = np.zeros(len(nym), np.bool_)
        bounds = np.r_[starts, len(nym)]
        for k in range(len(starts)):
            a, b = bounds[k], bounds[k + 1]
            tgt = tns[a] + int(rng.uniform(0, 48) * 60)
            j = a + int(np.searchsorted(tns[a:b], tgt)); j = min(j, b - 1)
            anchor[j] = True
            okfrom = a + int(np.searchsorted(tns[a:b], tns[j] + 60)); start_ok[okfrom:b] = True
    ln = line(Dd.tp, Dd.v, anchor, weighted)
    decide = (nym % 60 == 59) & (dow <= 4) & ~((dow == 4) & (nym >= 900))       # hour closes Mon..Fri 15:00 NY
    flat = (dow == 4) & (nym == 959)                                             # Friday 16:00 NY bar close
    sp, cm = COST[sc]
    return backtest(Dd.o, Dd.c, ln, decide, flat, start_ok, Dd.dayid, len(Dd.days), sp, cm, Dd.news)


def st(x):
    x = np.asarray(x); n = len(x); t = x.mean() / (x.std(ddof=1) / np.sqrt(n)) if n > 2 and x.std() > 0 else 0.0
    return {"days": int(n), "bp_day": round(float(x.mean() * 1e4), 3), "day_t": round(float(t), 2), "ann_pct": round(float(x.mean() * 252 * 100), 2),
            "p1": float(stats.t.sf(t, max(n - 1, 1)))}


if __name__ == "__main__":
    which = sys.argv[1]; a, b = P[which]
    if which == "vault": assert sl.OPEN_VAULT
    Dd = D(); dd = pd.DatetimeIndex(Dd.days)
    act = (dd >= a) & (dd < b)
    out = {}
    for name, fn in (("ZA_1m", lambda w, s: za(Dd, 1, w, s)), ("ZA_5m", lambda w, s: za(Dd, 5, w, s)), ("AVWAP_WEEK", lambda w, s: avwap(Dd, w, s))):
        r = {}
        for sc in ("gross", "A", "B"):
            for w, lab in ((True, "VWAP"), (False, "TWAP")):
                pnl, fl = fn(w, sc if sc != "gross" else "G")
                tr = fl > 0
                r[f"{lab}_{sc}"] = {**st(pnl[act & tr]), "flips_day": round(float(fl[act & tr].mean()), 2)}
                r[f"_{lab}_{sc}_series"] = pnl
            dif = r[f"_VWAP_{sc}_series"] - r[f"_TWAP_{sc}_series"]
            mask = act & ((r[f"_VWAP_{sc}_series"] != 0) | (r[f"_TWAP_{sc}_series"] != 0))
            r[f"VWAPminusTWAP_{sc}"] = st(dif[mask])
        out[name] = {k: v for k, v in r.items() if not k.startswith("_")}
        print(name, json.dumps({k: (v["bp_day"], v["day_t"], v.get("flips_day")) for k, v in out[name].items()}), flush=True)
        if name == "AVWAP_WEEK":
            rng = np.random.default_rng(86); sims = []
            for s_ in range(200):
                pnl, fl = avwap(Dd, True, "B", shift_h=True, rng=rng); m = act & (fl > 0)
                sims.append(pnl[m].mean() if m.any() else np.nan)
            sims = np.array(sims); real = out[name]["VWAP_B"]["bp_day"] / 1e4
            out[name]["random_anchor_B"] = {"mean_bp_day": round(float(np.nanmean(sims) * 1e4), 3), "p": float((np.sum(sims >= real) + 1) / (len(sims) + 1))}
            print("random anchor", out[name]["random_anchor_B"], flush=True)
    names = list(out); adj = sl.holm([out[k]["VWAP_B"]["p1"] for k in names])
    for k, h in zip(names, adj): out[k]["holm_B"] = float(h)
    print({k: round(out[k]["holm_B"], 4) for k in names})
    json.dump(out, open(f"{sl.HERE}/results_85_86_{which}.json", "w"), indent=1)
