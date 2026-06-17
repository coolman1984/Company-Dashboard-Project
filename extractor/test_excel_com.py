"""
test_excel_com.py — tests for the Excel COM helpers and extractor logic.

COM itself only runs on Windows with Excel, so these tests exercise the
*pure*, OS-independent logic in com_utils.py and the sheet-reading logic in
excel_com.py using lightweight fakes that mimic the COM object model
(UsedRange / Cells / Range.Value). This gives CI real coverage of the parts
that historically caused bugs — value cleaning, formula-error handling, the
chunk math, sheet selection and the no-hang open — without needing Windows.

Run: python3 -m extractor.test_excel_com
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
import unittest

from extractor import com_utils
from extractor.excel_com import ExcelComExtractor


# --------------------------------------------------------------------------
# Minimal fakes mimicking the win32com Excel object model.
# --------------------------------------------------------------------------
class _Count:
    def __init__(self, n):
        self.Count = n


class _UsedRange:
    def __init__(self, sheet):
        self.Rows = _Count(len(sheet._grid))
        self.Columns = _Count(max((len(r) for r in sheet._grid), default=0))
        self.Row = sheet._first_row
        self.Column = sheet._first_col


class _RangeValue:
    def __init__(self, value):
        self.Value = value


class FakeSheet:
    """A worksheet backed by a 2D grid; Range.Value returns tuple-of-tuples."""

    def __init__(self, name, grid, first_row=1, first_col=1):
        self.Name = name
        self._grid = grid
        self._first_row = first_row
        self._first_col = first_col

    @property
    def UsedRange(self):
        return _UsedRange(self)

    def Cells(self, row, col):
        return (row, col)

    def Range(self, c1, c2):
        (r1, col1), (r2, col2) = c1, c2
        block = []
        for r in range(r1, r2 + 1):
            gi = r - self._first_row
            grow = self._grid[gi] if 0 <= gi < len(self._grid) else []
            out = []
            for c in range(col1, col2 + 1):
                ci = c - self._first_col
                out.append(grow[ci] if 0 <= ci < len(grow) else None)
            block.append(tuple(out))
        return _RangeValue(tuple(block))


class FakeSheets:
    def __init__(self, sheets):
        self._sheets = sheets
        self.Count = len(sheets)

    def __call__(self, index):       # workbook.Sheets(i), 1-based
        return self._sheets[index - 1]


class FakeWorkbook:
    def __init__(self, sheets):
        self.Sheets = FakeSheets(sheets)


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------
class TestPureHelpers(unittest.TestCase):
    def test_is_cv_error(self):
        self.assertTrue(com_utils.is_cv_error(-2146826281))   # #DIV/0!
        self.assertTrue(com_utils.is_cv_error("#REF!"))
        self.assertFalse(com_utils.is_cv_error(0))
        self.assertFalse(com_utils.is_cv_error(True))         # bool is not an error
        self.assertFalse(com_utils.is_cv_error("hello"))
        self.assertFalse(com_utils.is_cv_error(None))

    def test_clean_com_value(self):
        self.assertEqual(com_utils.clean_com_value(-2146826265), (None, True))   # #REF!
        self.assertEqual(com_utils.clean_com_value("text"), ("text", False))
        self.assertEqual(com_utils.clean_com_value(42), (42, False))
        self.assertEqual(com_utils.clean_com_value(3.5), (3.5, False))
        self.assertEqual(com_utils.clean_com_value(True), (True, False))
        self.assertEqual(com_utils.clean_com_value(None), (None, False))
        val, err = com_utils.clean_com_value(dt.datetime(2026, 1, 2, 3, 4, 5))
        self.assertEqual(val, "2026-01-02T03:04:05")
        self.assertFalse(err)

    def test_normalize_block(self):
        self.assertEqual(com_utils.normalize_block(5), [[5]])
        self.assertEqual(com_utils.normalize_block(((1, 2), (3, 4))), [[1, 2], [3, 4]])
        self.assertEqual(com_utils.normalize_block(((1,), (2,))), [[1], [2]])

    def test_chunk_bounds(self):
        self.assertEqual(list(com_utils.chunk_bounds(0, 10)), [])
        self.assertEqual(list(com_utils.chunk_bounds(5, 2, start_row=2)),
                         [(2, 3), (4, 5), (6, 6)])
        # 790K-style: first chunk over data rows starting at row 2.
        first = next(iter(com_utils.chunk_bounds(790000, 10000, start_row=2)))
        self.assertEqual(first, (2, 10001))

    def test_excel_pid_unknown_is_zero(self):
        # No Hwnd / win32 unavailable / a mock object -> pid 0, never raises.
        class _NoHwnd:
            @property
            def Hwnd(self):
                raise AttributeError("no window")
        self.assertEqual(com_utils._excel_pid(_NoHwnd()), 0)
        self.assertEqual(com_utils._excel_pid(object()), 0)

    def test_terminate_orphan_noop_for_bad_pid(self):
        # Non-positive/unknown pids are a no-op and never raise (and on non-Windows
        # the windll path simply returns False rather than terminating anything).
        self.assertFalse(com_utils._terminate_orphan(0))
        self.assertFalse(com_utils._terminate_orphan(-1))
        self.assertFalse(com_utils._terminate_orphan(None))

    def test_fill_merged_cells(self):
        grid = [["Region", None, None],
                ["Africa", 1, 2],
                [None, 3, 4]]
        # Merge the header label across 3 cols, and the "Africa" label down 2 rows.
        out = com_utils.fill_merged_cells(grid, [(0, 0, 0, 2), (1, 0, 2, 0)])
        self.assertEqual(out[0], ["Region", "Region", "Region"])
        self.assertEqual(out[1][0], "Africa")
        self.assertEqual(out[2][0], "Africa")
        # Original is untouched (pure).
        self.assertIsNone(grid[0][1])

    def test_fill_merged_cells_extends_ragged_rows(self):
        grid = [["A"], ["B"]]
        out = com_utils.fill_merged_cells(grid, [(0, 0, 0, 2)])
        self.assertEqual(out[0], ["A", "A", "A"])

    def test_combine_header_rows(self):
        headers = [["", "2025", "2025", "2026"],
                   ["Region", "Q1", "Q2", "Q1"]]
        self.assertEqual(
            com_utils.combine_header_rows(headers),
            ["Region", "2025 / Q1", "2025 / Q2", "2026 / Q1"])
        # A single header row passes through unchanged.
        self.assertEqual(com_utils.combine_header_rows([["A", "B"]]), ["A", "B"])
        self.assertEqual(com_utils.combine_header_rows([]), [])

    def test_find_sheet_by_name_and_index(self):
        wb = FakeWorkbook([FakeSheet("Sheet3", [[1]]), FakeSheet("Sheet1", [[2]])])
        self.assertEqual(com_utils.find_sheet(wb, name="sheet1").Name, "Sheet1")   # case-insensitive
        self.assertEqual(com_utils.find_sheet(wb, name=" Sheet1 ").Name, "Sheet1")  # whitespace
        # Name missing -> fall back to index 2 (the documented Sheet1 slot).
        self.assertEqual(com_utils.find_sheet(wb, name="Nope", index=2).Name, "Sheet1")
        with self.assertRaises(KeyError):
            com_utils.find_sheet(wb, name="Nope")
        with self.assertRaises(KeyError):
            com_utils.find_sheet(wb, index=9)


# --------------------------------------------------------------------------
# No-hang open
# --------------------------------------------------------------------------
class _FakeWorkbooks:
    def __init__(self, behaviour):
        self._behaviour = behaviour
        self.calls = []

    def Open(self, path, **kwargs):
        self.calls.append(kwargs)
        return self._behaviour(len(self.calls), kwargs)


class _FakeExcel:
    def __init__(self, behaviour):
        self.Workbooks = _FakeWorkbooks(behaviour)


class TestOpenWorkbook(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)

    def tearDown(self):
        os.remove(self.path)

    def test_missing_file(self):
        excel = _FakeExcel(lambda n, kw: "wb")
        with self.assertRaises(FileNotFoundError):
            com_utils.open_workbook(excel, "/no/such/file.xlsx")

    def test_password_protected_raises_value_error(self):
        def behaviour(n, kw):
            raise Exception("The password you supplied is incorrect")
        excel = _FakeExcel(behaviour)
        with self.assertRaises(ValueError) as ctx:
            com_utils.open_workbook(excel, self.path)
        self.assertIn("password", str(ctx.exception).lower())
        # The guard password must have been passed to avoid a modal dialog.
        self.assertIn("Password", excel.Workbooks.calls[0])

    def test_corrupt_file_retries_in_extract_mode(self):
        def behaviour(n, kw):
            if n == 1:
                raise Exception("Unexpected end of file")
            return "recovered-wb"   # second call (CorruptLoad) succeeds
        excel = _FakeExcel(behaviour)
        wb = com_utils.open_workbook(excel, self.path)
        self.assertEqual(wb, "recovered-wb")
        self.assertEqual(excel.Workbooks.calls[1].get("CorruptLoad"),
                         com_utils.XL_EXTRACT_DATA)

    def test_corrupt_file_failing_twice_raises(self):
        def behaviour(n, kw):
            raise Exception("garbage")
        excel = _FakeExcel(behaviour)
        with self.assertRaises(ValueError) as ctx:
            com_utils.open_workbook(excel, self.path)
        self.assertIn("corrupt", str(ctx.exception).lower())


# --------------------------------------------------------------------------
# Sheet reading (the chunk/clean integration)
# --------------------------------------------------------------------------
class TestReadSheet(unittest.TestCase):
    def test_reads_grid_flags_errors_and_trims(self):
        grid = [
            ["a", "b", "c"],
            [1, 2, -2146826265],     # last cell is #REF!
            [4, 5, 6],
            [None, None, None],      # trailing empty row -> trimmed
        ]
        sheet = FakeSheet("Data", grid)
        warnings = []
        result = ExcelComExtractor()._read_sheet(sheet, warnings)
        self.assertEqual(result["name"], "Data")
        self.assertEqual(result["n_cols"], 3)
        self.assertEqual(result["cells"], [["a", "b", "c"], [1, 2, None], [4, 5, 6]])
        self.assertFalse(result["partial"])
        self.assertTrue(any("formula error" in w for w in warnings))

    def test_small_chunks_cover_all_rows(self):
        # Force multiple chunks by shrinking CHUNK_ROWS on the instance path.
        grid = [[i, i * 2] for i in range(1, 24)]   # 23 rows
        sheet = FakeSheet("Big", grid)
        ext = ExcelComExtractor()
        original = __import__("extractor.excel_com", fromlist=["CHUNK_ROWS"]).CHUNK_ROWS
        try:
            import extractor.excel_com as mod
            mod.CHUNK_ROWS = 10
            result = ext._read_sheet(sheet, [])
        finally:
            mod.CHUNK_ROWS = original
        self.assertEqual(len(result["cells"]), 23)
        self.assertEqual(result["cells"][0], [1, 2])
        self.assertEqual(result["cells"][-1], [23, 46])

    def test_read_chunk_failure_is_partial_not_fatal(self):
        class ExplodingSheet(FakeSheet):
            def Range(self, c1, c2):
                raise RuntimeError("COM RPC failure")
        sheet = ExplodingSheet("Bad", [[1, 2], [3, 4]])
        warnings = []
        result = ExcelComExtractor()._read_sheet(sheet, warnings)
        self.assertTrue(result["partial"])
        self.assertEqual(result["cells"], [])
        self.assertTrue(any("Partial extraction" in w for w in warnings))


class TestAvailability(unittest.TestCase):
    def test_not_available_off_windows(self):
        ok, reason = ExcelComExtractor().is_available()
        if not sys.platform.startswith("win"):
            self.assertFalse(ok)
            self.assertIn("Windows", reason)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
