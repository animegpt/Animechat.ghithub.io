//+------------------------------------------------------------------+
//| GoldDCFade.mq5                                                   |
//| FORWARD TEST ONLY (pre-registration #83).                        |
//| DC overshoot fade on XAUUSD M1, rules = research #58 variant B:  |
//| theta 0.2%, fade at 2 theta overshoot, catastrophe SL 3 theta,   |
//| exit at the next DC / 24h / 21:45 UTC.                           |
//| Standalone: Magic 770201, never touches other positions.         |
//+------------------------------------------------------------------+
#property copyright "gold-research"
#property version   "1.00"
#property description "DC overshoot fade forward test (#83). Rules are frozen: do not optimise."
#property description "Demo Raw/Zero account. Logs every trade to MQL5/Files/GoldDCFade_trades.csv"
#include <Trade/Trade.mqh>

//==================== frozen research rules (prereg #83) ====================
#define DC_THETA      0.002     // directional-change threshold (0.2%)
#define DC_OVERSHOOT  2.0       // fade when price is 2 theta beyond the DC price
#define DC_STOPK      3.0       // catastrophe stop distance = 3 theta from the fill
#define DC_MAXHOLD    1440      // minutes (24h)
#define EOD_UTC_MIN   1305      // 21:45 UTC force close
#define NOENTRY_FROM  1290      // 21:30 UTC ...
#define NOENTRY_TO    1380      // ... until 23:00 UTC no new entries

input group "Risk"
input double InpRiskPct     = 0.25;   // Risk per trade, % equity, on the 3-theta stop
input double InpFixedLot    = 0.0;    // Fixed lot (>0 overrides risk sizing)
input double InpMaxSpread   = 0.10;   // Max spread at entry, in price units (USD)
input group "Technical"
input int    InpServerUTC   = 0;      // Broker server time offset from UTC in hours (Exness = 0)
input long   InpMagic       = 770201; // Magic number (unique to this EA)
input int    InpWarmupBars  = 5000;   // M1 bars used to rebuild the DC state at start
input int    InpDeviation   = 30;     // Max deviation for market orders, points
input string InpCsvName     = "GoldDCFade_trades.csv"; // Trade log file (MQL5/Files)

CTrade trade;

//==================== DC state ====================
int      dcMode  = 0;      // 0 = undefined, 1 = up-run, -1 = down-run
double   dcHi    = 0.0, dcLo = 0.0, dcPx = 0.0;
int      dcDir   = 0;      // direction of the last DC event
bool     dcFaded = false;  // this leg already faded (or blocked)
datetime lastBar = 0;      // open time (server) of the last processed CLOSED M1 bar

//==================== open trade bookkeeping ====================
ulong    gTicket = 0;
long     gPosId  = 0;
int      gSide   = 0;
datetime gSigTime = 0, gEntTime = 0;
double   gSigPx = 0.0, gEntPx = 0.0, gSpread = 0.0, gSL = 0.0, gVol = 0.0;
string   gExitReason = "";
double   gExitSigPx  = 0.0;
ulong    pendClose[];

//==================== time helpers ====================
datetime ToUTC(datetime server) { return server - (datetime)(InpServerUTC * 3600); }

datetime NthSundayUTC(int year, int mon, int nth, int hourUTC)
  {
   MqlDateTime d; ZeroMemory(d);
   d.year = year; d.mon = mon; d.day = 1; d.hour = 0; d.min = 0; d.sec = 0;
   datetime first = StructToTime(d);
   MqlDateTime f; TimeToStruct(first, f);
   int add = (7 - f.day_of_week) % 7;               // days to the first Sunday
   return first + (datetime)((add + 7 * (nth - 1)) * 86400 + hourUTC * 3600);
  }

int NYOffset(datetime utc)                           // -4 (EDT) or -5 (EST)
  {
   MqlDateTime t; TimeToStruct(utc, t);
   datetime a = NthSundayUTC(t.year, 3, 2, 7);       // 2nd Sunday March, 02:00 EST = 07:00 UTC
   datetime b = NthSundayUTC(t.year, 11, 1, 6);      // 1st Sunday November, 02:00 EDT = 06:00 UTC
   return (utc >= a && utc < b) ? -4 : -5;
  }

