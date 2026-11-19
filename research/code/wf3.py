import pickle, numpy as np, pandas as pd, sys; sys.path.insert(0,'.')
from lib import *
D={c:pickle.load(open(f"{S}/trades_{c}USDT.pkl","rb")) for c in ("BTC","ETH")}
data={(c,tf):load(c+"USDT",tf) for c in ("BTC","ETH") for tf in ("1h","4h","1d")}
rc={}
def randmean(c,tf,H,side,Y):
    k=(c,tf,H,side,Y)
    if k not in rc:
        df=data[(c,tf)]; f=fwd(df,H,side)-(SPOT_RT if side==1 else FUT_RT)
        rc[k]=np.nanmean(f[(df.index.year==Y)&~np.isnan(f)])
    return rc[k]
def tst(r): return r.mean()/(r.std(ddof=1)/np.sqrt(len(r))) if len(r)>2 and r.std()>0 else -9
def excess(c,k,o):
    rm=np.array([randmean(c,k[1],k[2],k[3],y) for y in o.index.year]); return o.ret-rm
def select(Y,sides,topk):
    cut=pd.Timestamp(f"{Y}-01-01"); sc=[]
    for k in D["BTC"]:
        if k[3] not in sides: continue
        ts=[]
        for c in ("BTC","ETH"):
            o=D[c][k]; o=o[o.index<cut]
            if len(o)<20: ts=None; break
            ts.append(min(tst(o.ret),tst(excess(c,k,o))))
        if ts: sc.append((min(ts),k))
    sc.sort(reverse=True); return sc[:topk]
def oos_stat(picks_by_year,coin):
    ex=[]
    for Y,picks in picks_by_year.items():
        cut=pd.Timestamp(f"{Y}-01-01"); end=pd.Timestamp(f"{Y+1}-01-01")
        for s,k in picks:
            o=D[coin][k]; o=o[(o.index>=cut)&(o.index<end)]
            if len(o): ex.append(excess(coin,k,o).values)
    return np.concatenate(ex).mean()
def null_dist(picks_by_year,coin,nsim=2000,rng=np.random.default_rng(1)):
    tot=np.zeros(nsim); N=0
    for Y,picks in picks_by_year.items():
        cut=pd.Timestamp(f"{Y}-01-01"); end=pd.Timestamp(f"{Y+1}-01-01")
        groups={}
        for s,k in picks: groups.setdefault((k[0],k[1],k[3]),[]).append(k)
        for (nm,tf,side),ks in groups.items():
            df=data[(coin,tf)]; pool=np.flatnonzero(df.index.year==Y)
            cnt=max(len(D[coin][k][(D[coin][k].index>=cut)&(D[coin][k].index<end)]) for k in ks)
            if cnt==0: continue
            draws=pool[rng.integers(0,len(pool)-30,size=(nsim,cnt))]  # same random bars for all H of this signal
            for k in ks:
                n_k=len(D[coin][k][(D[coin][k].index>=cut)&(D[coin][k].index<end)])
                if n_k==0: continue
                f=fwd(df,k[2],side)-(SPOT_RT if side==1 else FUT_RT)
                v=np.nan_to_num(f[draws[:,:n_k]])-randmean(coin,tf,k[2],side,Y)
                tot+=v.sum(1); N+=n_k
    return tot/N
if __name__=="__main__":
    for sides,lab in (({1},"spot-long"),({1,-1},"long+short")):
        for topk in (1,3,5,10,20):
            P={Y:select(Y,sides,topk) for Y in (2022,2023,2024,2025)}
            if topk==5:
                for Y,p in P.items(): print(Y,[ (round(s,2),k) for s,k in p])
            for coin in ("BTC","ETH"):
                st=oos_stat(P,coin); nd=null_dist(P,coin)
                print(f"{lab:10s} top{topk:2d} {coin}: OOS mean excess {st*1e4:6.1f}bp  null sd {nd.std()*1e4:5.1f}  p={np.mean(nd>=st):.3f}",flush=True)
