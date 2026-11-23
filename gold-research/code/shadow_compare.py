"""Shadow evaluation of GoldWilliams_Shadow.mq5 (magic 770502).
Question: did the trades the frozen RF model WOULD HAVE sized up (size > 1) earn more than the ones it would have sized
down (size < 1)? The real trades were plain Williams; the size was only logged.

usage:
  python shadow_compare.py --trades GoldWilliams_Shadow_trades.csv \
        [--signals GoldWilliams_Shadow_signals.csv --bars GoldWilliams_Shadow_bars.csv] [--hist 20000] [--json out.json]
- trades : written by the EA at every exit (net_bp = real net P&L incl. commission/swap, shadow_size, shadow_pred)
- signals: written at every entry (all 206 features the EA computed)
- bars   : H1 bars dumped by the EA -> features + size recomputed in Python with the research code -> parity check.
           If parity fails, the analysis uses the Python size (research ground truth) and says so.
"""
import os, sys, json, argparse
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = f"{HERE}/mt5/rf_shadow_model.json"
# research benchmark (out-of-sample walk-forward 2009-2023, results_150 / report section 2)
BENCH = {"up_bp": 7.21, "down_bp": -1.29, "welch_t": 2.45, "n_trades": 2390, "years": 15}


def load_csv(p):
    return pd.read_csv(p, skipinitialspace=True)


def recompute(bars, T, hist):
    """research features at each trade's entry hour from the dumped bars (same window as the EA)."""
    import lab, ind3, features149 as F, export_rf as E
    J = json.load(open(MODEL))
    B = bars.copy(); B.index = pd.to_datetime(B.time_utc); B = B[["o", "h", "l", "c", "v"]].astype(float); B = B[B.v > 0].sort_index()
    B = B[~B.index.duplicated()]
    out = []
    for _, r in T.iterrows():
        t0 = pd.Timestamp(r.entry_time_utc).floor("h")
        done = B[B.index + pd.Timedelta(hours=1) <= t0].iloc[-hist:]
        if len(done) < 15000: out.append((np.nan, None)); continue
        day_end = t0 + pd.Timedelta(hours=30)                               # bars from t0 on: so the running H4/D1 group is 'incomplete'
        S = pd.concat([done, B[(B.index >= t0) & (B.index < day_end)]])
        M = lab.Mkt(S); bars_tf = F.tf_bars(M); raw = {}
        for tf in F.TFS:
            X = ind3.all_features(bars_tf[tf]); X["avail"] = bars_tf[tf]["avail"].values; X = X.sort_values("avail")
            row = X[X.avail <= t0].iloc[-1]
            for f in F.SIGNED + F.NONDIR + [p for b in F.PAIRS for p in b[:2]]: raw[f"{tf}__{f}"] = [row[f]]
        side = 1.0 if r.side == "BUY" else -1.0
        Xf = F.make_X(pd.DataFrame(raw), np.array([side]))[J["cols"]].values
        out.append((float(E.size_of(J, E.predict(J, Xf))[0]), Xf[0]))
    return out


def monthly_sharpe_diff(T, size):
    import metric149 as MT
    t = pd.to_datetime(T.day_ny); P = (str(t.min().to_period("M").start_time.date()), str((t.max() + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1)).date()))
    months = t.dt.to_period("M").nunique() if hasattr(t, "dt") else pd.Series(t).dt.to_period("M").nunique()
    return MT.evaluate(t, T.net_bp.values / 1e4, size, P, boot=months >= 12)   # block bootstrap meaningless < 12 months


