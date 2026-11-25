//+------------------------------------------------------------------+
//| GoldWilliams.mq5                                                 |
//| Larry Williams volatility breakout on XAUUSD (research #112).    |
//| Day = 17:00 -> 17:00 New York. Buy stop at Open + 0.6 x prev     |
//| range, sell stop at Open - 0.6 x prev range; first touched wins, |
//| one trade per day, exit at the day's close (16:58 NY).           |
//| DEMO forward test first. Magic 770501. Rules are frozen.         |
//| v1.08 CRITICAL: no contract-size fallback for the lot (cent acct  |
//| tick value is 0 right after start -> was 100x). Two independent   |
//| value checks must agree, else no orders. Trade-session check.     |
//| v1.07: placement attempted only while quotes are fresh (no log  |
//| spam during the daily break / weekends). Logic unchanged.         |
//| v1.06: retry order placement after the daily break (no fallback  |
//| on "market closed"); orders expire at the exit time (server).   |
//| v1.05: entries as OCO stop orders AT the levels (research fills  |
//| at the level; market-on-touch slipped ~105 USD on BTC tester).   |
//| v1.04: any symbol (BTCUSDc): weekend trading-day keys skipped as  |
//| in the research (Monday uses Friday range). No-op on gold.       |
//| v1.03: lot + net_bp from tick value (correct on USC cent accts).  |
//| v1.02: exit window from 16:50 NY (input; Exness: no ticks after  |
//| 16:58). v1.01: safety close if a position survives its day.      |
//| (missed 16:58 window, e.g. broker daily break). Logic unchanged.  |
//+------------------------------------------------------------------+
#property copyright "gold-research"
#property version   "1.08"
#property description "Williams volatility breakout (#112): gold passed discovery/confirmation/vault; v1.04 also for BTCUSDc (#165/#166, forward test)."
#property description "Demo first. Logs every trade to MQL5/Files/GoldWilliams_trades.csv"
#include <Trade/Trade.mqh>

#define K_RANGE      0.6       // research rule (frozen)

input group "Size"
input double InpLev        = 0.5;    // Notional as x equity (research portfolio check used ~0.4-0.5x)
input double InpFixedLot   = 0.0;    // Fixed lot (>0 overrides)
input group "Technical"
input int    InpExitNYMin  = 1010;   // Day-close exit from this NY minute (1010 = 16:50). v1.02: Exness sends no ticks 16:58-17:00 NY
input bool   InpPendingEntry = true;  // v1.05: OCO buy-stop / sell-stop at the levels (= research fills). false = old market-on-touch
input bool   InpSkipWeekendKeys = true; // v1.04: no trading on Sat/Sun trading-day keys; previous range = last weekday key (research). Gold: no effect
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
datetime gOrdersDay = 0;     // v1.05: day key for which the OCO stop orders are working
datetime gPlaceTried = 0;    // v1.05: day key for which placement was attempted (once per day)
datetime gNextTry = 0;       // v1.06: next retry time when the market was closed (daily break)
datetime gClosedMsgDay = 0;
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
bool IsWeekendKey(datetime key) { MqlDateTime t; TimeToStruct(key, t); return t.day_of_week == 0 || t.day_of_week == 6; }
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
   MqlRates r[]; int got = CopyRates(_Symbol, PERIOD_H1, 0, 120, r);    // oldest first (120: reaches Friday from Monday on 24/7 symbols)
   if(got < 30) return false;
   datetime today = TradingDayKey(nowUTC);
   double ph = -1, pl = 1e18, op = 0; datetime prevKey = 0; bool haveOpen = false;
   for(int k = got - 1; k >= 0; k--)
     {
      datetime key = TradingDayKey(ToUTC(r[k].time));
      if(key == today) { op = r[k].open; haveOpen = true; continue; }        // keeps overwriting -> earliest bar's open
      if(InpSkipWeekendKeys && IsWeekendKey(key)) continue;                  // v1.04: research drops weekend keys
      if(prevKey == 0) prevKey = key;
      if(key != prevKey) break;
      ph = MathMax(ph, r[k].high); pl = MathMin(pl, r[k].low);
     }
   if(!haveOpen || ph <= 0 || pl >= 1e17) return false;
   dOpen = op; prevRange = ph - pl; buyLvl = op + K_RANGE * prevRange; sellLvl = op - K_RANGE * prevRange;
   return prevRange > 0;
  }

