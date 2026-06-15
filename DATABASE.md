# Database layer — analysis & hardening (تحليل طبقة قواعد البيانات)

> What technology we use, why, how the pieces fit, and the edge-case hardening
> applied. Arabic summary at the end. / ملخص عربي في الآخر.

## 1. Technology & why

| Choice | What | Why it fits |
|--------|------|-------------|
| **SQLite** | one file `pl_detail.db` | Embedded, zero-admin, fully offline, trivial to ship/back up/swap atomically. Excellent for a **read-heavy analytical** workload (≈790K rows, one wide fact table). No server to secure or keep running. |
| **better-sqlite3** | server query engine (`server.js`) | Synchronous, fast, parameterised queries; opened **read-only** (`readonly + fileMustExist`, `query_only=ON`) so the API can never mutate the ledger. |
| **schema.sql** | canonical DDL | Single source of truth: the `pl_detail` table, 13 analytical indexes, 6 roll-up views. |

The data model in one line: a single denormalised **fact table** `pl_detail`
(one row per class × region × country × customer × product × period × version),
plus pre-defined **views** that roll it up for the dashboard.

### Key conventions (don't break these)
- **Period encoding:** `period` REAL = `year + period_number/1000`
  (2026.001 = FY2026 P01). Decoded with `CAST(ROUND((period - CAST(period AS INTEGER))*1000))`.
- **Version coverage:** `Actual` = realised periods, `T06` = the P06 bridge,
  `T07` = the P07–P12 outlook.
- Views aggregate **`WHERE version = 'Actual'`** only.

## 2. The three writers (and the consumer)

```
schema.sql  ──the one DDL──▶  db_schema.py  (apply_table / apply_indexes_and_views / apply_schema)
                                   │
        ┌──────────────────────────┼───────────────────────────┐
   seed_db.py                map_raw_to_db.py             ingest_sheet1.py
   (synthetic dev data)      (raw JSON → ledger)          (Windows COM, real .xlsb, 790K rows)
        └──────────────────────────┴───────────────────────────┘
                                   ▼
                             pl_detail.db
                                   ▼
                  server.js (read-only)  ──API──▶  dashboard / reports
```

**Before this round, `ingest_sheet1.py` hand-rolled its own `CREATE TABLE` and
its own views** — and the views had drifted (`net_sales_pct_change` plus an
extra `gross_margin_pct_change`, vs the schema's `net_sales_pct`). A database
built by the production COM path could therefore feed the dashboard view
columns it did not expect. **Now all three paths apply `schema.sql` through
`db_schema.py`**, so the structure is identical regardless of how the DB was
built. `test_db_schema.py` enforces this in CI and fails on any future drift.

## 3. Resilience already in place
- **Server:** read-only + `fileMustExist`; **fallback "limited mode"** serving
  cached JSON when SQLite is unavailable; strict input validation (allow-listed
  years/versions/dimensions/metrics); `parseInteger` guards with `isFinite`.
- **Mapper:** schema-driven columns/types; Arabic-aware value parsing; **post-load
  validation** with *fatal* checks (no rows, duplicate grain, NULLs in
  `year/version/period/net_sales`) that abort the atomic swap, plus *warning*
  checks (P&L identity drift). Builds into a temp file and `os.replace`s — the
  live DB is never half-written.

## 4. Edge-case hardening added this round
- **Schema drift eliminated** — single application path via `db_schema.py`;
  `ingest_sheet1.py` no longer defines its own table/views.
- **NaN / Infinity rejected at the door** — a corrupt cell or bad formula that
  parses to a non-finite number would poison every `SUM` and serialise as
  `null`. The mapper (`convert`) now raises a clear error, the COM cleaner
  (`com_utils.clean_com_value`) drops it to `null` + flags it, and the server
  serialises any stray non-finite number as `null` defensively.
- **Empty-database safety** — every view is verified to resolve (zero rows, no
  error) on an empty DB.
- **Compatibility guard test** (`test_db_schema.py`, 10 tests, runs on Linux/CI)
  proves the seed, mapper and COM-ingest column lists all match `schema.sql`,
  the views/indexes are present with stable output columns, and the COM ingest
  builds a structure identical to `schema.sql`.

## 5. Possible future work
- Move `seed_db.COLUMNS` / `ingest_sheet1.COLUMNS` to derive from
  `db_schema.column_names()` (the test already guarantees they match).
- WAL mode if a future concurrent-writer scenario appears (today's
  build-temp-then-`os.replace` swap already gives readers a consistent file).
- A typed `import_manifest` per client if multiple fact tables are added.

---

## ملخص بالعربي
- **التقنية:** SQLite (ملف واحد) + `better-sqlite3` للقراءة فقط في الخادم — اختيار
  مثالي لحِمل تحليلي قراءة-كثيف (٧٩٠ ألف صف)، يشتغل offline وسهل النسخ والتبديل.
- **`schema.sql` هو المصدر الوحيد للحقيقة**، ودلوقتي **كل المسارات** (البيانات
  التجريبية، الـ mapper، واستخراج COM) بتطبّقه عبر `db_schema.py` — فالجدول والـ
  views والفهارس واحدة بالظبط مهما كان المسار اللي بنى القاعدة.
- **اتصلح اختلاف الـ schema** اللي كان في `ingest_sheet1.py` (الـ views كانت
  مختلفة فعلًا).
- **تقوية edge cases:** رفض NaN/Infinity في الـ mapper والـ COM والخادم؛ التأكد إن
  الـ views بتشتغل على قاعدة فاضية؛ و**اختبار حارس** (`test_db_schema.py`) بيمنع أي
  اختلاف مستقبلي ويشتغل في الـ CI على Linux.
- **المتانة الموجودة أصلًا:** الخادم read-only + وضع احتياطي محدود، والـ mapper
  بيتحقق بعد التحميل ويعمل swap ذرّي فالقاعدة الحيّة عمرها ما تتكتب نص-نص.
