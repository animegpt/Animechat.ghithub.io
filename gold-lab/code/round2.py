"""#136 ASIANBRK, #137 PREFOMC, #138 TOM (prereg/PREREGISTRATION_135_138_round2.md). usage: python round2.py disc|conf"""
import sys, json, numpy as np, pandas as pd
import lab, bf
from lab import oco_stop_trade, trade_row
from lablog import log

CUM = 128831


def asianbrk(M):
    rows = []; h, l = M.h, M.l
    for t in range(len(M.days)):
        a = M.dh[t, 19]; b = M.dh[t, 2]; s3 = M.dh[t, 3]; e15 = M.dh[t, 15]
        if min(a, b, s3, e15) < 0 or not (a < b < s3 <= e15): continue
        hi = h[a:b + 1].max(); lo = l[a:b + 1].min()
        r = oco_stop_trade(M, s3, e15, [(1, hi, lo, None), (-1, lo, hi, None)], lambda j: e15)
        if r is not None: rows.append(r)
    return pd.DataFrame(rows)


def prefomc(M, dates):
    rows = []; cal = pd.DatetimeIndex(M.days)
    for d in dates:
        d = pd.Timestamp(d)
        if d not in cal: continue
        t = cal.get_loc(d)
        if t < 1: continue
        # 14:00 NY on the previous trading date belongs to day key of that date
        a = M.dh[t - 1, 14]; b = M.dh[t, 13]
        if a < 0 or b < 0 or b <= a: continue
        rows.append(trade_row(M, 1, a, M.o[a], b, M.c[b]))
    return pd.DataFrame(rows)


def tom(M):
    rows = []; days = M.days; mo = days.to_period("M")
    starts = np.flatnonzero(np.r_[True, mo[1:] != mo[:-1]])
    for s in starts:
        if s < 2 or s + 2 >= len(days): continue
        t_entry = s - 1                      # last trading day of the previous month: enter at its first bar open
        j0 = M.s[t_entry]; jx = M.e[s + 2]   # exit at the close of the 3rd trading day
        rows.append(trade_row(M, 1, j0, M.o[j0], jx, M.c[jx]))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    stage = sys.argv[1]; P = {"disc": lab.DISC, "conf": lab.CONF}[stage]
    M = lab.Mkt(lab.load_hourly("XAUUSD"))
    dates = [d for d in json.load(open("/home/user/lab/raw/fomc/fomc_dates.json")) if d not in ("2020-03-03", "2020-03-15")]
    T = {"ASIANBRK": asianbrk(M), "PREFOMC": prefomc(M, dates), "TOM": tom(M)}
    res = {k: lab.summ(M, v, P, two_sided=(k == "ASIANBRK")) for k, v in T.items()}
    if stage == "disc":
        adj = lab.holm([res[k]["net1"]["p1"] if "net1" in res[k] else 1 for k in T])
        for k, a in zip(T, adj): res[k]["holm"] = float(a)
    for k, r in res.items(): print(stage, k, json.dumps(r, default=float))
    json.dump(res, open(f"{lab.HERE}/results/results_136_138_{stage}.json", "w"), indent=1, default=float)
    if stage == "disc":
        log({"id": "136-138", "test": "Asian-range breakout, pre-FOMC drift, turn-of-month (prereg 135_138)", "trials_added": 3, "cum_trials": CUM,
             "disc": {k: {"n": v.get("n"), "net1_bp": v.get("net1", {}).get("bp"), "t1": v.get("net1", {}).get("t"), "t2": v.get("net2", {}).get("t"),
                          "holm": v.get("holm"), "p_rand": v.get("p_rand"), "p_time": v.get("p_time")} for k, v in res.items()}})