// v1.03: value of a 1.0 price move for 1 lot, in ACCOUNT currency (USD or USC cent accounts alike), from the broker's
// tick value. The old contract-size formula assumed a USD account and sized cent accounts 100x too large.
// v1.08: value of a 1.0 price move for 1 lot in ACCOUNT currency, or 0 if it cannot be trusted right now.
// Two independent sources must agree within 5 %: broker tick value and OrderCalcProfit. NEVER falls back to the
// contract size (on a cent account that is 100x too small a value -> 100x too large a lot).
double MoneyPerPricePerLot()
  {
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(!(tv > 0) || !(ts > 0)) return 0.0;
   double a = tv / ts;
   double px = SymbolInfoDouble(_Symbol, SYMBOL_BID), pr = 0;
   if(px <= 0 || !OrderCalcProfit(ORDER_TYPE_BUY, _Symbol, 1.0, px, px + 1.0, pr) || !(pr > 0)) return 0.0;
   if(MathAbs(pr - a) > 0.05 * MathMax(pr, a)) { static datetime w = 0; if(TimeCurrent() - w > 3600) { w = TimeCurrent(); PrintFormat("Williams: value check mismatch (tick %.6f vs calc %.6f) - no orders until they agree", a, pr); } return 0.0; }
   return a;
  }
// v1.08: is the symbol's TRADE session open now (server time)?
bool TradeSessionOpen()
  {
   datetime now = TimeTradeServer(); MqlDateTime t; TimeToStruct(now, t);
   datetime from, to; uint sec = (uint)(t.hour * 3600 + t.min * 60 + t.sec);
   for(uint k = 0; k < 10; k++)
     {
      if(!SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)t.day_of_week, k, from, to)) break;
      uint f = (uint)((long)from % 86400), e = (uint)((long)to % 86400); if(e == 0) e = 86400;
      if(sec >= f && sec < e) return true;
     }
   return false;
  }
double LotFor(double price)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot = InpFixedLot;
   double vpp = MoneyPerPricePerLot();
   if(vpp <= 0 || price <= 0) return 0.0;                                  // v1.08: value not trustworthy -> no lot
   if(lot <= 0) lot = AccountInfoDouble(ACCOUNT_EQUITY) * InpLev / (price * vpp);   // notional (account ccy) = InpLev x equity
   if(step <= 0) step = 0.01; lot = MathFloor(lot / step + 1e-9) * step;
   if(lot < mn) return 0.0; if(lot > mx) lot = mx; return NormalizeDouble(lot, 2);
  }

void LogTrade(datetime xT, double xPx, string why, double comm, double swap, double profit)
  {
   int h = FileOpen(InpCsvName, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE) return;
   if(FileSize(h) == 0) FileWrite(h, "day_ny", "side", "level", "entry_time_utc", "entry_price", "slippage", "spread", "exit_time_utc", "exit_price", "reason", "volume", "commission", "swap", "profit", "signal_bp", "net_bp");
   FileSeek(h, 0, SEEK_END);
   double notional = gVol * MoneyPerPricePerLot() * gEnt;   // v1.03: account currency, so net_bp is right on cent accounts too
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


//---- v1.05 pending-order helpers (OCO stop orders at the Williams levels)
int CountPendings()
  {
   int c = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--) { ulong t = OrderGetTicket(i); if(t == 0) continue; if(OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic) c++; }
   return c;
  }
void DeletePendings()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i); if(t == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic && !trade.OrderDelete(t))
         Print("Williams: pending delete failed #", t, " ", trade.ResultRetcodeDescription());
     }
  }
int CountPositions()
  {
   int c = 0;
   for(int k = PositionsTotal() - 1; k >= 0; k--) { ulong t = PositionGetTicket(k); if(t == 0) continue; if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic) c++; }
   return c;
  }
// both stops filled in one spike (rare): keep the earlier position, close the later one (research: one trade per day)
void CloseExtraPosition()
  {
   ulong keep = 0, extra = 0; datetime tk = 0;
   for(int k = PositionsTotal() - 1; k >= 0; k--)
     {
      ulong t = PositionGetTicket(k); if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME_MSC);
      if(keep == 0 || ot < tk) { if(keep != 0) extra = keep; keep = t; tk = ot; } else extra = t;
     }
   if(extra != 0) { Print("Williams: both stops filled, closing the later position #", extra); SafeClose(extra); }
  }