int NYHour(datetime utc)
  {
   MqlDateTime t; TimeToStruct(utc + (datetime)(NYOffset(utc) * 3600), t);
   return t.hour;
  }

int UTCMinuteOfDay(datetime utc)
  {
   MqlDateTime t; TimeToStruct(utc, t);
   return t.hour * 60 + t.min;
  }

//==================== global-variable persistence (survives restarts) ====================
string GVn(string k) { return "DCF_" + IntegerToString(InpMagic) + "_" + k; }
void   GVset(string k, double v) { GlobalVariableSet(GVn(k), v); }
double GVget(string k, double def) { return GlobalVariableCheck(GVn(k)) ? GlobalVariableGet(GVn(k)) : def; }

void SaveTrade()
  {
   GVset("pos", (double)gPosId); GVset("side", gSide); GVset("sigT", (double)gSigTime); GVset("entT", (double)gEntTime);
   GVset("sigPx", gSigPx); GVset("entPx", gEntPx); GVset("spr", gSpread); GVset("sl", gSL); GVset("vol", gVol);
  }

void LoadTrade()
  {
   gPosId = (long)GVget("pos", 0); gSide = (int)GVget("side", 0);
   gSigTime = (datetime)(long)GVget("sigT", 0); gEntTime = (datetime)(long)GVget("entT", 0);
   gSigPx = GVget("sigPx", 0); gEntPx = GVget("entPx", 0); gSpread = GVget("spr", 0); gSL = GVget("sl", 0); gVol = GVget("vol", 0);
  }

//==================== position helpers ====================
bool FindPos(ulong &tk)
  {
   for(int k = PositionsTotal() - 1; k >= 0; k--)
     {
      ulong t = PositionGetTicket(k);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic) { tk = t; return true; }
     }
   return false;
  }

bool SafeClose(ulong tk)
  {
   bool ok = trade.PositionClose(tk);
   uint rc = trade.ResultRetcode();
   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED || rc == TRADE_RETCODE_DONE_PARTIAL)) return true;
   if(!PositionSelectByTicket(tk)) return true;
   int np = ArraySize(pendClose);
   for(int k = 0; k < np; k++) if(pendClose[k] == tk) return false;
   ArrayResize(pendClose, np + 1); pendClose[np] = tk;
   Print("Close of #", tk, " rejected (", trade.ResultRetcodeDescription(), ") - will retry every 30 s");
   return false;
  }

void RetryPendingCloses()
  {
   static datetime lastTry = 0;
   if(ArraySize(pendClose) == 0 || TimeCurrent() - lastTry < 30) return;
   lastTry = TimeCurrent();
   for(int k = ArraySize(pendClose) - 1; k >= 0; k--)
     {
      ulong tk = pendClose[k];
      bool gone = !PositionSelectByTicket(tk);
      if(!gone)
        {
         bool ok = trade.PositionClose(tk); uint rc = trade.ResultRetcode();
         gone = ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED || rc == TRADE_RETCODE_DONE_PARTIAL);
         if(gone) Print("Delayed close of #", tk, " done");
        }
      if(gone)
        {
         for(int m = k; m < ArraySize(pendClose) - 1; m++) pendClose[m] = pendClose[m + 1];
         ArrayResize(pendClose, ArraySize(pendClose) - 1);
        }
     }
  }

