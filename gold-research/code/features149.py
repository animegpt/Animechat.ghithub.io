"""#149 feature engineering: Williams #112 trades + three-indicator features on H1 / H4 / D1, all from bars COMPLETED
before the entry bar starts. Directional features are multiplied by the trade side; bull/bear event pairs become
with-trade / against-trade. See prereg/PREREGISTRATION_149_152.md.
usage: python features149.py XAUUSD|XAGUSD  -> /home/user/lab/cache/feat149_<inst>[_vault].parquet"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab, ind3

TFS = ("H1", "H4", "D1")
SIGNED = ["pac_sw_trend", "pac_in_trend", "pac_pd_pos", "pac_pd_zone", "om_hw", "om_hw_sig", "om_hw_slope", "om_hw_zone",
          "om_mf", "om_mf_slope", "om_conf", "om_conf_agree", "so_st_dir", "so_st_dist", "so_rb_z", "so_rb_out"]
NONDIR = ["so_st_strength", "so_st_factor"]
# (bullish-version, bearish-version, kind)  kind: since = bars-since (log1p), lvl = level/count
PAIRS = []
for nm in ("sw", "in"):
    for e in ("bos", "choch", "chochp", "sweep"):
        PAIRS.append((f"pac_{nm}_{e}_b", f"pac_{nm}_{e}_s", "since"))
    for e in ("ob_n", "ob_d", "ob_in"):
        PAIRS.append((f"pac_{nm}_{e}_b", f"pac_{nm}_{e}_s", "lvl"))
PAIRS += [("pac_fvg_b", "pac_fvg_s", "since"), ("pac_fvg_n_b", "pac_fvg_n_s", "lvl"), ("pac_fvg_d_b", "pac_fvg_d_s", "lvl"),
          ("pac_eqh", "pac_eql", "since"), ("pac_eqh_d", "pac_eql_d", "lvl"),   # EQH = liquidity above (long target)
          ("om_x50_b", "om_x50_s", "since"), ("om_rev_b", "om_rev_s", "since"), ("om_div_b", "om_div_s", "since"),
          ("so_st_flip_b", "so_st_flip_s", "since"), ("so_rb_touch_dn", "so_rb_touch_up", "since")]


def williams(M):
    """#112 frozen: open +-0.6 x yesterday's range, first touch wins, exit at day close (lab engine, as check112)."""
    O, H, L = M.D.o.values, M.D.h.values, M.D.l.values; rng = H - L; rows = []
    for t in range(1, len(M.days)):
        r1 = rng[t - 1]
        if r1 <= 0: continue
        r = lab.oco_stop_trade(M, M.s[t], M.e[t], [(1, O[t] + 0.6 * r1, None, None), (-1, O[t] - 0.6 * r1, None, None)],
                               lambda j, t=t: M.e[t])
        if r is not None: rows.append(r)
    return pd.DataFrame(rows)


def tf_bars(M):
    """H1, H4 (blocks of 4 NY hours from 17:00), D1 (17:00 NY days). Each with 'avail' = time the bar is complete (UTC)."""
    df = M.df[["o", "h", "l", "c", "v"]].copy()
    h1 = df.copy(); h1["avail"] = h1.index + pd.Timedelta(hours=1)
    key = (M.ny + pd.Timedelta(hours=7)).normalize()
    blk = ((M.nyh - 17) % 24) // 4
    out = {"H1": h1}
    for nm, g in (("H4", [key, blk]), ("D1", [key])):
        tmp = df.copy(); tmp["ts"] = df.index
        agg = tmp.groupby(g, sort=True).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), v=("v", "sum"),
                                            first=("ts", "first"), last=("ts", "last"), n=("o", "size"))
        if nm == "D1": agg = agg[agg.n >= 10]
        agg = agg.sort_values("first")
        agg["avail"] = agg["last"] + pd.Timedelta(hours=1)
        out[nm] = agg.set_index("first")[["o", "h", "l", "c", "v", "avail"]]
    return out


def build(inst, vault=False):
    M = lab.Mkt(lab.load_hourly(inst, vault=vault), inst)
    T = williams(M)
    T["t0"] = M.idx[T.j0.values]                       # start time of entry bar (UTC naive)
    T = T.sort_values("t0").reset_index(drop=True)
    bars = tf_bars(M); raw = {}
    for tf in TFS:
        B = bars[tf]; F = ind3.all_features(B)
        F["avail"] = B["avail"].values
        F = F.sort_values("avail")
        X = pd.merge_asof(T[["t0"]], F, left_on="t0", right_on="avail", direction="backward", allow_exact_matches=True)
        assert (X.avail <= X.t0).all()
        raw[f"{tf}__age_h"] = (X.t0 - X.avail).dt.total_seconds().values / 3600     # staleness diagnostic (not a feature)
        for f in SIGNED + NONDIR + [p for b in PAIRS for p in b[:2]]: raw[f"{tf}__{f}"] = X[f].values
    R = pd.DataFrame(raw)
    out = pd.concat([T[["t", "t0", "side", "ep", "xp", "gross", "net1", "net2", "j0", "jx"]], R], axis=1)
    return out


def make_X(R, side):
    """raw (bull-positive) columns + side vector (+1/-1) -> signed feature matrix (DataFrame)"""
    side = np.asarray(side, float); cols = {}
    for tf in TFS:
        g = lambda f: R[f"{tf}__{f}"].values
        for f in SIGNED: cols[f"{tf}_{f}"] = g(f) * side
        for f in NONDIR: cols[f"{tf}_{f}"] = g(f)
        for b, s, kind in PAIRS:
            wb, ws = g(b), g(s)
            w = np.where(side > 0, wb, ws); a = np.where(side > 0, ws, wb)
            base = b[:-2] if b.endswith("_b") else b
            if kind == "since": w, a = np.log1p(np.minimum(w, 999)), np.log1p(np.minimum(a, 999))
            cols[f"{tf}_{base}_with"] = w; cols[f"{tf}_{base}_against"] = a
        al = ((g("pac_sw_trend") * side > 0).astype(int) + (g("om_hw") * side > 0).astype(int)
              + (g("so_st_dir") * side > 0).astype(int))
        cols[f"{tf}_align3"] = al.astype(float)
    C = pd.DataFrame(cols)
    for ind, f in (("pac", "pac_sw_trend"), ("om", "om_hw"), ("so", "so_st_dir")):
        C[f"mtf_{ind}_votes"] = sum((C[f"{tf}_{f}"] > 0).astype(int) for tf in TFS).astype(float)
    C["mtf_align3_majority"] = sum((C[f"mtf_{i}_votes"] >= 2).astype(int) for i in ("pac", "om", "so")).astype(float)
    C["mtf_align9"] = sum(C[f"{tf}_align3"] for tf in TFS)
    return C


if __name__ == "__main__":
    inst = sys.argv[1]; vault = len(sys.argv) > 2 and sys.argv[2] == "vault"
    os.makedirs(lab.CACHE, exist_ok=True)
    D = build(inst, vault=vault)
    p = f"{lab.CACHE}/feat149_{inst}{'_vault' if vault else ''}.parquet"; D.to_parquet(p)
    print(p, D.shape, "n_features", make_X(D, D.side).shape[1])
