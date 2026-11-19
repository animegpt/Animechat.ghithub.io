import pickle, numpy as np, pandas as pd, sys
S=sys.argv[1]
B=pickle.load(open(f"{S}/trades_BTCUSDT.pkl","rb")); E=pickle.load(open(f"{S}/trades_ETHUSDT.pkl","rb"))
def tst(r): 
    return r.mean()/(r.std(ddof=1)/np.sqrt(len(r))) if len(r)>2 and r.std()>0 else -9
def run(sides,topk,label):
    rows=[]
    for Y in (2022,2023,2024,2025):
        cut=pd.Timestamp(f"{Y}-01-01"); end=pd.Timestamp(f"{Y+1}-01-01")
        sc=[]
        for k in B:
            if k[3] not in sides: continue
            b=B[k]; e=E[k]; bi=b[b.index<cut].ret; ei=e[e.index<cut].ret
            if len(bi)<20 or len(ei)<20: continue
            sc.append((min(tst(bi),tst(ei)),k))
        sc.sort(reverse=True); pick=[k for _,k in sc[:topk]]
        for k in pick:
            for coin,D in (("BTC",B),("ETH",E)):
                o=D[k]; o=o[(o.index>=cut)&(o.index<end)]
                rows.append(dict(Y=Y,coin=coin,cfg=str(k),is_t=round([s for s,kk in sc if kk==k][0],2),n=len(o),mean_bp=o.ret.mean()*1e4 if len(o) else np.nan,sum_pct=o.ret.sum()*100,mae=o.mae.min()*100 if len(o) else np.nan))
    d=pd.DataFrame(rows)
    print(f"\n=== WF {label}: top{topk} by min(t_BTC,t_ETH) in-sample ===")
    if topk<=3: print(d.round(1).to_string())
    g=d.groupby(["Y","coin"]).agg(n=("n","sum"),mean_bp=("mean_bp","mean"),sum_pct=("sum_pct","mean")).round(1)
    print(g.to_string())
    allr=[]
    return d
for sides,lab in (({1,-1},"spot-long + futures-short"),({1},"spot long only")):
    for k in (1,10):
        run(sides,k,lab)