//==================== CSV log ====================
void WriteCsv(datetime xTime, double xPx, string reason, double comm, double swap, double profit)
  {
   int h = FileOpen(InpCsvName, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE) { Print("CSV open failed: ", GetLastError()); return; }
   if(FileSize(h) == 0)
      FileWrite(h, "signal_time_utc", "entry_time_utc", "side", "signal_price", "entry_price", "slippage", "spread_entry", "sl",
                "exit_time_utc", "exit_price", "exit_reason", "exit_signal_price", "volume", "commission", "swap", "profit_usd",
                "signal_bp", "fill_bp", "net_bp", "hold_min");
   FileSeek(h, 0, SEEK_END);
   double contract = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double xs = (gExitSigPx > 0 ? gExitSigPx : xPx);
   double sigbp  = (gSigPx > 0 ? gSide * (xs - gSigPx) / gSigPx * 1e4 : 0.0);
   double fillbp = (gEntPx > 0 ? gSide * (xPx - gEntPx) / gEntPx * 1e4 : 0.0);
   double notional = gVol * contract * gEntPx;
   double netbp = (notional > 0 ? (profit + comm + swap) / notional * 1e4 : 0.0);
   long holdm = (long)(xTime - gEntTime) / 60;
   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   FileWrite(h, TimeToString(ToUTC(gSigTime), TIME_DATE | TIME_MINUTES), TimeToString(ToUTC(gEntTime), TIME_DATE | TIME_SECONDS),
             (gSide == 1 ? "BUY" : "SELL"), DoubleToString(gSigPx, dg), DoubleToString(gEntPx, dg),
             DoubleToString(gSide * (gEntPx - gSigPx), dg), DoubleToString(gSpread, dg), DoubleToString(gSL, dg),
             TimeToString(ToUTC(xTime), TIME_DATE | TIME_SECONDS), DoubleToString(xPx, dg), reason, DoubleToString(xs, dg),
             DoubleToString(gVol, 2), DoubleToString(comm, 2), DoubleToString(swap, 2), DoubleToString(profit, 2),
             DoubleToString(sigbp, 3), DoubleToString(fillbp, 3), DoubleToString(netbp, 3), IntegerToString(holdm));
   FileClose(h);
  }

// position has disappeared: read its deals, log, reset
void FinishTrade()
  {
   if(gPosId == 0) { gTicket = 0; return; }
   double comm = 0, swap = 0, profit = 0, xPx = 0; datetime xTime = TimeCurrent(); string reason = gExitReason;
   if(HistorySelectByPosition(gPosId))
     {
      int nd = HistoryDealsTotal();
      for(int k = 0; k < nd; k++)
        {
         ulong d = HistoryDealGetTicket(k);
         if(d == 0) continue;
         comm   += HistoryDealGetDouble(d, DEAL_COMMISSION);
         swap   += HistoryDealGetDouble(d, DEAL_SWAP);
         profit += HistoryDealGetDouble(d, DEAL_PROFIT);
         long entry = HistoryDealGetInteger(d, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
           {
            xPx = HistoryDealGetDouble(d, DEAL_PRICE); xTime = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
            long why = HistoryDealGetInteger(d, DEAL_REASON);
            if(reason == "") reason = (why == DEAL_REASON_SL ? "SL" : "OTHER");
           }
        }
     }
   if(reason == "SL" || reason == "OTHER") gExitSigPx = xPx;
   WriteCsv(xTime, xPx, reason, comm, swap, profit);
   PrintFormat("DCFade exit %s %s @ %.2f profit %.2f comm %.2f", (gSide == 1 ? "BUY" : "SELL"), reason, xPx, profit, comm);
   gTicket = 0; gPosId = 0; gSide = 0; gExitReason = ""; gExitSigPx = 0; GVset("pos", 0);
  }

void RequestExit(string reason, double sigPx)
  {
   if(gTicket == 0 || gExitReason != "") return;
   gExitReason = reason; gExitSigPx = sigPx;
   if(SafeClose(gTicket) && !PositionSelectByTicket(gTicket)) FinishTrade();
  }

//==================== DC state machine (identical to code/dcfade58.py) ====================
bool DCUpdate(double p)
  {
   bool now = false;
   if(dcMode == 0)
     {
      if(p > dcHi) dcHi = p;
      if(p < dcLo) dcLo = p;
      if(p <= dcHi * (1 - DC_THETA))      { dcMode = -1; dcLo = p; now = true; dcDir = -1; dcPx = p; }
      else if(p >= dcLo * (1 + DC_THETA)) { dcMode = 1;  dcHi = p; now = true; dcDir = 1;  dcPx = p; }
     }
   else if(dcMode == 1)
     {
      if(p > dcHi) dcHi = p;
      else if(p <= dcHi * (1 - DC_THETA)) { dcMode = -1; dcLo = p; now = true; dcDir = -1; dcPx = p; }
     }
   else
     {
      if(p < dcLo) dcLo = p;
      else if(p >= dcLo * (1 + DC_THETA)) { dcMode = 1; dcHi = p; now = true; dcDir = 1; dcPx = p; }
     }
   return now;
  }

bool OvershootHit(double p)
  {
   return (dcDir == 1 && p >= dcPx * (1 + DC_OVERSHOOT * DC_THETA)) || (dcDir == -1 && p <= dcPx * (1 - DC_OVERSHOOT * DC_THETA));
  }

//==================== sizing ====================
double NormLot(double lot)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) step = 0.01;
   lot = MathFloor(lot / step + 1e-9) * step;
   if(lot < mn) return 0.0;
   if(lot > mx) lot = mx;
   return NormalizeDouble(lot, 2);
  }

