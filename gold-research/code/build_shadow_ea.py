"""Generate mt5/GoldWilliams_Shadow.mq5 from the template + mt5/rf_shadow_model.json (300 trees, same approach as the
earlier build_mt5_ea.py: trees written out as flat MQL5 arrays). Feature assembly is generated from features149 so the
column order equals the model's training order (asserted)."""
import os, json
import features149 as F
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = json.load(open(f"{HERE}/mt5/rf_shadow_model.json")); cols = J["cols"]
RAWN = []
for f in F.SIGNED + F.NONDIR + [p for b in F.PAIRS for p in b[:2]]:
    if f not in RAWN: RAWN.append(f)
ri = {f: k for k, f in enumerate(RAWN)}
TFI = {"H1": 0, "H4": 1, "D1": 2}
lines, order = [], []
L1 = lambda e: f"MathLog(1.0 + MathMin({e}, 999.0))"
for tf in F.TFS:
    t = TFI[tf]; R = lambda f: f"RAW[{t}][{ri[f]}]"
    for f in F.SIGNED: order.append(f"{tf}_{f}"); lines.append(f"{R(f)} * side")
    for f in F.NONDIR: order.append(f"{tf}_{f}"); lines.append(R(f))
    for b, s, kind in F.PAIRS:
        base = b[:-2] if b.endswith("_b") else b
        w = f"(side > 0 ? {R(b)} : {R(s)})"; a = f"(side > 0 ? {R(s)} : {R(b)})"
        if kind == "since": w, a = L1(w), L1(a)
        order += [f"{tf}_{base}_with", f"{tf}_{base}_against"]; lines += [w, a]
    order.append(f"{tf}_align3")
    lines.append(f"(({R('pac_sw_trend')} * side > 0) ? 1.0 : 0.0) + (({R('om_hw')} * side > 0) ? 1.0 : 0.0) + (({R('so_st_dir')} * side > 0) ? 1.0 : 0.0)")
pos = {c: k for k, c in enumerate(order)}
for ind, f in (("pac", "pac_sw_trend"), ("om", "om_hw"), ("so", "so_st_dir")):
    order.append(f"mtf_{ind}_votes")
    lines.append(" + ".join(f"((out[{pos[f'{tf}_{f}']}] > 0) ? 1.0 : 0.0)" for tf in F.TFS))
pos = {c: k for k, c in enumerate(order)}
order.append("mtf_align3_majority")
lines.append(" + ".join(f"((out[{pos[f'mtf_{i}_votes']}] >= 2) ? 1.0 : 0.0)" for i in ("pac", "om", "so")))
order.append("mtf_align9"); lines.append(" + ".join(f"out[{pos[f'{tf}_align3']}]" for tf in F.TFS))
assert order == cols, "feature order mismatch"

rawblock = f"#define NRAW {len(RAWN)}\nstring RAWN[NRAW] = {{" + ", ".join(f'"{x}"' for x in RAWN) + "};"
asm = [f"#define NFEAT {len(cols)}", "string FEATN[NFEAT] = {" + ", ".join(f'"{c}"' for c in cols) + "};",
       "void Assemble(double side, double &out[])", "  {"]
asm += [f"   out[{k}] = {e};   // {c}" for k, (e, c) in enumerate(zip(lines, cols))]
asm += ["  }"]
feat, thr, left, right, val, off = [], [], [], [], [], []
for t in J["trees"]:
    o = len(feat); off.append(o)
    feat += t["feature"]; thr += t["threshold"]; val += t["value"]
    left += [x + o if x >= 0 else -1 for x in t["left"]]; right += [x + o if x >= 0 else -1 for x in t["right"]]
def arr(typ, name, xs, fmt):
    body = ",".join(fmt(x) for x in xs); return f"const {typ} {name}[{len(xs)}] = {{{body}}};"
model = [f"// RF regression, {len(J['trees'])} trees, {len(feat)} nodes. params {J['params']}. Trained on gold 2005-2023 (research #150).",
         f"#define NTREES {len(J['trees'])}", f"#define NREF {len(J['ref_sorted'])}",
         arr("int", "T_OFF", off, str), arr("int", "T_FEAT", feat, str), arr("double", "T_THR", thr, repr),
         arr("int", "T_LEFT", left, str), arr("int", "T_RIGHT", right, str), arr("double", "T_VAL", val, repr),
         arr("double", "REF", J["ref_sorted"], repr),
         "double PredictRF(const double &x[])",
         "  {",
         "   double s = 0;",
         "   for(int t = 0; t < NTREES; t++)",
         "     {",
         "      int nd = T_OFF[t];",
         "      while(T_LEFT[nd] >= 0) nd = ((double)(float)x[T_FEAT[nd]] <= T_THR[nd]) ? T_LEFT[nd] : T_RIGHT[nd];   // sklearn: float32 features",
         "      s += T_VAL[nd];",
         "     }",
         "   return s / NTREES;",
         "  }"]
src = open(f"{HERE}/mt5/GoldWilliams_Shadow.template.mq5").read()
src = src.replace("//@@RAWNAMES@@", rawblock).replace("//@@ASSEMBLE@@", "\n".join(asm)).replace("//@@MODEL@@", "\n".join(model))
assert "@@" not in src
open(f"{HERE}/mt5/GoldWilliams_Shadow.mq5", "w").write(src)
print("written", len(src), "chars | NRAW", len(RAWN), "NFEAT", len(cols), "nodes", len(feat))
