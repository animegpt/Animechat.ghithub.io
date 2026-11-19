"""Price Action Concepts -> testable boolean features (no lookahead: everything known at bar close)."""
import numpy as np, pandas as pd
from lib import atr, rma_atr

def structure(df,size):
    """LuxAlgo-style leg() pivots + BOS/CHoCH/CHoCH+ breaks. Returns dict of bool arrays."""
    h=df.h.values; l=df.l.values; c=df.c.values; n=len(c)
    hh=pd.Series(h).rolling(size).max().values; ll=pd.Series(l).rolling(size).min().values
    leg=0; ph=np.nan; pl=np.nan; phx=False; plx=False; trend=0
    lows=[]; highs=[]   # pivot history for CHoCH+
    out={k:np.zeros(n,bool) for k in ["bos_bull","choch_bull","chochp_bull","bos_bear","choch_bear","chochp_bear"]}
    piv_hi_idx=np.full(n,-1); piv_lo_idx=np.full(n,-1)
    phi=-1; pli=-1
    for t in range(size,n):
        newH = h[t-size] > hh[t]; newL = l[t-size] < ll[t]
        prev=leg
        if newH: leg=0
        elif newL: leg=1
        if leg!=prev:
            if leg==1: pl=l[t-size]; plx=False; pli=t-size; lows.append(pl)
            else: ph=h[t-size]; phx=False; phi=t-size; highs.append(ph)
        piv_hi_idx[t]=phi; piv_lo_idx[t]=pli
        if not np.isnan(ph) and not phx and c[t]>ph and c[t-1]<=ph:
            phx=True
            if trend==-1:
                plus=len(lows)>1 and lows[-1]>lows[-2]
                out["chochp_bull" if plus else "choch_bull"][t]=True
            else: out["bos_bull"][t]=True
            trend=1
        if not np.isnan(pl) and not plx and c[t]<pl and c[t-1]>=pl:
            plx=True
            if trend==1:
                plus=len(highs)>1 and highs[-1]<highs[-2]
                out["chochp_bear" if plus else "choch_bear"][t]=True
            else: out["bos_bear"][t]=True
            trend=-1
    out["any_bull"]=out["bos_bull"]|out["choch_bull"]|out["chochp_bull"]
    out["any_bear"]=out["bos_bear"]|out["choch_bear"]|out["chochp_bear"]
    out["piv_hi_idx"]=piv_hi_idx; out["piv_lo_idx"]=piv_lo_idx
    return out

def order_blocks(df,st,max_age=200):
    """On bullish break: OB = bar with lowest (volatility-parsed) low between last pivot-high and break bar.
       Signal 'ob_retest_bull' = first bar where low touches OB top while close stays above OB bottom (not mitigated).
       Symmetric for bear."""
    h=df.h.values; l=df.l.values; c=df.c.values; n=len(c)
    a=atr(df,200).values
    hv=(h-l)>=2*np.nan_to_num(a,nan=1e18)
    ph=np.where(hv,l,h); pl=np.where(hv,h,l)
    bull=np.zeros(n,bool); bear=np.zeros(n,bool)
    act_b=[]; act_s=[]   # (top,btm,created)
    for t in range(n):
        if st["any_bull"][t] and st["piv_hi_idx"][t]>=0:
            s=st["piv_hi_idx"][t]
            if t-s>=2:
                j=s+np.argmin(pl[s:t]); act_b.append([ph[j],pl[j],t])
        if st["any_bear"][t] and st["piv_lo_idx"][t]>=0:
            s=st["piv_lo_idx"][t]
            if t-s>=2:
                j=s+np.argmax(ph[s:t]); act_s.append([ph[j],pl[j],t])
        keep=[]
        for ob in act_b:
            if t<=ob[2]: keep.append(ob); continue
            if c[t]<ob[1] or t-ob[2]>max_age: continue        # mitigated / expired
            if l[t]<=ob[0]: bull[t]=True; continue             # retest -> signal once, then consumed
            keep.append(ob)
        act_b=keep[-10:]
        keep=[]
        for ob in act_s:
            if t<=ob[2]: keep.append(ob); continue
            if c[t]>ob[0] or t-ob[2]>max_age: continue
            if h[t]>=ob[1]: bear[t]=True; continue
            keep.append(ob)
        act_s=keep[-10:]
    return bull,bear

