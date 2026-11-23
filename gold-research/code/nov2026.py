"""Gold after 2026-10 (descriptive only, prereg 155-157): Dukascopy 1-minute BID day files 2026-11-01..2026-11-22 ->
hourly bars -> $LABCACHE/XAUUSD_BID_nov2026.parquet.  usage: python nov2026.py download | build"""
import os, sys, lzma, time, datetime as dt
import numpy as np, pandas as pd, requests
RAW = os.environ.get("LABRAW", "/home/user/lab/raw") + "/XAUUSD/MIN"
CACHE = os.environ.get("LABCACHE", "/home/user/lab/cache")
DAYS = [dt.date(2026, 11, 1) + dt.timedelta(i) for i in range(22)]

if sys.argv[1] == "download":
    os.makedirs(RAW, exist_ok=True); s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"
    for p in range(40):
        todo = [d for d in DAYS if d.weekday() != 5 and not os.path.exists(f"{RAW}/{d}.bi5")]
        print("pass", p, "todo", len(todo), flush=True)
        if not todo: break
        for d in todo:
            try:
                r = s.get(f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{d.year}/{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5", timeout=90)
                if r.status_code == 200: open(f"{RAW}/{d}.bi5", "wb").write(r.content)
                elif r.status_code == 404: open(f"{RAW}/{d}.bi5", "wb").write(b"")
                else: time.sleep(20)
            except Exception: s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"; time.sleep(10)
            time.sleep(2)
        time.sleep(20)
else:
    out = []
    for d in DAYS:
        f = f"{RAW}/{d}.bi5"
        if not os.path.exists(f) or os.path.getsize(f) == 0: continue
        raw = lzma.decompress(open(f, "rb").read())
        a = np.frombuffer(raw, dtype=">i4").reshape(-1, 6).astype(np.int64); v = np.frombuffer(raw, dtype=">f4").reshape(-1, 6)[:, 5]
        m = pd.DataFrame({"o": a[:, 1], "c": a[:, 2], "l": a[:, 3], "h": a[:, 4]}, index=pd.Timestamp(d) + pd.to_timedelta(a[:, 0], unit="s")) / 1e3
        m["v"] = v; out.append(m[m.v > 0])
    m = pd.concat(out).sort_index()
    h = m.resample("1h").agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()
    h = h[h.v > 0]; h.to_parquet(f"{CACHE}/XAUUSD_BID_nov2026.parquet"); print(h.index.min(), h.index.max(), len(h))
