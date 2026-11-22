"""Resumable Dukascopy downloader: XAUUSD hourly BID+ASK (monthly files) 2004-01..2026-10, then 1-minute BID (daily files).
3 polite worker threads, retries in later passes. Raw dir from env GDATA."""
import requests, time, datetime as dt, os, threading
from concurrent.futures import ThreadPoolExecutor
R=os.environ.get("GDATA")+"/raw"
jobs=[]
for side,folder in (("BID","cache_XAUUSD_h"),("ASK","cache_XAUUSD_ASK_h")):
    for y in range(2004,2027):
        for m in range(1,13):
            if (y,m)<=(2026,10): jobs.append((f"{R}/{folder}/{y}-{m:02d}.bi5",f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{y}/{m-1:02d}/{side}_candles_hour_1.bi5"))
d0=dt.date(2004,1,1); days=[d0+dt.timedelta(i) for i in range((dt.date(2026,11,1)-d0).days)]
for d in days:
    if d.weekday()==5: continue
    jobs.append((f"{R}/cache_XAUUSD/{d}.bi5",f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{d.year}/{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5"))
tl=threading.local()
def S():
    if not hasattr(tl,"s"): tl.s=requests.Session(); tl.s.headers["User-Agent"]="Mozilla/5.0"
    return tl.s
def work(job):
    f,u=job
    try:
        r=S().get(u,timeout=60)
        if r.status_code==200: open(f,"wb").write(r.content); return 1
        if r.status_code==404: open(f,"wb").write(b""); return 1
        time.sleep(1.0)       # 503 = file being generated server-side; retried next pass
    except Exception:
        tl.s=requests.Session(); tl.s.headers["User-Agent"]="Mozilla/5.0"; time.sleep(2)
    return 0
for f,_ in jobs: os.makedirs(os.path.dirname(f),exist_ok=True)
for p in range(40):
    todo=[j for j in jobs if not os.path.exists(j[0])]
    print(time.strftime("%H:%M:%S"),"pass",p,"todo",len(todo),"of",len(jobs),flush=True)
    if not todo: break
    done=0
    with ThreadPoolExecutor(3) as ex:
        for i,ok in enumerate(ex.map(work,todo)):
            done+=ok
            if i%250==0: print(time.strftime("%H:%M:%S"),p,i,len(todo),"ok",done,flush=True)
    time.sleep(5)
print("ALLDONE",flush=True)
