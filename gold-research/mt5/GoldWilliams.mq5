//+------------------------------------------------------------------+
//| GoldWilliams.mq5                                                 |
//| Larry Williams volatility breakout on XAUUSD (research #112).    |
//| Day = 17:00 -> 17:00 New York. Buy stop at Open + 0.6 x prev     |
//| range, sell stop at Open - 0.6 x prev range; first touched wins, |
//| one trade per day, exit at the day's close (16:58 NY).           |
//| DEMO forward test first. Magic 770501. Rules are frozen.         |
//| v1.02: exit window from 16:50 NY (input; Exness: no ticks after  |
//| 16:58). v1.01: safety close if a position survives its day.      |
//| (missed 16:58 window, e.g. broker daily break). Logic unchanged.  |
//+------------------------------------------------------------------+
#property copyright "gold-research"
#property version   "1.02"
#property description "Williams volatility breakout (#112): passed discovery 2004-16, confirmation 2017-23 (weak) and the vault 2024-26."
#property description "Demo first. Logs every trade to MQL5/Files/GoldWilliams_trades.csv"
#include <Trade/Trade.mqh>

#define K_RANGE      0.6       // research rule (frozen)

input group "Size"
input double InpLev        = 0.5;    // Notional as x equity (research portfolio check used ~0.4-0.5x)
input double InpFixedLot   = 0.0;    // Fixed lot (>0 overrides)
input group "Technical"
input int    InpExitNYMin  = 1010;   // Day-close exit from this NY minute (1010 = 16:50). v1.02: Exness sends no ticks 16:58-17:00 NY
input int    InpServerUTC  = 0;      // Broker server offset from UTC (Exness = 0)
input long   InpMagic      = 770501; // Magic number
input int    InpDeviation  = 30;     // Max deviation, points
input double InpMaxSpread  = 0.0;    // Skip entry if spread > this (USD); 0 = off (research had no filter)
input string InpCsvName    = "GoldWilliams_trades.csv";

CTrade trade;
datetime dayKey = 0;          // NY date of the current trading day (17:00 NY start)
double   dOpen = 0, buyLvl = 0, sellLvl = 0, prevRange = 0;
bool     tradedToday = false;
bool     gStale = false;
ulong    pendClose[];
// open trade bookkeeping
ulong gTicket = 0; long gPosId = 0; int gSide = 0; double gLvl = 0, gEnt = 0, gVol = 0, gSpr = 0; datetime gEntT = 0; datetime gDayKey = 0;

datetime ToUTC(datetime s) { return (datetime)((long)s - (long)InpServerUTC * 3600); }
datetime NthSundayUTC(int y, int mon, int nth, int hUTC)
  {
   MqlDateTime d; ZeroMemory(d); d.year = y; d.mon = mon; d.day = 1;
   datetime f = StructToTime(d); MqlDateTime s; TimeToStruct(f, s);
   int add = (7 - s.day_of_week) % 7;
   return (datetime)((long)f + (long)(add + 7 * (nth - 1)) * 86400 + (long)hUTC * 3600);
  }
int NYOffset(datetime utc)
  {
   MqlDateTime t; TimeToStruct(utc, t);
   return (utc >= NthSundayUTC(t.year, 3, 2, 7) && utc < NthSundayUTC(t.year, 11, 1, 6)) ? -4 : -5;
  }
datetime ToNY(datetime utc) { return (datetime)((long)utc + (long)NYOffset(utc) * 3600); }
datetime TradingDayKey(datetime utc)        // NY date of the 17:00->17:00 day containing utc
  {
   datetime ny = ToNY(utc); MqlDateTime t; TimeToStruct((datetime)((long)ny + 7 * 3600), t);
   t.hour = 0; t.min = 0; t.sec = 0; return StructToTime(t);
  }
int NYMinute(datetime utc) { MqlDateTime t; TimeToStruct(ToNY(utc), t); return t.hour * 60 + t.min; }

bool FindPos(ulong &tk)
  {
   for(int k = PositionsTotal() - 1; k >= 0; k--)
     {
      ulong t = PositionGetTicket(k); if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic) { tk = t; return true; }
     }
   return false;
  }
bool SafeClose(ulong tk)
  {
   bool ok = trade.PositionClose(tk); uint rc = trade.ResultRetcode();
   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED || rc == TRADE_RETCODE_DONE_PARTIAL)) return true;
   if(!PositionSelectByTicket(tk)) return true;
   int np = ArraySize(pendClose); for(int k = 0; k < np; k++) if(pendClose[k] == tk) return false;
   ArrayResize(pendClose, np + 1); pendClose[np] = tk; Print("Close rejected (", trade.ResultRetcodeDescription(), "), retry every 30 s"); return false;
  }
