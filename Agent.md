# Agent.md — Best Practices & Problem-Solving Patterns

> ⚠️ **Multi-agent project.** The mandatory coordination protocol (rules, task
> board, shared work journal) is in [`AGENTS.md`](AGENTS.md) — read it first.
> This file is technical lessons only, not the rules.

> This file captures lessons learned, best practices, and problem-solving patterns from building the Company Dashboard project. Read this at the start of any task to avoid repeating mistakes and to apply proven patterns.

## Current v4 Direction

The production dashboard is now SQLite-first. Use parameterized `better-sqlite3` queries for interactive filters and keep `api_data/` only as a database-unavailable fallback. The pre-computation guidance below remains useful for very expensive or immutable workloads, but it is no longer the primary dashboard architecture.

The executive overview is a reconciled CFO decision cockpit. Cards, monthly charts, P&L tables, concentration metrics, and product actions must use `/api/executive-outlook` so definitions tie. Never infer EBITDA, operating cash flow, free cash flow, working capital, or balance-sheet ratios from the P&L-only ledger.

---

## 1. Pre-Computation Pattern (The Biggest Lesson)

### Problem
When a dashboard allows users to select any combination of filters (dimension × metric × year range), querying the database on every request is too slow. Python subprocess for each API call added 1-5 seconds of latency.

### Solution: Pre-Compute Everything
1. Create a `precompute_data.py` script that runs ALL possible queries and saves results as JSON files
2. Server loads all JSON into memory at startup (`fs.readFileSync` + `JSON.parse`)
3. API endpoints serve from memory — instant responses (2-35ms)

### Critical Rule: Cover ALL Combinations
- **Mistake**: Initially only pre-computed 4 consecutive year pairs (2022→2023, 2023→2024, etc.)
- **Bug**: Dashboard allows ANY year1/year2 combination (e.g., 2022→2026). Non-consecutive pairs returned 404.
- **Fix**: Generate ALL combinations: `[(y1,y2) for y1 in years for y2 in years if y1 < y2]`
- **Safety Net**: Always add a server-side fallback that computes from cached view data if the pre-computed file is missing.

### Pattern
```
Pre-compute → JSON files → Load into memory at startup → Serve instantly
Always add fallback computation for missing combinations
```

---

## 2. Excel COM Automation (win32com)

### Key Rules
- **0-indexed tuples**: `data[r][c]` NOT `data[r+1][c+1]`. This caused `IndexError` multiple times.
- **Sheet ordering**: Sheet3 is `workbook.Sheets(1)`, Sheet1 is `workbook.Sheets(2)`. Don't assume sheet index matches sheet name.
- **Chunked reading**: For large ranges (790K rows), read 10,000 rows at a time. Bulk `Range.Value` calls are fast but memory-hungry.
- **Always cleanup**: `excel.Quit()` in a `finally` block. If script crashes, Excel stays running — use `taskkill /F /IM EXCEL.EXE`.
- **UnicodeEncodeError**: Windows console can't print Unicode chars (✓, ⊘). Use ASCII alternatives (OK, SKIP).
- **DisplayAlerts = False**: Prevents Excel dialogs from blocking the script.

### COM Pattern
```python
excel = win32com.client.DispatchEx("Excel.Application")
excel.Visible = False
excel.DisplayAlerts = False
try:
    workbook = excel.Workbooks.Open(file_path, ReadOnly=True)
    # ... work with data ...
finally:
    workbook.Close(False)
    excel.Quit()
```

### Use `extractor/com_utils.py` — don't hand-roll COM again
All the dangerous choreography now lives in one tested module. Prefer it over
re-writing the pattern:
- **`excel_session()`** — context manager that configures a dialog-free Excel
  (`Visible/DisplayAlerts/EnableEvents/AskToUpdateLinks/Interactive` off) and
  *guarantees* `Quit()` + ref release + `CoUninitialize()` on exit. Also sets
  **`AutomationSecurity = 3` (force-disable macros)** — client files are
  untrusted; never let a workbook macro run on open.
- **`open_workbook(excel, path)`** — never hangs: passes a **guard `Password`**
  so a protected file raises instead of popping a modal password dialog,
  `UpdateLinks=0` / `IgnoreReadOnlyRecommended=True` / `Notify=False` to kill
  link/read-only prompts, and **retries a corrupt file once with
  `CorruptLoad=xlExtractData`** before giving a clean error.
- **`find_sheet(workbook, name, index)`** — match by name (case/space-tolerant)
  with an index fallback. Replaces the brittle hard-coded `Sheets(2)`.
