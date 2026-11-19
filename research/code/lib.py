import numpy as np, pandas as pd, json, os
S=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG=f"{S}/testlog.jsonl"
SPOT_RT=2*(7.5+2.0)/1e4      # 0.075% fee + 2bp slippage per side
FUT_RT=2*(5.0+2.0)/1e4       # 0.05% taker + 2bp slippage per side (+ funding added separately)
RNG=np.random.default_rng(7)

def load(sym="BTCUSDT",tf="1h",market="spot",hidden=False):
    name=f"{market}_{sym}_1h"
    df=pd.read_parquet(f"{S}/raw/{'hidden_'+name if hidden else name+'_dev'}.parquet")
    if hidden:  # warm-up history needed for indicators
        dev=pd.read_parquet(f"{S}/raw/{name}_dev.parquet"); df=pd.concat([dev,df])
    if tf!="1h":
        rule={"4h":"4h","1d":"1D"}[tf]
        df=df.resample(rule,label="left",closed="left").agg({"o":"first","h":"max","l":"min","c":"last","v":"sum","qv":"sum","n":"sum","tbv":"sum","tbqv":"sum"}).dropna()
    return df

def funding_cum(df,sym="BTCUSDT",hidden=False):
    """cumulative funding aligned to df bars (value at bar i = funding paid up to bar i close)"""
    f=pd.read_parquet(f"{S}/raw/fund_{sym}_dev.parquet")
    if hidden: f=pd.concat([f,pd.read_parquet(f"{S}/raw/hidden_fund_{sym}.parquet")])
    cs=f.fr.cumsum()
    return cs.reindex(df.index,method="ffill").fillna(0).values

def align(fu,df):
    """futures bars re-indexed to the spot timestamps (missing bars forward-filled) so signal positions match"""
    return fu.reindex(df.index).ffill()

def trades(df,sig,H,side=1,cost=SPOT_RT,fund=None,start=None,end=None):
    assert len(sig)==len(df), "signal/data length mismatch"
    """sig: bool array, entry at close of signal bar, exit at close H bars later; non-overlapping.
       returns DataFrame of trades with net return and MAE (worst adverse excursion during trade)."""
    c=df.c.values; h=df.h.values; l=df.l.values; idx=df.index; n=len(c)
    s=np.asarray(sig,bool).copy()
    if start is not None: s&=(idx>=pd.Timestamp(start))
    if end is not None: s&=(idx<pd.Timestamp(end))
    out=[]; i=0; cand=np.flatnonzero(s)
    nxt=-1
    for i in cand:
        if i<=nxt or i+H>=n: continue
        e=c[i]; x=c[i+H]
        if side==1: g=x/e-1; mae=l[i+1:i+H+1].min()/e-1
        else: g=e/x-1; mae=e/h[i+1:i+H+1].max()-1
        fr=0.0
        if fund is not None: fr=(fund[i+H]-fund[i])*side   # long pays positive funding, short receives
        out.append((idx[i],g-cost-fr,mae,i))
        nxt=i+H
    t=pd.DataFrame(out,columns=["t","ret","mae","i"]).set_index("t")
    return t

def fwd(df,H,side=1):
    c=df.c.values; r=np.full(len(c),np.nan); r[:-H]=c[H:]/c[:-H]-1
    return r if side==1 else (1/(1+r)-1)

def random_baseline(df,t,H,side=1,cost=SPOT_RT,nsim=2000):
    """same number of entries per calendar year, random bars, same hold/side/cost"""
    f=fwd(df,H,side)-cost; yrs=df.index.year.values
    sims=np.zeros(nsim); tot=len(t)
    if tot==0: return np.nan,np.nan
    for y,cnt in t.index.year.value_counts().items():
        pool=np.flatnonzero((yrs==y)&~np.isnan(f))
        draw=RNG.integers(0,len(pool),size=(nsim,cnt))
        sims+=f[pool[draw]].sum(1)
    sims/=tot
    m=t.ret.mean()
    return float(sims.mean()), float((np.sum(sims>=m)+1)/(nsim+1))

def summarize(t):
    if len(t)==0: return {}
    g=t.groupby(t.index.year)
    by={int(y):{"n":int(len(x)),"mean_bp":round(x.ret.mean()*1e4,1),"win":round((x.ret>0).mean(),2),
                 "sum_pct":round(x.ret.sum()*100,1),"worst_mae_pct":round(x.mae.min()*100,1)} for y,x in g}
    r=t.ret; tstat=r.mean()/(r.std(ddof=1)/np.sqrt(len(r))) if len(r)>2 else np.nan
    return {"n":int(len(r)),"mean_bp":round(r.mean()*1e4,1),"t":round(float(tstat),2),"win":round(float((r>0).mean()),3),
            "worst_mae_pct":round(float(t.mae.min()*100),1),"years":by}

def test(name,df,sig,H,side=1,cost=SPOT_RT,family="",tf="",sym="BTCUSDT",log=True,start=None,end=None,nsim=2000,fund=None):
    t=trades(df,sig,H,side,cost,fund=fund,start=start,end=end)
    s=summarize(t)
    if not s: s={"n":0}
    else:
        rb,p=random_baseline(df,t,H,side,cost,nsim)
        s["rand_mean_bp"]=round(rb*1e4,1); s["excess_bp"]=round(s["mean_bp"]-rb*1e4,1); s["p_vs_random"]=round(p,4)
    rec={"name":name,"family":family,"tf":tf,"sym":sym,"H":H,"side":side,"cost_rt_bp":round(cost*1e4,1),**s}
    if log:
        with open(LOG,"a") as fh: fh.write(json.dumps(rec)+"\n")
    return rec,t

def atr(df,n):
    pc=df.c.shift(1); tr=pd.concat([df.h-df.l,(df.h-pc).abs(),(df.l-pc).abs()],axis=1).max(1)
    return tr.rolling(n).mean()
def rma_atr(df,n):
    pc=df.c.shift(1); tr=pd.concat([df.h-df.l,(df.h-pc).abs(),(df.l-pc).abs()],axis=1).max(1)
    return tr.ewm(alpha=1/n,adjust=False).mean()
