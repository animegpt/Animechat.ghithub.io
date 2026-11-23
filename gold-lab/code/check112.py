"""Engine check after a data rebuild: Williams #112 must give disc n 2053, net1 +5.09bp t 2.25 (net2 +7.29 t 3.23); conf n 1123."""
import json, lab, refs
M = lab.Mkt(lab.load_hourly("XAUUSD")); T = refs.williams(M)
d = lab.summ(M, T, lab.DISC, nsim=200); c = lab.summ(M, T, lab.CONF, nsim=200)
print(json.dumps({"disc": {k: d[k] for k in ("n", "net1", "net2")}, "conf": {k: c[k] for k in ("n", "net1", "net2")}}, default=float))
