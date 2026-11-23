"""#89 watch-list patterns on 1968-1998 (Bundesbank) and #90 COT crowding (prereg/PREREGISTRATION_89_91_three_doors.md).
usage: python doors89_90.py <hist dir> [conf]"""
import sys, os, re, glob, zipfile, io, json, numpy as np, pandas as pd
from scipy import stats

SWAP = 0.4316 / 4000; SLIP = 0.1e-4


def bb(path):
    rows = []
    for line in open(path, encoding="utf-8-sig"):
        p = line.strip().split(",")
        if len(p) >= 2 and re.match(r"\d{4}-\d{2}-\d{2}$", p[0]) and p[1] not in (".", ""):
            rows.append((pd.Timestamp(p[0]), float(p[1])))
    return pd.Series(dict(rows)).sort_index()


def gold_usd(H):
    g = bb(f"{H}/bb_D.XAU.DEM.EA.AC.C01.csv"); fx = bb(f"{H}/bb_D.USD.DEM.AA.AC.000.csv")
    j = pd.concat([g, fx], axis=1, keys=["g", "fx"]).dropna()
    return (j.g / j.fx / 32.1507).rename("p")


def trade(P, d0, d1, side=1):
    pe, px = P[d0], P[d1]; g = side * (px / pe - 1)
    cost = 0.12 / pe + 0.12 / px + 2 * SLIP + (SWAP * (d1 - d0).days if side == 1 else 0.0)
    return g - cost, g


def st(x, label=""):
    x = np.asarray(x); n = len(x)
    if n < 3: return {"n": n}
    t = x.mean() / (x.std(ddof=1) / np.sqrt(n))
    return {"n": int(n), "net_bp": round(float(x.mean() * 1e4), 2), "t": round(float(t), 2), "win": round(float((x > 0).mean()), 3),
            "p1": float(stats.t.sf(t, n - 1))}


def fomc_dates(H):
    out = []
    for f in sorted(glob.glob(f"{H}/fomc/*.htm")):
        y = int(os.path.basename(f)[:4]); s = open(f, encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:-(?:(January|February|March|April|May|June|July|August|September|October|November|December)\s+)?(\d{1,2}))?\s+Meeting\s*-\s*(\d{4})", s):
            mon = m.group(3) or m.group(1); day = m.group(4) or m.group(2)
            try: out.append(pd.Timestamp(f"{day} {mon} {m.group(5)}"))
            except Exception: pass
    return sorted(set(out))


def door1(P, H):
    d = P.index; res = {}; T = {}
    ym = d.to_period("M"); g = pd.Series(d, index=d).groupby(ym)
    months = sorted(set(ym))
    tom = []
    for k in range(len(months) - 1):
        cur = g.get_group(months[k]).values; nxt = g.get_group(months[k + 1]).values
        if len(cur) < 2 or len(nxt) < 3: continue
        tom.append(trade(P, pd.Timestamp(cur[-2]), pd.Timestamp(nxt[2])))
    T["TOM"] = tom
    jf = []
    for y in range(1969, 1999):
        dec = d[(d.year == y - 1) & (d.month == 12)]; feb = d[(d.year == y) & (d.month == 2)]
        if len(dec) and len(feb): jf.append(trade(P, dec[-1], feb[-1]))
    T["JANFEB"] = jf
    fr = []
    for x in d[d.dayofweek == 3]:
        y_ = x + pd.Timedelta(days=1)
        if y_ in P.index: fr.append(trade(P, x, y_))
    T["FRI"] = fr
    pf = []; pf94 = []
    for D in fomc_dates(H):
        if D not in P.index: continue
        k = P.index.get_loc(D)
        if k == 0: continue
        r = trade(P, P.index[k - 1], D); pf.append(r)
        if D.year >= 1994: pf94.append(r)
    T["PREFOMC"] = pf
    for k, v in T.items():
        res[k] = {**st([a for a, b in v]), "gross_bp": round(float(np.mean([b for a, b in v]) * 1e4), 2)}
    adj = holm([res[k]["p1"] for k in res])
    for k, a in zip(res, adj): res[k]["holm_p"] = round(float(a), 4); res[k]["pass"] = bool(res[k]["net_bp"] > 0 and res[k]["t"] >= 2 and a < 0.05)
    res["PREFOMC_1994_1998_descriptive"] = st([a for a, b in pf94])
    res["n_fomc_dates"] = len(fomc_dates(H))
    return res


def holm(p):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p); adj = np.empty(m); run = 0
    for r, k in enumerate(o): run = max(run, (m - r) * p[k]); adj[k] = min(1, run)
    return adj


def cot_legacy(H):
    frames = []
    for z in sorted(glob.glob(f"{H}/cot/deacot*.zip")):
        with zipfile.ZipFile(z) as zz:
            for nm in zz.namelist():
                df = pd.read_csv(zz.open(nm), low_memory=False)
                df.columns = [c.strip() for c in df.columns]
                code = df["CFTC Contract Market Code"].astype(str).str.strip()
                frames.append(df[code == "088691"])
    df = pd.concat(frames)
    dcol = [c for c in df.columns if "YYYY-MM-DD" in c][0]
    out = pd.DataFrame({"date": pd.to_datetime(df[dcol]), "oi": df["Open Interest (All)"].astype(float),
                        "nl": df["Noncommercial Positions-Long (All)"].astype(float), "ns": df["Noncommercial Positions-Short (All)"].astype(float)})
    out = out.drop_duplicates("date").set_index("date").sort_index()
    out["net"] = (out.nl - out.ns) / out.oi
    out["pct"] = out.net.rolling(156, min_periods=156).apply(lambda a: (a <= a[-1]).mean(), raw=True)
    return out


def door2(P, C, start, end, hold=20):
    C = C[(C.index >= start - pd.Timedelta(days=7)) & (C.index < end)]
    res = {}
    for name, flag, side in (("CS_LONG", C.pct <= 0.10, 1), ("CL_SHORT", C.pct >= 0.90, -1)):
        f = flag.values; starts = C.index[np.r_[False, f[1:] & ~f[:-1]] | (np.r_[f[:1], np.zeros(len(f) - 1, bool)] & False)]
        trs = []; busy = pd.Timestamp("1900-01-01")
        for dt in starts:
            avail = dt + pd.Timedelta(days=4)
            k = P.index.searchsorted(avail)
            if k + hold >= len(P): continue
            d0 = P.index[k]
            if d0 < start or d0 >= end or d0 <= busy: continue
            d1 = P.index[k + hold]; trs.append(trade(P, d0, d1, side)); busy = d1
        res[name] = {**st([a for a, b in trs]), "gross_bp": round(float(np.mean([b for a, b in trs]) * 1e4), 2) if trs else None}
    adj = holm([res[k].get("p1", 1) for k in res])
    for k, a in zip(res, adj): res[k]["holm_p"] = round(float(a), 4)
    return res


if __name__ == "__main__":
    H = sys.argv[1]; P = gold_usd(H)
    print("gold USD/oz", P.index.min().date(), P.index.max().date(), len(P), "range", round(P.min(), 1), round(P.max(), 1))
    r1 = door1(P, H); print("#89", json.dumps(r1, indent=0))
    C = cot_legacy(H); print("COT rows", len(C), C.index.min().date(), C.index.max().date())
    r2 = door2(P, C, pd.Timestamp("1986-01-01"), pd.Timestamp("1999-01-01")); print("#90 discovery", json.dumps(r2))
    json.dump({"door1": r1, "door2_disc": r2}, open(os.path.join(os.path.dirname(__file__), "..", "results_89_90.json"), "w"), indent=1, default=float)
