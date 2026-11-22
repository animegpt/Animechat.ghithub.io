"""Hourly XAUUSD BID (monthly files) 2004-01..2026-10, single thread, polite, multi-pass."""
import requests, time, os
R=os.environ["GDATA"]+"/raw/cache_XAUUSD_h"; os.makedirs(R,exist_ok=True)
jobs=[(y,m) for y in range(2004,2027) for m in range(1,13) if (y,m)<=(2026,10)]
s=requests.Session(); s.headers["User-Agent"]="Mozilla/5.0"
for p in range(60):
    todo=[(y,m) for y,m in jobs if not os.path.exists(f"{R}/{y}-{m:02d}.bi5")]
    print(time.strftime("%H:%M:%S"),"pass",p,"todo",len(todo),flush=True)
    if not todo: break
    for y,m in todo:
        try:
            r=s.get(f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{y}/{m-1:02d}/BID_candles_hour_1.bi5",timeout=60)
            if r.status_code==200: open(f"{R}/{y}-{m:02d}.bi5","wb").write(r.content)
            else: time.sleep(5)
        except Exception: s=requests.Session(); s.headers["User-Agent"]="Mozilla/5.0"; time.sleep(3)
        time.sleep(1.0)
    time.sleep(30)
print("HOURDONE",flush=True)
