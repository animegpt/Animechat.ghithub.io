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


# ------------------------------------------------------------------ #159 three-indicator sizing on the combo
def ind_features(M, T):
    import features149 as F, ind3
    bars = F.tf_bars(M); raw = {}
    q = pd.DataFrame({"t0": pd.DatetimeIndex(T.t0)}).reset_index()
    for tf in F.TFS:
        B = bars[tf]; FF = ind3.all_features(B); FF["avail"] = B["avail"].values; FF = FF.sort_values("avail")
        X = pd.merge_asof(q.sort_values("t0"), FF, left_on="t0", right_on="avail", direction="backward").sort_values("index")
        for f in F.SIGNED + F.NONDIR + [p for b in F.PAIRS for p in b[:2]]: raw[f"{tf}__{f}"] = X[f].values
    R = pd.DataFrame(raw).fillna(0.0)
    return F.make_X(R, T.side.values.astype(float)).values


def models_fit(kind, X, y_reg, y_cls):
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    if kind == "rf":
        m = RandomForestRegressor(n_estimators=300, max_depth=6, max_features="sqrt", min_samples_leaf=100, random_state=0, n_jobs=4).fit(X, y_reg)
        return [m], [m.predict(X)]
    ms = [HistGradientBoostingClassifier(max_iter=300, max_depth=3, learning_rate=0.1, min_samples_leaf=50, l2_regularization=1.0, early_stopping=False, random_state=0),
          RandomForestClassifier(n_estimators=300, max_depth=6, max_features="sqrt", min_samples_leaf=100, random_state=0, n_jobs=4),
          make_pipeline(StandardScaler(), LogisticRegression(penalty="l1", solver="liblinear", C=0.03, max_iter=2000)),
          ExtraTreesClassifier(n_estimators=300, max_depth=6, max_features="sqrt", min_samples_leaf=100, random_state=0, n_jobs=4)]
    ms = [m.fit(X, y_cls) for m in ms]
    return ms, [m.predict_proba(X)[:, 1] for m in ms]


def models_score(kind, ms, ptr, X):
    pct = lambda x, ref: np.searchsorted(np.sort(ref), x, side="right") / len(ref)
    if kind == "rf": return pct(ms[0].predict(X), ptr[0])
    te = np.mean([pct(m.predict_proba(X)[:, 1], r) for m, r in zip(ms, ptr)], axis=0)
    tr = np.mean([pct(r, r) for r in ptr], axis=0)
    return pct(te, tr)


def ind():
    D = load(); M = lab.Mkt(lab.load_hourly("XAUUSD"))
    S, O, W = D["S"], D["O"], D["W"]
    T = {"sonic": S, "overnight": O, "williams": W}
    X = {k: ind_features(M, v) for k, v in T.items()}
    r = {k: K.net_returns(v, "A") for k, v in T.items()}
    yr = {k: v.t0.dt.year.values for k, v in T.items()}
    sizes = {}; finals = {}
    for struct in ("joint", "per"):
        for kind in ("rf", "ens"):
            name = f"{struct}_{kind}"; sz = {k: pd.Series(1.0, index=v.index) for k, v in T.items()}
            for Y in TEST + [2024]:
                if struct == "per":
                    for k in T:
                        tr = (yr[k] >= 2005) & (yr[k] < Y)
                        ms, ptr = models_fit(kind, X[k][tr], r[k][tr], (r[k][tr] > 0).astype(int))
                        if Y == 2024: finals[(name, k)] = (ms, ptr); continue
                        te = yr[k] == Y
                        if te.any(): sz[k].iloc[np.flatnonzero(te)] = 0.5 + models_score(kind, ms, ptr, X[k][te])
                else:
                    Xs, ys, yc = [], [], []
                    sd = {k: r[k][(yr[k] >= 2005) & (yr[k] < Y)].std() for k in T}
                    for j, k in enumerate(T):
                        tr = (yr[k] >= 2005) & (yr[k] < Y); oh = np.zeros((tr.sum(), 3)); oh[:, j] = 1
                        Xs.append(np.hstack([X[k][tr], oh])); ys.append(r[k][tr] / sd[k]); yc.append((r[k][tr] > 0).astype(int))
                    ms, ptr = models_fit(kind, np.vstack(Xs), np.concatenate(ys), np.concatenate(yc))
                    if Y == 2024: finals[(name, "joint")] = (ms, ptr, sd); continue
                    for j, k in enumerate(T):
                        te = yr[k] == Y
                        if te.any():
                            oh = np.zeros((te.sum(), 3)); oh[:, j] = 1
                            sz[k].iloc[np.flatnonzero(te)] = 0.5 + models_score(kind, ms, ptr, np.hstack([X[k][te], oh]))
            sizes[name] = sz; print("fitted", name, flush=True)
    pickle.dump(dict(sizes=sizes, finals=finals), open(f"{CD}/ind159.pkl", "wb"))
    evaluate_ind(D, sizes)


