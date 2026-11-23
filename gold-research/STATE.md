# STATE — Williams × three indicators (#149–#153)

Branch `claude/williams-three-indicators-research-roosgl`, folder `gold-research/`.
Prereg: `prereg/PREREGISTRATION_149_153.md` (committed before any evaluation).

## Data (rebuild, the user's packs were not available — user chose "rebuild from scratch")
- Downloader: `/home/user/lab/code/dl.py` (copy of gold-lab/code/dl.py). Raw files: `/home/user/lab/raw/{XAUUSD,XAGUSD}/BID/YYYY-MM.bi5`.
  - `cd /home/user/lab && LABRAW=/home/user/lab/raw python3 code/dl.py XAUUSD 2004-01 2026-10` (about 2-4 h, throttled)
  - `... dl.py XAGUSD 2022-01 2026-10`
- Cache: `/home/user/lab/cache` (lab.load_hourly splits off the gold vault >= 2024 automatically).
- Python deps: `pip install scikit-learn numba pandas scipy pyarrow joblib`.

## Pipeline
1. `cd gold-research/code && python features149.py XAUUSD` (+ `python features149.py XAGUSD vault` for silver 2022-2026)
2. `python check149.py` (look-ahead check) — done on 2004 data: 0 mismatches; re-run on full data.
3. Williams reproduction check (n 2053 disc 2004-2016, net1 t ~2.25).
4. `python models150.py run && python models150.py eval`  (#150)
5. `python rules151.py` (#151, 50,000 rules + 20 nulls)
6. `python verdict152.py verdict`, then `python verdict152.py silver <name>`; vault only for a winner after an independent audit.

## Status
- [x] Prereg, indicator code (ind3.py), features (206), metric, models, rules, verdict code; synthetic smoke tests OK.
- [x] Data download done (gold 274 files, silver 58). Williams reproduced exactly (disc n2053 t2.25, conf n1123).
- [x] #149 features (206, look-ahead 0 mismatches), #150 models, #151 rules, #152 verdict + silver.
- RESULT: NO WINNER. 16/20 models pass D>0 both periods & t>=2 (best RF-reg 0.5-1.5: D +0.292 t 3.14/3.30), all fail
  Holm over 50,020 trials and DSR (N 350,192). Rules: best disc t 4.975 < luck threshold 4.993. Silver (descriptive):
  RF-reg D +0.256 t 2.28. Vault NOT opened, audit not run (only for a winner). Report: REPORT_WILLIAMS_3IND.md
- [x] #153: Sonic fails. Overnight: 4 models pass #153 technical gates (t ~7, DSR >0.98) but Overnight is net-negative at
  Exness cost (Sharpe -1.06; sized still -0.35..-0.47) -> not tradable. Signal = short-term mean reversion (IC -0.22).
- STUDY CLOSED. Cumulative trials after #153: 350,212. Vault untouched. No EA/Pine (no winner).
- Ideas for a NEW pre-registration: (a) M5 features (user request); (b) Shadow-only RF-reg sizing on Demo (no effect on
  trades); (c) gold short-horizon reversal around 15:00-16:00 NY as its own strategy (short side has no swap).

If the conversation ends: "اقرأ STATE.md وكمّل".

## Next time (user request, 2026-11-23)
- M5 timeframe test: separate new pre-registration AFTER #149-#153 is finished (Dukascopy minute data is one file per day,
  about 60 h for 2005-2026 at the current throttle; plan a limited period).
