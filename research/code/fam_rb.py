import sys; sys.path.insert(0,'.')
from lib import *; from pac import rev_bands
rows=[]
for sym in ("BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"):
    for tf,Hs in (("1h",[6,12,24,48]),("4h",[3,6,12,24])):
        df=load(sym,tf); R=rev_bands(df)
        for k in (3,4,5,6):
            for H in Hs:
                rec,t=test(f"rbBreak{k}|long",df,R[f"above{k}"],H,1,SPOT_RT,"RB_FAMILY",tf,sym,nsim=1000)
                r={kk:rec.get(kk) for kk in ["sym","tf","H","n","mean_bp","t","excess_bp","p_vs_random"]}; r["k"]=k
                for y in range(2020,2026): r[f"y{y}"]=rec.get("years",{}).get(y,{}).get("mean_bp")
                rows.append(r)
d=pd.DataFrame(rows); pd.set_option("display.width",250)
print(d.to_string())
d.to_csv(f"{S}/rb_family.csv")
