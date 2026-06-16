# Task Board — who is doing what, right now

> **نظام المهام الحي لجميع الوكلاء**
> قبل ما تبدأ أي مهمة: انقلها لـ In Progress وسجّل اسمك.
> لما تخلص: انقلها لـ Done واكتب commit hash أو PR رقم.

---

## 🟢 Ready (جاهز للبدء)

| # | المهمة | الوصف | الوكيل المقترح |
|---|--------|-------|----------------|
| R1 | Client-specific report templates | قوالب تقارير مخصصة لكل عميل | claude |
| R2 | Multi-scenario comparison | مقارنة عدة سيناريوهات مع بعض (`reports/scenario.py`) | claude |
| R3 | Scenarios in live dashboard | عرض السيناريوهات مباشرة في لوحة التحكم | claude/hermes |
| R4 | Volume/price decomposition | تحليل حجم/سعر في السيناريوهات | claude |
| R5 | Full-text search for knowledge base | بحث نصي كامل في brain/knowledge | hermes |
| R6 | HTML/graph viewer for brain | عارض رسومي للجراف في المتصفح | claude/hermes |
| R7 | Note→report deep links | روابط من ملاحظات المعرفة إلى تقارير محددة | claude |
| R8 | OCR for scanned PDFs | مسار OCR للمستندات الممسوحة ضوئيًا | claude |
| R9 | Live Outlook COM extraction | استخراج مباشر من Outlook على Windows | codex/claude |
| R10 | Merged-cell & multi-row headers | دعم الخلايا المدمجة والرؤوس متعددة الصفوف | claude |
| R11 | English RTL dashboard QA | اختبار الواجهة الإنجليزية على سطح المكتب والموبايل | hermes |
| R12 | Client-specific wording polish | تدقيق الصياغة عند توفر ملفات عميل حقيقية | — |

---

## 🟡 In Progress (شغّال عليه)

| # | المهمة | الوكيل | الفرع | منذ |
|---|--------|--------|-------|-----|
| I1 | Full-text search for knowledge base | hermes | `hermes/priorities-execution` | 2026-06-16 |
| I2 | Excel/PDF download from web UI | hermes | `hermes/priorities-execution` | 2026-06-16 |

---

## 🟢 Done (تم وإترفع)

| # | المهمة | الوكيل | commit/PR | التاريخ |
|---|--------|--------|-----------|---------|
| D0 | Sample data + unified reports + MCP tools | hermes | pending | 2026-06-16 |
| D1 | Mapping review tool | hermes | `74ce462` → main | 2026-06-15 |
| D2 | CI gate + agent plan + DoD | claude | PR #15 | 2026-06-16 |
| D3 | Arabic PDF: vendored font | claude | PR #14 | 2026-06-16 |
| D4 | Arabic deep-content translation | claude | PR #13 | 2026-06-16 |
| D5 | Documentation alignment | claude | PR #12 | 2026-06-16 |
| D6 | MCP server (harness layer) | claude | PR #11 | 2026-06-15 |
| D7 | Project structure + governance | claude | PR #10 | 2026-06-15 |
| D8 | DB schema unification | claude | PR #9 | 2026-06-15 |
| D9 | Excel COM extraction hardening | claude | PR #8 | 2026-06-15 |
| D10 | Phase 2 import workspace | claude | PR #7 | 2026-06-15 |
| D11 | Arabic RTL dashboard | claude | PR #6 | 2026-06-15 |
| D12 | Arabic export correctness | claude | PR #5 | 2026-06-15 |
| D13 | .xlsb/.xls/CSV readers | claude | PR #4 | 2026-06-15 |
| D14 | Arabic-aware mapper | claude | PR #3 | 2026-06-15 |
| D15 | Arabic normalization core | claude | PR #2 | 2026-06-15 |
| D16 | Docs + hardening fixes | claude | PR #1 | 2026-06-14 |

---

## 📋 قواعد اللوحة

1. **وكيل واحد لكل مهمة.** الـ In Progress لازم يبقى فيه اسم الوكيل والفرع.
2. **سجّل commit/PR في Done.** متعتبرش المهمة مخلّصة من غير الرابط.
3. **لو عايز تبدأ مهمة من Ready:** انقلها لـ In Progress، اكتب اسمك واسم الفرع، وابدأ.
4. **متلمسش ملف شغّال عليه وكيل تاني.** اسأل الأول.
5. **اللوحة دي بتترفع مع الكود.** أي وكيل يعدّلها قبل الـ push.

---

*آخر تحديث: 2026-06-16 — hermes*
