"""monitor.py: live health check (CUSUM, pre-registered #107) for GoldComboAI (Sonic + Overnight) and GoldDCFade.

usage:
  python monitor.py ReportHistory.html            # MT5 account/tester report (HTML, UTF-8 or UTF-16)
  python monitor.py ReportHistory.csv             # same table exported as CSV (columns: Time, Type, Direction, Volume, Profit, Commission, Swap, Balance, Comment)
  python monitor.py GoldDCFade_trades.csv         # the GoldDCFade log (MQL5/Files)
Thresholds come from monitor_thresholds.json (same folder), calibrated on out-of-sample trades:
red = 5% false-alarm probability per year, yellow = 20%.

Output per strategy: GREEN (healthy) / YELLOW (watch: do not add capital) / RED (stop and review)."""
import sys, os, re, json, csv, io
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TH = json.load(open(os.path.join(HERE, "monitor_thresholds.json")))
SONIC_RISK, ON_LEV = 0.003, 2.0


def read_text(path):
    raw = open(path, "rb").read()
    for enc in ("utf-16", "utf-8-sig", "cp1252"):
        try:
            t = raw.decode(enc)
            if "<" in t or "," in t or ";" in t: return t
        except Exception: pass
    return raw.decode("latin-1")


def html_rows(text):
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I):
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if cells: rows.append(cells)
    return rows


def deals_table(rows):
    """find the Deals table: header containing Direction and Profit"""
    for k, r in enumerate(rows):
        low = [c.lower() for c in r]
        if "direction" in low and "profit" in low and ("deal" in low or "time" in low):
            hdr = low; out = []
            for r2 in rows[k + 1:]:
                if len(r2) < len(hdr) - 2: break
                out.append(dict(zip(hdr, r2)))
            return out
    return []


def num(x):
    try: return float(str(x).replace(" ", "").replace(",", ""))
    except Exception: return 0.0


def combo_trades(deals):
    """pair 'in' deals (comment says the strategy) with later 'out' deals of the same volume and opposite type"""
    open_ = []; res = {"GoldComboAI_Sonic": [], "GoldComboAI_Overnight": []}; bal = None
    for d in deals:
        typ, dire, vol, com = d.get("type", "").lower(), d.get("direction", "").lower(), num(d.get("volume", 0)), d.get("comment", "")
        b = num(d.get("balance", 0)) or bal
        if dire == "in" and typ in ("buy", "sell"):
            strat = "GoldComboAI_Sonic" if "sonic" in com.lower() else "GoldComboAI_Overnight" if "overnight" in com.lower() else None
            if strat: open_.append([strat, typ, vol, b])
        elif dire in ("out", "out by") and typ in ("buy", "sell"):
            net = num(d.get("profit", 0)) + num(d.get("commission", 0)) + num(d.get("swap", 0)) + num(d.get("fee", 0))
            for k, (strat, t0, v0, b0) in enumerate(open_):
                if t0 != typ and abs(v0 - vol) < 1e-9:
                    base = b0 or (b - net if b else None)
                    if base:
                        res[strat].append(net / (base * SONIC_RISK) if strat.endswith("Sonic") else net / (base * ON_LEV))
                    open_.pop(k); break
        bal = b
    return res


def dc_trades(text):
    r = list(csv.DictReader(io.StringIO(text)))
    return {"GoldDCFade": [num(x["net_bp"]) / 1e4 for x in r if x.get("net_bp") not in (None, "")]}


def cusum(x, th):
    z = np.asarray(x) / th["sd"]; m0 = th["m0_sd_units"]; S = 0.0; path = []
    for v in z: S = max(0.0, S + m0 / 2 - v); path.append(S)
    return np.array(path)


def streaks(x):
    cur = mx = 0
    for v in x:
        cur = cur + 1 if v <= 0 else 0; mx = max(mx, cur)
    return cur, mx


def verdict(name, x):
    th = TH[name]; n = len(x)
    if n == 0: return f"{name}: no trades found"
    S = cusum(x, th); s = S[-1]; cur, mx = streaks(x)
    state = "RED   - stop and review" if s >= th["h_red"] else "YELLOW - watch, do not add capital" if s >= th["h_yellow"] else "GREEN - healthy"
    exp_mean = th["mean"]; live_mean = float(np.mean(x))
    lines = [f"== {name} ==", f"  trades: {n} | live mean: {live_mean:.5g} (out-of-sample expectation {exp_mean:.5g}) | win rate {np.mean(np.array(x) > 0):.0%} (expected {th['win_rate']:.0%})",
             f"  CUSUM: {s:.2f} (yellow at {th['h_yellow']}, red at {th['h_red']}) -> {state}",
             f"  losing streak: current {cur}, longest {mx}. Chance per year of a streak >= {mx}: " +
             (f"{th['p_losing_streak_per_year'].get(str(min([k for k in map(int, th['p_losing_streak_per_year']) if k >= mx], default=25)), 0):.0%}" if mx >= 5 else "common"),
             f"  if the edge had vanished, a red alarm would come after ~{th['median_trades_to_red_if_edge_zero']} trades (median)"]
    return "\n".join(lines)


if __name__ == "__main__":
    path = sys.argv[1]; text = read_text(path)
    if "net_bp" in text.splitlines()[0]: groups = dc_trades(text)
    elif "<tr" in text.lower(): groups = combo_trades(deals_table(html_rows(text)))
    else:
        rdr = list(csv.reader(io.StringIO(text), delimiter=";" if text.count(";") > text.count(",") else ","))
        groups = combo_trades(deals_table(rdr))
    for name, x in groups.items(): print(verdict(name, x)); print()
