"""build the #88 cache: condition masks + per-minute outcomes (2017-2023 dev data; vault excluded by the loader)"""
import os, json, time, numpy as np
import os88_lib as L

if __name__ == "__main__":
    t0 = time.time(); os.makedirs(L.CACHE, exist_ok=True)
    D = L.Data(); print("minutes", D.n, D.idx.min(), D.idx.max(), "disc_end", D.disc_end, flush=True)
    names, CL, CS = L.conditions(D); print("conditions", len(names), round(time.time() - t0), "s", flush=True)
    np.save(f"{L.CACHE}/condL.npy", np.stack([CL[k] for k in names])); np.save(f"{L.CACHE}/condS.npy", np.stack([CS[k] for k in names]))
    for k in names:
        a = CL[k][:D.disc_end].mean(); b = CS[k][:D.disc_end].mean()
        if a == 0 or a == 1: print("WARN degenerate condition", k, a)
    for wide, tag in ((0.0, ""), (3.0, "_wide")):
        O = L.outcomes(D, wide)
        for (side, ex), d in O.items():
            for f in ("g", "A", "B", "C", "xi", "ok"):
                np.save(f"{L.CACHE}/out{tag}_{side}_{ex}_{f}.npy", d[f])
        print("outcomes", tag, round(time.time() - t0), "s", flush=True)
    np.save(f"{L.CACHE}/dayid.npy", D.dayid); np.save(f"{L.CACHE}/tns.npy", D.tns)
    np.save(f"{L.CACHE}/series.npy", np.stack([D.o, D.h, D.l, D.c, D.v]))
    json.dump({"names": names, "disc_end": D.disc_end, "conf_end": D.conf_end, "n": D.n}, open(f"{L.CACHE}/meta.json", "w"))
    print("done", round(time.time() - t0), "s", flush=True)
