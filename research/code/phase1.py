import sys; sys.path.insert(0,'.')
from lib import *; from pac import *
def feats(df):
    F={}
    for sz,tag in ((5,"int"),(50,"swg")):
        st=structure(df,sz)
        for k in ["bos","choch","chochp","any"]:
            F[f"{tag}_{k}_bull"]=st[f"{k}_bull"]; F[f"{tag}_{k}_bear"]=st[f"{k}_bear"]
        b,s=order_blocks(df,st); F[f"{tag}_ob_bull"]=b; F[f"{tag}_ob_bear"]=s
    nb,ns,rb,rs=fvg(df); F["fvg_new_bull"]=nb;F["fvg_new_bear"]=ns;F["fvg_ret_bull"]=rb;F["fvg_ret_bear"]=rs
    nb,ns,rb,rs=fvg(df,filt=2.0); F["fvgF_new_bull"]=nb;F["fvgF_new_bear"]=ns
    for k,v in rev_bands(df).items(): F["rb_"+k.replace("below","").replace("above","")+("_bull" if "below" in k else "_bear")]=v
    b,s=sweeps(df,10); F["sweep10_bull"]=b;F["sweep10_bear"]=s
    b,s=sweeps(df,30); F["sweep30_bull"]=b;F["sweep30_bear"]=s
    b,s=equal_hl(df); F["eq_bull"]=b;F["eq_bear"]=s
    return F
if __name__=="__main__":
    sym=sys.argv[1] if len(sys.argv)>1 else "BTCUSDT"
    for tf,Hs in (("1h",[6,12,24,48]),("4h",[3,6,12,24])):
        df=load(sym,tf); F=feats(df)
        fu=align(load(sym,tf,"um"),df); fc=funding_cum(fu,sym)
        for name,sig in F.items():
            for H in Hs:
                # spot long: on bull signal (continuation) and on bear signal (fade)
                test(name+"|long",df,sig,H,1,SPOT_RT,"PAC",tf,sym,nsim=1000)
                # futures short: on bear signal (continuation) and bull signal (fade)
                test(name+"|short",fu,sig,H,-1,FUT_RT,"PAC",tf,sym,nsim=1000,fund=fc)
        print(tf,"done",flush=True)