void RetryPendingCloses()
  {
   static datetime last = 0; if(ArraySize(pendClose) == 0 || TimeCurrent() - last < 30) return; last = TimeCurrent();
   for(int k = ArraySize(pendClose) - 1; k >= 0; k--)
     {
      ulong tk = pendClose[k]; bool gone = !PositionSelectByTicket(tk);
      if(!gone) { bool ok = trade.PositionClose(tk); uint rc = trade.ResultRetcode(); gone = ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED || rc == TRADE_RETCODE_DONE_PARTIAL); }
      if(gone) { for(int m = k; m < ArraySize(pendClose) - 1; m++) pendClose[m] = pendClose[m + 1]; ArrayResize(pendClose, ArraySize(pendClose) - 1); }
     }
  }

// previous full trading day's range and today's open from H1 bars
bool ComputeLevels(datetime nowUTC)
  {
   MqlRates r[]; int got = CopyRates(_Symbol, PERIOD_H1, 0, 72, r);     // oldest first
   if(got < 30) return false;
   datetime today = TradingDayKey(nowUTC);
   double ph = -1, pl = 1e18, op = 0; datetime prevKey = 0; bool haveOpen = false;
   for(int k = got - 1; k >= 0; k--)
     {
      datetime key = TradingDayKey(ToUTC(r[k].time));
      if(key == today) { op = r[k].open; haveOpen = true; continue; }        // keeps overwriting -> earliest bar's open
      if(prevKey == 0) prevKey = key;
      if(key != prevKey) break;
      ph = MathMax(ph, r[k].high); pl = MathMin(pl, r[k].low);
     }
   if(!haveOpen || ph <= 0 || pl >= 1e17) return false;
   dOpen = op; prevRange = ph - pl; buyLvl = op + K_RANGE * prevRange; sellLvl = op - K_RANGE * prevRange;
   return prevRange > 0;
  }

double LotFor(double price)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot = InpFixedLot;
   if(lot <= 0) lot = AccountInfoDouble(ACCOUNT_EQUITY) * InpLev / (price * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE));
   if(step <= 0) step = 0.01; lot = MathFloor(lot / step + 1e-9) * step;
   if(lot < mn) return 0.0; if(lot > mx) lot = mx; return NormalizeDouble(lot, 2);
  }

void LogTrade(datetime xT, double xPx, string why, double comm, double swap, double profit)
  {
   int h = FileOpen(InpCsvName, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE) return;
   if(FileSize(h) == 0) FileWrite(h, "day_ny", "side", "level", "entry_time_utc", "entry_price", "slippage", "spread", "exit_time_utc", "exit_price", "reason", "volume", "commission", "swap", "profit", "signal_bp", "net_bp");
   FileSeek(h, 0, SEEK_END);
   double contract = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE), notional = gVol * contract * gEnt;
   double sigbp = gLvl > 0 ? gSide * (xPx - gLvl) / gLvl * 1e4 : 0, netbp = notional > 0 ? (profit + comm + swap) / notional * 1e4 : 0;
   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   FileWrite(h, TimeToString(gDayKey, TIME_DATE), gSide == 1 ? "BUY" : "SELL", DoubleToString(gLvl, dg), TimeToString(ToUTC(gEntT), TIME_DATE | TIME_SECONDS),
             DoubleToString(gEnt, dg), DoubleToString(gSide * (gEnt - gLvl), dg), DoubleToString(gSpr, dg), TimeToString(ToUTC(xT), TIME_DATE | TIME_SECONDS),
             DoubleToString(xPx, dg), why, DoubleToString(gVol, 2), DoubleToString(comm, 2), DoubleToString(swap, 2), DoubleToString(profit, 2),
             DoubleToString(sigbp, 3), DoubleToString(netbp, 3));
   FileClose(h);
  }

