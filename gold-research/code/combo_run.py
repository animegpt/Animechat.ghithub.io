"""#158-#161 runner. usage: python combo_run.py build | ai | base | ind | alloc | silver | all
Caches in /home/user/lab/cache/combo/. Results in results/results_158..161*.json"""
import os, sys, json, pickle, warnings
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, combo158 as K, metric149 as MT
warnings.filterwarnings("ignore")
CD = f"{lab.CACHE}/combo"; os.makedirs(CD, exist_ok=True); RES = f"{lab.HERE}/results"
TEST = list(range(2009, 2024)); P_ALL = ("2009-01-01", "2024-01-01"); P_D = ("2009-01-01", "2017-01-01"); P_C = ("2017-01-01", "2024-01-01")
SIZES = {"plan": dict(sonic=0.0015, on=1.0, w=0.5), "live": dict(sonic=0.003, on=2.0, w=0.5)}
CUM_BEFORE = 350217


def load_eur(vault=False):
    d = f"{lab.RAW}/EURUSD/BID"
    if not os.path.isdir(d) or len(os.listdir(d)) < 200: return None
    try: return lab.load_hourly("EURUSD", vault=vault)
    except Exception as e: print("EUR load failed", e); return None


# ------------------------------------------------------------------ build
def build(inst="XAUUSD", vault=False, tag="gold"):
    M = lab.Mkt(lab.load_hourly(inst, vault=vault), inst); E = K.EA(M)
    S = K.sim_sonic(E, inst)
    eur_df = load_eur(vault=True)
    eur, cov = K.eur_returns(E, eur_df)
    O = K.sim_overnight(E, eur, S)
    W = K.sim_williams(M)
    meta = {"eur_coverage": cov, "eur_available": eur_df is not None}
    pickle.dump(dict(S=S, O=O, W=W, meta=meta), open(f"{CD}/trades_{tag}.pkl", "wb"))
    print(tag, "sonic", len(S), "overnight", len(O), "williams", len(W), meta)
    return M, E


def load(tag="gold"):
    return pickle.load(open(f"{CD}/trades_{tag}.pkl", "rb"))


# ------------------------------------------------------------------ walk-forward AI reproductions
def rank_mult(p, train_p):
    q = np.quantile(train_p, np.linspace(0, 1, 101))
    out = np.empty(len(p))
    for k, x in enumerate(p):
        if x < q[0]: out[k] = 0.5; continue
        j = np.searchsorted(q, x, side="right")
        if j >= len(q): out[k] = 1.5; continue
        lo, hi = q[j - 1], q[j]
        out[k] = 0.5 + ((j - 1) + ((x - lo) / (hi - lo) if hi > lo else 0.0)) / (len(q) - 1)
    return out


def sonic_R(S, scn, inst="XAUUSD"):
    return K.net_returns(S, scn, inst) * S.ep.values / S.dist.values


def hgb():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=300, max_depth=3, learning_rate=0.05, min_samples_leaf=20, early_stopping=False, random_state=0)


def on_frozen_prob(X):
    Z = np.where(np.isnan(X), K.ON_MEAN, X)
    s = K.ON_ICPT + ((Z - K.ON_MEAN) / K.ON_SD) @ K.ON_COEF
    return 1 / (1 + np.exp(-s))


def ai():
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    D = load(); S, O = D["S"], D["O"]
    X = np.vstack(S.feats.values); yS = (sonic_R(S, "A") > 0).astype(int); yr = S.t0.dt.year.values
    S["ai_mult"] = np.nan; finals = {}
    for Y in TEST + [2024]:
        tr = (yr >= 2005) & (yr < Y); m = hgb().fit(X[tr], yS[tr]); ptr = m.predict_proba(X[tr])[:, 1]
        if Y == 2024: finals["sonic"] = (m, ptr); continue
        te = yr == Y
        if te.any(): S.loc[te, "ai_mult"] = rank_mult(m.predict_proba(X[te])[:, 1], ptr)
    XO = np.vstack(O.feats.values); yO = (O.xp.values / O.ep.values - 1 > 0).astype(int); yro = O.t0.dt.year.values
    pf = on_frozen_prob(XO); cal = (yro >= 2004) & (yro <= 2008)
    q = float((pf[cal] <= K.ON_THR).mean())
    O["ai_take"] = np.nan; O["frozen_take"] = pf > K.ON_THR
    for Y in TEST + [2024]:
        tr = (yro >= 2005) & (yro < Y); Xt = XO[tr]; mu = np.nanmean(Xt, 0)
        Xi = np.where(np.isnan(XO), mu, XO)
        sc = StandardScaler().fit(Xi[tr]); lr = LogisticRegression(C=1.0, max_iter=2000).fit(sc.transform(Xi[tr]), yO[tr])
        ptr = lr.predict_proba(sc.transform(Xi[tr]))[:, 1]; thr = float(np.quantile(ptr, q))
        if Y == 2024: finals["on"] = (sc, lr, thr, mu); continue
        te = yro == Y
        if te.any(): O.loc[te, "ai_take"] = (lr.predict_proba(sc.transform(Xi[te]))[:, 1] > thr).astype(float)
    D.update(S=S, O=O, finals=finals, q=q); pickle.dump(D, open(f"{CD}/trades_gold.pkl", "wb"))
    t = S[S.t0.dt.year >= 2009]; o = O[O.t0.dt.year >= 2009]
    print("sonic ai_mult 2009-23 mean", round(t.ai_mult.mean(), 3), "| overnight q", round(q, 3), "take share WF", round(o.ai_take.mean(), 3),
          "frozen", round(o.frozen_take.mean(), 3))


