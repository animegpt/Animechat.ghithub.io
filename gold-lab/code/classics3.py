"""#123-#132 classics part 3 (prereg/PREREGISTRATION_123_132_classics3.md) + references (#112 Williams, Sonic, Overnight).
usage: python classics3.py disc|conf   |  OPEN_VAULT=1 python classics3.py vault NAME"""
import sys, json, numpy as np, pandas as pd
import lab
from lab import Mkt, oco_stop_trade, run_exit, trade_row

nan = np.nan


def wilder(x, n):
    return pd.Series(x).ewm(alpha=1 / n, adjust=False).mean().values


def rsi(x, n):
    d = np.r_[0, np.diff(x)]; up = wilder(np.maximum(d, 0), n); dn = wilder(np.maximum(-d, 0), n)
    return 100 - 100 / (1 + up / np.where(dn == 0, 1e-12, dn))


def sess_bars(M, t):
    """first session hour bar (08 NY), first tradable bar after it (09), session close bar (15:00-16:00 bar)"""
    return M.bar_at(t, 8), M.bar_at(t, 9), M.bar_at(t, 15)


def build_trades(M, name):
    D = M.D; O, H, L, C = (D[k].values for k in "ohlc"); n = len(C); rows = []; busy = -1
    o, h, l, c = M.o, M.h, M.l, M.c
    end_of_day = lambda t: M.e[min(t, n - 1)]

    if name == "PINBALL":
        lbr = rsi(np.r_[0, np.diff(C)], 3)  # RSI(3) of the 1-day change series
        for t in range(10, n):
            if M.s[t] <= busy: continue
            fh, f9, f16 = sess_bars(M, t)
            if min(fh, f9, f16) < 0 or f9 > f16: continue
            ohi, olo = h[fh], l[fh]
            if lbr[t - 1] < 30: od = [(1, ohi, olo, None)]
            elif lbr[t - 1] > 70: od = [(-1, olo, ohi, None)]
            else: continue
            r = oco_stop_trade(M, f9, f16, od, lambda j: f16)
            if r is None: continue
            if r["how"] == 0 and r["gross"] > 0 and t + 1 < n:      # carry to next day's 16:00, stop at entry
                g16 = M.bar_at(t + 1, 15)
                if g16 > f16:
                    xj, xp, how = run_exit(o, h, l, c, f16, r["side"], r["ep"], nan, g16, False)
                    r = trade_row(M, r["side"], r["j0"], r["ep"], xj, xp, how=how)
            rows.append(r); busy = r["jx"]

    elif name == "ORB60":
        for t in range(1, n):
            fh, f9, f16 = sess_bars(M, t)
            if min(fh, f9, f16) < 0 or f9 > f16: continue
            ohi, olo = h[fh], l[fh]
            r = oco_stop_trade(M, f9, f16, [(1, ohi, olo, None), (-1, olo, ohi, None)], lambda j: f16)
            if r is not None: rows.append(r)

    elif name == "SPECTRAP":
        for t in range(12, n):
            if M.s[t] <= busy: continue
            od = []
            for k in (1, 2, 3):
                b = t - k
                if b < 11: continue
                if C[b] > H[b - 10:b].max():
                    od.append((-1, L[b], max(H[b:t].max(), 0), None)); break
            for k in (1, 2, 3):
                b = t - k
                if b < 11: continue
                if C[b] < L[b - 10:b].min():
                    od.append((1, H[b], L[b:t].min(), None)); break
            if not od: continue
            r = oco_stop_trade(M, M.s[t], M.e[t], od, lambda j: M.e[t])
            if r is not None: rows.append(r); busy = r["jx"]

    elif name == "ANTI":
        ll = pd.Series(L).rolling(7).min().values; hh = pd.Series(H).rolling(7).max().values
        K = 100 * (C - ll) / np.where(hh - ll == 0, nan, hh - ll); Dd = pd.Series(K).rolling(10).mean().values
        for t in range(20, n):
            if M.s[t] <= busy: continue
            a, b, cc, d = K[t - 1], K[t - 2], K[t - 3], None
            od = []
            if Dd[t - 1] > Dd[t - 2] and b < cc and a > b: od.append((1, H[t - 1], L[t - 1], None))
            if Dd[t - 1] < Dd[t - 2] and b > cc and a < b: od.append((-1, L[t - 1], H[t - 1], None))
            if not od: continue
            r = oco_stop_trade(M, M.s[t], M.e[t], od, lambda j: end_of_day(t + 2))
            if r is not None: rows.append(r); busy = r["jx"]

    elif name in ("ICHIMOKU", "KELTNER"):
        if name == "ICHIMOKU":
            hh = lambda k: pd.Series(H).rolling(k).max().values; lo = lambda k: pd.Series(L).rolling(k).min().values
            ten = (hh(9) + lo(9)) / 2; kij = (hh(26) + lo(26)) / 2; sa = (ten + kij) / 2; sb = (hh(52) + lo(52)) / 2
            sa26 = np.r_[np.full(26, nan), sa[:-26]]; sb26 = np.r_[np.full(26, nan), sb[:-26]]
            top = np.fmax(sa26, sb26); bot = np.fmin(sa26, sb26)
            t = 80
            while t < n - 1:
                s = 0
                if ten[t] > kij[t] and ten[t - 1] <= kij[t - 1] and C[t] > top[t]: s = 1
                elif ten[t] < kij[t] and ten[t - 1] >= kij[t - 1] and C[t] < bot[t]: s = -1
                if s == 0: t += 1; continue
                u = t + 1
                while u < n - 1 and not ((s == 1 and ten[u] < kij[u]) or (s == -1 and ten[u] > kij[u])): u += 1
                j0 = M.s[t + 1]; jx = M.s[u + 1] if u + 1 < n else M.e[n - 1]
                xp = o[jx] if u + 1 < n else c[jx]
                rows.append(trade_row(M, s, j0, o[j0], jx, xp)); t = u
        else:
            tp = (H + L + C) / 3; mid = pd.Series(tp).rolling(10).mean().values; w = pd.Series(H - L).rolling(10).mean().values
            up, dn = mid + w, mid - w
            t = 12
            while t < n:
                r = oco_stop_trade(M, M.s[t], M.e[t], [(1, up[t - 1], None, None), (-1, dn[t - 1], None, None)], lambda j: M.e[t])
                if r is None: t += 1; continue
                s = r["side"]; d0 = t
                u = d0
                while u < n - 1 and not ((s == 1 and C[u] < mid[u]) or (s == -1 and C[u] > mid[u])): u += 1
                jx = M.e[u]
                rows.append(trade_row(M, s, r["j0"], r["ep"], jx, c[jx])); t = u + 1

    elif name.startswith("TD"):
        tf = name.split("_")[1]
        if tf == "D1":
            bO, bH, bL, bC = O, H, L, C; bs = M.s; be = M.e
        else:  # 4H bars anchored at 17:00 NY
            blk = ((M.nyh - 17) % 24) // 4; key = np.r_[0, np.cumsum((np.diff(blk) != 0) | (np.diff(M.dayof) != 0))]
            g = pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "k": key, "i": np.arange(len(o))}).groupby("k")
            A = g.agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), s=("i", "first"), e=("i", "last"))
            A = A[M.dayof[A.s.values] >= 0]
            bO, bH, bL, bC = (A[k].values for k in "ohlc"); bs = A.s.values; be = A.e.values
        nb = len(bC); pc = np.r_[bC[0], bC[:-1]]; tr = np.maximum(bH - bL, np.maximum(abs(bH - pc), abs(bL - pc)))
        bcnt = np.zeros(nb, int); scnt = np.zeros(nb, int)
        for i in range(4, nb):
            bcnt[i] = bcnt[i - 1] + 1 if bC[i] < bC[i - 4] else 0
            scnt[i] = scnt[i - 1] + 1 if bC[i] > bC[i - 4] else 0
        sig = []  # (bar index where signal completes, side, stop)
        if name.startswith("TD9"):
            for i in range(9, nb):
                if bcnt[i] == 9:
                    k = i - 8 + int(np.argmin(bL[i - 8:i + 1])); sig.append((i, 1, bL[k] - tr[k]))
                if scnt[i] == 9:
                    k = i - 8 + int(np.argmax(bH[i - 8:i + 1])); sig.append((i, -1, bH[k] + tr[k]))
        else:
            state = 0; cnt = 0; c8 = nan; ext = []; start = 0
            for i in range(9, nb):
                if bcnt[i] == 9: state, cnt, c8, ext, start = 1, 0, nan, [], i
                elif scnt[i] == 9: state, cnt, c8, ext, start = -1, 0, nan, [], i
                if state == 0: continue
                if state == 1 and bC[i] <= bL[i - 2]:
                    if cnt < 12:
                        cnt += 1; ext.append(i)
                        if cnt == 8: c8 = bC[i]
                    elif bL[i] <= c8:
                        ext.append(i); k = start + int(np.argmin(bL[start:i + 1])); sig.append((i, 1, bL[k] - tr[k])); state = 0
                elif state == -1 and bC[i] >= bH[i - 2]:
                    if cnt < 12:
                        cnt += 1; ext.append(i)
                        if cnt == 8: c8 = bC[i]
                    elif bH[i] >= c8:
                        ext.append(i); k = start + int(np.argmax(bH[start:i + 1])); sig.append((i, -1, bH[k] + tr[k])); state = 0
        for i, s, stp in sig:
            if i + 4 >= nb: continue
            j0 = bs[i + 1]
            if j0 <= busy: continue
            jx = be[i + 4]
            xj, xp, how = run_exit(o, h, l, c, j0, s, stp, nan, jx, True)
            if how == 1 and xj == j0: xp = min(stp, o[j0]) if s == 1 else max(stp, o[j0])
            rows.append(trade_row(M, s, j0, o[j0], xj, xp, how=how)); busy = xj

    elif name == "W112":
        rng = H - L
        for t in range(1, n):
            r1 = rng[t - 1]
            if r1 <= 0: continue
            r = oco_stop_trade(M, M.s[t], M.e[t], [(1, O[t] + 0.6 * r1, None, None), (-1, O[t] - 0.6 * r1, None, None)], lambda j: M.e[t])
            if r is not None: rows.append(r)
    return pd.DataFrame(rows)


