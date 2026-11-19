import sys; sys.path.insert(0,'.')
from lib import *
def first(v): v=np.asarray(v,bool); return v&~np.r_[False,v[:-1]]
def featsB(df,tf,sym):
    F={}
    c=df.c
    for N in (20,55,100):
        F[f"donch{N}_up"]=first(c>df.h.rolling(N).max().shift(1)); F[f"donch{N}_dn"]=first(c<df.l.rolling(N).min().shift(1))
    for N in (20,50,100):
        F[f"tsmom{N}_up"]=first(c>c.shift(N)); F[f"tsmom{N}_dn"]=first(c<c.shift(N))
    r=c.pct_change()
    sd=r.rolling(500 if tf!="1d" else 90).std()
    for k in (2,3,4):
        F[f"bigdrop{k}sd"]=(r<-k*sd).values; F[f"bigpump{k}sd"]=(r>k*sd).values
    z=(df.qv-df.qv.rolling(200).mean())/df.qv.rolling(200).std()
    F["volspike_up"]=((z>3)&(r>0)).values; F["volspike_dn"]=((z>3)&(r<0)).values
    tb=(df.tbqv/df.qv); tz=(tb-tb.rolling(200).mean())/tb.rolling(200).std()
    F["takerbuy_hi"]=first(tz>2.5); F["takerbuy_lo"]=first(tz<-2.5)
    # funding extremes (8h rate, mapped to bar)
    f=pd.read_parquet(f"{S}/raw/fund_{sym}_dev.parquet").fr
    fb=f.reindex(df.index,method="ffill")
    fz=(fb-fb.rolling(90*24 if tf=="1h" else 90*6 if tf=="4h" else 90).mean())/fb.rolling(90*24 if tf=="1h" else 90*6 if tf=="4h" else 90).std()
    F["fund_neg"]=first(fb<0); F["fund_z_lo"]=first(fz<-2); F["fund_z_hi"]=first(fz>2); F["fund_hi"]=first(fb>0.0005)
    # squeeze -> breakout: bandwidth at 120-bar low then close outside 20-bar BB
    m=c.rolling(20).mean(); s=c.rolling(20).std(); bw=(4*s/m)
    sq=bw<=bw.rolling(120).min()*1.1
    F["squeeze_up"]=first(sq.shift(1).fillna(False)&(c>m+2*s)); F["squeeze_dn"]=first(sq.shift(1).fillna(False)&(c<m-2*s))
    return F
if __name__=="__main__":
    sym=sys.argv[1] if len(sys.argv)>1 else "BTCUSDT"
    for tf,Hs in (("1h",[6,12,24,48]),("4h",[3,6,12,24]),("1d",[1,3,5,10])):
        df=load(sym,tf); F=featsB(df,tf,sym)
        fu=align(load(sym,tf,"um"),df); fc=funding_cum(fu,sym)
        for name,sig in F.items():
            for H in Hs:
                test(name+"|long",df,sig,H,1,SPOT_RT,"CLASSIC",tf,sym,nsim=1000)
                test(name+"|short",fu,sig,H,-1,FUT_RT,"CLASSIC",tf,sym,nsim=1000,fund=fc)
        print(tf,"done",flush=True)
    # seasonality: hour-of-day (1h, hold 1..4h) and day-of-week (1d hold 1d), long & short
    df=load(sym,"1h"); fu=align(load(sym,"1h","um"),df); fc=funding_cum(fu,sym)
    for hr in range(24):
        sig=(df.index.hour==hr)
        for H in (1,4):
            test(f"hour{hr:02d}|long",df,sig,H,1,SPOT_RT,"SEASON","1h",sym,nsim=500)
            test(f"hour{hr:02d}|short",fu,sig,H,-1,FUT_RT,"SEASON","1h",sym,nsim=500,fund=fc)
    df=load(sym,"1d"); fu=align(load(sym,"1d","um"),df); fc=funding_cum(fu,sym)
    for dw in range(7):
        sig=(df.index.dayofweek==dw)
        test(f"dow{dw}|long",df,sig,1,1,SPOT_RT,"SEASON","1d",sym,nsim=1000)
        test(f"dow{dw}|short",fu,sig,1,-1,FUT_RT,"SEASON","1d",sym,nsim=1000,fund=fc)
    sig=(df.index.day>=28)|(df.index.day<=2)
    for H in (1,3): test("turnofmonth|long",df,sig,H,1,SPOT_RT,"SEASON","1d",sym)
    print("season done")