# ------------------------------------------------------------------ portfolio
def months(P):
    return pd.period_range(P[0], pd.Timestamp(P[1]) - pd.Timedelta(days=1), freq="M")


def monthly(tx, r, P):
    ms = months(P); s = pd.Series(r, index=pd.DatetimeIndex(tx).to_period("M")).groupby(level=0).sum()
    return s.reindex(ms).fillna(0.0)


def strat_returns(D, scn, sz, inst="XAUUSD", P=P_ALL, w_size=None, s_size=None, o_size=None):
    """per-strategy monthly return series (fraction of equity) for one cost scenario and size set"""
    S, O, W = D["S"], D["O"], D["W"]
    a, b = pd.Timestamp(P[0]), pd.Timestamp(P[1])
    s = S[(S.t0 >= a) & (S.t0 < b)]; o = O[(O.t0 >= a) & (O.t0 < b)]; w = W[(W.t0 >= a) & (W.t0 < b)]
    mult = s.ai_mult.fillna(1.0).values if "ai_mult" in s else np.ones(len(s))
    rs = sz["sonic"] * mult * sonic_R(s, scn, inst) * (s_size.loc[s.index].values if s_size is not None else 1)
    take = o.ai_take.values > 0.5 if "ai_take" in o else np.ones(len(o), bool)
    ro_all = sz["on"] * K.net_returns(o, scn, inst)
    ro = ro_all * take * (o_size.loc[o.index].values if o_size is not None else 1)
    rw = sz["w"] * K.net_returns(w, scn, inst) * (w_size.loc[w.index].values if w_size is not None else 1)
    return pd.DataFrame({"sonic": monthly(s.tx, rs, P), "overnight": monthly(o.tx, ro, P), "williams": monthly(w.tx, rw, P),
                         "overnight_plain": monthly(o.tx, ro_all, P)})


def stats_of(x):
    x = np.asarray(x, float); eq = np.cumsum(x); dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    sh = x.mean() / x.std(ddof=1) * np.sqrt(12) if x.std(ddof=1) > 0 else 0.0
    return {"ann_ret_pct": round(x.mean() * 1200, 2), "sharpe": round(float(sh), 2), "maxdd_pct": round(float(dd * 100), 1),
            "t_month": round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if x.std(ddof=1) > 0 else 0.0, 2)}


def per_trade(T, r, P):
    a, b = pd.Timestamp(P[0]), pd.Timestamp(P[1]); m = ((T.t0 >= a) & (T.t0 < b)).values; x = r[m]
    return {"n": int(m.sum()), "mean_bp": round(float(x.mean() * 1e4), 2), "t": round(lab.tstat(x), 2)}


def base():
    D = load(); out = {}
    S, O, W = D["S"], D["O"], D["W"]
    for scn in K.SCN:
        R = {}
        o_take = O[O.ai_take > 0.5] if "ai_take" in O else O
        for pn, P in (("2009_2016", P_D), ("2017_2023", P_C), ("2009_2023", P_ALL)):
            R[pn] = {"overnight_AI_per_night": per_trade(o_take, K.net_returns(o_take, scn), P),
                     "overnight_plain_per_night": per_trade(O, K.net_returns(O, scn), P),
                     "sonic_R_per_trade": (lambda d: {**d, "mean_R": round(float(np.mean(sonic_R(S, scn)[((S.t0 >= P[0]) & (S.t0 < P[1])).values])), 3)})(per_trade(S, K.net_returns(S, scn), P)),
                     "williams_per_trade": per_trade(W, K.net_returns(W, scn), P)}
        for sn, sz in SIZES.items():
            df = strat_returns(D, scn, sz)
            port = df.sonic + df.overnight + df.williams
            R[sn] = {"strategies": {k: stats_of(df[k]) for k in ("sonic", "overnight", "overnight_plain", "williams")},
                     "portfolio": stats_of(port), "portfolio_without_overnight": stats_of(df.sonic + df.williams),
                     "portfolio_2009_2016": stats_of(port[:96]), "portfolio_2017_2023": stats_of(port[96:]),
                     "corr": df[["sonic", "overnight", "williams"]].corr().round(3).to_dict()}
        out[scn] = R
        print(scn, "ON-AI night bp", R["2009_2023"]["overnight_AI_per_night"], "| plan port", R["plan"]["portfolio"], "| without ON", R["plan"]["portfolio_without_overnight"])
    json.dump(out, open(f"{RES}/results_158_base.json", "w"), indent=1, default=float)
    return out


if __name__ == "__main__":
    st = sys.argv[1]
    if st in ("build", "all"): build()
    if st in ("ai", "all"): ai()
    if st in ("base", "all"): base()
