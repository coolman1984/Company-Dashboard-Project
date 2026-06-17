# Task Board — who is doing what, right now

> **نظام المهام الحي لجميع الوكلاء**
> قبل ما تبدأ أي مهمة: انقلها لـ In Progress وسجّل اسمك.
> لما تخلص: انقلها لـ Done واكتب commit hash أو PR رقم.

---

## 🟢 Ready (جاهز للبدء)

| # | المهمة | الوصف | الوكيل المقترح |
|---|--------|-------|----------------|
| R4 | Volume/price decomposition | تحليل حجم/سعر مدمج في الداشبورد | claude |
| R7 | Note→report deep links | روابط من ملاحظات المعرفة إلى تقارير محددة | claude |
| R9 | Live Outlook COM extraction | استخراج مباشر من Outlook على Windows | codex/claude |
| R12 | Client-specific wording polish | تدقيق الصياغة عند توفر ملفات عميل حقيقية | — |

---

## 🟡 In Progress (شغّال عليه)

| # | المهمة | الوكيل | منذ |
|---|--------|--------|-----|
| — | — | — | — |

---

## 🟢 Done (تم وإترفع)

| # | المهمة | الوكيل | commit/PR | التاريخ |
|---|--------|--------|-----------|---------|
| R1 | Client-specific report templates | hermes | `80a8ba6` → main | 2026-06-17 |
| R8 | OCR for scanned PDFs | claude | `10514af` → main | 2026-06-17 |
| R6 | HTML/graph viewer for brain | claude | `e33a3f2` → main | 2026-06-17 |
| R3 | Scenarios in live dashboard | claude | `d80d167` → main | 2026-06-17 |
| R2 | Multi-scenario comparison | claude | `5e065ba` → main | 2026-06-17 |
| R5 | Full-text search for knowledge base | hermes | `5b47c76` → main | 2026-06-16 |
| D17 | Full-text search for knowledge base | hermes | `5b47c76` → main | 2026-06-16 |
| D18 | Excel/PDF download from web UI | hermes | `5b47c76` → main | 2026-06-16 |
| D19 | Source lineage tables + mapper integration | hermes | `5b47c76` → main | 2026-06-16 |
| D20 | MCP harness tools | hermes | `5b47c76` → main | 2026-06-16 |
| D0 | Sample data + unified reports + MCP tools | hermes | `27e1bcf` → main | 2026-06-16 |
| D1 | Mapping review tool | hermes | `74ce462` → main | 2026-06-15 |
| R11 | English RTL dashboard QA | claude | PR #15 | 2026-06-16 |
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

*آخر تحديث: 2026-06-17 — hermes (لوحة محدثة + R1 قيد التطوير)*
