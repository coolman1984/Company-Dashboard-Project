"""
com_utils.py — shared, hard-won safety helpers for Excel COM automation.

Everything COM-related and dangerous lives here so the COM extractor
(`excel_com.py`) and the bulk production ingest (`ingest_sheet1.py`) share ONE
correct implementation of the patterns documented in Agent.md:

  * a session context-manager that disables every blocking dialog, **disables
    macros** (client files are untrusted), and *guarantees* Excel is quit and
    the COM library uninitialised — even on crash — so no orphaned EXCEL.EXE;
  * an `open_workbook` that refuses to hang on password-protected files (the
    classic COM deadlock), retries damaged files in data-extraction mode, and
    raises clear errors instead of cryptic COM ones;
  * pure, OS-independent helpers (`clean_com_value`, `is_cv_error`,
    `find_sheet`, `chunk_bounds`, `normalize_block`) that carry the fiddly
    grid/sheet/value logic and are unit-tested on any platform via mocks.

IMPORTANT: the COM calls themselves only run on Windows with Excel installed.
The win32com/pythoncom imports are deliberately lazy (inside the functions) so
this module imports cleanly on Linux/CI for the mocked tests.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

# Excel CVErr codes as surfaced through Range.Value by pywin32 (large negative
# ints). Mapping them lets us turn formula errors into clean nulls + a warning
# instead of leaking magic numbers into the database.
CV_ERRORS = {
    -2146826281: "#DIV/0!",
    -2146826246: "#N/A",
    -2146826259: "#NAME?",
    -2146826288: "#NULL!",
    -2146826252: "#NUM!",
    -2146826265: "#REF!",
    -2146826273: "#VALUE!",
}
CV_ERROR_STRINGS = ("#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!", "#GETTING_DATA")

# Excel constants (avoid importing the type library just for these).
XL_EXTRACT_DATA = 2          # CorruptLoad mode: salvage data from a damaged file
MSO_SEC_FORCE_DISABLE = 3    # AutomationSecurity: never run macros on open

# A non-empty guard password. If a workbook is genuinely password-protected,
# Open() raises with this wrong password instead of popping a modal dialog that
# would hang an unattended/automated run forever. Ignored for unprotected files.
_PROMPT_GUARD_PASSWORD = "_com_utils_no_prompt_"


def is_cv_error(value):
    """True if a COM cell value is an Excel formula error (#REF!, #DIV/0! ...)."""
    if isinstance(value, bool):  # bool is an int subclass — never an error code
        return False
    if isinstance(value, int) and value in CV_ERRORS:
        return True
    if isinstance(value, str) and value in CV_ERROR_STRINGS:
        return True
    return False


def clean_com_value(value):
    """Make one COM cell value JSON-friendly; return (clean_value, had_error).

    * formula errors (#REF! etc.)        -> (None, True)
    * datetimes (pywintypes/py datetime)  -> (isoformat string, False)
    * None/str/int/float/bool             -> (value, False)
    * anything else                       -> (str(value), False)
    """
    import datetime as dt
    import math

    if is_cv_error(value):
        return None, True
    if isinstance(value, dt.datetime):
        return value.isoformat(), False
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat(), False
    # NaN/Infinity (e.g. a #DIV/0! that slips through as a float) would poison
    # every SUM downstream — drop them to null and flag as an error cell.
    if isinstance(value, float) and not math.isfinite(value):
        return None, True
    if value is None or isinstance(value, (str, int, float, bool)):
        return value, False
    # pywintypes.TimeType and other COM scalars fall through to a safe string.
    return str(value), False


def normalize_block(block):
    """Normalise a COM Range.Value result into a list of row-lists.

    Range.Value comes back as a scalar for a 1x1 range, a flat tuple for a
    single row/column, or a tuple-of-tuples for a grid. This flattens all three
    shapes into a consistent list[list].
    """
    if not isinstance(block, tuple):
        return [[block]]
    rows = []
    for com_row in block:
        if isinstance(com_row, tuple):
            rows.append(list(com_row))
        else:
            rows.append([com_row])
    return rows


def chunk_bounds(total_rows, chunk_size, start_row=1):
    """Yield inclusive (first_row, last_row) 1-based ranges covering the data.

    `total_rows` is the count of DATA rows (headers already excluded by the
    caller). Returns nothing for non-positive inputs, so callers never read a
    bogus range out of an empty sheet.
    """
    if total_rows <= 0 or chunk_size <= 0:
        return
    read = 0
    while read < total_rows:
        take = min(chunk_size, total_rows - read)
        top = start_row + read
        yield top, top + take - 1
        read += take


def find_sheet(workbook, name=None, index=None):
    """Return a worksheet by NAME (preferred) or 1-based INDEX.

    Matching by name is case/whitespace-tolerant. Falls back to `index` if the
    name is not found (or not given). Raises KeyError if neither resolves — far
    safer than the hard-coded `Sheets(2)` that Agent.md warns about.
    """
    count = int(workbook.Sheets.Count)
    if name:
        target = str(name).strip().casefold()
        for i in range(1, count + 1):
            sheet = workbook.Sheets(i)
            if str(sheet.Name).strip().casefold() == target:
                return sheet
    if index is not None:
        if 1 <= index <= count:
            return workbook.Sheets(index)
        raise KeyError(f"sheet index {index} out of range (1..{count})")
    raise KeyError(f"sheet named {name!r} not found among {count} sheet(s)")


def _excel_pid(excel):
    """Best-effort OS process id for an Excel Application, via its window handle.

    Returns 0 if it can't be determined (e.g. no Hwnd, win32 unavailable, or a
    mock). Pure enough to unit-test the edge cases on any platform.
    """
    try:
        import win32process
        hwnd = int(excel.Hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return int(pid) if pid and int(pid) > 0 else 0
    except Exception:  # noqa: BLE001 — any failure means "unknown pid", never fatal
        return 0


def _terminate_orphan(pid):
    """Last resort: force-kill an Excel process that survived Quit().

    This is the safety net for the audit's #1 risk — a hung/crashed COM session
    leaving an orphaned EXCEL.EXE that slowly eats memory. Windows-only and
    strictly best-effort: it never raises and returns True only if a termination
    was actually attempted. A non-positive/unknown pid is a no-op.
    """
    if not pid or int(pid) <= 0:
        return False
    try:
        import ctypes
        PROCESS_TERMINATE = 0x0001
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
        if not handle:
            return False
        try:
            ctypes.windll.kernel32.TerminateProcess(handle, 1)
            return True
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 — no windll on non-Windows, dead pid, etc.
        return False


@contextmanager
def excel_session(disable_macros=True):
    """Context manager yielding a configured, dialog-free Excel application.

    Guarantees cleanup: Excel is quit, references released and the COM library
    uninitialised on exit, success or failure — preventing orphaned EXCEL.EXE
    processes (the #1 COM gotcha). Windows-only; imports COM lazily.
    """
    import gc

    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    excel = None
    pid = 0
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        # Silence every interactive surface that could block an automated run.
        excel.Visible = False
        excel.DisplayAlerts = False
        for prop, val in (
            ("EnableEvents", False),       # don't fire workbook/auto macros
            ("AskToUpdateLinks", False),   # don't prompt to update links
            ("AlertBeforeOverwriting", False),
            ("ScreenUpdating", False),
            ("Interactive", False),        # block stray user input/dialogs
        ):
            try:
                setattr(excel, prop, val)
            except Exception:  # noqa: BLE001 — property unsupported on some builds
                pass
        if disable_macros:
            # Client files are untrusted: never let a macro execute on open.
            try:
                excel.AutomationSecurity = MSO_SEC_FORCE_DISABLE
            except Exception:  # noqa: BLE001
                pass
        # Remember the OS process so we can force-kill it if Quit() doesn't take
        # (a hung dialog, a crashed automation server) — the orphaned-EXCEL.EXE
        # safety net. Captured before yield so we still have it after a crash.
        pid = _excel_pid(excel)
        yield excel
    finally:
        if excel is not None:
            try:
                excel.Quit()
            except Exception:  # noqa: BLE001 — best-effort; never mask the real error
                pass
        excel = None
        gc.collect()
        try:
            pythoncom.CoUninitialize()
        except Exception:  # noqa: BLE001
            pass
        # If the process is still alive after a graceful Quit + GC, terminate it
        # so an unattended run can never leak Excel processes over time.
        _terminate_orphan(pid)


def open_workbook(excel, path, read_only=True):
    """Open a workbook without ever hanging on a dialog.

    * Missing file            -> FileNotFoundError (clear, early).
    * Password-protected      -> ValueError (the guard password makes Open raise
                                 instead of popping a modal password dialog).
    * Corrupt/damaged file    -> one automatic retry in data-extraction mode,
                                 then ValueError if that also fails.

    Returns the opened Workbook COM object.
    """
    abspath = os.path.abspath(path)
    if not os.path.exists(abspath):
        raise FileNotFoundError(f"workbook not found: {abspath}")
    try:
        return excel.Workbooks.Open(
            abspath,
            UpdateLinks=0,
            ReadOnly=read_only,
            IgnoreReadOnlyRecommended=True,
            Notify=False,
            AddToMru=False,
            Password=_PROMPT_GUARD_PASSWORD,
        )
    except Exception as exc:  # noqa: BLE001 — classify and re-raise cleanly
        message = str(exc).lower()
        if "password" in message or "protect" in message:
            raise ValueError(
                f"Workbook is password-protected and cannot be opened "
                f"unattended: {path}"
            ) from exc
        # Damaged file: try once more salvaging whatever data Excel can recover.
        try:
            return excel.Workbooks.Open(
                abspath,
                UpdateLinks=0,
                ReadOnly=read_only,
                CorruptLoad=XL_EXTRACT_DATA,
            )
        except Exception as exc2:  # noqa: BLE001
            raise ValueError(
                f"Cannot open workbook (corrupt or unsupported format?): "
                f"{path} ({exc2})"
            ) from exc2