double LotFor(double price)
  {
   if(InpFixedLot > 0) return NormLot(InpFixedLot);
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tv <= 0) tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0 || ts <= 0) return 0.0;
   double vpp = tv / ts;                                   // account money per 1.0 price move per 1 lot
   double dist = price * DC_STOPK * DC_THETA;
   double risk = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
   return NormLot(risk / (dist * vpp));
  }

//==================== entry ====================
void TryEntry(datetime sigBarOpen, double sigPx)
  {
   int side = -dcDir;                                     // fade
   datetime sigUTC = ToUTC(sigBarOpen);
   int nyh = NYHour(sigUTC);
   if(nyh <= 2 || nyh == 16 || nyh == 17) { Print("DCFade signal skipped: NY hour ", nyh); return; }
   int um = UTCMinuteOfDay(ToUTC(TimeCurrent()));
   if(um >= NOENTRY_FROM && um < NOENTRY_TO) { Print("DCFade signal skipped: close to 21:45 UTC / rollover"); return; }
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double spr = ask - bid;
   if(spr > InpMaxSpread) { PrintFormat("DCFade signal skipped: spread %.3f > %.3f", spr, InpMaxSpread); return; }
   double px = (side == 1 ? ask : bid);
   double lot = LotFor(px);
   if(lot <= 0) { Print("DCFade signal skipped: lot below broker minimum"); return; }
   double sl = NormalizeDouble(px * (1 - side * DC_STOPK * DC_THETA), _Digits);
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviation);
   bool ok = (side == 1 ? trade.Buy(lot, _Symbol, 0, sl, 0, "DCFade#83") : trade.Sell(lot, _Symbol, 0, sl, 0, "DCFade#83"));
   if(!ok) { Print("DCFade order failed: ", trade.ResultRetcodeDescription()); return; }
   ulong tk;
   if(!FindPos(tk) || !PositionSelectByTicket(tk)) { Print("DCFade: position not found after fill"); return; }
   gTicket = tk; gPosId = PositionGetInteger(POSITION_IDENTIFIER); gSide = side;
   gSigTime = sigBarOpen; gSigPx = sigPx; gEntTime = (datetime)PositionGetInteger(POSITION_TIME);
   gEntPx = PositionGetDouble(POSITION_PRICE_OPEN); gSpread = spr; gVol = PositionGetDouble(POSITION_VOLUME);
   gSL = NormalizeDouble(gEntPx * (1 - side * DC_STOPK * DC_THETA), _Digits);   // 3 theta from the ACTUAL fill
   if(MathAbs(gSL - PositionGetDouble(POSITION_SL)) >= _Point)
      if(!trade.PositionModify(tk, gSL, 0)) Print("DCFade: SL re-anchor failed: ", trade.ResultRetcodeDescription());
   SaveTrade();
   PrintFormat("DCFade ENTRY %s %.2f lots @ %.2f (signal %.2f, spread %.3f, SL %.2f)", (side == 1 ? "BUY" : "SELL"), gVol, gEntPx, sigPx, spr, gSL);
  }

