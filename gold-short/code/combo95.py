"""#95 weak-signal combination + cost-aware trading (prereg/PREREGISTRATION_95_96_machine.md).
usage: BARS=1m GDATA=... python combo95.py disc|conf"""
import os, sys, json, numpy as np, pandas as pd
os.environ.setdefault("BARS", "1m")
from numba import njit
from scipy import stats
import os88_lib as L
import shortlib as sl

H = 30


def components(D):
    c = D.c
    mo, osh = L.dcstate(c, 0.002); s1 = -np.clip(osh, -4, 4)
    X = np.log(c) - np.log(pd.Series(c).ewm(span=60, adjust=False).mean().values)
    s = pd.Series(X).rolling(1440, min_periods=720).std().values; s2 = -np.clip(X / s, -4, 4)
    s3 = (((D.nym >= 960) & (D.nym < 1200)) & (D.nydow <= 3)).astype(float)
    m = pd.DataFrame({"h": D.h, "l": D.l, "c": c}, index=D.idx).resample("1h", label="left", closed="left").agg({"h": "max", "l": "min", "c": "last"}).dropna()
    eh, el, e89 = L.ema(m.h.values, 34), L.ema(m.l.values, 34), L.ema(m.c.values, 89); mid = (eh + el) / 2
    up = (mid > e89) & (mid > L.shift(mid, 5)) & (e89 > L.shift(e89, 5)); dn = (mid < e89) & (mid < L.shift(mid, 5)) & (e89 < L.shift(e89, 5))
    reg = np.where(up, 1.0, np.where(dn, -1.0, 0.0))
    close_t = (m.index + pd.Timedelta("1h")).values.astype("datetime64[ns]").astype(np.int64)
    p = np.searchsorted(close_t, D.tns + 60 * 10 ** 9, side="right") - 1
    s4 = np.where(p >= 0, reg[np.clip(p, 0, None)], 0.0)
    r240 = np.log(c) - np.log(L.shift(c, 240)); s5 = np.where(np.abs(r240) > 0.0075, np.sign(r240), 0.0)
    S = np.vstack([s1, s2, s3, s4, s5]).T
    return np.nan_to_num(S)


def target(D):
    o = D.o; n = len(o); y = np.full(n, np.nan)
    i1 = np.arange(n) + 1; i2 = np.arange(n) + 1 + H; ok = i2 < n
    dt = np.zeros(n); dt[ok] = (D.tns[i2[ok]] - D.tns[i1[ok]]) / 6e10
    good = ok & (dt <= H + 10)
    y[good] = (np.log(o[i2[good]]) - np.log(o[i1[good]])) * 1e4
    return y


@njit(cache=True)
def engine(o, f, cB, sidecost, flatz, newsn, tau, minstep, noband, dayid, ndays):
    n = len(o); pnl = np.zeros(ndays); x = 0.0; pend = 0.0; haspend = False; turnover = 0.0
    for t in range(n - 1):
        if haspend:
            dlt = abs(pend - x)
            pnl[dayid[t]] -= dlt * sidecost[t]; turnover += dlt; x = pend; haspend = False
        pnl[dayid[t]] += x * (o[t + 1] / o[t] - 1.0)
        # decide at close of t for open of t+1
        if flatz[t + 1]:
            tgt = 0.0
        else:
            ft = f[t]; c = cB[t]
            if noband: tgt = max(-1.0, min(1.0, ft / c))
            else: tgt = (1.0 if ft > 0 else -1.0) * min(1.0, (abs(ft) - c) / c) if abs(ft) > c else 0.0
        if flatz[t + 1]: new = 0.0
        elif noband: new = tgt
        else:
            new = x + tau * (tgt - x)
            if abs(new - x) < minstep: new = x
        if newsn[t + 1] and abs(new) > abs(x): new = x
        if new != x: pend = new; haspend = True
    return pnl, turnover


