"""Generate mt5/combo/GoldComboShadow.mqh: the 206 three-indicator features (same MQL5 port as GoldWilliams_Shadow,
parity-checked 0.0 on 388 trades) + the two #159 per-strategy RF models (Sonic, Overnight) + entry/exit logging.
Everything is prefixed GS_ so it cannot collide with GoldComboAI.mq5 names. LOG ONLY: never sends or changes orders."""
import os, re, json
import features149 as F
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = open(f"{HERE}/mt5/GoldWilliams_Shadow.template.mq5").read()

# ---- reuse the verified pieces of the Williams Shadow template
time_part = TPL[TPL.index("datetime ToUTC(datetime s)"):TPL.index("//==================================================================== indicator port")]
ind_part = TPL[TPL.index("//==================================================================== indicator port"):TPL.index("//---- features in research column order")]
names = ["ToUTC", "NthSundayUTC", "NYOffset", "ToNY", "TradingDayKey", "NYMinute", "NYHour", "IsNum", "Clip", "Sgn", "Rma", "Ema",
         "TrueRange", "Since", "RollMean", "RollSum", "Structure", "OrderBlocks", "Fvg", "EqLevels", "Divergence", "StOne", "StAi",
         "RAWN", "NRAW", "RAW", "gTf", "Put", "ComputeRaw", "BuildAndCompute", "NANV", "BIGV", "gShNote", "InpHistBars", "InpMinBars"]
body = time_part + ind_part
for nm in sorted(names, key=len, reverse=True):
    body = re.sub(rf"\b{nm}\b", f"GS_{nm}", body)
# local OHLCV arrays of the TF aggregation renamed (avoid hiding GoldComboAI globals O,H,L,C)
b0 = body.index("bool GS_BuildAndCompute"); seg = body[b0:]
for a, b in (("O", "tO"), ("H", "tH"), ("L", "tL"), ("C", "tC"), ("V", "tV")):
    seg = re.sub(rf"\b{a}\b", b, seg)
body = body[:b0] + seg
body = body.replace("double GS_RAW[3][GS_NRAW];", "double GS_RAW[3][GS_NRAW];")

# ---- raw names + assembly (identical generation to build_shadow_ea.py)
RAWN = []
for f in F.SIGNED + F.NONDIR + [p for b in F.PAIRS for p in b[:2]]:
    if f not in RAWN: RAWN.append(f)
ri = {f: k for k, f in enumerate(RAWN)}; TFI = {"H1": 0, "H4": 1, "D1": 2}
lines, order = [], []
L1 = lambda e: f"MathLog(1.0 + MathMin({e}, 999.0))"
for tf in F.TFS:
    t = TFI[tf]; R = lambda f: f"GS_RAW[{t}][{ri[f]}]"
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
    order.append(f"mtf_{ind}_votes"); lines.append(" + ".join(f"((out[{pos[f'{tf}_{f}']}] > 0) ? 1.0 : 0.0)" for tf in F.TFS))
pos = {c: k for k, c in enumerate(order)}
order.append("mtf_align3_majority"); lines.append(" + ".join(f"((out[{pos[f'mtf_{i}_votes']}] >= 2) ? 1.0 : 0.0)" for i in ("pac", "om", "so")))
order.append("mtf_align9"); lines.append(" + ".join(f"out[{pos[f'{tf}_align3']}]" for tf in F.TFS))
models = {k: json.load(open(f"{HERE}/mt5/combo/rf_combo_{k}.json")) for k in ("sonic", "overnight")}
for J in models.values(): assert order == J["cols"], "feature order mismatch"
rawblock = f"#define GS_NRAW {len(RAWN)}\nstring GS_RAWN[GS_NRAW] = {{" + ", ".join(f'"{x}"' for x in RAWN) + "};"
body = body.replace("//@@RAWNAMES@@", rawblock)
asm = [f"#define GS_NFEAT {len(order)}", "string GS_FEATN[GS_NFEAT] = {" + ", ".join(f'"{c}"' for c in order) + "};",
       "void GS_Assemble(double side, double &out[])", "  {"] + [f"   out[{k}] = {e};" for k, e in enumerate(lines)] + ["  }"]


