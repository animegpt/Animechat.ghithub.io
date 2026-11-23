"""Dukascopy monthly hourly-candle downloader (bi5). Usage: python dl.py INST [START_YYYY-MM] [END_YYYY-MM]
Writes $LABRAW/INST/BID/YYYY-MM.bi5 (format read by lab.load_hourly). Skips files already present; retries with backoff."""
import os, sys, time, random, urllib.request
RAW = os.environ.get("LABRAW", "/home/user/lab/raw")
inst = sys.argv[1]; a = sys.argv[2] if len(sys.argv) > 2 else "2004-01"; b = sys.argv[3] if len(sys.argv) > 3 else "2026-10"
side = "BID"; d = f"{RAW}/{inst}/{side}"; os.makedirs(d, exist_ok=True)
y, m = map(int, a.split("-")); y1, m1 = map(int, b.split("-")); todo = []
while (y, m) <= (y1, m1):
    todo.append((y, m)); m += 1
    if m == 13: y, m = y + 1, 1
for (y, m) in todo:
    f = f"{d}/{y}-{m:02d}.bi5"
    if os.path.exists(f) and os.path.getsize(f) > 0: continue
    url = f"https://datafeed.dukascopy.com/datafeed/{inst}/{y}/{m-1:02d}/{side}_candles_hour_1.bi5"
    for k in range(40):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            if len(data) == 0: raise IOError("empty")
            open(f + ".tmp", "wb").write(data); os.replace(f + ".tmp", f); print(inst, y, m, len(data), flush=True); break
        except Exception as e:
            time.sleep(min(120, 3 * 1.5 ** k) * (0.5 + random.random()))
    else:
        print("FAILED", inst, y, m, flush=True)
    time.sleep(1.0 + random.random())
print("DONE", inst, flush=True)