class Run:
    def __init__(self):
        self.D = D = L.Data()
        self.S = components(D); self.y = target(D)
        de = D.disc_end; self.de = de
        mu = self.S[:de].mean(0); sd = self.S[:de].std(0); sd[sd == 0] = 1; self.Z = (self.S - mu) / sd
        P = D.o
        self.cB = ((0.03 + 0.07) / P + 2 * 0.1e-4) * 1e4
        tm = D.tm
        self.flatz = ((tm >= 1245) & (tm <= 1395)) | ((D.dow == 4) & (tm >= 1170)) | (D.dow == 5) | (D.dow == 6)
        self.side = {}
        for k, (sp, cm, sm) in {"A": (0.24, 0.0, 1), "B": (0.03, 0.07, 1), "C": (0.06, 0.14, 2)}.items():
            self.side[k] = 0.5 * sp * np.where(D.news, 3, 1) / P + 0.5 * cm / P + sm * 0.1e-4
        rows = np.arange(0, de, 5); ok = np.isfinite(self.y[rows]) & ~D.noentry[np.minimum(rows + 1, D.n - 1)]
        self.fit_rows = rows[ok]

    def ridge(self):
        Zr = self.Z[self.fit_rows]; yr = self.y[self.fit_rows]; n = len(yr)
        Xd = np.c_[np.ones(n), Zr]; lam = 0.01 * n; I = np.eye(6); I[0, 0] = 0
        b = np.linalg.solve(Xd.T @ Xd + lam * I, Xd.T @ yr); return b
    def gk(self):
        Zr = self.Z[self.fit_rows]; yr = self.y[self.fit_rows]
        ic = np.array([np.corrcoef(Zr[:, i], yr)[0, 1] for i in range(5)]); return ic, np.r_[0.0, ic * yr.std()]
    def uni(self, i):
        Zr = self.Z[self.fit_rows, i]; yr = self.y[self.fit_rows]; b, a = np.polyfit(Zr, yr, 1)
        w = np.zeros(6); w[0] = a; w[1 + i] = b; return w
    def forecast(self, w): return w[0] + self.Z @ w[1:]

    def evaluate(self, f, lo, hi, noband=False, scen=("A", "B", "C")):
        D = self.D; out = {}
        sl_ = slice(lo, hi); dayid = D.dayid[sl_] - D.dayid[lo]; nd = int(dayid.max()) + 1
        for k in scen:
            pnl, to = engine(D.o[sl_], f[sl_], self.cB[sl_], self.side[k][sl_], self.flatz[sl_], D.news[sl_], 0.25, 0.1, noband, dayid, nd)
            act = pnl != 0; x = pnl[act]
            t = float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else 0.0
            out[k] = {"bp_day": round(float(pnl.sum() / nd * 1e4), 3), "day_t": round(t, 2), "ann_pct": round(float(pnl.sum() / nd * 252 * 100), 2),
                      "turnover_day": round(float(to / nd), 2), "p1": float(stats.t.sf(t, max(len(x) - 1, 1)))}
        return out


if __name__ == "__main__":
    which = sys.argv[1]; R = Run(); D = R.D
    lo, hi = (0, R.de) if which == "disc" else (R.de, D.conf_end)
    names = ["DC_FADE", "OU", "OVERNIGHT", "SONIC_H1", "SCALE_LAW"]
    wr = R.ridge(); ic, wg = R.gk()
    res = {"ridge_w": wr.round(4).tolist(), "gk_ic": ic.round(4).tolist(), "gk_w": wg.round(4).tolist(), "fit_rows": int(len(R.fit_rows))}
    fr = R.forecast(wr); fg = R.forecast(wg)
    res["COMBO_RIDGE"] = R.evaluate(fr, lo, hi); res["COMBO_GK"] = R.evaluate(fg, lo, hi)
    res["NOBAND_RIDGE"] = R.evaluate(fr, lo, hi, noband=True, scen=("B",))
    for i, nm in enumerate(names): res[f"SINGLE_{nm}"] = R.evaluate(R.forecast(R.uni(i)), lo, hi, scen=("B",))
    for k in ["COMBO_RIDGE", "COMBO_GK", "NOBAND_RIDGE"] + [f"SINGLE_{n}" for n in names]: print(which, k, json.dumps(res[k]), flush=True)
    rng = np.random.default_rng(95); sims = []; sdr = fr[lo:hi].std()
    for k in range(200):
        w = np.r_[0.0, rng.normal(size=5)]; f = R.forecast(w); f = f * (sdr / f[lo:hi].std())
        sims.append(R.evaluate(f, lo, hi, scen=("B",))["B"]["bp_day"])
    sims = np.array(sims)
    for k in ("COMBO_RIDGE", "COMBO_GK"):
        res[k]["placebo_p"] = float((np.sum(sims >= res[k]["B"]["bp_day"]) + 1) / 201)
    res["placebo_mean_bp_day"] = round(float(sims.mean()), 3); res["placebo_p95_bp_day"] = round(float(np.percentile(sims, 95)), 3)
    if which == "disc":
        adj = sl.holm([res[k]["B"]["p1"] for k in ("COMBO_RIDGE", "COMBO_GK")])
        res["COMBO_RIDGE"]["holm"], res["COMBO_GK"]["holm"] = float(adj[0]), float(adj[1])
    print("weights ridge", res["ridge_w"], "IC", res["gk_ic"], "placebo", res["placebo_mean_bp_day"], res["placebo_p95_bp_day"],
          {k: res[k].get("placebo_p") for k in ("COMBO_RIDGE", "COMBO_GK")}, {k: res[k].get("holm") for k in ("COMBO_RIDGE", "COMBO_GK")}, flush=True)
    json.dump(res, open(f"{sl.HERE}/results_95_{which}.json", "w"), indent=1, default=float)