def analyse(T, size, pred):
    up = T.net_bp[size > 1].values; dn = T.net_bp[size < 1].values
    res = {"n_trades": int(len(T)), "n_up": int(len(up)), "n_down": int(len(dn)),
           "months": int(pd.to_datetime(T.day_ny).dt.to_period("M").nunique()),
           "plain_mean_bp": round(float(T.net_bp.mean()), 2),
           "up_mean_bp": round(float(up.mean()), 2) if len(up) else None, "down_mean_bp": round(float(dn.mean()), 2) if len(dn) else None,
           "up_win": round(float((up > 0).mean()), 3) if len(up) else None, "down_win": round(float((dn > 0).mean()), 3) if len(dn) else None}
    if len(up) >= 3 and len(dn) >= 3:
        w = stats.ttest_ind(up, dn, equal_var=False)
        res["diff_bp"] = round(float(up.mean() - dn.mean()), 2); res["welch_t"] = round(float(w.statistic), 2)
        res["p_one_sided"] = round(float(w.pvalue / 2 if w.statistic > 0 else 1 - w.pvalue / 2), 4)
        rng = np.random.default_rng(0)
        bs = [rng.choice(up, len(up)).mean() - rng.choice(dn, len(dn)).mean() for _ in range(5000)]
        res["diff_ci95_bp"] = [round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)]
        ic = stats.spearmanr(pred, T.net_bp.values); res["spearman_ic"] = round(float(ic.correlation), 3); res["ic_p"] = round(float(ic.pvalue), 4)
        res["pnl_plain_bp_sum"] = round(float(T.net_bp.sum()), 1); res["pnl_sized_bp_sum"] = round(float((T.net_bp * size).sum()), 1)
        if res["months"] >= 6: res["monthly_sharpe"] = monthly_sharpe_diff(T, size)
        # power: trades needed for t = 2 if the research difference were true, at this sample's spread
        sd = np.sqrt((up.var(ddof=1) + dn.var(ddof=1)) / 2); eff = BENCH["up_bp"] - BENCH["down_bp"]
        need = int(np.ceil(2 * (2 * sd / eff) ** 2))
        res["power"] = {"research_diff_bp": round(eff, 2), "sd_bp": round(float(sd), 1), "trades_needed_for_t2": need,
                        "approx_months_needed": int(np.ceil(need / (BENCH["n_trades"] / BENCH["years"] / 12)))}
    return res


def verdict(res):
    if "welch_t" not in res: return "Too few trades in one of the groups (need >= 3 each)."
    p = res["power"]; enough = res["n_trades"] >= p["trades_needed_for_t2"]
    s = (f"Up-sized trades {res['up_mean_bp']} bp vs down-sized {res['down_mean_bp']} bp (diff {res['diff_bp']} bp, "
         f"95% CI {res['diff_ci95_bp']}, Welch t {res['welch_t']}). Research expected +{BENCH['up_bp']} vs {BENCH['down_bp']}.")
    if not enough:
        s += (f" TOO EARLY: about {p['trades_needed_for_t2']} trades (~{p['approx_months_needed']} months) are needed before a t of 2 is"
              f" even possible if the research effect is real; with {res['n_trades']} trades this result is mostly noise either way.")
    elif res["welch_t"] >= 2: s += " Live data SUPPORT the model (t >= 2 with enough trades)."
    elif res["diff_bp"] > 0: s += " Same direction as research but not significant."
    else: s += " Live data do NOT support the model."
    return s


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--trades", required=True); ap.add_argument("--signals"); ap.add_argument("--bars")
    ap.add_argument("--hist", type=int, default=20000); ap.add_argument("--json"); a = ap.parse_args()
    T = load_csv(a.trades); T = T[T.shadow_ok == 1].reset_index(drop=True)
    out = {"source_size": "ea"}
    size = T.shadow_size.values.astype(float); pred = T.shadow_pred.values.astype(float)
    if a.bars:
        rc = recompute(load_csv(a.bars), T, a.hist); py = np.array([x[0] for x in rc])
        ok = ~np.isnan(py)
        par = {"n_checked": int(ok.sum()), "size_mean_abs_diff": round(float(np.abs(py[ok] - size[ok]).mean()), 4) if ok.any() else None,
               "size_max_abs_diff": round(float(np.abs(py[ok] - size[ok]).max()), 4) if ok.any() else None,
               "same_up_down_group": round(float(((py[ok] > 1) == (size[ok] > 1)).mean()), 3) if ok.any() else None}
        if a.signals:
            S = load_csv(a.signals); J = json.load(open(MODEL))
            S = S[S.shadow_ok == 1].set_index("entry_time_utc")
            fe = []
            for (_, r), x in zip(T.iterrows(), rc):
                if x[1] is None or r.entry_time_utc not in S.index: continue
                fe.append(np.abs(S.loc[r.entry_time_utc, J["cols"]].values.astype(float) - x[1]))
            if fe:
                F_ = np.array(fe); worst = pd.Series(F_.max(0), index=J["cols"]).sort_values(ascending=False)
                par["features_max_abs_diff_top5"] = worst.head(5).round(5).to_dict()
                par["share_features_equal"] = round(float((F_ < 1e-4).mean()), 4)
        par["passes"] = par["n_checked"] > 0 and par["size_mean_abs_diff"] is not None and par["size_mean_abs_diff"] <= 0.03
        out["parity"] = par
        if not par["passes"] and ok.all():
            size = py; out["source_size"] = "python (EA parity failed -> research recomputation used)"
    out["analysis"] = analyse(T, size, pred if out["source_size"] == "ea" else size)
    out["verdict"] = verdict(out["analysis"]); out["research_benchmark"] = BENCH
    print(json.dumps(out, indent=1, default=float))
    if a.json: json.dump(out, open(a.json, "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
