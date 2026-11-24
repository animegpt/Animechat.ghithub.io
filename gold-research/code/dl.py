"""Dukascopy hourly BID monthly files -> $LABRAW/{INST}/BID/YYYY-MM.bi5. Usage: python dl.py INST 2004-01 2026-10
Polite single-thread, resumable, multi-pass. Empty file = 404 (no data that month)."""
import requests, time, os, sys
inst, a, b = sys.argv[1], sys.argv[2], sys.argv[3]
R = f"{os.environ.get('LABRAW', '/home/user/lab/raw')}/{inst}/BID"; os.makedirs(R, exist_ok=True)
ya, ma = map(int, a.split("-")); yb, mb = map(int, b.split("-"))
jobs = [(y, m) for y in range(ya, yb + 1) for m in range(1, 13) if (ya, ma) <= (y, m) <= (yb, mb)]
s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"
for p in range(80):
    todo = [(y, m) for y, m in jobs if not os.path.exists(f"{R}/{y}-{m:02d}.bi5")]
    print(time.strftime("%H:%M:%S"), inst, "pass", p, "todo", len(todo), flush=True)
    if not todo: break
    for y, m in todo:
        try:
            r = s.get(f"https://datafeed.dukascopy.com/datafeed/{inst}/{y}/{m-1:02d}/BID_candles_hour_1.bi5", timeout=90)
            if r.status_code == 200: open(f"{R}/{y}-{m:02d}.bi5", "wb").write(r.content); print(time.strftime("%H:%M:%S"), inst, y, m, len(r.content), flush=True)
            elif r.status_code == 404: open(f"{R}/{y}-{m:02d}.bi5", "wb").write(b"")
            else: time.sleep(20)
        except Exception as e:
            s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"; time.sleep(10)
        time.sleep(1.0)
    time.sleep(30)
print("DONE", inst, flush=True)