void FinishIfClosed()
  {
   if(gTicket == 0 || PositionSelectByTicket(gTicket)) return;
   double comm = 0, swap = 0, profit = 0, xPx = 0; datetime xT = TimeCurrent(); string why = "CLOSE";
   if(HistorySelectByPosition(gPosId))
      for(int k = 0; k < HistoryDealsTotal(); k++)
        {
         ulong d = HistoryDealGetTicket(k); if(d == 0) continue;
         comm += HistoryDealGetDouble(d, DEAL_COMMISSION); swap += HistoryDealGetDouble(d, DEAL_SWAP); profit += HistoryDealGetDouble(d, DEAL_PROFIT);
         long e = HistoryDealGetInteger(d, DEAL_ENTRY);
         if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_OUT_BY) { xPx = HistoryDealGetDouble(d, DEAL_PRICE); xT = (datetime)HistoryDealGetInteger(d, DEAL_TIME); if(HistoryDealGetInteger(d, DEAL_REASON) == DEAL_REASON_SL) why = "SL"; }
        }
   static int waits = 0; if(xPx <= 0 && waits < 30) { waits++; return; } waits = 0;
   if(gStale && why == "CLOSE") why = "STALE_CLOSE"; gStale = false;
   LogTrade(xT, xPx, why, comm, swap, profit); gTicket = 0; gPosId = 0; gSide = 0;
  }

void OnTickLogic()
  {
   RetryPendingCloses(); FinishIfClosed();
   datetime nowUTC = ToUTC(TimeCurrent());
   datetime key = TradingDayKey(nowUTC);
   if(key != dayKey) { dayKey = key; tradedToday = false; if(!ComputeLevels(nowUTC)) { dOpen = 0; } }
   int nm = NYMinute(nowUTC);
   ulong tk;
   if(FindPos(tk))
     {
      datetime posKey = TradingDayKey(ToUTC((datetime)PositionGetInteger(POSITION_TIME)));
      if(posKey != dayKey) { gStale = true; SafeClose(tk); return; }           // v1.01 safety: never hold past the trading day
      if(nm >= InpExitNYMin && nm < 17 * 60) SafeClose(tk);                    // day close
      return;
     }
   if(tradedToday || dOpen <= 0 || (nm >= InpExitNYMin && nm < 17 * 60)) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int side = bid >= buyLvl ? 1 : (bid <= sellLvl ? -1 : 0);                  // research triggers on BID high/low
   if(side == 0) return;
   tradedToday = true;                                                         // first touched level wins, one trade per day
   if(InpMaxSpread > 0 && ask - bid > InpMaxSpread) { Print("Williams: skipped, spread ", ask - bid); return; }
   double px = side == 1 ? ask : bid, lot = LotFor(px);
   if(lot <= 0) { Print("Williams: lot below minimum"); return; }
   trade.SetExpertMagicNumber(InpMagic); trade.SetDeviationInPoints(InpDeviation);
   bool ok = side == 1 ? trade.Buy(lot, _Symbol, 0, 0, 0, "Williams#112") : trade.Sell(lot, _Symbol, 0, 0, 0, "Williams#112");
   if(!ok) { Print("Williams order failed: ", trade.ResultRetcodeDescription()); return; }
   if(FindPos(tk) && PositionSelectByTicket(tk))
     {
      gTicket = tk; gPosId = PositionGetInteger(POSITION_IDENTIFIER); gSide = side; gLvl = side == 1 ? buyLvl : sellLvl;
      gEnt = PositionGetDouble(POSITION_PRICE_OPEN); gVol = PositionGetDouble(POSITION_VOLUME); gEntT = (datetime)PositionGetInteger(POSITION_TIME); gSpr = ask - bid; gDayKey = dayKey;
      PrintFormat("Williams %s %.2f lots @ %.2f (level %.2f, open %.2f, prev range %.2f)", side == 1 ? "BUY" : "SELL", gVol, gEnt, gLvl, dOpen, prevRange);
     }
  }

int OnInit()
  {
   PrintFormat("GoldWilliams #112 on %s | contract %.2f | magic %I64d", _Symbol, SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE), InpMagic);
   ulong tk; if(FindPos(tk) && PositionSelectByTicket(tk)) { gTicket = tk; gPosId = PositionGetInteger(POSITION_IDENTIFIER); gSide = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1; gEnt = PositionGetDouble(POSITION_PRICE_OPEN); gVol = PositionGetDouble(POSITION_VOLUME); gEntT = (datetime)PositionGetInteger(POSITION_TIME); gDayKey = TradingDayKey(ToUTC(gEntT)); tradedToday = true; }
   EventSetTimer(10); return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason) { EventKillTimer(); }
void OnTimer() { OnTickLogic(); }
void OnTick() { OnTickLogic(); }
//+------------------------------------------------------------------+