def evaluate_ind(D, sizes):
    out = {}; pvals = []
    for name, sz in sizes.items():
        res = {}
        for scn in K.SCN:
            b = strat_returns(D, scn, SIZES["plan"]); s = strat_returns(D, scn, SIZES["plan"], s_size=sz["sonic"], o_size=sz["overnight"], w_size=sz["williams"])
            pb = (b.sonic + b.overnight + b.williams).values; ps = (s.sonic + s.overnight + s.williams).values
            e = {}
            for pn, sl in (("2009_2016", slice(0, 96)), ("2017_2023", slice(96, 180)), ("2009_2023", slice(0, 180))):
                Dv, tj = MT.jkm(pb[sl], ps[sl]); e[pn] = {"D": round(float(Dv), 3), "t_jkm": round(float(tj), 2)}
            e["2009_2023"]["t_boot"] = round(MT.boot_t(pb, ps), 2)
            e["sharpe_base"] = round(float(pb.mean() / pb.std(ddof=1) * np.sqrt(12)), 3); e["sharpe_sized"] = round(float(ps.mean() / ps.std(ddof=1) * np.sqrt(12)), 3)
            e["overlay"] = (ps - pb).tolist()
            res[scn] = e
        out[name] = res; pvals.append(float(stats.norm.sf(res["A"]["2009_2023"]["t_jkm"])))
    N = CUM_BEFORE + 8
    adj = MT.holm(pvals + [1.0] * 4)[:len(pvals)]
    for (name, res), a in zip(out.items(), adj):
        A = res["A"]; dsr, sr, _ = MT.dsr_monthly(np.array(A["overlay"]), N, 0.0843)
        g = {"g1_D_pos_t2": A["2009_2023"]["D"] > 0 and A["2009_2023"]["t_jkm"] >= 2 and A["2009_2023"]["t_boot"] >= 2,
             "g2_both_periods": A["2009_2016"]["D"] > 0 and A["2017_2023"]["D"] > 0, "g4_holm": bool(a < 0.05), "g5_dsr": dsr >= 0.95}
        res["verdict"] = {"holm": float(a), "dsr": dsr, "gates": g, "passes_gold_gates": all(g.values())}
        for scn in res:
            if scn != "verdict": res[scn].pop("overlay", None)
        print(name, {s: (res[s]["2009_2023"]["D"], res[s]["2009_2023"]["t_jkm"], res[s]["2009_2016"]["D"], res[s]["2017_2023"]["D"]) for s in ("A", "B", "C")}, res["verdict"]["gates"], round(dsr, 3))
    json.dump(out, open(f"{RES}/results_159_ind.json", "w"), indent=1, default=float)


# ------------------------------------------------------------------ #160 allocation
def mdd(x):
    eq = np.cumsum(x, axis=-1); return (eq - np.maximum.accumulate(np.concatenate([np.zeros(eq.shape[:-1] + (1,)), eq], -1), -1)[..., 1:]).min(-1)


def boot_paths(R, n=5000, L=36, block=6, seed=11):
    rng = np.random.default_rng(seed); T = len(R); nb = int(np.ceil(L / block))
    st = rng.integers(0, T, (n, nb)); idx = ((st[:, :, None] + np.arange(block)) % T).reshape(n, -1)[:, :L]
    return R[idx]                                  # (n, L, k)


def scale_to_dd(R, w, limit=0.15):
    Rs = R - 0.5 * R.mean(0)                       # edges shrunk by 50 %
    paths = boot_paths(Rs) @ w                     # (n, L)
    lo, hi = 0.0, 20.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if -np.percentile(mdd(mid * paths), 5) <= limit: lo = mid
        else: hi = mid
    return lo