//==================== per closed M1 bar (same order as code/dcfade58.py) ====================
void OnClosedBar(datetime barOpen, double close, bool live)
  {
   bool dcNow = DCUpdate(close);
   if(live && gTicket != 0 && PositionSelectByTicket(gTicket))
     {
      datetime barClose = barOpen + 60;
      if(dcNow) RequestExit("DC", close);
      else if((long)(barClose - gEntTime) >= (long)DC_MAXHOLD * 60) RequestExit("24h", close);
     }
   if(dcNow) dcFaded = false;
   bool flat = (gTicket == 0);
   if(flat && !dcFaded && !dcNow && dcDir != 0 && OvershootHit(close))
     {
      dcFaded = true;                                     // one fade per leg, even if a filter blocks it
      if(live) TryEntry(barOpen, close);
     }
  }

void Housekeeping()
  {
   RetryPendingCloses();
   if(gTicket != 0 && !PositionSelectByTicket(gTicket)) FinishTrade();     // SL hit or delayed close done
   if(gTicket != 0)
     {
      int um = UTCMinuteOfDay(ToUTC(TimeCurrent()));
      if(um >= EOD_UTC_MIN && um < NOENTRY_TO)
         RequestExit("EOD", SymbolInfoDouble(_Symbol, SYMBOL_BID));
     }
  }

//==================== events ====================
int OnInit()
  {
   if(_Period != PERIOD_M1) Print("Note: GoldDCFade always works on M1 data, whatever the chart timeframe.");
   PrintFormat("GoldDCFade #83 on %s | digits %d point %.5f contract %.2f tick size %.5f tick value %.5f vol min %.2f step %.2f",
               _Symbol, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS), _Point, SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE), SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP));
   if(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE) <= 0) { Print("Bad symbol properties"); return INIT_FAILED; }
   // rebuild DC state from history (no trading)
   MqlRates r[];
   int got = CopyRates(_Symbol, PERIOD_M1, 1, InpWarmupBars, r);   // oldest first, excludes the forming bar
   if(got <= 100) { Print("Not enough M1 history yet (", got, "), will retry"); return INIT_SUCCEEDED; }
   dcMode = 0; dcHi = r[0].close; dcLo = r[0].close; dcPx = r[0].close; dcDir = 0; dcFaded = false;
   for(int k = 1; k < got; k++) OnClosedBar(r[k].time, r[k].close, false);
   lastBar = r[got - 1].time;
   // restore an open trade after a restart
   ulong tk;
   if(FindPos(tk) && PositionSelectByTicket(tk))
     {
      LoadTrade(); gTicket = tk;
      if(gPosId != PositionGetInteger(POSITION_IDENTIFIER))
        {
         gPosId = PositionGetInteger(POSITION_IDENTIFIER); gSide = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1);
         gEntPx = PositionGetDouble(POSITION_PRICE_OPEN); gEntTime = (datetime)PositionGetInteger(POSITION_TIME);
         gVol = PositionGetDouble(POSITION_VOLUME); gSL = PositionGetDouble(POSITION_SL); gSigPx = 0; gSigTime = gEntTime; gSpread = 0;
        }
      Print("DCFade: resumed open position #", tk);
     }
   EventSetTimer(10);
   PrintFormat("DC state rebuilt from %d bars: mode %d, last DC dir %d @ %.2f, faded %s", got, dcMode, dcDir, dcPx, (dcFaded ? "yes" : "no"));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer() { Housekeeping(); }

void OnTick()
  {
   Housekeeping();
   datetime cur = iTime(_Symbol, PERIOD_M1, 0);
   if(cur == 0 || cur == lastBar) return;
   if(lastBar == 0)                                       // history was not ready at OnInit
     {
      if(OnInit() != INIT_SUCCEEDED || lastBar == 0) return;
     }
   MqlRates r[];
   int got = CopyRates(_Symbol, PERIOD_M1, lastBar + 60, cur - 1, r);   // every closed bar since the last one processed
   if(got <= 0) return;
   for(int k = 0; k < got; k++)
     {
      if(r[k].time <= lastBar) continue;
      bool last = (k == got - 1);
      OnClosedBar(r[k].time, r[k].close, last);          // trade only on the newest closed bar
      lastBar = r[k].time;
     }
  }
//+------------------------------------------------------------------+
