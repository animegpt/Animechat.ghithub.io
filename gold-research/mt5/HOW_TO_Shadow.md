# GoldWilliams_Shadow.mq5: طريقة التشغيل والمقارنة

## وش يسوي
- **تداول Williams #112 بنفس منطق GoldWilliams.mq5 حرفيًا.** الحجم الفعلي ما يتغير أبدًا.
- **وقت كل دخول، وبعد ما تتنفذ الصفقة** (فما يأخرها):
  - يحسب 206 خاصية من المؤشرات الثلاثة على H1/H4/D1. يبنيها من شموع H1 على توقيت نيويورك (اليوم يبدأ 17:00)، نفس طريقة البحث.
  - يشغّل نموذج RF المجمّد: 300 شجرة، تدرّب على الذهب 2005–2023 (#150).
  - يسجّل **الحجم اللي كان النموذج بيستخدمه** (0.5–1.5) بدون ما ينفذه.
- **Magic 770502.** شغّله **بدل** GoldWilliams (770501)، **مو معه**، وإلا تتكرر الصفقات.

## الملفات (MQL5/Files)
| الملف | متى ينكتب | وش فيه |
|---|---|---|
| `GoldWilliams_Shadow_trades.csv` | عند كل خروج | الصفقة الحقيقية + net_bp + shadow_size + shadow_pred + shadow_volume |
| `GoldWilliams_Shadow_signals.csv` | عند كل دخول | الـ 206 خاصية اللي حسبها الـ EA + التوقع والحجم |
| `GoldWilliams_Shadow_bars.csv` | مرة كل يوم تداول (يستبدل القديم) | شموع H1 (حوالي 60 ألف)، عشان Python يتأكد من الحساب |

## ⚠️ v1.02: وقت الخروج
اختبار Exness بيّن إن **ما فيه أي تيك بين 16:58 و 17:00 نيويورك**، لأن الاستراحة اليومية تبدأ قبلها.
فالخروج صار يبدأ **16:50 نيويورك** (الإعداد InpExitNYMin = 1010)، يعني قبل إغلاق البحث بحوالي 8 دقايق بس.
وإغلاق الأمان (STALE_CLOSE) باقي كاحتياط. في الاختبار لازم يكون **نادر جدًا**.

## الخطوات
1. **التركيب:** انسخ `GoldWilliams_Shadow.mq5` لمجلد `MQL5/Experts`، واعمله Compile في MetaEditor.
   > ⚠️ ما قدرت أعمل Compile للكود هنا (ما فيه MetaTrader في البيئة). لو طلع أي خطأ ترجمة، أرسله لي.
2. **التاريخ:** الـ EA يحتاج **15,000 شمعة H1 على الأقل** (الافتراضي 20,000). روح Tools → Options → Charts → Max bars، وخلّه 100000 أو أكثر. وافتح شارت XAUUSDc H1 وارجع لورا عشان ينزل التاريخ.
3. **اختبار المطابقة أولًا (مهم):**
   - ⚠️ Strategy Tester يعطي الروبوت تاريخ حوالي سنة بس قبل بداية الاختبار. عشان كذا:
     - ابدأ الاختبار من **2023-01-01** لين **2025-06-30**.
     - حط **InpMinBars = 4000**.
     - شغّل السكربت بـ `--minbars 4000 --hist 20000`. المطابقة تقارن EA مع Python على **نفس** النافذة.
   - **في الديمو الحي** خلّ InpMinBars = 15000.
   - شغّله في Strategy Tester على XAUUSDc، فترة 2024–2025، بوضع Every tick based on real ticks.
   - الملفات تطلع في مجلد الـ Tester Agent: `...\Tester\Agent-...\MQL5\Files`.
   - بعدها شغّل:
     ```
     python gold-research/code/shadow_compare.py --trades GoldWilliams_Shadow_trades.csv \
            --signals GoldWilliams_Shadow_signals.csv --bars GoldWilliams_Shadow_bars.csv
     ```
   - لازم يطلع `"parity": {"passes": true}`، يعني متوسط فرق الحجم ≤ 0.03 بين الـ EA و Python.
   - لو ما تطابق: السكربت يستخدم حجم Python تلقائيًا (هو الحقيقة البحثية) ويقولك. وأرسل لي `features_max_abs_diff_top5` عشان أصلّح الـ EA.
   - ⚠️ نتيجة الربح من Tester على 2024–2026 **مو دليل**، لأنها فترة الخزنة. المقصود من هذي الخطوة **المطابقة بس**.
4. **الديمو للأمام:** شغّله على حساب Demo، وكل كم شهر شغّل نفس الأمر على ملفات الديمو.

## وش يقول لك السكربت
- **مقارنة المجموعتين:** متوسط ربح الصفقات اللي كان النموذج **بيكبّرها** (size>1) مقابل اللي كان **بيصغّرها** (size<1). معها الفرق، و t (Welch)، وفترة ثقة 95٪ (bootstrap)، و IC.
- **مقارنة المحفظة:** الربح الكلي "عادي" مقابل "لو تحجّم"، و Sharpe الشهري محجّم مقابل عادي (من 6 أشهر وطالع).
- **المرجع البحثي** (خارج العينة 2009–2023): المكبَّرة **+7.21bp**، والمصغَّرة **−1.29bp**.

## ⏳ الصراحة عن المدة
- الفرق المتوقع حوالي 8.5bp، وتذبذب الصفقة الواحدة حوالي 75bp. فعشان نوصل t≈2 نحتاج تقريبًا **600 صفقة، يعني 3.5 لين 4 سنين**.
- بعد كم شهر (50–100 صفقة)، أي نتيجة، حلوة أو سيئة، **أغلبها ضجيج**. والسكربت يقولها صريحة: `TOO EARLY`.
- اللي نقدر نتأكد منه بسرعة:
  - (1) الـ EA يحسب نفس البحث (المطابقة).
  - (2) توزيع الأحجام طبيعي (حوالي نصف فوق 1 ونصف تحت).
  - (3) ما فيه انهيار واضح، يعني الصفقات المكبّرة مو أسوأ بفرق كبير.

## F1 shadow (#155, added 2026-11-24)
- Input `InpShadowF1` (default true). At 16:00 NY, if a Williams position is open and was entered before 16:00, the EA
  checks the completed 15:00-NY H1 bar: if it moved WITH the trade -> `f1_flag = 1` and the price the early exit would
  have got (bid for longs, ask for shorts) is stored. `f1_flag = 0` rule not met, `2` = 15:00 bar missing, `-1` = never checked
  (entry after 16:00). Nothing is closed early: the trade still exits at 16:58.
- `f1_delta_bp` = side × (f1_exit_price − real exit price) / entry × 1e4 (only for flag 1) = what F1 would have added,
  with the REAL spreads of both moments.
- Not compiled/tested in MT5 here (no MetaTrader in this container). Compile in MetaEditor; check one day by hand.
