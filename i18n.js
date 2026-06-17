/*
 * i18n.js - language + digit direction for the dashboard (Stage 6.5).
 *
 * Loaded before app.js. Reads the saved preferences (defaulting to Arabic,
 * right-to-left, since the product runs mainly on Arabic data), sets the
 * document direction/language, swaps the Cairo font in, translates every
 * element carrying a data-i18n="key" attribute, and exposes a tiny API on
 * window.I18N for app.js to use (translate a key, localize digits).
 *
 * Switching language or digits just saves the preference and reloads, so every
 * view - including charts created on load - renders in the right direction
 * without any live re-rendering complexity.
 */
(function () {
    "use strict";

    var DICT = {
        ar: {
            "doc.title": "مركز قيادة الشركة المالي",
            "brand.name": "نظام المالية",
            "brand.tag": "مركز قيادة الشركة",
            "nav.analytics": "التحليلات",
            "tab.reports": "التقارير",
            "tab.overview": "نظرة عامة",
            "tab.regional": "المناطق",
            "tab.product": "المنتجات",
            "tab.drilldown": "الانحرافات",
            "tab.scenario": "السيناريو",
            "tab.trends": "الاتجاهات",
            "tab.portfolio": "المحفظة",
            "meta.records": "السجلات",
            "meta.database": "قاعدة البيانات",
            "meta.coverage": "التغطية",
            "filter.year": "السنة",
            "filter.version": "النسخة",
            "filter.region": "المنطقة",
            "filter.country": "الدولة",
            "opt.all_years": "كل السنوات",
            "opt.all_regions": "كل المناطق",
            "opt.all_countries": "كل الدول",
            "btn.apply": "تطبيق الفلاتر",
            "btn.reset": "إعادة ضبط",
            "btn.refresh": "تحديث",
            "btn.try_again": "إعادة المحاولة",
            "status.connecting": "جارٍ الاتصال...",
            "alert.load_fail": "تعذّر تحميل البيانات",
            "page.overview.title": "النظرة التنفيذية",
            "page.overview.sub": "أداء الأرباح والخسائر مباشرة من سجل قاعدة بيانات SQLite",
            "page.regional.title": "الأداء حسب المنطقة",
            "page.regional.sub": "الجغرافيا التجارية والربحية والمساهمة السوقية",
            "page.product.title": "اقتصاديات المنتجات",
            "page.product.sub": "الإيرادات والربحية حسب مجموعة المنتج",
            "page.drilldown.title": "مسببات الانحراف",
            "page.drilldown.sub": "الأبعاد المحرّكة للتغيّر المالي بين الفترات",
            "page.scenario.title": "ماذا لو",
            "page.scenario.sub": "اختبر قرارًا قبل اتخاذه",
            "page.trends.title": "اتجاهات 5 سنوات",
            "page.trends.sub": "أداء الأرباح والخسائر ونسب الكفاءة 2022–2026",
            "page.portfolio.title": "مصفوفة المحفظة الاستراتيجية",
            "page.portfolio.sub": "نمو مجموعات المنتجات مقابل الهامش لقرارات تخصيص رأس المال",
            "page.reports.title": "تقارير الشركة",
            "page.reports.sub": "إنشاء وتحميل التقارير المالية مباشرة من قاعدة البيانات",
            "page.ask.title": "اسأل البيانات",
            "page.ask.sub": "اكتب سؤالك بالعربية أو الإنجليزية — تُجاب محليًا",
            "page.briefing.title": "الملخص التنفيذي",
            "page.briefing.sub": "صفحة واحدة: ما تغيّر، وما المخاطر، وما الإجراء",
            "page.guardian.title": "الحارس",
            "page.guardian.sub": "مراقبة الشذوذ — ما يبدو غير معتاد، متتبَّعًا لمصدره",
            "page.pricing.title": "مساعد التسعير",
            "page.pricing.sub": "اقتراحات إعادة التسعير والخصم الزائد ورفع السعر",
            "page.health.title": "المصدر والجودة",
            "page.health.sub": "من أين أتت الأرقام وهل هي سليمة",
            "page.knowledge.title": "قاعدة المعرفة",
            "page.knowledge.sub": "ابحث في ملاحظات الشركة وقراراتها وتعريفاتها",
            "reports.sectionTitle": "تقارير الشركة",
            "reports.sectionDesc": "إنشاء وتحميل التقارير المالية مباشرة من قاعدة البيانات",
            "tab.health": "المصدر والجودة",
            "health.sectionTitle": "مصدر البيانات وجودتها",
            "health.sectionDesc": "من أين أتت الأرقام المحمّلة وهل تجتاز فحوص السلامة — للدفاع عن أي رقم على الشاشة.",
            "health.checksTitle": "فحوص سلامة البيانات",
            "health.checksSubtitle": "محسوبة مباشرة من قاعدة البيانات الحالية",
            "health.historyTitle": "سجل عمليات الاستيراد",
            "health.historySubtitle": "عمليات تحميل لكل عميل (تظهر بعد استيراد ملف عميل حقيقي)",
            "whatif.title": "روافع ماذا-لو",
            "whatif.subtitle": "عدّل الافتراضات وشاهد أثرها على توقعات السنة الكاملة مباشرة",
            "whatif.reset": "إعادة ضبط",
            "whatif.netsales": "صافي المبيعات",
            "whatif.cogs": "تكلفة البضاعة",
            "whatif.opex": "المصروفات التشغيلية",
            "whatif.tax": "معدل الضريبة",
            "whatif.scales": "تكلفة البضاعة تتناسب مع الإيراد",
            "sensitivity.title": "حساسية الربح",
            "sensitivity.subtitle": "أي رافعة تحرّك صافي الدخل أكثر (±٥٪)",
            "compare.title": "ثلاث خطط جنبًا إلى جنب",
            "compare.subtitle": "متحفّظة · أساسية · طموحة — أرباح وخسائر السنة الكاملة",
            "tab.briefing": "الملخص التنفيذي",
            "briefing.title": "الملخص التنفيذي",
            "briefing.subtitle": "صفحة واحدة: ما الذي تغيّر، وما المخاطر، وما الإجراء — ومدى موثوقية الأرقام.",
            "briefing.print": "طباعة / حفظ PDF",
            "tab.ask": "اسأل",
            "ask.title": "اسأل البيانات",
            "ask.subtitle": "اكتب سؤالك بالعربية أو الإنجليزية — تُجاب محليًا، ولا تغادر أي بيانات الجهاز.",
            "ask.run": "اسأل",
            "ask.resultTitle": "الإجابة",
            "tab.guardian": "الحارس",
            "guardian.title": "الحارس — مراقبة الشذوذ",
            "guardian.subtitle": "النظام يراقب السجل وينبّهك لأي شيء غير معتاد — وكل تنبيه متتبَّع إلى مصدره.",
            "guardian.enableAlerts": "تفعيل التنبيهات",
            "guardian.ack": "تعليم الكل كمقروء",
            "tab.pricing": "مساعد التسعير",
            "pricing.title": "مساعد التسعير",
            "pricing.subtitle": "أين تخسر مالًا، أو تخصم كثيرًا، أو يمكنك رفع السعر — مع المصدر لكل توصية.",
            "tab.knowledge": "قاعدة المعرفة",
            "knowledge.sectionTitle": "قاعدة المعرفة",
            "knowledge.sectionDesc": "ابحث في تعريفات الشركة وأعرافها وقراراتها وعملياتها.",
            "knowledge.searchLabel": "ابحث في الملاحظات",
            "ui.lang_toggle": "English",
            "ui.digits_toggle": "١٢٣"
        },
        en: {
            "doc.title": "Company Finance Command Center",
            "brand.name": "Finance OS",
            "brand.tag": "Company command center",
            "nav.analytics": "Analytics",
            "tab.reports": "Reports",
            "tab.overview": "Overview",
            "tab.regional": "Regional",
            "tab.product": "Products",
            "tab.drilldown": "Variance",
            "tab.scenario": "Scenario",
            "tab.trends": "Trends",
            "tab.portfolio": "Portfolio",
            "meta.records": "Records",
            "meta.database": "Database",
            "meta.coverage": "Coverage",
            "filter.year": "Year",
            "filter.version": "Version",
            "filter.region": "Region",
            "filter.country": "Country",
            "opt.all_years": "All years",
            "opt.all_regions": "All regions",
            "opt.all_countries": "All countries",
            "btn.apply": "Apply filters",
            "btn.reset": "Reset",
            "btn.refresh": "Refresh",
            "btn.try_again": "Try again",
            "status.connecting": "Connecting...",
            "alert.load_fail": "We couldn't load the data",
            "page.overview.title": "Executive Overview",
            "page.overview.sub": "Live profit and loss performance from the SQLite detail ledger",
            "page.regional.title": "Regional Performance",
            "page.regional.sub": "Commercial geography, profitability and market contribution",
            "page.product.title": "Product Economics",
            "page.product.sub": "Revenue and profitability by product group",
            "page.drilldown.title": "Variance Contributors",
            "page.drilldown.sub": "The dimensions driving financial movement between periods",
            "page.scenario.title": "What-If Scenarios",
            "page.scenario.sub": "Test a decision before you take it",
            "page.trends.title": "5-Year Trends",
            "page.trends.sub": "Structural P&L performance and efficiency ratios FY2022–FY2026",
            "page.reports.title": "Company Reports",
            "page.reports.sub": "Generate and download financial reports directly from the database",
            "page.ask.title": "Ask the data",
            "page.ask.sub": "Type a question in Arabic or English — answered locally",
            "page.briefing.title": "Executive Briefing",
            "page.briefing.sub": "One page: what changed, what is at risk, what to do",
            "page.guardian.title": "Guardian",
            "page.guardian.sub": "Anomaly watch — what looks unusual, traced to its source",
            "page.pricing.title": "Price helper",
            "page.pricing.sub": "Reprice, over-discounted, and raise-price suggestions",
            "page.health.title": "Source & Health",
            "page.health.sub": "Where the numbers come from and whether they are clean",
            "page.knowledge.title": "Knowledge base",
            "page.knowledge.sub": "Search the company notes, decisions and definitions",
            "reports.sectionTitle": "Company Reports",
            "reports.sectionDesc": "Generate and download financial reports directly from the database",
            "tab.health": "Source & Health",
            "health.sectionTitle": "Source & Data Health",
            "health.sectionDesc": "Where the loaded numbers come from and whether they pass integrity checks — defend any figure on screen.",
            "health.checksTitle": "Data integrity checks",
            "health.checksSubtitle": "Computed live from the current database",
            "health.historyTitle": "Import run history",
            "health.historySubtitle": "Per-client load runs (present after a real client import)",
            "whatif.title": "What-if levers",
            "whatif.subtitle": "Adjust assumptions and see the full-year outlook impact live",
            "whatif.reset": "Reset",
            "whatif.netsales": "Net sales",
            "whatif.cogs": "COGS",
            "whatif.opex": "Operating expense",
            "whatif.tax": "Tax rate",
            "whatif.scales": "COGS scales with revenue",
            "sensitivity.title": "Profit sensitivity",
            "sensitivity.subtitle": "Which lever moves net income the most (±5%)",
            "compare.title": "Three plans side by side",
            "compare.subtitle": "Conservative · Base · Aggressive — full-year P&L",
            "tab.briefing": "Briefing",
            "briefing.title": "Executive briefing",
            "briefing.subtitle": "One page: what changed, what's at risk, what to do — and how trustworthy the numbers are.",
            "briefing.print": "Print / Save PDF",
            "tab.ask": "Ask",
            "ask.title": "Ask the data",
            "ask.subtitle": "Type a question in Arabic or English — answered locally, no data leaves the machine.",
            "ask.run": "Ask",
            "ask.resultTitle": "Answer",
            "tab.guardian": "Guardian",
            "guardian.title": "Guardian — anomaly watch",
            "guardian.subtitle": "The system watches the ledger and flags what looks unusual — every alert is traced to its source.",
            "guardian.enableAlerts": "Enable alerts",
            "guardian.ack": "Mark all seen",
            "tab.pricing": "Price helper",
            "pricing.title": "Price helper",
            "pricing.subtitle": "Where you lose money, discount too much, or could charge more — with the source behind each one.",
            "tab.knowledge": "Knowledge",
            "knowledge.sectionTitle": "Knowledge base",
            "knowledge.sectionDesc": "Search the company's definitions, conventions, decisions, and processes.",
            "knowledge.searchLabel": "Search notes",
            "page.portfolio.title": "Strategic Portfolio Matrix",
            "page.portfolio.sub": "Product group growth vs margin positioning for capital allocation decisions",
            "ui.lang_toggle": "العربية",
            "ui.digits_toggle": "123"
        }
    };

    var WESTERN = "0123456789";
    var ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩";

    var AR_TEXT = {
        "Loading...": "جارٍ التحميل...",
        "Live SQLite": "قاعدة SQLite مباشرة",
        "Executive Overview": "النظرة التنفيذية",
        "Live profit and loss performance from the SQLite detail ledger": "أداء الأرباح والخسائر مباشرة من سجل قاعدة بيانات SQLite",
        "Data is fresh.": "البيانات محدّثة.",
        "Year": "السنة",
        "Metric": "المؤشر",
        "Primary year": "السنة الأساسية",
        "Compare with": "المقارنة مع",
        "From year": "من سنة",
        "To year": "إلى سنة",
        "Dimension": "البعد",
        "Current year": "السنة الحالية",
        "Analyze": "تحليل",
        "Run analysis": "تشغيل التحليل",
        "Running query...": "جارٍ تشغيل الاستعلام...",
        "Export CSV": "تصدير CSV",
        "Actual + Outlook": "الفعلي + التوقع",
        "Reporting view": "عرض التقرير",
        "Version": "النسخة",
        "All years": "كل السنوات",
        "All regions": "كل المناطق",
        "All countries": "كل الدول",
        "Loading live data...": "جارٍ تحميل البيانات المباشرة...",
        "Database coverage is unavailable.": "تغطية قاعدة البيانات غير متاحة.",
        "Choose two different years": "اختر سنتين مختلفتين",
        "CSV exported": "تم تصدير CSV",
        "Report downloaded": "تم تحميل التقرير",
        "Download failed": "فشل التحميل",
        "Export needs setup": "هذا التنسيق يحتاج إلى تثبيت إضافي على الخادم",
        "Board pack": "حزمة المجلس",
        "Building board pack…": "جارٍ تجهيز حزمة المجلس…",
        "Board pack ready": "حزمة المجلس جاهزة",
        "Healthy": "سليم",
        "Review": "للمراجعة",
        "Overall status": "الحالة العامة",
        "Checks passed": "الفحوص الناجحة",
        "Warnings": "تحذيرات",
        "No checks available": "لا توجد فحوص متاحة",
        "Category": "الفئة",
        "Check": "الفحص",
        "Value": "القيمة",
        "Status": "الحالة",
        "Warning": "تحذير",
        "Client": "العميل",
        "When": "التوقيت",
        "Rows": "الصفوف",
        "No client import runs yet. Runs appear here after importing a client file.": "لا توجد عمليات استيراد عملاء بعد. تظهر العمليات هنا بعد استيراد ملف عميل.",
        "Line item": "البند",
        "Baseline": "الأساس",
        "Scenario": "السيناريو",
        "Change": "التغير",
        "Net income": "صافي الدخل",
        "Net income is most sensitive to": "صافي الدخل أكثر حساسية لـ",
        "swings it by": "يحرّكه بمقدار",
        "Lever": "الرافعة",
        "Swing": "التأرجح",
        "Conservative": "متحفّظة",
        "Base": "أساسية",
        "Aggressive": "طموحة",
        "Net income range across plans": "مدى صافي الدخل عبر الخطط",
        "Net sales": "صافي المبيعات",
        "Operating profit": "الربح التشغيلي",
        "Gross margin %": "نسبة هامش الربح الإجمالي",
        "increases by": "يرتفع بمقدار",
        "decreases by": "ينخفض بمقدار",
        "baseline": "الأساس",
        "vs prior year": "مقابل السنة السابقة",
        "What changed": "ما الذي تغيّر",
        "Top risks": "أهم المخاطر",
        "Recommended actions": "الإجراءات الموصى بها",
        "Source confidence": "موثوقية المصدر",
        "improved by": "تحسّن بمقدار",
        "declined by": "تراجع بمقدار",
        "operating profit": "ربح تشغيلي",
        "No material changes versus prior year.": "لا توجد تغيرات جوهرية مقابل السنة السابقة.",
        "No material risks flagged.": "لا توجد مخاطر جوهرية.",
        "Maintain the current plan; monitor monthly.": "حافظ على الخطة الحالية مع المتابعة الشهرية.",
        "loss-making product groups": "مجموعات منتجات خاسرة",
        "revenue at risk": "إيراد معرّض للخطر",
        "product groups with negative gross margin": "مجموعات منتجات بهامش إجمالي سالب",
        "revenue exposed": "إيراد معرّض",
        "Top 5 customers concentrate": "أكبر 5 عملاء يمثّلون",
        "of revenue": "من الإيراد",
        "largest": "الأكبر",
        "Gross margin compressed": "انضغط هامش الربح الإجمالي بمقدار",
        "Review pricing and direct cost for loss-making groups before committing further volume.": "راجع التسعير والتكلفة المباشرة للمجموعات الخاسرة قبل الالتزام بمزيد من الحجم.",
        "Re-price or exit negative-margin product groups.": "أعد تسعير أو اخرج من مجموعات المنتجات ذات الهامش السالب.",
        "Diversify the customer base to reduce dependence on the largest accounts.": "نوّع قاعدة العملاء لتقليل الاعتماد على أكبر الحسابات.",
        "Protect margin: audit discounts, channel mix, and COGS drivers.": "احمِ الهامش: راجع الخصومات ومزيج القنوات ومحركات تكلفة البضاعة.",
        "Lineage coverage": "تغطية تتبّع المصدر",
        "rows": "صف",
        "High": "مرتفع",
        "Medium": "متوسط",
        "Type to search the knowledge base.": "اكتب للبحث في قاعدة المعرفة.",
        "Select a note to read it here.": "اختر ملاحظة لقراءتها هنا.",
        "No notes match.": "لا توجد ملاحظات مطابقة.",
        "Opens in dashboard": "يفتح في لوحة التحكم",
        "Linked references": "الإشارات المرتبطة",
        "Related notes": "ملاحظات ذات صلة",
        "Default": "افتراضي",
        "Switching client": "جارٍ تبديل العميل",
        "Client changed": "تم تغيير العميل",
        "Alerts": "تنبيهات",
        "New": "جديدة",
        "NEW": "جديد",
        "new alerts": "تنبيهات جديدة",
        "All alerts marked as seen": "تم تعليم كل التنبيهات كمقروءة",
        "Losing money": "تخسر مالًا",
        "Over-discounted": "خصم زائد",
        "Raise price": "ارفع السعر",
        "Fix": "أصلح",
        "Opportunity": "فرصة",
        "Pricing looks healthy — no actions needed.": "التسعير يبدو سليمًا — لا حاجة لإجراء.",
        "loses money (operating profit is negative)": "يخسر مالًا (الربح التشغيلي سالب)",
        "margin": "الهامش",
        "vs company average": "مقابل متوسط الشركة",
        "Reprice or exit.": "أعد التسعير أو اخرج.",
        "below the company average": "أقل من متوسط الشركة",
        "Review discounts and pricing.": "راجع الخصومات والتسعير.",
        "demand growing": "الطلب ينمو",
        "but margin is thin": "لكن الهامش رفيع",
        "Room to raise price.": "هناك مجال لرفع السعر.",
        "Alerts enabled": "تم تفعيل التنبيهات",
        "Alerts not enabled": "لم يتم تفعيل التنبيهات",
        "Alerts are not supported here": "التنبيهات غير مدعومة هنا",
        "What the guardian flagged": "ما رصده الحارس",
        "Understood as": "فُهم كالتالي",
        "Could not answer": "تعذّرت الإجابة",
        "Item": "البند",
        "Total": "الإجمالي",
        "All clear — no anomalies detected.": "كل شيء سليم — لا يوجد شذوذ.",
        "Operating expense": "المصروفات التشغيلية",
        "COGS": "تكلفة المبيعات",
        "operating profit turned negative for the first time after": "الربح التشغيلي أصبح سالبًا لأول مرة بعد",
        "profitable years": "سنوات مربحة",
        "gross margin fell": "انخفض هامش الربح الإجمالي",
        "purchases collapsed": "انهارت المشتريات",
        "avg": "المتوسط",
        "operating expense surged": "قفزت المصروفات التشغيلية",
        "revenue grew": "نما الإيراد",
        "spiked vs the year average": "قفز مقارنة بمتوسط السنة",
        "Net Sales": "صافي المبيعات",
        "Gross Margin": "إجمالي الربح",
        "Operating Expense": "المصروفات التشغيلية",
        "Operating Profit": "الربح التشغيلي",
        "Profit Before Tax": "الربح قبل الضريبة",
        "Corporate Tax": "ضريبة الشركات",
        "Net Income": "صافي الدخل",
        "Query failed": "فشل الاستعلام",
        "Querying SQLite": "جارٍ الاستعلام من SQLite",
        "Connecting": "جارٍ الاتصال",
        "Connection failed": "فشل الاتصال",
        "Running in limited mode": "تشغيل في وضع محدود",
        "Fallback cache": "ذاكرة احتياطية",
        "We couldn’t load the dashboard data": "تعذّر تحميل بيانات لوحة التحكم",
        "The live database is not connected, so the dashboard is showing only saved summary data. Some sections may be empty until the database is set up.": "قاعدة البيانات المباشرة غير متصلة، لذلك تعرض لوحة التحكم بيانات الملخصات المحفوظة فقط. قد تكون بعض الأقسام فارغة حتى يتم إعداد قاعدة البيانات.",
        "The data service may still be starting up, or it has not been set up yet. Wait a moment and click Try again. If this is a fresh setup, the database needs to be created first — see the Getting Started guide.": "قد تكون خدمة البيانات ما زالت قيد التشغيل أو لم يتم إعدادها بعد. انتظر قليلًا ثم اضغط إعادة المحاولة. إذا كان هذا إعدادًا جديدًا، يجب إنشاء قاعدة البيانات أولًا — راجع دليل البدء.",

        "2026 executive outlook": "توقعات تنفيذية 2026",
        "Actual P01-P05 plus T06 P06 plus T07 P07-P12, compared with FY2025": "فعلي P01-P05 + T06 P06 + T07 P07-P12 مقارنة بالسنة المالية 2025",
        "Revenue movers — year on year": "محركات الإيرادات — سنة بسنة",
        "Products ranked by absolute revenue change; top gainers and largest declines at a glance": "ترتيب المنتجات حسب التغير المطلق في الإيرادات؛ أكبر الزيادات والانخفاضات في لمحة",
        "Revenue trend: Actual to outlook": "اتجاه الإيرادات: من الفعلي إلى التوقع",
        "Cumulative monthly revenue with completed and remaining periods separated": "الإيرادات الشهرية التراكمية مع فصل الفترات المكتملة والمتبقية",
        "Actual through P05, outlook begins P06": "الفعلي حتى P05، والتوقع يبدأ من P06",
        "Actual P01-P05 + T06 P06 + T07 P07-P12, compared with FY2025": "فعلي P01-P05 + T06 P06 + T07 P07-P12، مقارنة بالسنة المالية 2025",
        "Gross margin %: Actual to outlook": "نسبة هامش الربح الإجمالي: من الفعلي إلى التوقع",
        "Monthly margin quality and second-half profitability risk": "جودة الهامش الشهرية ومخاطر ربحية النصف الثاني",
        "Solid Actual, dashed operating outlook": "خط متصل للفعلي، وخط متقطع للتوقع التشغيلي",
        "P&L summary: 2026 outlook": "ملخص الأرباح والخسائر: توقعات 2026",
        "Actual progress, full-year outlook, prior year, and variance in one reconciliation": "تقدم الفعلي، وتوقع السنة الكاملة، والسنة السابقة، والانحراف في تسوية واحدة",
        "Operating profit is shown instead of EBITDA because depreciation and amortization are not available in the source ledger. Cash-flow KPIs are intentionally excluded for the same reason.": "يُعرض الربح التشغيلي بدلًا من EBITDA لأن الإهلاك والإطفاء غير متاحين في سجل المصدر. مؤشرات التدفق النقدي مستبعدة عمدًا للسبب نفسه.",
        "CFO decision center": "مركز قرارات المدير المالي",
        "Forward-looking profitability, operating leverage, concentration, and intervention signals": "الربحية المستقبلية، والرافعة التشغيلية، والتركيز، وإشارات التدخل",
        "Profit bridge vs FY2025": "جسر الربح مقارنة بالسنة المالية 2025",
        "Where revenue growth converts, or fails to convert, into earnings": "أين يتحول نمو الإيرادات، أو يفشل في التحول، إلى أرباح",
        "Revenue concentration exposure": "التعرض لتركيز الإيرادات",
        "Share of 2026 outlook held by the largest customers": "حصة أكبر العملاء من توقعات 2026",
        "Product profitability action matrix": "مصفوفة إجراءات ربحية المنتجات",
        "Top product groups by 2026 revenue — margin quality, COGS efficiency, and YoY movement with management action tiers": "أهم مجموعات المنتجات حسب إيرادات 2026 — جودة الهامش، وكفاءة تكلفة المبيعات، والحركة السنوية مع مستويات إجراءات الإدارة",

        "Regional performance": "الأداء حسب المنطقة",
        "Compare commercial geographies using live database filters": "قارن المناطق التجارية باستخدام فلاتر قاعدة البيانات المباشرة",
        "Regional comparison": "مقارنة المناطق",
        "Selected metric across regions and available years": "المؤشر المختار عبر المناطق والسنوات المتاحة",
        "Regional detail": "تفاصيل المناطق",
        "Live grouped SQLite results": "نتائج SQLite مجمعة مباشرة",
        "Product profitability": "ربحية المنتجات",
        "Rank product groups and compare performance periods": "رتّب مجموعات المنتجات وقارن فترات الأداء",
        "Top product groups": "أهم مجموعات المنتجات",
        "Ranked by the selected metric": "مرتبة حسب المؤشر المختار",
        "Gross margin quality": "جودة هامش الربح الإجمالي",
        "Margin percentage for leading product groups": "نسبة الهامش لأهم مجموعات المنتجات",
        "Product detail": "تفاصيل المنتجات",
        "Current and comparison period performance": "أداء الفترة الحالية وفترة المقارنة",
        "Variance contributors": "مساهمو الانحراف",
        "Identify the dimensions driving change between two periods": "تحديد الأبعاد التي تقود التغير بين فترتين",
        "Impact ranking": "ترتيب الأثر",
        "Largest positive and negative contributors": "أكبر المساهمين الإيجابيين والسلبيين",
        "Variance detail": "تفاصيل الانحراف",
        "Sorted by absolute financial impact": "مرتبة حسب الأثر المالي المطلق",
        "2026 operating outlook": "التوقع التشغيلي 2026",
        "Actual P01-P05 plus T06 P06 plus T07 P07-P12": "فعلي P01-P05 + T06 P06 + T07 P07-P12",
        "Period plan": "خطة الفترات",
        "Actual history with remaining 2026 operating versions": "التاريخ الفعلي مع النسخ التشغيلية المتبقية لعام 2026",
        "Outlook composition": "مكونات التوقع",
        "Contribution of each period version to the combined outlook": "مساهمة كل نسخة فترة في التوقع المجمّع",
        "Scenario details": "تفاصيل السيناريو",
        "Versions represent different periods and combine into the outlook": "النسخ تمثل فترات مختلفة وتتجمع في التوقع",
        "5-Year financial trends": "اتجاهات مالية لخمس سنوات",
        "Structural P&L performance and efficiency ratios from FY2022 through FY2026": "أداء الأرباح والخسائر الهيكلي ونسب الكفاءة من السنة المالية 2022 حتى 2026",
        "Revenue & gross margin trend": "اتجاه الإيرادات وهامش الربح الإجمالي",
        "Annual revenue (bars, left axis) with gross margin % overlay (line, right axis)": "الإيرادات السنوية (أعمدة، المحور الأيسر) مع نسبة هامش الربح الإجمالي (خط، المحور الأيمن)",
        "Cost efficiency": "كفاءة التكلفة",
        "COGS and operating expense as % of revenue — lower is better": "تكلفة المبيعات والمصروفات التشغيلية كنسبة من الإيرادات — الأقل أفضل",
        "Year-on-year growth rates": "معدلات النمو السنوية",
        "Revenue, gross profit, and operating profit YoY % change": "نسبة تغير الإيرادات والربح الإجمالي والربح التشغيلي سنة بسنة",
        "5-year P&L summary": "ملخص أرباح وخسائر لخمس سنوات",
        "With % of revenue column and year-on-year growth rate": "مع عمود النسبة من الإيرادات ومعدل النمو السنوي",
        "Strategic portfolio matrix": "مصفوفة المحفظة الاستراتيجية",
        "Product group positioning by growth rate and gross margin — BCG-style quadrant for capital allocation decisions": "تموضع مجموعات المنتجات حسب معدل النمو وهامش الربح الإجمالي — رباعيات بأسلوب BCG لقرارات تخصيص رأس المال",
        "Growth vs margin matrix": "مصفوفة النمو مقابل الهامش",
        "Bubble size = revenue. Quadrants guide invest / harvest / fix / exit decisions.": "حجم الفقاعة = الإيرادات. تساعد الرباعيات في قرارات الاستثمار / الحصاد / الإصلاح / الخروج.",
        "Portfolio detail": "تفاصيل المحفظة",
        "Products ranked by revenue with quadrant classification and recommended action": "المنتجات مرتبة حسب الإيرادات مع تصنيف الرباعيات والإجراء المقترح",

        "Net Sales": "صافي المبيعات",
        "Revenue": "الإيرادات",
        "Revenue outlook": "توقع الإيرادات",
        "COGS": "تكلفة المبيعات",
        "Cost of Sales": "تكلفة المبيعات",
        "Gross Margin": "هامش الربح الإجمالي",
        "Gross Profit": "الربح الإجمالي",
        "Gross profit": "الربح الإجمالي",
        "Gross Margin %": "نسبة هامش الربح الإجمالي",
        "GM %": "نسبة الهامش الإجمالي",
        "gross margin %": "نسبة هامش الربح الإجمالي",
        "$ millions": "ملايين الدولارات",
        "% of revenue": "نسبة من الإيرادات",
        "of revenue": "من الإيرادات",
        "COGS %": "نسبة تكلفة المبيعات",
        "OpEx %": "نسبة المصروفات التشغيلية",
        "YoY": "سنوي",
        "Change": "التغير",
        "Change %": "نسبة التغير",
        "Impact": "الأثر",
        "Product group": "مجموعة المنتج",
        "Revenue share": "حصة الإيرادات",
        "Growth %": "نسبة النمو",
        "Op margin %": "نسبة الهامش التشغيلي",
        "Quadrant": "الربع",
        "Risk tier": "مستوى المخاطر",
        "Recommended action": "الإجراء المقترح",
        "Combined outlook": "التوقع المجمّع",
        "Actual share": "حصة الفعلي",
        "Growth": "النمو",
        "Operating Expense": "المصروفات التشغيلية",
        "OpEx": "المصروفات التشغيلية",
        "Operating Profit": "الربح التشغيلي",
        "Operating profit": "الربح التشغيلي",
        "Profit Before Tax": "الربح قبل الضريبة",
        "Corporate Tax": "ضريبة الشركات",
        "Net Income": "صافي الدخل",
        "Net Profit": "صافي الربح",
        "Net profit": "صافي الربح",
        "Revenue at risk": "الإيرادات المعرضة للخطر",
        "Actual": "الفعلي",
        "Outlook": "التوقع",
        "Actual / YTD": "الفعلي / منذ بداية السنة",
        "Actual P01-P05": "الفعلي P01-P05",
        "T06 P06": "T06 P06",
        "T07 P07-P12": "T07 P07-P12",
        "Combined 2026": "إجمالي 2026",
        "Region": "المنطقة",
        "Country": "الدولة",
        "Product Group": "مجموعة المنتج",
        "Product group": "مجموعة المنتج",
        "Customer": "العميل",
        "Class": "الفئة",
        "Unassigned": "غير مخصص",
        "Unmapped product": "منتج غير مطابق",
        "No trend data available.": "لا توجد بيانات اتجاهات متاحة.",
        "No data for selected years.": "لا توجد بيانات للسنوات المختارة.",
        "No 2026 scenario records match the filters.": "لا توجد سجلات سيناريو 2026 مطابقة للفلاتر.",
        "Intervene": "تدخل",
        "Recover": "استرداد",
        "Watch": "مراقبة",
        "Star": "نجم",
        "Scale": "توسيع",
        "High concentration risk": "مخاطر تركّز مرتفعة",
        "Moderate concentration": "تركيز متوسط",
        "Diversified": "متنوع",
        "Stars — Invest & grow": "نجوم — استثمر ونمِّ",
        "Cash Cows — Harvest & defend": "مصادر نقد — احصد ودافع",
        "Question Marks — Fix or exit": "علامات استفهام — أصلح أو اخرج",
        "Traps — Exit priority": "مصائد — أولوية الخروج",
        "Stars &mdash; Invest &amp; grow": "نجوم — استثمر ونمِّ",
        "Cash Cows &mdash; Harvest &amp; defend": "مصادر نقد — احصد ودافع",
        "Question Marks &mdash; Fix or exit": "علامات استفهام — أصلح أو اخرج",
        "Traps &mdash; Exit priority": "مصائد — أولوية الخروج",

        "Gross margin improvement": "تحسن هامش الربح الإجمالي",
        "Gross margin compression": "انكماش هامش الربح الإجمالي",
        "Incremental operating margin": "الهامش التشغيلي الإضافي",
        "Loss-making revenue exposure": "التعرض لإيرادات الخسارة",
        "Top 5 customer concentration": "تركيز أكبر 5 عملاء",
        "Operating leverage": "الرافعة التشغيلية",
        "Operating leverage cannot be calculated &mdash; one or both metrics have no prior-year base.": "لا يمكن حساب الرافعة التشغيلية — أحد المؤشرين أو كليهما ليس له أساس سنة سابقة.",
        "Revenue and profit growing in similar proportion &mdash; neutral operating leverage.": "الإيرادات والأرباح تنمو بنسبة متقاربة — رافعة تشغيلية محايدة.",
        "Operating profit is growing faster than revenue &mdash; cost structure is scaling efficiently.": "الربح التشغيلي ينمو أسرع من الإيرادات — هيكل التكاليف يتوسع بكفاءة.",
        "Revenue is growing faster than profit &mdash; costs are not scaling well. Review opex discipline.": "الإيرادات تنمو أسرع من الأرباح — التكاليف لا تتوسع بشكل جيد. راجع انضباط المصروفات التشغيلية.",

        "completed": "مكتمل",
        "vs": "مقابل",
        "Margin": "الهامش",
        "Signal": "الإشارة",
        "pp change over period": "نقطة مئوية تغير خلال الفترة",
        "CAGR over": "معدل النمو السنوي المركب على مدى",
        "years": "سنوات",
        "--": "--",
        "MB SQLite": "ميغابايت SQLite",

        "Reporting view": "عرض التقرير",
        "Product group": "مجموعة المنتج",
        "Revenue share": "حصة الإيرادات",
        "Growth %": "نسبة النمو",
        "Op margin %": "نسبة الهامش التشغيلي",
        "Recommended action": "الإجراء المقترح",
        "Account": "البند",
        "ACCOUNT": "البند",
        "Status": "الحالة",
        "STATUS": "الحالة",
        "MANAGEMENT ACTION": "إجراء الإدارة",
        "Management action": "إجراء الإدارة",
        "Amount": "القيمة",
        "% Revenue": "نسبة الإيرادات",
        "CHANGE VS FY2025": "التغير مقابل السنة المالية 2025",
        "ACTUAL 2026 P01-P05": "فعلي 2026 P01-P05",
        "2026 OUTLOOK P01-P12": "توقعات 2026 P01-P12",
        "2025 FULL YEAR": "كامل سنة 2025",
        "VARIANCE VS 2025": "الانحراف مقابل 2025",
        "AMOUNT": "القيمة",
        "% REVENUE": "نسبة الإيرادات",
        "Operating Expenses": "المصروفات التشغيلية",
        "Strong growth": "نمو قوي",
        "Growing but margin eroding": "نمو مع تآكل الهامش",
        "Declining — margin also falling": "انخفاض مع تراجع الهامش أيضًا",
        "Revenue declining": "انخفاض الإيرادات",
        "High-margin product with stable or improving economics. Prioritise volume growth and defend price positioning.": "منتج عالي الهامش باقتصاديات مستقرة أو متحسنة. أعطِ أولوية لنمو الحجم ودافع عن تموضع السعر.",
        "Margins healthy and stable. Defend pricing discipline and look for selective volume growth opportunities.": "الهوامش صحية ومستقرة. حافظ على انضباط التسعير وابحث عن فرص نمو انتقائية في الحجم.",
        "Operating loss despite positive gross margin. OpEx exceeds the margin contribution — review fixed cost allocation.": "خسارة تشغيلية رغم هامش ربح إجمالي موجب. المصروفات التشغيلية تتجاوز مساهمة الهامش — راجع توزيع التكلفة الثابتة.",
        "Negative gross margin — losing money on every unit sold. Reprice, renegotiate COGS, or exit this volume.": "هامش ربح إجمالي سلبي — خسارة على كل وحدة مباعة. أعد التسعير أو تفاوض على تكلفة المبيعات أو اخرج من هذا الحجم.",
        "Gross margin below 10% — insufficient buffer to absorb operating expense. Target repricing or direct cost reduction.": "هامش الربح الإجمالي أقل من 10% — لا توجد مساحة كافية لامتصاص المصروفات التشغيلية. استهدف إعادة التسعير أو خفض التكلفة المباشرة.",
        "Combined outlook": "التوقع المجمّع",
        "Actual share": "حصة الفعلي",
        "Change vs FY": "التغير مقابل السنة المالية",
        "GM pp shift": "تغير هامش الربح (نقطة مئوية)",
        "GM Δ": "Δ هامش الربح",
        "Growth": "النمو",
        "Signal": "الإشارة",
        "Change %": "نسبة التغير",
        "Metric": "المؤشر",
        "Combined outlook": "التوقع المجمّع",
        "Actual share": "حصة الفعلي",
        // Case variants for dynamic header construction
        "Actual P01-P05": "الفعلي P01-P05",
        "T06 P06": "T06 P06",
        "T07 P07-P12": "T07 P07-P12",
        "Actual 2026 P01-P05": "فعلي 2026 P01-P05",
        "2026 Outlook P01-P12": "توقعات 2026 P01-P12",
        // Signal copy translations
        "Gross margin improvement": "تحسن هامش الربح الإجمالي",
        "Gross margin compression": "انضغاط هامش الربح الإجمالي",
        "Incremental operating margin": "الهامش التشغيلي الإضافي",
        "Loss-making revenue exposure": "التعرض لإيرادات الخسارة",
        "Top 5 customer concentration": "تركيز أكبر 5 عملاء",
        "Operating leverage": "الرافعة التشغيلية",
        // Standalone signal labels + user-facing error messages (Stage 6.5b)
        "Strong growth": "نمو قوي",
        "Growing but margin eroding": "نمو لكن الهامش يتآكل",
        "Database query timed out": "انتهت مهلة استعلام قاعدة البيانات",
        "Chart.js did not load": "تعذّر تحميل Chart.js",
    };

    function getLang() {
        var v = localStorage.getItem("dashboardLang");
        return v === "en" || v === "ar" ? v : "ar";   // default Arabic
    }

    function getDigits() {
        var v = localStorage.getItem("dashboardDigits");
        return v === "arabic" || v === "western" ? v : "western";  // default Western
    }

    function t(key) {
        var lang = getLang();
        return (DICT[lang] && DICT[lang][key] !== undefined) ? DICT[lang][key] : undefined;
    }

    function localizeDigits(text) {
        if (getDigits() !== "arabic" || text == null) return text;
        return String(text).replace(/[0-9]/g, function (d) {
            return ARABIC_INDIC.charAt(WESTERN.indexOf(d));
        });
    }

    function translateText(text) {
        if (getLang() !== "ar" || text == null) return text;
        var raw = String(text);
        var leading = raw.match(/^\s*/)[0];
        var trailing = raw.match(/\s*$/)[0];
        var core = raw.trim();
        if (!core) return raw;
        if (AR_TEXT[core] !== undefined) return leading + AR_TEXT[core] + trailing;

        var dynamic = core
            .replace(/^FY(\d{4})$/, "السنة المالية $1")
            .replace(/^(\d{4}) executive outlook$/, "التوقع التنفيذي $1")
            .replace(/^(\d{4}) executive performance$/, "الأداء التنفيذي $1")
            .replace(/^FY(\d{4}) Actual$/, "فعلي السنة المالية $1")
            .replace(/^FY(\d{4}) Full Year$/, "كامل السنة المالية $1")
            .replace(/^(\d{4}) Full Year$/, "كامل سنة $1")
            .replace(/^Variance vs (\d{4})$/, "الانحراف مقابل $1")
            .replace(/^FY(\d{4}) full-year Actual, compared with FY(\d{4})$/, "فعلي كامل السنة المالية $1، مقارنة بالسنة المالية $2")
            .replace(/^Top product groups by (\d{4}) revenue — margin quality, COGS efficiency, and YoY movement with management action tiers$/, "أهم مجموعات المنتجات حسب إيرادات $1 — جودة الهامش، وكفاءة تكلفة المبيعات، والحركة السنوية مع مستويات إجراءات الإدارة")
            .replace(/^FY(\d{4}) REVENUE$/, "إيرادات السنة المالية $1")
            .replace(/^CHANGE VS FY(\d{4})$/, "التغير مقابل السنة المالية $1")
            .replace(/^ACTUAL (\d{4}) P(\d{2})-P(\d{2})$/, "فعلي $1 P$2-P$3")
            .replace(/^(\d{4}) OUTLOOK P(\d{2})-P(\d{2})$/, "توقعات $1 P$2-P$3")
            .replace(/^(\d{4}) FULL YEAR$/, "كامل سنة $1")
            .replace(/^VARIANCE VS (\d{4})$/, "الانحراف مقابل $1")
            .replace(/^Source: live SQLite \(([0-9,]+) records\)\s*\|\s*Actual: P(\d{2})-P(\d{2})\s*\|\s*(\d{4}) outlook: Actual P(\d{2})-P(\d{2}) \+ T06 P06 \+ T07 P07-P12\.$/, "المصدر: SQLite مباشر ($1 سجل) | الفعلي: P$2-P$3 | توقعات $4: فعلي P$5-P$6 + T06 P06 + T07 P07-P12.")
            .replace(/^Actual P(\d{2})-P(\d{2}) \+ T06 P06 \+ T07 P07-P12, compared with FY(\d{4})$/, "فعلي P$1-P$2 + T06 P06 + T07 P07-P12، مقارنة بالسنة المالية $3")
            .replace(/^(\d+(?:\.\d+)?)% of outlook$/, "$1% من التوقع")
            .replace(/^(\d+) product groups forecast below operating break-even$/, "$1 مجموعات منتجات متوقعة دون نقطة التعادل التشغيلي")
            .replace(/^Top (\d+) groups by (\d{4}) outlook revenue · (\d+) loss-making \((.*) revenue at risk\)$/, "أكبر $1 مجموعات حسب إيرادات توقعات $2 · $3 خاسرة ($4 إيرادات معرضة للخطر)")
            .replace(/^FY(\d{4}) outlook$/, "توقعات السنة المالية $1")
            .replace(/^P&L summary: (\d{4}) outlook$/, "ملخص الأرباح والخسائر: توقعات $1")
            .replace(/^Profit bridge vs FY(\d{4})$/, "جسر الربح مقارنة بالسنة المالية $1")
            .replace(/^Share of (\d{4}) outlook held by the largest customers$/, "حصة أكبر العملاء من توقعات $1")
            .replace(/^Share of FY(\d{4}) outlook held by the largest customers$/, "حصة أكبر العملاء من توقعات السنة المالية $1")
            .replace(/^Variance vs FY(\d{4})$/, "الانحراف مقابل السنة المالية $1")
            .replace(/^Revenue: \$(.*)M$/, "الإيرادات: $1 مليون دولار")
            .replace(/^GM%: (.*)%$/, "نسبة الهامش الإجمالي: $1%")
            .replace(/^gross margin %$/, "نسبة هامش الربح الإجمالي")
            .replace(/^YoY growth %$/, "نسبة النمو السنوي")
            .replace(/^change in \$ millions$/, "التغير بملايين الدولارات")
            .replace(/^Revenue growth % vs prior year$/, "نمو الإيرادات % مقابل السنة السابقة")
            .replace(/^Gross margin %$/, "نسبة هامش الربح الإجمالي")
            .replace(/^FY(\d{4}) revenue$/, "إيرادات السنة المالية $1")
            // Signal copy translations
            .replace(/^FY(\d{4}) outlook margin versus FY(\d{4})\. Protect the mix and cost gains behind the improvement\.$/, "هامش توقعات السنة المالية $1 مقابل السنة المالية $2. حافظ على مزيج المنتجات ومكاسب التكلفة وراء التحسن.")
            .replace(/^FY(\d{4}) outlook margin versus FY(\d{4})\. Prioritize pricing, mix, and direct-cost recovery\.$/, "هامش توقعات السنة المالية $1 مقابل السنة المالية $2. أعطِ أولوية للتسعير والمزيج واسترداد التكلفة المباشرة.")
            .replace(/^Operating profit change divided by revenue change versus FY(\d{4})\. Negative conversion signals value-destructive growth\.$/, "تغير الربح التشغيلي مقسومًا على تغير الإيرادات مقابل السنة المالية $1. التحويل السلبي يشير إلى نمو مدمر للقيمة.")
            .replace(/^Share of FY(\d{4}) outlook revenue generated by product groups below operating break-even\.$/, "حصة إيرادات توقعات السنة المالية $1 الناتجة عن مجموعات منتجات دون نقطة التعادل التشغيلي.")
            .replace(/^Revenue dependency on the five largest customers in the FY(\d{4}) outlook\.$/, "اعتماد الإيرادات على أكبر خمسة عملاء في توقعات السنة المالية $1.")
            .replace(/^Revenue and profit growing in similar proportion — neutral operating leverage\.$/, "الإيرادات والأرباح تنمو بنسبة متقاربة — رافعة تشغيلية محايدة.")
            .replace(/^Operating profit is growing faster than revenue — cost structure is scaling efficiently\.$/, "الربح التشغيلي ينمو أسرع من الإيرادات — هيكل التكلفة يتوسع بكفاءة.")
            .replace(/^Revenue is growing faster than profit — costs are not scaling well\. Review opex discipline\.$/, "الإيرادات تنمو أسرع من الربح — التكاليف لا تتوسع جيدًا. راجع انضباط المصروفات التشغيلية.")
            .replace(/^Operating leverage cannot be calculated — one or both metrics have no prior-year base\.$/, "لا يمكن حساب الرافعة التشغيلية — أحد المؤشرين أو كلاهما ليس له أساس سنة سابقة.")
            // Table headers
            .replace(/^Change vs FY(\d{4})$/, "التغير مقابل السنة المالية $1")
            .replace(/^Actual (\d{4}) P01-P05$/, "فعلي $1 P01-P05")
            .replace(/^(\d{4}) Outlook P01-P12$/, "توقعات $1 P01-P12")
            // Signal action sentences (Stage 6.5b)
            .replace(/^Gross margin fell (\d+(?:\.\d+)?) pp YoY\. Review discount policy, channel mix, and COGS drivers urgently\.$/,
                "انخفض هامش الربح الإجمالي $1 نقطة مئوية سنويًا. راجع سياسة الخصم ومزيج القنوات ومحركات تكلفة المبيعات بشكل عاجل.")
            .replace(/^Margin slipping (\d+(?:\.\d+)?) pp — monitor channel mix and discount exposure before it accelerates\.$/,
                "الهامش ينزلق $1 نقطة مئوية — راقب مزيج القنوات والتعرض للخصومات قبل أن يتسارع.")
            // Profitability footer — segments (also reachable via the " · " split below)
            .replace(/^Top (\d+) groups by (\d{4}) outlook revenue$/, "أكبر $1 مجموعات حسب إيرادات توقعات $2")
            .replace(/^(\d+) loss-making \((.+) revenue at risk\)$/, "$1 خاسرة ($2 إيرادات معرضة للخطر)")
            .replace(/^(\d+) margin eroding$/, "$1 بهامش متآكل")
            .replace(/^(\d+) below safe threshold$/, "$1 دون الحد الآمن")
            .replace(/^All (\d+) product groups profitable and stable$/, "جميع مجموعات المنتجات الـ$1 رابحة ومستقرة");

        // Compositional fallback: many footers/notes are segments joined by
        // " · ". If the whole string didn't match, translate each segment.
        if (dynamic === core && core.indexOf(" · ") !== -1) {
            var segments = core.split(" · ").map(function (seg) { return translateText(seg); });
            dynamic = segments.join(" · ");
        }
        return leading + dynamic + trailing;
    }

    function translateNodeTree(rootNode) {
        if (getLang() !== "ar" || !rootNode) return;
        if (rootNode.nodeType === Node.TEXT_NODE) {
            rootNode.nodeValue = translateText(rootNode.nodeValue);
            if (getDigits() === "arabic") rootNode.nodeValue = localizeDigits(rootNode.nodeValue);
            return;
        }
        if (rootNode.nodeType !== Node.ELEMENT_NODE && rootNode !== document) return;
        var walker = document.createTreeWalker(rootNode, NodeFilter.SHOW_TEXT, {
            acceptNode: function (node) {
                var parent = node.parentElement;
                if (!parent) return NodeFilter.FILTER_REJECT;
                var tag = parent.tagName;
                if (tag === "SCRIPT" || tag === "STYLE" || tag === "TEXTAREA") {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        var nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        for (var i = 0; i < nodes.length; i++) {
            nodes[i].nodeValue = translateText(nodes[i].nodeValue);
            if (getDigits() === "arabic") nodes[i].nodeValue = localizeDigits(nodes[i].nodeValue);
        }
    }

    function apply() {
        var lang = getLang();
        var doc = document.documentElement;
        doc.setAttribute("lang", lang);
        doc.setAttribute("dir", lang === "ar" ? "rtl" : "ltr");

        var title = t("doc.title");
        if (title) document.title = title;

        var nodes = document.querySelectorAll("[data-i18n]");
        for (var i = 0; i < nodes.length; i++) {
            var value = t(nodes[i].getAttribute("data-i18n"));
            if (value !== undefined) nodes[i].textContent = value;
        }
        translateNodeTree(document.body);
    }

    function observeDynamicText() {
        if (getLang() !== "ar" || !window.MutationObserver || !document.body) return;
        var observer = new MutationObserver(function (mutations) {
            observer.disconnect();
            for (var i = 0; i < mutations.length; i++) {
                if (mutations[i].type === "characterData") {
                    translateNodeTree(mutations[i].target);
                } else {
                    for (var j = 0; j < mutations[i].addedNodes.length; j++) {
                        translateNodeTree(mutations[i].addedNodes[j]);
                    }
                    if (mutations[i].target && mutations[i].target.nodeType === Node.ELEMENT_NODE) {
                        translateNodeTree(mutations[i].target);
                    }
                }
            }
            observer.observe(document.body, { childList: true, characterData: true, subtree: true });
        });
        observer.observe(document.body, { childList: true, characterData: true, subtree: true });
    }

    function setLang(lang) {
        localStorage.setItem("dashboardLang", lang);
        location.reload();
    }

    function setDigits(mode) {
        localStorage.setItem("dashboardDigits", mode);
        location.reload();
    }

    // Apply direction/language/font as early as possible to avoid a flash.
    var root = document.documentElement;
    root.setAttribute("lang", getLang());
    root.setAttribute("dir", getLang() === "ar" ? "rtl" : "ltr");

    document.addEventListener("DOMContentLoaded", function () {
        apply();
        observeDynamicText();
        var langBtn = document.getElementById("langToggle");
        if (langBtn) {
            langBtn.textContent = t("ui.lang_toggle");
            langBtn.addEventListener("click", function () {
                setLang(getLang() === "ar" ? "en" : "ar");
            });
        }
        var digitBtn = document.getElementById("digitToggle");
        if (digitBtn) {
            digitBtn.textContent = t("ui.digits_toggle");
            digitBtn.addEventListener("click", function () {
                setDigits(getDigits() === "arabic" ? "western" : "arabic");
            });
        }
    });

    window.I18N = {
        t: t,
        lang: getLang,
        digits: getDigits,
        localizeDigits: localizeDigits,
        translateText: translateText,
        translateNodeTree: translateNodeTree,
        setLang: setLang,
        setDigits: setDigits,
        apply: apply
    };
})();
