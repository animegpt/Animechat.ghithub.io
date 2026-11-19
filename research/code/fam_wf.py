import sys; sys.path.insert(0,'.')
from lib import *; from pac import rev_bands
from scipy.stats import norm
coins=("BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT")
T={}
for sym in coins:
    for tf,Hs in (("1h",[6,12,24,48]),("4h",[3,6,12,24])):
        df=load(sym,tf); R=rev_bands(df)
        for k in (3,4,5,6):
            for H in Hs: T[(sym,tf,k,H)]=trades(df,R[f"above{k}"],H)
cfgs=sorted({(tf,k,H) for (_,tf,k,H) in T})
def t_(r): return r.mean()/(r.std(ddof=1)/np.sqrt(len(r))) if len(r)>5 else 0
rows=[]
for Y in (2022,2023,2024,2025):
    cut=pd.Timestamp(f"{Y}-01-01"); end=pd.Timestamp(f"{Y+1}-01-01")
    sc=sorted(((np.median([t_(T[(s,)+c].ret[T[(s,)+c].index<cut]) for s in coins]),c) for c in cfgs),reverse=True)
    best=sc[0][1]
    for s in coins:
        o=T[(s,)+best]; o=o[(o.index>=cut)&(o.index<end)]
        rows.append(dict(Y=Y,cfg=best,sym=s,n=len(o),mean_bp=round(o.ret.mean()*1e4,1),sum_pct=round(o.ret.sum()*100,1),mae=round(o.mae.min()*100,1)))
d=pd.DataFrame(rows); print(d.to_string())
print(d.groupby("sym")[["n","sum_pct"]].sum())
print("pooled OOS mean bp:",round(np.average(d.mean_bp.fillna(0),weights=d.n),1))
# full-dev ranking by median t
sc=sorted(((np.median([t_(T[(s,)+c].ret) for s in coins]),c) for c in cfgs),reverse=True)
print("top configs full dev by median t across 5 coins:",[(round(a,2),c) for a,c in sc[:6]])