// v1.06: server time of today's exit (InpExitNYMin on the trading-day key's NY date), for order expiry
datetime ExitServerTime()
  {
   MqlDateTime k; TimeToStruct(dayKey, k); k.hour = InpExitNYMin / 60; k.min = InpExitNYMin % 60; k.sec = 0;
   datetime ny = StructToTime(k);                                  // NY local time
   datetime utc = (datetime)((long)ny - (long)NYOffset((datetime)((long)ny + 5 * 3600)) * 3600);
   return (datetime)((long)utc + (long)InpServerUTC * 3600);
  }
void PlaceDayOrders()
  {
   DeletePendings(); gOrdersDay = dayKey;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), spr = ask - bid;
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT), minDist = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * pt;
   trade.SetExpertMagicNumber(InpMagic); trade.SetDeviationInPoints(InpDeviation);
   // already beyond a level when the day's orders are placed (gap) -> research fills at the open: market order now
   if(bid >= buyLvl || bid <= sellLvl) { gOrdersDay = 0; return; }       // handled by the market-on-touch path below
   double bl = NormalizeDouble(buyLvl + spr, _Digits), sl = NormalizeDouble(sellLvl, _Digits);   // buy stop triggers on ASK: +spread = BID at the level
   double lotB = LotFor(bl), lotS = LotFor(sl);
   if(lotB <= 0 || lotS <= 0)
     {   // v1.08: value not ready (cent conversion syncing) or below minimum -> no orders, retry in 60 s
      DeletePendings(); gOrdersDay = 0; gPlaceTried = 0; gNextTry = TimeCurrent() + 60;
      static datetime lw = 0; if(TimeCurrent() - lw > 3600) { lw = TimeCurrent(); Print("Williams: lot not available yet (value check / minimum) - retrying"); }
      return;
     }
   long em = SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_MODE); bool canExp = (em & SYMBOL_EXPIRATION_SPECIFIED) != 0;
   ENUM_ORDER_TYPE_TIME tt = canExp ? ORDER_TIME_SPECIFIED : ORDER_TIME_GTC; datetime ex = canExp ? ExitServerTime() : 0;
   if(canExp && ex <= TimeCurrent() + 60) { tt = ORDER_TIME_GTC; ex = 0; }
   uint rcB = 0, rcS = 0;
   bool okB = (bl - ask > minDist) && trade.BuyStop(lotB, bl, _Symbol, 0, 0, tt, ex, "Williams#112 BS"); if(!okB) rcB = trade.ResultRetcode();
   bool okS = (bid - sl > minDist) && trade.SellStop(lotS, sl, _Symbol, 0, 0, tt, ex, "Williams#112 SS"); if(!okS) rcS = trade.ResultRetcode();
   if((!okB || !okS) && (rcB == TRADE_RETCODE_MARKET_CLOSED || rcS == TRADE_RETCODE_MARKET_CLOSED))
     {   // v1.06: daily break (gold 17:00-18:00 NY) -> retry every minute, no fallback
      DeletePendings(); gOrdersDay = 0; gPlaceTried = 0; gNextTry = TimeCurrent() + 60;
      if(gClosedMsgDay != dayKey) { gClosedMsgDay = dayKey; Print("Williams: market closed, will place the day orders when it reopens"); }
      return;
     }
   PrintFormat("Williams day orders: buy stop %.2f %s | sell stop %.2f %s (open %.2f, prev range %.2f, expiry %s)", bl, okB ? "ok" : "NOT placed", sl, okS ? "ok" : "NOT placed", dOpen, prevRange, ex > 0 ? TimeToString(ex) : "GTC");
   if(!okB || !okS) { DeletePendings(); gOrdersDay = 0; Print("Williams: falling back to market-on-touch today"); }
  }