NAMES = ["PINBALL", "ORB60", "SPECTRAP", "ANTI", "TD9_D1", "TD13_D1", "TD9_H4", "TD13_H4", "ICHIMOKU", "KELTNER"]
TWO = {k: True for k in NAMES}

if __name__ == "__main__":
    stage = sys.argv[1]
    M = Mkt(lab.load_hourly("XAUUSD"))
    P = {"disc": lab.DISC, "conf": lab.CONF, "vault": lab.VAULT}[stage]
    names = NAMES + ["W112"] if stage != "vault" else sys.argv[2].split(",")
    res = {}; trades = {}
    for nm in names:
        T = build_trades(M, nm); trades[nm] = T
        res[nm] = lab.summ(M, T, P, two_sided=True)
        r = res[nm]; print(stage, nm, r.get("n"), "gross", r.get("gross_bp"), "net1", r.get("net1", {}).get("bp"), r.get("net1", {}).get("t"),
                           "net2", r.get("net2", {}).get("bp"), "p_rand", r.get("p_rand"), "p_time", r.get("p_time"), flush=True)
    if stage == "disc":
        adj = lab.holm([res[k]["net1"]["p1"] if "net1" in res[k] else 1 for k in NAMES])
        for k, a in zip(NAMES, adj): res[k]["holm"] = round(float(a), 4)
    days = M.days[(M.days >= P[0]) & (M.days < P[1])]
    if "W112" in trades:
        w = lab.daily_pnl(trades["W112"], days=days)
        for nm in names:
            if nm != "W112" and len(trades[nm]): res[nm]["corr_W112"] = round(float(np.corrcoef(lab.daily_pnl(trades[nm], days=days), w)[0, 1]), 3)
    json.dump(res, open(f"{lab.HERE}/results/results_123_132_{stage}.json", "w"), indent=1, default=float)
    for nm in names:
        if len(trades[nm]): lab.period(trades[nm], P).to_csv(f"/home/user/lab/out/trades_{nm}_{stage}.csv", index=False)
