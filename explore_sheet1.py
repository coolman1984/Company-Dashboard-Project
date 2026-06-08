"""
Quick exploration of Sheet1 structure - read headers and sample data only.
"""
import os
import pythoncom
import win32com.client

def explore_sheet1():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(BASE_DIR, "PL 2022~2026.xlsb")
    
    pythoncom.CoInitialize()
    excel = None
    
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        
        workbook = excel.Workbooks.Open(file_path, ReadOnly=True)
        sheet = workbook.Sheets(2)  # Sheet1 is the second sheet
        print(f"Sheet name: {sheet.Name}")
        
        # Get used range info
        used_range = sheet.UsedRange
        rows = used_range.Rows.Count
        cols = used_range.Columns.Count
        print(f"Dimensions: {rows} rows x {cols} columns")
        
        # Read just the header row (row 1)
        header_range = sheet.Range(sheet.Cells(1, 1), sheet.Cells(1, cols))
        headers = header_range.Value[0]
        print(f"\n--- Column Headers ({len(headers)} columns) ---")
        for i, h in enumerate(headers):
            col_letter = chr(65 + i) if i < 26 else chr(64 + i//26) + chr(65 + i%26)
            print(f"  Col {i+1} ({col_letter}): {h}")
        
        # Read first 5 data rows
        print(f"\n--- Sample Data (rows 2-6) ---")
        sample_range = sheet.Range(sheet.Cells(2, 1), sheet.Cells(6, cols))
        sample = sample_range.Value
        for r in range(len(sample)):
            row_data = [sample[r][c] for c in range(len(sample[r]))]
            print(f"Row {r+2}: {row_data[:10]}...")  # First 10 cols only
        
        # Check data types in a few columns
        print(f"\n--- Data type check (row 2) ---")
        row2_range = sheet.Range(sheet.Cells(2, 1), sheet.Cells(2, cols))
        row2 = row2_range.Value[0]
        for i, val in enumerate(row2):
            if val is not None and val != "":
                print(f"  Col {i+1}: type={type(val).__name__}, value={val}")
        
        workbook.Close(SaveChanges=False)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if excel:
            try:
                excel.Quit()
            except:
                pass
        pythoncom.CoUninitialize()
        print("Cleanup complete.")

if __name__ == "__main__":
    explore_sheet1()