def model_arrays(J, P):
    feat, thr, left, right, val, off = [], [], [], [], [], []
    for t in J["trees"]:
        o = len(feat); off.append(o); feat += t["feature"]; thr += t["threshold"]; val += t["value"]
        left += [x + o if x >= 0 else -1 for x in t["left"]]; right += [x + o if x >= 0 else -1 for x in t["right"]]
    arr = lambda typ, nm, xs, fmt: f"const {typ} {P}{nm}[{len(xs)}] = {{{','.join(fmt(x) for x in xs)}}};"
    return [f"// {J['model']}", arr("int", "OFF", off, str), arr("int", "FEAT", feat, str), arr("double", "THR", thr, repr),
            arr("int", "LEFT", left, str), arr("int", "RIGHT", right, str), arr("double", "VAL", val, repr), arr("double", "REF", J["ref_sorted"], repr)]


mdl = model_arrays(models["sonic"], "GS_S_") + model_arrays(models["overnight"], "GS_O_")
mdl += ["""double GS_Tree(const int &off[], const int &feat[], const double &thr[], const int &left[], const int &right[], const double &val[], const double &x[])
  {
   double s = 0; int nt = ArraySize(off);
   for(int t = 0; t < nt; t++)
     {
      int nd = off[t];
      while(left[nd] >= 0) nd = ((double)(float)x[feat[nd]] <= thr[nd]) ? left[nd] : right[nd];   // sklearn: float32 features
      s += val[nd];
     }
   return s / nt;
  }
double GS_Pct(const double &ref[], double p) { int c = 0, m = ArraySize(ref); for(int k = 0; k < m; k++) if(ref[k] <= p) c++; return (double)c / m; }"""]

