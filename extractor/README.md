# Extraction Engine

**Turn a client's messy files (Excel, PDF, Word, Outlook email) into clean,
faithful JSON — the first station of the assembly line in [ROADMAP.md](../ROADMAP.md).**

This is Stage 1: *intake*. It captures every original document into a single,
consistent JSON shape and keeps an audit trail. Spreadsheet captures can then be
mapped into the analytics database with `map_raw_to_db.py` and a reviewed,
client-specific mapping JSON.

---

## The idea in one picture

```
intake/                      extractor engine                 raw/
--------                     ----------------                 ----
client files   ──►  pick the best available extractor  ──►   one .raw.json per file
(.xlsx .pdf          per file type, read it faithfully,       + manifest.jsonl (audit log)
 .docx .msg ...)     never crash on a bad file
```

You drop files in `intake/`. You run one command. You get a faithful JSON copy
of each original in `raw/`, plus a manifest recording exactly what was taken and
when. Nothing is interpreted or changed yet — the original is preserved first.

---

## How to run it

```bash
pip install -r extractor/requirements.txt   # one-time (install what you need)
python3 -m extractor.cli --list             # show which file types are ready
python3 -m extractor.cli                     # capture intake/ -> raw/
python3 -m extractor.cli --force             # re-capture even unchanged files
python3 -m extractor.test_extractor          # run the self-test
```

On Windows, `--list` will show `excel-com` as **available** and it becomes the
preferred Excel reader automatically.

---

## Design decisions (the architecture)

### 1. COM-first on Windows, cross-platform fallback everywhere
Excel/Word/Outlook **COM automation** drives the real Microsoft Office apps and
gives full fidelity and full control — including binary `.xlsb` workbooks that
pure-Python libraries can't read. COM is **Windows-only**, so each Office type
also has a cross-platform extractor (openpyxl, python-docx, …) that runs on any
machine and in CI. The [registry](registry.py) picks the **first available**
extractor for each file, so COM is used when present and the fallback otherwise —
both produce the **same JSON envelope**, so nothing downstream cares which ran.

### 2. One universal "raw envelope", type-specific content
Every extractor returns the same outer shape ([raw.py](raw.py)); only `content`
differs by file type:

```jsonc
{
  "schema_version": 1,
  "source":   { "filename", "relpath", "bytes", "sha256", "extension", "modified_at" },
  "extractor": "excel-com",            // which reader produced this
  "extracted_at": "2026-06-14T08:00:00Z",
  "document_type": "spreadsheet",      // spreadsheet | document | pdf | email
  "content":  { /* sheets | paragraphs+tables | pages | headers+body */ },
  "warnings": [ /* e.g. "page 3 had no text - likely scanned, send to OCR" */ ]
}
```

The `sha256` fingerprint preserves integrity and lets re-runs skip unchanged
files. `warnings` flags things a human should look at (the human-in-the-loop).

### 3. Never crash on one bad file
A single unreadable file, a missing library, or even a broken native dependency
must not stop a 500-file run. Unsupported types and unavailable extractors are
**skipped with a clear reason**; per-file errors are logged to the manifest and
the run continues.

### 4. Everything is auditable
`raw/manifest.jsonl` gets one line per file processed: timestamp, filename,
fingerprint, extractor used, result, and any warnings. This answers "what did we
take from the client, with what, and when?"

### 5. Robust edge case handling (added in Phase 2)
Real-world client files are messy. Every extractor now includes:

**File integrity guards:**
- File size limits (50-200MB depending on type) with warnings
- Empty file detection (0 bytes)
- Corrupt file detection with clear error messages
- Binary content detection for CSV files

**Content-level error handling:**
- Excel: Formula errors (#REF!, #DIV/0!) converted to null with warnings
- PDF: Encrypted/password-protected PDF detection
- CSV: Parse errors tracked per line (max 5 shown, rest summarized)
- Word: Per-paragraph error tracking
- All: Partial extraction on failure (never all-or-nothing)

**Graceful degradation:**
- Sheet-level errors in Excel don't abort the workbook
- Page-level errors in PDF don't abort the document
- Paragraph-level errors in Word don't abort the document
- Attachment errors in emails don't abort the message
- All errors logged with row/page/paragraph numbers for human review

**Encoding and format detection:**
- CSV: BOM detection, UTF-8 → Windows-1256 → Latin-1 fallback chain
- CSV: Binary content heuristic (>10% non-printable bytes)
- All: Consistent error messages that suggest next steps

---

## What each extractor covers

| Extractor        | File types            | Where it runs            | Status |
|------------------|-----------------------|--------------------------|--------|
| `excel-com`      | .xlsx .xlsm .xlsb .xls | Windows + Excel (COM)    | primary, written; test on Windows |
| `excel-openpyxl` | .xlsx .xlsm            | anywhere                 | done, tested |
| `word-docx`      | .docx                  | anywhere                 | done, tested |
| `pdf-text`       | .pdf (digital)         | anywhere (pdfplumber)    | written; needs pdfplumber |
| `outlook-msg`    | .msg .eml              | anywhere (extract-msg)   | written; needs extract-msg |

---

## Known boundaries / what's next

- **Scanned PDFs & photos** have no selectable text. `pdf-text` flags them with a
  warning; a dedicated **OCR stage** (text-recognition + AI) is the follow-up.
- **Live Outlook mailboxes / .pst** (vs. saved `.msg`) want a Windows COM path,
  mirroring `excel_com.py`. Saved `.msg`/`.eml` work cross-platform today.
- **Mapping raw → database.** Spreadsheet raw JSON can be loaded into the
  dashboard's `pl_detail` table with `map_raw_to_db.py` and a small mapping file
  (see `../mapping.example.json`). The mapper includes a **post-load validation**
  step that checks for duplicate grains, nulls in required columns, P&L arithmetic
  identities, and prints a coverage report. Structural problems abort the load
  before the database is swapped in; P&L arithmetic drift is reported as a
  non-blocking warning. Non-spreadsheet sources still need target shapes before
  they can be mapped safely.
- **COM cannot be tested in Linux/CI.** The COM extractors are written to the
  project's COM conventions (see `Agent.md`) and must be validated on a Windows
  machine with Office installed.
