"""Slow resumable Dukascopy 1-minute XAUUSD BID downloader (user spec): sequential, sleep 3 s between files,
up to 15 attempts per file, 60 s pause on HTTP 503/429, resumes from existing files. Order: 2017-01..2026-10, then 2004..2016."""
import requests, time, datetime as dt, os
R=os.environ["GDATA"]+"/raw/cache_XAUUSD"; os.makedirs(R,exist_ok=True)
def days(a,b):
    return [a+dt.timedelta(i) for i in range((b-a).days) if (a+dt.timedelta(i)).weekday()!=5]
order=days(dt.date(2017,1,1),dt.date(2026,11,1))+days(dt.date(2004,1,1),dt.date(2017,1,1))
s=requests.Session(); s.headers["User-Agent"]="Mozilla/5.0"
done=sum(os.path.exists(f"{R}/{d}.bi5") for d in order); print("start",done,len(order),flush=True)
for d in order:
    f=f"{R}/{d}.bi5"
    if os.path.exists(f): continue
    u=f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{d.year}/{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5"
    for k in range(15):
        try:
            r=s.get(u,timeout=90)
            if r.status_code==200: open(f,"wb").write(r.content); break
            if r.status_code==404: open(f,"wb").write(b""); break
            time.sleep(60 if r.status_code in (429,503) else 10)
        except Exception:
            s=requests.Session(); s.headers["User-Agent"]="Mozilla/5.0"; time.sleep(15)
    else: print("GAVEUP",d,flush=True)
    done+=1
    if done%50==0: print(time.strftime("%m-%d %H:%M"),"done",done,"/",len(order),d,flush=True)
    time.sleep(3)
print("SLOWDONE",flush=True)
