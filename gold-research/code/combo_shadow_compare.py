"""Shadow evaluation for GoldComboAI + GoldComboShadow.mqh (per strategy: SONIC, OVERNIGHT).
Did the trades the frozen #159 RF would have sized UP earn more than the ones it would have sized DOWN?
usage: python combo_shadow_compare.py --trades GoldComboShadow_trades.csv [--signals GoldComboShadow_signals.csv
       --bars GoldComboShadow_bars.csv --minbars 15000 --hist 20000] [--json out.json]"""
import os, sys, json, argparse
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shadow_compare as SC
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = {"SONIC": f"{HERE}/mt5/combo/rf_combo_sonic.json", "OVERNIGHT": f"{HERE}/mt5/combo/rf_combo_overnight.json"}
BENCH = json.load(open(f"{HERE}/mt5/combo/research_benchmark.json"))
BKEY = {"SONIC": "sonic", "OVERNIGHT": "overnight"}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--trades", required=True); ap.add_argument("--signals"); ap.add_argument("--bars")
    ap.add_argument("--hist", type=int, default=20000); ap.add_argument("--minbars", type=int, default=15000); ap.add_argument("--json")
    a = ap.parse_args()
    T_all = SC.load_csv(a.trades); T_all = T_all[T_all.shadow_ok == 1]
    bars = SC.load_csv(a.bars) if a.bars else None
    S_all = SC.load_csv(a.signals) if a.signals else None
    out = {}
    for strat, mp in MODELS.items():
        T = T_all[T_all.strategy == strat].reset_index(drop=True)
        if len(T) == 0: out[strat] = {"note": "no trades yet"}; continue
        SC.MODEL = mp; b = BENCH[BKEY[strat]]
        SC.BENCH = {"up_bp": b["up_bp"], "down_bp": b["down_bp"], "welch_t": b["welch_t"], "n_trades": b["n_trades"], "years": b["years"]}
        res = {"source_size": "ea"}; size = T.shadow_size.values.astype(float); pred = T.shadow_pred.values.astype(float)
        if bars is not None:
            rc = SC.recompute(bars, T, a.hist, a.minbars); py = np.array([x[0] for x in rc]); ok = ~np.isnan(py)
            par = {"n_checked": int(ok.sum())}
            if ok.any():
                par.update(size_mean_abs_diff=round(float(np.abs(py[ok] - size[ok]).mean()), 4), size_max_abs_diff=round(float(np.abs(py[ok] - size[ok]).max()), 4),
                           same_up_down_group=round(float(((py[ok] > 1) == (size[ok] > 1)).mean()), 3))
            if S_all is not None:
                J = json.load(open(mp)); S = S_all[(S_all.strategy == strat) & (S_all.shadow_ok == 1)].set_index("position_id"); fe = []
                for (_, r), x in zip(T.iterrows(), rc):
                    if x[1] is None or r.position_id not in S.index: continue
                    fe.append(np.abs(S.loc[r.position_id, J["cols"]].values.astype(float) - x[1]))
                if fe:
                    F_ = np.array(fe); par["share_features_equal"] = round(float((F_ < 1e-4).mean()), 4)
                    par["features_max_abs_diff_top5"] = pd.Series(F_.max(0), index=J["cols"]).sort_values(ascending=False).head(5).round(5).to_dict()
            par["passes"] = bool(ok.any() and par.get("size_mean_abs_diff", 1) <= 0.03)
            res["parity"] = par
            if not par["passes"] and ok.all(): size = py; res["source_size"] = "python (EA parity failed -> research recomputation used)"
        res["analysis"] = SC.analyse(T, size, pred if res["source_size"] == "ea" else size)
        res["verdict"] = SC.verdict(res["analysis"]); res["research_benchmark"] = SC.BENCH
        out[strat] = res
    print(json.dumps(out, indent=1, default=float))
    if a.json: json.dump(out, open(a.json, "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