def alloc():
    D = load(); out = {}
    for scn in K.SCN:
        df = strat_returns(D, scn, SIZES["plan"])[["sonic", "overnight", "williams"]]
        est = df.iloc[:96].values; test = df.iloc[96:].values
        mu, sd = est.mean(0), est.std(0, ddof=1); tt = mu / (sd / np.sqrt(len(est)))
        cov = np.cov(est.T)
        W = {"risk_parity": 1 / sd,
             "kelly": np.clip(np.linalg.solve(cov, mu), 0, None),
             "robust": (1 / sd) * np.clip(tt / 2, 0, 1)}
        R = {}
        for nm, w in W.items():
            if w.sum() <= 0: R[nm] = {"weights": [0, 0, 0], "note": "all off"}; continue
            w = w / np.max(w); k = scale_to_dd(est, w); wf = k * w
            te = test @ wf; es = est @ wf
            R[nm] = {"mult": [round(float(x), 3) for x in wf],
                     "InpRiskPct": round(0.15 * wf[0], 3), "InpOnLev": round(1.0 * wf[1], 2), "InpLev_Williams": round(0.5 * wf[2], 2),
                     "estimation_2009_2016": stats_of(es), "test_2017_2023": stats_of(te)}
        R["plan_sizes_test"] = stats_of(test.sum(1)); R["disc_t"] = [round(float(x), 2) for x in tt]
        out[scn] = R
        print(scn, {k: (v.get("InpRiskPct"), v.get("InpOnLev"), v.get("InpLev_Williams"), v.get("test_2017_2023", {}).get("sharpe"), v.get("test_2017_2023", {}).get("maxdd_pct")) for k, v in R.items() if isinstance(v, dict) and "mult" in v}, "plan test", R["plan_sizes_test"])
    json.dump(out, open(f"{RES}/results_160_alloc.json", "w"), indent=1, default=float)


# ------------------------------------------------------------------ #161 silver clean ground (frozen gold models)
def silver():
    G = load(); fin = G["finals"]; I = pickle.load(open(f"{CD}/ind159.pkl", "rb"))
    M = lab.Mkt(lab.load_hourly("XAGUSD", vault=True), "XAGUSD"); E = K.EA(M)
    S = K.sim_sonic(E, "XAGUSD"); O = K.sim_overnight(E, np.zeros(E.n), S); W = K.sim_williams(M)
    m, ptr = fin["sonic"]; S["ai_mult"] = rank_mult(m.predict_proba(np.vstack(S.feats.values))[:, 1], ptr)
    sc, lr_, thr, mu = fin["on"]; XO = np.vstack(O.feats.values); XO = np.where(np.isnan(XO), mu, XO)
    O["ai_take"] = (lr_.predict_proba(sc.transform(XO))[:, 1] > thr).astype(float)
    D = dict(S=S, O=O, W=W); P = ("2023-01-01", "2026-11-01"); inst = "XAGUSD"
    b = strat_returns(D, "A", SIZES["plan"], inst=inst, P=P); pb = (b.sonic + b.overnight + b.williams).values
    a, z = pd.Timestamp(P[0]), pd.Timestamp(P[1])
    out = {"per_trade": {"sonic_R": float(np.mean(sonic_R(S, "A", inst)[((S.t0 >= a) & (S.t0 < z)).values])),
                         "sonic_n": int(((S.t0 >= a) & (S.t0 < z)).sum()),
                         "overnight_AI": per_trade(O[O.ai_take > 0.5], K.net_returns(O[O.ai_take > 0.5], "A", inst), P),
                         "overnight_plain": per_trade(O, K.net_returns(O, "A", inst), P),
                         "williams": per_trade(W, K.net_returns(W, "A", inst), P)},
           "strategies": {k: stats_of(b[k]) for k in ("sonic", "overnight", "overnight_plain", "williams")}, "portfolio": stats_of(pb), "models": {}}
    T = {"sonic": S, "overnight": O, "williams": W}; X = {k: ind_features(M, v) for k, v in T.items()}
    for name in I["sizes"]:
        kind = name.split("_")[1]; sz = {}
        for j, k in enumerate(T):
            if name.startswith("per"):
                ms, ptr2 = I["finals"][(name, k)]; sz[k] = pd.Series(0.5 + models_score(kind, ms, ptr2, X[k]), index=T[k].index)
            else:
                ms, ptr2, sd = I["finals"][(name, "joint")]; oh = np.zeros((len(X[k]), 3)); oh[:, j] = 1
                sz[k] = pd.Series(0.5 + models_score(kind, ms, ptr2, np.hstack([X[k], oh])), index=T[k].index)
        sdf = strat_returns(D, "A", SIZES["plan"], inst=inst, P=P, s_size=sz["sonic"], o_size=sz["overnight"], w_size=sz["williams"])
        ps = (sdf.sonic + sdf.overnight + sdf.williams).values; Dv, tj = MT.jkm(pb, ps)
        out["models"][name] = {"D": round(float(Dv), 3), "t_jkm": round(float(tj), 2), "sharpe_sized": stats_of(ps)["sharpe"]}
    print(json.dumps(out, indent=1, default=float))
    json.dump(out, open(f"{RES}/results_161_silver.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    st = sys.argv[1]
    if st in ("build", "all"): build()
    if st in ("ai", "all"): ai()
    if st in ("base", "all"): base()
    if st in ("ind", "all"): ind()
    if st in ("alloc", "all"): alloc()
    if st in ("silver", "all"): silver()
