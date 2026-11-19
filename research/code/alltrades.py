import sys, pickle; sys.path.insert(0,'.')
from lib import *; from phase1 import feats; from phase2 import featsB
sym=sys.argv[1]; store={}
for tf,Hs in (("1h",[6,12,24,48]),("4h",[3,6,12,24]),("1d",[1,3,5,10])):
    df=load(sym,tf); fu=align(load(sym,tf,"um"),df); fc=funding_cum(fu,sym)
    F=featsB(df,tf,sym)
    if tf!="1d": F.update({k:v for k,v in feats(df).items()})
    for name,sig in F.items():
        for H in Hs:
            store[(name,tf,H,1)]=trades(df,sig,H,1,SPOT_RT)[["ret","mae"]]
            store[(name,tf,H,-1)]=trades(fu,sig,H,-1,FUT_RT,fund=fc)[["ret","mae"]]
    print(sym,tf,len(store),flush=True)
pickle.dump(store,open(f"{S}/trades_{sym}.pkl","wb"))