- **`clean_com_value` / `is_cv_error`** — turn CVErr formula errors (#REF!,
  #DIV/0! → large negative ints from pywin32) into `null` + a warning;
  `chunk_bounds` / `normalize_block` carry the chunk math and grid shaping.

### More gotchas learned
- **Password dialog = silent hang.** An unattended run blocks forever on a
  modal password prompt. The guard-password trick in `open_workbook` converts
  it to a catchable error.
- **Macros on open are a security risk** with untrusted client files — disable
  via `AutomationSecurity`.
- **Don't index a partial load.** `ingest_sheet1.py` only builds indexes/views
  after a *complete* load; a failed/aborted run leaves an unindexed DB to be
  rebuilt (and previously crashed with `UnboundLocalError` referencing
  `total_inserted` — now initialised before the COM block).
- **COM logic is testable without Windows.** `extractor/test_excel_com.py`
  fakes the `UsedRange/Cells/Range.Value` object model, so value-cleaning,
  chunking, sheet selection and the no-hang open all run in CI on Linux.

---

## 3. Database Best Practices

### SQLite for Analytics
- Create indexes AFTER bulk loading (much faster than incremental indexing)
- Use `executemany()` for bulk inserts (10K rows at a time)
- Create views for common query patterns (v_yearly_pl, v_regional_pl, etc.)
- 12 indexes + 6 views = fast analytical queries on 790K rows

### When Native Drivers Aren't Available
- `better-sqlite3` requires native compilation — may not be available
- DuckDB requires `pip install` — network may be down
- **Fallback**: Python `sqlite3` is built-in and always available
- **Better fallback**: Pre-compute everything as JSON, serve statically

---

## 4. Dashboard Architecture

### Separate HTML and JavaScript
- Keep `index.html` for structure, `app.js` for logic
- Large inline `<script>` blocks get truncated during file writes
- Easier to maintain and debug

### Client-Side Caching
- Fetch data once, cache in JavaScript variables
- Re-render charts/tables from cache when only the metric/year changes
- Example: `regionalDataCache` and `mgroupDataCache`

### Lazy Tab Loading
- Only fetch data when a tab is first visited
- Track with `tabLoaded = { overview: true, regional: false, ... }`

### Error Handling
- `safeFetch()` with AbortController timeout (10s)
- Toast notifications for success/error feedback
- Button loading states (disable + "Loading..." text)
- Input validation before API calls (year1 ≠ year2)

---

## 5. Performance Optimization Checklist

When a dashboard or API is slow:

1. **Identify the bottleneck**: Is it the query, the transport, or the rendering?
2. **Pre-compute**: Can the data be computed once and cached as JSON?
3. **Client-side cache**: Can data be fetched once and re-used for different views?
4. **Lazy load**: Can data be fetched only when needed (tab visit)?
5. **Batch operations**: Can multiple small queries be replaced with one bulk query?
6. **Index properly**: Are database indexes covering the query patterns?
7. **Limit results**: Do you need all rows or just top N?

---

## 6. Common Pitfalls & Fixes

| Pitfall | Fix |
|---------|-----|
| Pre-computing only some combinations | Generate ALL combinations, add server fallback |
| Python subprocess per API call | Pre-compute JSON, serve from memory |
| Inline JS too large for single file write | Separate into app.js |
| win32com 0-indexed tuples | Use `data[r][c]` not `data[r+1][c+1]` |
| UnicodeEncodeError on Windows | Use ASCII alternatives |
| Excel process left running | Always `excel.Quit()` in `finally` block |
| Sheet index ≠ sheet name | Check `workbook.Sheets(i).Name` |
| Database locked | Close connections, delete WAL/SHM files |
| npm native modules unavailable | Use Python subprocess or pre-compute JSON |
| curl on Windows cmd with & in URL | Wrap URL in double quotes |

---

## 7. File Write Best Practices

When writing large files via the `write_to_file` tool:

- **Don't try to write everything in one call** if the content is very large (>500 lines of JS)
- Split into separate files: HTML structure + JS logic + CSS
- If a file write gets truncated, use `replace_in_file` to add the missing parts
- Test after writing by checking for syntax errors

---

## 8. Testing Checklist

After making changes, always verify:

1. **Server starts**: `node server.js` — check for errors
2. **API responds**: `curl http://localhost:3001/api/status`
3. **All endpoints work**: Test each API endpoint with curl
4. **Edge cases**: Test non-consecutive year pairs, empty results, invalid inputs
5. **Dashboard loads**: Open in browser, check console for errors
6. **All tabs work**: Click each tab, verify data loads
7. **All drill-down combinations**: Test different dimension × metric × year combinations

---

## 9. SKILL.md Maintenance

- **Always update SKILL.md** after any change to the pipeline, database, server, or dashboard
- Add entries to the Change Log with version number
- Update metrics (file count, response times, etc.)
- Document new troubleshooting items
- Keep the file structure section current

---

## 10. Project Workflow

The recommended order for building a data dashboard:

1. **Explore** the data source (understand structure, size, quirks)
2. **Extract** small summary first (validate approach)
3. **Ingest** full data into database (chunked, with progress logging)
4. **Index** after loading (not during)
5. **Pre-compute** all dashboard queries as JSON
6. **Build server** to serve static JSON from memory
7. **Build dashboard** with lazy loading and client-side caching
8. **Test** all combinations thoroughly
9. **Document** everything in SKILL.md
10. **Create Agent.md** with lessons learned
