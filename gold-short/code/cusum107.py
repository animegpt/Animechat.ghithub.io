"""#107 CUSUM calibration from out-of-sample trades + #108 Monte Carlo for the capital plan.
usage: BARS=1h GDATA=... python cusum107.py <overnight_wf_nights.csv>"""
import os, sys, json, numpy as np, pandas as pd
os.environ["BARS"] = "1h"
import shortlib as sl

SWAP = 0.4316 / 4000
rng = np.random.default_rng(107)


def oos_samples(nights_csv):
    import long97 as LF, deep101 as DP
    m = LF.hourly(); T = DP.sonic_trades(m, "1h", False); son = T[(T.index >= "2017-01-01") & (T.index < "2024-01-01")].R.values
    ON = pd.read_csv(nights_csv, index_col=0, parse_dates=True)
    on = ((ON.p20 / ON.p16 - 1) - (0.24 / ON.p16 + 2e-5)).values                          # per night, 1x notional, cost A
    os.environ["BARS"] = "1m"; import importlib; importlib.reload(sl); import dc84
    mm = sl.load_minutes(); mm = mm[mm.index >= pd.Timestamp("2017-01-01", tz="UTC")]
    O, H, L, C = (mm[k].values.astype(np.float64) for k in "ohlc"); ny = mm.index.tz_convert("America/New_York")
    ii, xx, g, sd, how, _ = dc84.run(C, O, H, L, ny.hour.values.astype(np.int64), mm.index.values.astype("datetime64[m]").astype(np.int64), 0.002, 2.0, 3.0, 1440, 0)
    dc = g - (0.10 / O[ii] + 2e-5)
    return {"GoldComboAI_Sonic": son, "GoldComboAI_Overnight": on, "GoldDCFade": dc}


def cusum_path(z, m0, h):
    S = 0.0
    for i, x in enumerate(z):
        S = max(0.0, S + m0 / 2 - x)
        if S >= h: return i + 1
    return 0


def calibrate(x, per_year):
    mu, sd = x.mean(), x.std(ddof=1); z = x / sd; m0 = mu / sd
    def falarm(h, n=2000):
        return np.mean([cusum_path(rng.choice(z, per_year), m0, h) > 0 for _ in range(n)])
    def find(target):
        lo, hi = 0.1, 60.0
        for _ in range(30):
            mid = (lo + hi) / 2
            if falarm(mid, 600) > target: lo = mid
            else: hi = mid
        return hi
    h_red, h_yel = find(0.05), find(0.20)
    z0 = z - m0                                                  # edge = 0
    delays = [cusum_path(rng.choice(z0, 20 * per_year), m0, h_red) for _ in range(1000)]
    delays = np.array([d if d > 0 else 20 * per_year for d in delays])
    sign = np.where(x > 0, 1, 0)
    def streak_prob(N, n=4000):
        hits = 0
        for _ in range(n):
            s = rng.choice(sign, per_year); run = 0; mx = 0
            for v in s:
                run = run + 1 if v == 0 else 0; mx = max(mx, run)
            hits += mx >= N
        return hits / n
    return {"mean": float(mu), "sd": float(sd), "m0_sd_units": round(float(m0), 4), "trades_per_year": int(per_year), "win_rate": round(float((x > 0).mean()), 3),
            "h_yellow": round(h_yel, 3), "h_red": round(h_red, 3), "false_alarm_red_per_year": 0.05,
            "median_trades_to_red_if_edge_zero": int(np.median(delays)), "p90_trades_to_red_if_edge_zero": int(np.percentile(delays, 90)),
            "p_losing_streak_per_year": {N: round(streak_prob(N), 3) for N in (5, 8, 10, 12, 15, 18, 20, 25)}}


def capital_mc(son_R, on_r, years=3, n=4000):
    """daily-ish simulation by trade counts per year; sizes: sonic risk %, overnight x notional"""
    out = {}
    for swap in (False, True):
        s_adj = son_R - (0.0 if not swap else 0.0)                 # swap on Sonic longs already small; reported via Overnight below
        o_adj = on_r - (SWAP if swap else 0.0) * np.where(rng.random(len(on_r)) < 0.25, 3, 1).mean()
        for name, (sr, ox) in {"current_0.30_2.0": (0.30, 2.0), "proposed_0.23_1.5": (0.23, 1.5), "half_0.15_1.0": (0.15, 1.0)}.items():
            for edge in (1.0, 0.5, 0.0):
                S = s_adj - (1 - edge) * s_adj.mean(); O = o_adj - (1 - edge) * o_adj.mean()
                dds = []; rets = []
                for _ in range(n):
                    ps = rng.choice(S, 95 * years) * sr / 100; po = rng.choice(O, 100 * years) * ox
                    allr = np.concatenate([ps, po]); rng.shuffle(allr)
                    eq = np.cumprod(1 + allr); dds.append((eq / np.maximum.accumulate(eq) - 1).min()); rets.append(eq[-1] - 1)
                dds = np.array(dds); rets = np.array(rets)
                out[f"{'swap' if swap else 'swapfree'}|{name}|edge{int(edge*100)}"] = {
                    "p95_maxdd_pct": round(float(-np.percentile(dds, 5) * 100), 1), "p_dd_gt_15": round(float((dds < -0.15).mean()), 3),
                    "median_3y_ret_pct": round(float(np.median(rets) * 100), 1), "p_loss_3y": round(float((rets < 0).mean()), 3)}
    return out


if __name__ == "__main__":
    X = oos_samples(sys.argv[1])
    per = {"GoldComboAI_Sonic": 95, "GoldComboAI_Overnight": 100, "GoldDCFade": 350}
    cal = {k: calibrate(v, per[k]) for k, v in X.items()}
    for k, v in cal.items(): print(k, json.dumps(v), flush=True)
    json.dump(cal, open(f"{sl.HERE}/mt5/monitor_thresholds.json", "w"), indent=1)
    mc = capital_mc(X["GoldComboAI_Sonic"], X["GoldComboAI_Overnight"])
    for k, v in mc.items(): print(k, v, flush=True)
    json.dump(mc, open(f"{sl.HERE}/results_108_capital_mc.json", "w"), indent=1)
    # Bayesian shrinkage prior summary
    pri = {}
    for k, v in X.items():
        se = v.std(ddof=1) / np.sqrt(len(v)); pri[k] = {"oos_mean": float(v.mean()), "se": float(se), "prior_mean_shrunk50": float(0.5 * v.mean()), "prior_sd": float(se),
                                                        "p_edge_pos_prior": round(float(1 - __import__('scipy').stats.norm.cdf(0, 0.5 * v.mean(), se)), 3)}
    json.dump(pri, open(f"{sl.HERE}/results_108_priors.json", "w"), indent=1); print(pri)
