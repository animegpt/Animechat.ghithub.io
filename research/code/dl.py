import os, sys, io, zipfile, urllib.request, concurrent.futures as cf
import pandas as pd
S=sys.argv[1]
months=[f"{y}-{m:02d}" for y in range(2020,2027) for m in range(1,13) if f"{y}-{m:02d}"<="2026-10"]
def get(url):
    try:
        with urllib.request.urlopen(url,timeout=60) as r: b=r.read()
        z=zipfile.ZipFile(io.BytesIO(b)); return z.read(z.namelist()[0]).decode()
    except Exception as e: return None
def kl(market,sym,iv):
    base={"spot":"spot","um":"futures/um"}[market]
    urls=[f"https://data.binance.vision/data/{base}/monthly/klines/{sym}/{iv}/{sym}-{iv}-{m}.zip" for m in months]
    with cf.ThreadPoolExecutor(16) as ex: txts=list(ex.map(get,urls))
    rows=[]
    for t in txts:
        if not t: continue
        for line in t.splitlines():
            p=line.split(",")
            if not p[0].isdigit(): continue
            rows.append(p[:11])
    df=pd.DataFrame(rows,columns="ot o h l c v ct qv n tbv tbqv".split())
    df=df.astype(float); ot=df.ot.astype("int64")
    ot=ot.where(ot<1e14, ot//1000)  # 2025+ spot uses microseconds
    df.index=pd.to_datetime(ot,unit="ms"); df=df[~df.index.duplicated()].sort_index()
    return df[["o","h","l","c","v","qv","n","tbv","tbqv"]]
def fund(sym):
    urls=[f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip" for m in months]
    with cf.ThreadPoolExecutor(16) as ex: txts=list(ex.map(get,urls))
    rows=[]
    for t in txts:
        if not t: continue
        for line in t.splitlines():
            p=line.split(",")
            if p[0].isdigit(): rows.append((int(p[0]),float(p[2])))
    df=pd.DataFrame(rows,columns=["t","fr"]); df.index=pd.to_datetime(df.t,unit="ms"); return df[["fr"]].sort_index()
def save(df,name):
    cut=pd.Timestamp("2025-11-01")
    df[df.index<cut].to_parquet(f"{S}/raw/{name}_dev.parquet")
    df[df.index>=cut].to_parquet(f"{S}/raw/hidden_{name}.parquet")
    print(name,len(df),df.index.min(),df.index.max(),flush=True)
for sym in ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"]:
    save(kl("spot",sym,"1h"),f"spot_{sym}_1h")
for sym in ["BTCUSDT","ETHUSDT"]:
    save(kl("um",sym,"1h"),f"um_{sym}_1h"); save(fund(sym),f"fund_{sym}")
