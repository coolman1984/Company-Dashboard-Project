"""
Extract PL data from Sheet3 of PL 2022~2026.xlsb using Excel COM automation.
Dumps the data to pl_data.json for the web dashboard.
"""
import json
import os
import pythoncom
import win32com.client

def extract_pl_data():
    file_path = r"D:\WORK\Software Development\GitHub\Company Dashboard\PL 2022~2026.xlsb"
    output_path = r"D:\WORK\Software Development\GitHub\Company Dashboard\pl_data.json"
    
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return
    
    pythoncom.CoInitialize()
    excel = None
    
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        
        print("Opening workbook...")
        workbook = excel.Workbooks.Open(file_path, ReadOnly=True)
        
        # List all sheets
        print(f"Workbook has {workbook.Sheets.Count} sheets:")
        for i in range(1, workbook.Sheets.Count + 1):
            sname = workbook.Sheets(i).Name
            print(f"  Sheet {i}: '{sname}'")
        
        # Use the sheet named "Sheet3"
        target_sheet = workbook.Sheets(1)  # Sheet3 is the first sheet
        sheet_name = target_sheet.Name
        print(f"\nUsing sheet: '{sheet_name}'")
        
        # Use UsedRange to get dimensions
        used_range = target_sheet.UsedRange
        first_row = used_range.Row
        first_col = used_range.Column
        rows_count = used_range.Rows.Count
        cols_count = used_range.Columns.Count
        print(f"UsedRange: starts at ({first_row},{first_col}), size: {rows_count} rows x {cols_count} columns")
        
        # Read the used range in bulk
        print(f"Reading data in bulk...")
        data = used_range.Value
        
        # Debug: inspect the data structure
        print(f"Data type: {type(data)}")
        if isinstance(data, tuple):
            print(f"Data length (rows): {len(data)}")
            if len(data) > 0:
                print(f"First row type: {type(data[0])}")
                if isinstance(data[0], tuple):
                    print(f"First row length (cols): {len(data[0])}")
                    print(f"First row sample: {data[0][:5]}")
                else:
                    print(f"First element: {data[0]}")
            if len(data) > 1:
                print(f"Second row type: {type(data[1])}")
                if isinstance(data[1], tuple):
                    print(f"Second row length: {len(data[1])}")
                    print(f"Second row sample: {data[1][:5]}")
        
        # Process the data into structured format
        result = {
            "sheetName": sheet_name,
            "rows": rows_count,
            "cols": cols_count,
            "headers": [],
            "data": [],
            "rawData": []
        }
        
        # Convert COM data to list of lists
        # win32com returns 0-indexed tuples for 2D ranges
        if isinstance(data, tuple):
            for r in range(len(data)):
                row_data = []
                if isinstance(data[r], tuple):
                    for c in range(len(data[r])):
                        val = data[r][c] if data[r][c] is not None else ""
                        row_data.append(val)
                else:
                    row_data.append(data[r] if data[r] is not None else "")
                result["rawData"].append(row_data)
        else:
            # Single cell
            result["rawData"].append([data if data is not None else ""])
        
        # First row is likely headers
        if result["rawData"]:
            result["headers"] = result["rawData"][0]
            result["data"] = result["rawData"][1:]
        
        # Get all sheet names
        sheet_names = []
        for i in range(1, workbook.Sheets.Count + 1):
            sheet_names.append(workbook.Sheets(i).Name)
        result["allSheetNames"] = sheet_names
        
        # Save to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str)
        
        print(f"\nData extracted successfully!")
        print(f"Output: {output_path}")
        print(f"Rows: {rows_count}, Columns: {cols_count}")
        print(f"Headers: {result['headers']}")
        
        # Print all rows for verification
        print("\n--- All rows ---")
        for i, row in enumerate(result["rawData"]):
            print(f"Row {i+1}: {row}")
        
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
    extract_pl_data()
