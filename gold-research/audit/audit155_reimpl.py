import sys; sys.path.insert(0, "/home/user/Animechat.ghithub.io/gold-research/code")
import numpy as np, pandas as pd, lab

def days(df):
    ny = df.index.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
    key = (ny + pd.Timedelta(hours=7)).normalize()
    g = pd.DataFrame({"k": key, "i": np.arange(len(df))})
    D = g.groupby("k").i.agg(["first", "last", "size"])
    D = D[(D["size"] >= 10) & (D.index.dayofweek <= 4)]
    return ny.hour.values, D

def net(side, ep, xp, spr):
    return 1e4*(side*(xp/ep-1) - 0.5*spr/ep - 0.5*spr/xp - 2e-5)

def run(inst, spr, vault):
    df = lab.load_hourly(inst, vault=vault)
    df = df[df.index < pd.Timestamp("2024-01-01")]
    o, h, l, c = (df[k].values.astype(float) for k in "ohlc")
    hr, D = days(df)
    rows = []
    S, E = D["first"].values, D["last"].values
    for d in range(1, len(D)):
        s, e = S[d], E[d]; ps, pe = S[d-1], E[d-1]
        R = h[ps:pe+1].max() - l[ps:pe+1].min()
        op = o[s]; up, dn = op + 0.6*R, op - 0.6*R
        if R <= 0: continue
        for j in range(s, e+1):
            tu, td = h[j] >= up, l[j] <= dn
            if tu or td: break
        else: continue
        C = next((k for k in range(s, e+1) if hr[k] == 13), None)
        cands = []
        for side, hit, lv in ((1, tu, up), (-1, td, dn)):
            if not hit: continue
            ep = max(o[j], lv) if side == 1 else min(o[j], lv)
            base = net(side, ep, c[e], spr)
            f1 = base; ch1 = False
            if hr[e] == 16 and e-1 >= s and hr[e-1] == 15 and j <= e-1 and side*(c[e-1]/o[e-1]-1) > 0:
                f1 = net(side, ep, c[e-1], spr); ch1 = True
            f2 = base; ch2 = False
            if C is not None and j <= C:
                f2 = net(side, ep, c[C], spr); ch2 = C != e
            cands.append((base, f1, f2, ch1, ch2))
        r = min(cands, key=lambda x: x[0])
        rows.append((D.index[d], *r))
    return pd.DataFrame(rows, columns=["k", "base", "f1", "f2", "ch1", "ch2"]).set_index("k")

def t(x): return x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))
def rep(T, name, a, b):
    x = T[(T.index.year >= a) & (T.index.year <= b)]
    out = f"{name} {a}-{b}: n={len(x)} base={x.base.mean():+.3f}bp t={t(x.base):.2f}"
    for v in ("f1", "f2"):
        dd = x[v]-x.base
        out += f" | {v}: changed={int(x['ch'+v[1]].sum())} dmean={dd.mean():+.3f} t={t(dd):.2f} var={x[v].mean():+.3f}"
    print(out)

G = run("XAUUSD", 0.24, False)
rep(G, "gold", 2004, 2016); rep(G, "gold", 2017, 2023)
Sv = run("XAGUSD", 0.025, True)
for a, b in ((2011, 2016), (2017, 2022), (2011, 2022), (2004, 2022)): rep(Sv, "silver", a, b)
