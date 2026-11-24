# GoldComboAI v1.00 → v1.01: إغلاق أمان لـ Overnight + Shadow (تسجيل بس)

**وش يتغير:**
- **(1) إغلاق أمان:** لو صفقة Overnight مفتوحة أكثر من 6 ساعات، تتسكّر. الخروج الأساسي الساعة 20:00 نيويورك ما يتغير.
- **(2) Shadow:** عند كل دخول Sonic أو Overnight، يحسب رأي نموذج RF (#159) ويسجّله في CSV.
- **منطق الدخول والحجم ما يتغير ولا حرف.**

**التطبيق:**
1. انسخ `GoldComboShadow.mqh` لنفس مجلد `GoldComboAI.mq5`، يعني `MQL5\Experts`.
2. طبّق التعديلات الخمسة تحت (A لين E) على نسخة من GoldComboAI.mq5. **احتفظ بالأصلي.**
3. اعمل Compile.

---

### A) الإصدار
```
#property version   "1.00"
```
←
```
#property version   "1.01"
```

### B) تضمين الـ Shadow: بعد سطر `double   NaNv;` (آخر سطر في قسم globals)
```
double   NaNv;
```
←
```
double   NaNv;
#include "GoldComboShadow.mqh"   // v1.01: shadow AI logging only (never trades)
```

### C) إغلاق أمان Overnight: داخل `OnNewBar()`، بعد بلوك الخروج الساعة 20:00 مباشرة
**النص الموجود:**
```
   if(ny.hour == 20 && onOpen)
     {
      if(InpAutoTrade) SafeClose(otk);
      Notify(StringFormat("OVERNIGHT EXIT %s @ %.2f (20:00 New York)", _Symbol, C[i]));
      onOpen = false;
     }
```
**أضف بعده:**
```
   // v1.01 SAFETY: Overnight is a 4-hour trade. If the 20:00 NY bar was missed (terminal offline, no tick),
   // close at the next new bar instead of holding it (and paying swap) for days.
   if(onOpen && TimeCurrent() - oop > 6 * 3600)
     {
      if(InpAutoTrade) SafeClose(otk);
      Notify(StringFormat("OVERNIGHT SAFETY EXIT %s @ %.2f (open > 6 h)", _Symbol, C[i]));
      onOpen = false;
     }
```

### D) Shadow عند دخول Sonic: داخل بلوك `if(ok)` بعد دخول Sonic
**النص الموجود:**
```
               GVset("sOpen", 1); GVset("sRisk", lot * dist * vpp);
```
←
```
               GVset("sOpen", 1); GVset("sRisk", lot * dist * vpp);
               GS_AfterEntry(InpMagicSonic, "SONIC", sig);   // v1.01 shadow log (after the order, never changes it)
```

### E) Shadow عند دخول Overnight + الاستطلاع في OnTick
**النص الموجود (دخول Overnight):**
```
            if(InpAutoTrade) { trade.SetExpertMagicNumber(InpMagicON); if(!trade.Buy(lot, _Symbol, 0, 0, 0, "Overnight AI")) Print("ON order failed: ", trade.ResultRetcodeDescription()); }
```
←
```
            if(InpAutoTrade) { trade.SetExpertMagicNumber(InpMagicON); if(!trade.Buy(lot, _Symbol, 0, 0, 0, "Overnight AI")) Print("ON order failed: ", trade.ResultRetcodeDescription()); else GS_AfterEntry(InpMagicON, "OVERNIGHT", 1); }
```
**وفي `OnTick()`، أول سطر:**
```
void OnTick()
  {
   if(ArraySize(pendClose) > 0) RetryPendingCloses();
```
←
```
void OnTick()
  {
   GS_Poll();                                     // v1.01 shadow: logs closed tracked trades + daily bar dump
   if(ArraySize(pendClose) > 0) RetryPendingCloses();
```

---

## الإعدادات الجديدة (مجموعة "Shadow AI")
| الإعداد | الافتراضي | ملاحظة |
|---|---|---|
| InpGSShadow | true | لو false، ما يحسب ولا يسجّل شي |
| GS_InpHistBars | 80000 | نموذج Overnight يحتاج حوالي 80 ألف شمعة H1 (13 سنة) عشان يطابق البحث. Sonic يثبت من 20 ألف. لو الوسيط يعطي أقل، الرقم الفعلي ينكتب في عمود `bars_used` |
| GS_InpMinBars | 15000 | في Strategy Tester للمطابقة استخدم 4000 |
| InpGSDumpBars | true | تفريغ شموع H1 مرة يوميًا لاختبار المطابقة |

## الملفات اللي تطلع (MQL5/Files)
- `GoldComboShadow_signals.csv`: عند كل دخول. فيه الاستراتيجية، و position_id، والـ 206 خاصية، والحجم المقترح، و bars_used.
- `GoldComboShadow_trades.csv`: عند كل خروج. فيه الربح الحقيقي (net_money و net_bp و ret_equity) مع الحجم المقترح.
- `GoldComboShadow_bars.csv`: شموع H1 لاختبار المطابقة.

## المقارنة بعد كم شهر
```
python gold-research/code/combo_shadow_compare.py --trades GoldComboShadow_trades.csv \
       --signals GoldComboShadow_signals.csv --bars GoldComboShadow_bars.csv --hist 80000
```
السكربت يعطيك لكل استراتيجية لحالها (Sonic و Overnight):
- **المطابقة:** هل الـ EA يحسب نفس Python؟
- **المقارنة:** الصفقات اللي كان بيكبّرها مقابل اللي كان بيصغّرها.

## ⚠️ تنبيهات
- **ملاحظة:** الـ Shadow يتتبع الصفقات المفتوحة في الذاكرة. لو انعاد تشغيل MT5 وصفقة مفتوحة، ما ينكتب سطر الخروج حقها. سطر الدخول موجود في signals مع position_id، فتقدر تربطه بتقرير الحساب.
- **بعد Compile:** شغّله أول في **Strategy Tester** (1 minute OHLC، و GS_InpMinBars = 4000) عشان تتأكد إن:
  - (أ) الصفقات **نفس** صفقات v1.00 بالضبط.
  - (ب) المطابقة تنجح.
- **بعدها:** الحساب الحقيقي أو الديمو، وقرار هذا **لك**.
- **المرجع البحثي** (2009–2023، خارج العينة): Sonic: المكبَّرة +8.3bp والمصغَّرة −1.3bp. Overnight: المكبَّرة −0.3bp والمصغَّرة −5.1bp. **الحكم الإحصائي يحتاج سنين.**