void OnTickLogic()
  {
   RetryPendingCloses(); FinishIfClosed();
   datetime nowUTC = ToUTC(TimeCurrent());
   datetime key = TradingDayKey(nowUTC);
   if(key != dayKey) { dayKey = key; tradedToday = false; if(!ComputeLevels(nowUTC)) { dOpen = 0; } if(InpSkipWeekendKeys && IsWeekendKey(key)) tradedToday = true; }
   int nm = NYMinute(nowUTC);
   ulong tk;
   bool exitWin = nm >= InpExitNYMin && nm < 17 * 60;
   if(InpPendingEntry && (exitWin || (gOrdersDay != 0 && gOrdersDay != dayKey)) && CountPendings() > 0) { DeletePendings(); gOrdersDay = 0; }
   if(FindPos(tk))
     {
      if(CountPendings() > 0) DeletePendings();                                // v1.05 OCO: one filled -> cancel the other
      if(CountPositions() > 1) { CloseExtraPosition(); return; }
      if(gTicket == 0 && PositionSelectByTicket(tk))                           // v1.05: a stop order filled -> bookkeeping
        {
         gTicket = tk; gPosId = PositionGetInteger(POSITION_IDENTIFIER); gSide = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
         gLvl = gSide == 1 ? buyLvl : sellLvl; gEnt = PositionGetDouble(POSITION_PRICE_OPEN); gVol = PositionGetDouble(POSITION_VOLUME);
         gEntT = (datetime)PositionGetInteger(POSITION_TIME); gSpr = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID); gDayKey = dayKey;
         tradedToday = true;
         PrintFormat("Williams %s %.2f lots filled @ %.2f (level %.2f)", gSide == 1 ? "BUY" : "SELL", gVol, gEnt, gLvl);
        }
      datetime posKey = TradingDayKey(ToUTC((datetime)PositionGetInteger(POSITION_TIME)));
      if(posKey != dayKey) { gStale = true; SafeClose(tk); return; }           // v1.01 safety: never hold past the trading day
      if(exitWin) SafeClose(tk);                                               // day close
      return;
     }
   if(tradedToday || dOpen <= 0 || exitWin) return;
   if(InpPendingEntry)
     {
      bool fresh = TimeTradeServer() - (datetime)SymbolInfoInteger(_Symbol, SYMBOL_TIME) < 120 && TradeSessionOpen();   // v1.08: quoting AND trade session open
      if(gPlaceTried != dayKey && TimeCurrent() >= gNextTry && fresh) { gPlaceTried = dayKey; PlaceDayOrders(); }   // on "market closed" PlaceDayOrders re-arms a retry
      if(gOrdersDay == dayKey) return;                                         // orders working; fills are picked up above
      if(gPlaceTried != dayKey) return;                                        // v1.06: waiting for the market to reopen: never market-enter while closed
     }
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int side = bid >= buyLvl ? 1 : (bid <= sellLvl ? -1 : 0);                  // research triggers on BID high/low
   if(side == 0) return;
   double px = side == 1 ? ask : bid, lot = LotFor(px);
   if(lot <= 0) { static datetime lw2 = 0; if(TimeCurrent() - lw2 > 3600) { lw2 = TimeCurrent(); Print("Williams: lot not available yet (value check / minimum)"); } return; }   // v1.08
   tradedToday = true;                                                         // first touched level wins, one trade per day
   if(InpMaxSpread > 0 && ask - bid > InpMaxSpread) { Print("Williams: skipped, spread ", ask - bid); return; }
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
   { double px0 = SymbolInfoDouble(_Symbol, SYMBOL_BID);
     PrintFormat("Sizing check: account %s | equity %.2f | 1.0 price move x 1 lot = %.4f %s | lot now = %.2f (notional %.2f = %.2fx equity)",
                 AccountInfoString(ACCOUNT_CURRENCY), AccountInfoDouble(ACCOUNT_EQUITY), MoneyPerPricePerLot(), AccountInfoString(ACCOUNT_CURRENCY),
                 LotFor(px0), LotFor(px0) * MoneyPerPricePerLot() * px0, AccountInfoDouble(ACCOUNT_EQUITY) > 0 ? LotFor(px0) * MoneyPerPricePerLot() * px0 / AccountInfoDouble(ACCOUNT_EQUITY) : 0.0); }
   ulong tk; if(FindPos(tk) && PositionSelectByTicket(tk)) { gTicket = tk; gPosId = PositionGetInteger(POSITION_IDENTIFIER); gSide = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1; gEnt = PositionGetDouble(POSITION_PRICE_OPEN); gVol = PositionGetDouble(POSITION_VOLUME); gEntT = (datetime)PositionGetInteger(POSITION_TIME); gDayKey = TradingDayKey(ToUTC(gEntT)); tradedToday = true; }
   if(InpPendingEntry && CountPendings() > 0 && !FindPos(tk)) DeletePendings();   // v1.05: restart -> re-place today's orders fresh (never adopt old ones)
   EventSetTimer(10); return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason) { EventKillTimer(); }
void OnTimer() { OnTickLogic(); }
void OnTick() { OnTickLogic(); }
//+------------------------------------------------------------------+