head = """//+------------------------------------------------------------------+
//| GoldComboShadow.mqh  (GENERATED by code/build_combo_shadow.py)   |
//| SHADOW for GoldComboAI: at every Sonic / Overnight entry it      |
//| computes the 206 three-indicator features and the frozen #159    |
//| per-strategy RF model and LOGS the size it would have used       |
//| (0.5-1.5). It never sends, closes or resizes any order.          |
//| Research verdict #159: "probable, not proven" (DSR fail).        |
//+------------------------------------------------------------------+
input group "Shadow AI (log only, never trades)"
input bool   InpGSShadow     = true;     // Log the three-indicator RF opinion for each Sonic / Overnight trade
input int    GS_InpHistBars  = 80000;    // H1 bars for the features. Overnight model needs ~80000 (13 y) to match research; Sonic is stable from 20000
input int    GS_InpMinBars   = 15000;    // min usable bars (Strategy Tester parity run: e.g. 4000)
input bool   InpGSDumpBars   = true;     // dump H1 bars once per day (Python parity check)
string GS_SigFile = "GoldComboShadow_signals.csv", GS_TrdFile = "GoldComboShadow_trades.csv", GS_BarFile = "GoldComboShadow_bars.csv";
double GS_NANV = 0; bool GS_inited = false; string GS_gShNote = "";
"""
body = body.replace("GS_InpHistBars", "GS_InpHistBars").replace("GS_InpMinBars", "GS_InpMinBars")
tail = r'''
struct GS_Rec { long pid; string strat; int side; datetime entT; double ep, vol, eq, pred, pct, size; bool ok; };
GS_Rec GS_recs[];

double GS_VPP() { double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE); return ts > 0 ? tv / ts : 0; }

// call right AFTER a successful entry order of Sonic (magic, "SONIC", side) or Overnight (magic, "OVERNIGHT", 1)
void GS_AfterEntry(long magic, string strat, int side)
  {
   if(!InpGSShadow) return;
   if(!GS_inited) { GS_NANV = MathSqrt(-1.0); GS_inited = true; }
   long pid = 0; datetime entT = TimeCurrent(); double ep = 0, vol = 0;
   for(int k = PositionsTotal() - 1; k >= 0; k--)
     {
      ulong tk = PositionGetTicket(k); if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != magic) continue;
      pid = PositionGetInteger(POSITION_IDENTIFIER); entT = (datetime)PositionGetInteger(POSITION_TIME);
      ep = PositionGetDouble(POSITION_PRICE_OPEN); vol = PositionGetDouble(POSITION_VOLUME); break;
     }
   if(pid == 0) { Print("Shadow: position not found after entry (", strat, ")"); return; }
   GS_Rec r; r.pid = pid; r.strat = strat; r.side = side; r.entT = entT; r.ep = ep; r.vol = vol; r.eq = AccountInfoDouble(ACCOUNT_EQUITY);
   r.pred = 0; r.pct = 0; r.size = 1.0; r.ok = false;
   double x[]; ArrayResize(x, GS_NFEAT);
   MqlDateTime t; TimeToStruct(GS_ToUTC(entT), t); t.min = 0; t.sec = 0; datetime t0 = StructToTime(t);
   for(int a = 0; a < 3; a++) for(int k = 0; k < GS_NRAW; k++) GS_RAW[a][k] = GS_NANV;
   GS_gShNote = "";
   if(GS_BuildAndCompute(t0))
     {
      GS_Assemble((double)side, x); bool ok = true;
      for(int k = 0; k < GS_NFEAT; k++) if(!GS_IsNum(x[k])) { ok = false; GS_gShNote = "NaN feature " + IntegerToString(k); break; }
      if(ok)
        {
         if(strat == "SONIC") { r.pred = GS_Tree(GS_S_OFF, GS_S_FEAT, GS_S_THR, GS_S_LEFT, GS_S_RIGHT, GS_S_VAL, x); r.pct = GS_Pct(GS_S_REF, r.pred); }
         else                 { r.pred = GS_Tree(GS_O_OFF, GS_O_FEAT, GS_O_THR, GS_O_LEFT, GS_O_RIGHT, GS_O_VAL, x); r.pct = GS_Pct(GS_O_REF, r.pred); }
         r.size = 0.5 + r.pct; r.ok = true; GS_gShNote = "ok";
        }
     }
   PrintFormat("Shadow %s: %s pred %.6f -> would size x%.2f (NOT applied)", strat, r.ok ? "ok" : GS_gShNote, r.pred, r.size);
   int h = FileOpen(GS_SigFile, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(h != INVALID_HANDLE)
     {
      if(FileSize(h) == 0) { string hd = "strategy,position_id,side,entry_time_utc,entry_price,volume,equity,bars_used,shadow_ok,shadow_pred,shadow_pct,shadow_size,note"; for(int k = 0; k < GS_NFEAT; k++) hd += "," + GS_FEATN[k]; FileWriteString(h, hd + "\r\n"); }
      FileSeek(h, 0, SEEK_END);
      string row = strat + "," + IntegerToString(pid) + "," + IntegerToString(side) + "," + TimeToString(GS_ToUTC(entT), TIME_DATE | TIME_SECONDS) + "," + DoubleToString(ep, _Digits) + ","
                   + DoubleToString(vol, 2) + "," + DoubleToString(r.eq, 2) + "," + IntegerToString(MathMin(Bars(_Symbol, PERIOD_H1) - 1, GS_InpHistBars)) + "," + (r.ok ? "1" : "0") + "," + DoubleToString(r.pred, 10) + "," + DoubleToString(r.pct, 4) + "," + DoubleToString(r.size, 4) + "," + GS_gShNote;
      for(int k = 0; k < GS_NFEAT; k++) row += "," + (r.ok ? DoubleToString(x[k], 8) : "");
      FileWriteString(h, row + "\r\n"); FileClose(h);
     }
   int n_ = ArraySize(GS_recs); ArrayResize(GS_recs, n_ + 1); GS_recs[n_] = r;
  }

bool GS_IsOpen(long pid)
  {
   for(int k = PositionsTotal() - 1; k >= 0; k--) { ulong tk = PositionGetTicket(k); if(tk != 0 && PositionGetInteger(POSITION_IDENTIFIER) == pid) return true; }
   return false;
  }

void GS_DumpBars()
  {
   static datetime lastKey = 0; if(!InpGSDumpBars) return;
   datetime key = GS_TradingDayKey(GS_ToUTC(TimeCurrent())); if(key == lastKey) return; lastKey = key;
   MqlRates rr[]; int got = CopyRates(_Symbol, PERIOD_H1, 1, GS_InpHistBars + 40000, rr); if(got <= 0) return;
   int h = FileOpen(GS_BarFile, FILE_WRITE | FILE_CSV | FILE_ANSI, ','); if(h == INVALID_HANDLE) return;
   FileWriteString(h, "time_utc,o,h,l,c,v\r\n");
   for(int i = 0; i < got; i++)
      FileWriteString(h, TimeToString(GS_ToUTC(rr[i].time), TIME_DATE | TIME_MINUTES) + "," + DoubleToString(rr[i].open, _Digits) + "," + DoubleToString(rr[i].high, _Digits) + ","
                      + DoubleToString(rr[i].low, _Digits) + "," + DoubleToString(rr[i].close, _Digits) + "," + IntegerToString(rr[i].tick_volume) + "\r\n");
   FileClose(h);
  }

// call at the start of OnTick: logs closed shadow-tracked trades (real P&L) + daily bar dump
void GS_Poll()
  {
   if(!InpGSShadow) return;
   static datetime last = 0; if(TimeCurrent() - last < 10) return; last = TimeCurrent();
   GS_DumpBars();
   for(int i = ArraySize(GS_recs) - 1; i >= 0; i--)
     {
      if(GS_IsOpen(GS_recs[i].pid)) continue;
      if(!HistorySelectByPosition(GS_recs[i].pid)) continue;
      double net = 0, xp = 0; datetime xT = 0;
      for(int d = 0; d < HistoryDealsTotal(); d++)
        {
         ulong dt = HistoryDealGetTicket(d); if(dt == 0) continue;
         net += HistoryDealGetDouble(dt, DEAL_PROFIT) + HistoryDealGetDouble(dt, DEAL_COMMISSION) + HistoryDealGetDouble(dt, DEAL_SWAP);
         long e = HistoryDealGetInteger(dt, DEAL_ENTRY);
         if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_OUT_BY) { xp = HistoryDealGetDouble(dt, DEAL_PRICE); xT = (datetime)HistoryDealGetInteger(dt, DEAL_TIME); }
        }
      if(xp <= 0) continue;                                   // exit deal not in history yet
      GS_Rec r = GS_recs[i]; double notional = r.vol * GS_VPP() * r.ep;
      double netbp = notional > 0 ? net / notional * 1e4 : 0, reteq = r.eq > 0 ? net / r.eq : 0;
      int h = FileOpen(GS_TrdFile, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
      if(h != INVALID_HANDLE)
        {
         if(FileSize(h) == 0) FileWrite(h, "strategy", "position_id", "side", "day_ny", "entry_time_utc", "entry_price", "exit_time_utc", "exit_price", "volume", "net_money", "net_bp", "ret_equity", "shadow_ok", "shadow_pred", "shadow_pct", "shadow_size");
         FileSeek(h, 0, SEEK_END);
         FileWrite(h, r.strat, IntegerToString(r.pid), r.side == 1 ? "BUY" : "SELL", TimeToString(GS_TradingDayKey(GS_ToUTC(r.entT)), TIME_DATE), TimeToString(GS_ToUTC(r.entT), TIME_DATE | TIME_SECONDS),
                   DoubleToString(r.ep, _Digits), TimeToString(GS_ToUTC(xT), TIME_DATE | TIME_SECONDS), DoubleToString(xp, _Digits), DoubleToString(r.vol, 2), DoubleToString(net, 2),
                   DoubleToString(netbp, 3), DoubleToString(reteq, 6), r.ok ? "1" : "0", DoubleToString(r.pred, 10), DoubleToString(r.pct, 4), DoubleToString(r.size, 4));
         FileClose(h);
        }
      for(int m = i; m < ArraySize(GS_recs) - 1; m++) GS_recs[m] = GS_recs[m + 1];
      ArrayResize(GS_recs, ArraySize(GS_recs) - 1);
     }
  }
'''
src = head + body + "\n".join(asm) + "\n" + "\n".join(mdl) + "\n" + tail
assert "@@" not in src
open(f"{HERE}/mt5/combo/GoldComboShadow.mqh", "w").write(src)
print("written", len(src), "chars | GS_ symbols", len(re.findall(r"\bGS_", src)))
