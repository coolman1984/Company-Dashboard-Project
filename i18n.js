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
            "ui.lang_toggle": "English",
            "ui.digits_toggle": "١٢٣"
        },
        en: {
            "doc.title": "Company Finance Command Center",
            "brand.name": "Finance OS",
            "brand.tag": "Company command center",
            "nav.analytics": "Analytics",
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
            "page.portfolio.title": "Strategic Portfolio Matrix",
            "page.portfolio.sub": "Product group growth vs margin positioning for capital allocation decisions",
            "ui.lang_toggle": "العربية",
            "ui.digits_toggle": "123"
        }
    };

    var WESTERN = "0123456789";
    var ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩";

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
        setLang: setLang,
        setDigits: setDigits,
        apply: apply
    };
})();