def fvg(df,filt=0.0):
    h=df.h.values; l=df.l.values; c=df.c.values; o=df.o.values; n=len(c)
    rng=(pd.Series(h).rolling(300).max()-pd.Series(l).rolling(300).min()).values
    th=rng*filt/100
    new_b=np.zeros(n,bool); new_s=np.zeros(n,bool); ret_b=np.zeros(n,bool); ret_s=np.zeros(n,bool)
    gb=[]; gs=[]
    for t in range(2,n):
        if l[t]>h[t-2] and c[t-1]>h[t-2] and (l[t]-h[t-2])>np.nan_to_num(th[t]):
            new_b[t]=True; gb.append([l[t],h[t-2],t])
        if h[t]<l[t-2] and c[t-1]<l[t-2] and (l[t-2]-h[t])>np.nan_to_num(th[t]):
            new_s[t]=True; gs.append([l[t-2],h[t],t])
        k=[]
        for g in gb:   # bullish gap: top=l[t], btm=h[t-2]; retest when price dips into gap, invalid if close below btm
            if t<=g[2]: k.append(g); continue
            if c[t]<g[1] or t-g[2]>100: continue
            if l[t]<=g[0]: ret_b[t]=True; continue
            k.append(g)
        gb=k[-8:]
        k=[]
        for g in gs:
            if t<=g[2]: k.append(g); continue
            if c[t]>g[0] or t-g[2]>100: continue
            if h[t]>=g[1]: ret_s[t]=True; continue
            k.append(g)
        gs=k[-8:]
    return new_b,new_s,ret_b,ret_s

def rev_bands(df,length=30):
    basis=df.c.rolling(length).mean(); span=atr(df,length)
    out={}
    for k in (3,4,5,6):
        out[f"below{k}"]=(df.c<basis-span*k).values
        out[f"above{k}"]=(df.c>basis+span*k).values
    # first touch only (entering the band)
    for kk in list(out):
        v=out[kk]; out[kk]=v&~np.r_[False,v[:-1]]
    return out

def sweeps(df,size=10):
    """liquidity sweep: wick beyond last confirmed pivot low/high, close back inside."""
    h=df.h.values; l=df.l.values; c=df.c.values; n=len(c)
    pl=pd.Series(l).rolling(2*size+1,center=True).min().values==l
    ph=pd.Series(h).rolling(2*size+1,center=True).max().values==h
    bull=np.zeros(n,bool); bear=np.zeros(n,bool); lastL=np.nan; lastH=np.nan; usedL=usedH=False
    for t in range(n):
        j=t-size
        if j>=0 and pl[j]: lastL=l[j]; usedL=False
        if j>=0 and ph[j]: lastH=h[j]; usedH=False
        if not usedL and not np.isnan(lastL) and l[t]<lastL and c[t]>lastL: bull[t]=True; usedL=True
        elif not np.isnan(lastL) and c[t]<lastL: usedL=True
        if not usedH and not np.isnan(lastH) and h[t]>lastH and c[t]<lastH: bear[t]=True; usedH=True
        elif not np.isnan(lastH) and c[t]>lastH: usedH=True
    return bull,bear

def equal_hl(df,size=3,thr=0.1):
    """EQL/EQH pivots (within thr*ATR200 of previous pivot); signal = later sweep of that equal level and close back."""
    h=df.h.values; l=df.l.values; c=df.c.values; n=len(c)
    a=atr(df,200).values
    hh=pd.Series(h).rolling(size).max().values; ll=pd.Series(l).rolling(size).min().values
    leg=0; lastpl=np.nan; lastph=np.nan; eql=np.nan; eqh=np.nan
    bull=np.zeros(n,bool); bear=np.zeros(n,bool)
    for t in range(size,n):
        prev=leg
        if h[t-size]>hh[t]: leg=0
        elif l[t-size]<ll[t]: leg=1
        if leg!=prev:
            if leg==1:
                v=l[t-size]
                if not np.isnan(lastpl) and abs(v-lastpl)<thr*np.nan_to_num(a[t],nan=0): eql=min(v,lastpl)
                lastpl=v
            else:
                v=h[t-size]
                if not np.isnan(lastph) and abs(v-lastph)<thr*np.nan_to_num(a[t],nan=0): eqh=max(v,lastph)
                lastph=v
        if not np.isnan(eql) and l[t]<eql:
            if c[t]>eql: bull[t]=True
            eql=np.nan
        if not np.isnan(eqh) and h[t]>eqh:
            if c[t]<eqh: bear[t]=True
            eqh=np.nan
    return bull,bear
