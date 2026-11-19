import pickle, numpy as np, pandas as pd, sys; sys.path.insert(0,'.')
from lib import load, align, SPOT_RT, FUT_RT, fwd, funding_cum
B=pickle.load(open(f"{S}/trades_BTCUSDT.pkl","rb")) if False else None
