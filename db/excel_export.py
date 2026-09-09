import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from db.operations import get_full_report_matrix, get_shortage_report, get_battalion_inventory

HEADER_FILL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")


def _style_header(ws, ncols):
    for cell in ws[1]:
        cell.font = Font(name="Arial", bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    for idx in range(1, ncols + 1):
        ws.column_dimensions[get_column_letter(idx)].width = 20


def build_full_report(output_path: str, layer: str = "personal"):
    item_names, platoons_data = get_full_report_matrix(layer)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for platoon in platoons_data:
        ws = wb.create_sheet(title=platoon["platoon_name"][:31])
        ws.sheet_view.rightToLeft = True
        headers = ["שם חייל"] + item_names
        ws.append(headers)
        _style_header(ws, len(headers))
        for soldier in platoon["soldiers"]:
            row = [soldier["full_name"]] + [soldier["items"].get(name, "") for name in item_names]
            ws.append(row)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name="Arial")
                if cell.column > 1:
                    cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions["A"].width = 22
        for idx in range(2, len(headers) + 1):
            ws.column_dimensions[get_column_letter(idx)].width = 13
        ws.freeze_panes = "B2"
    wb.save(output_path)
    return output_path


def build_shortage_report(output_path: str):
    rows = get_shortage_report()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "חוסרים"
    ws.sheet_view.rightToLeft = True
    headers = ["מחלקה", "שם חייל", "פריט", "כמות"]
    ws.append(headers)
    _style_header(ws, len(headers))
    for r in rows:
        ws.append([r["platoon"], r["full_name"], r["item"], r["quantity"]])
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Arial")
    ws.freeze_panes = "A2"
    wb.save(output_path)
    return output_path


def build_battalion_inventory_report(output_path: str):
    """דוח ציוד מול הגדוד - פריט, סה'כ, אצל מי, מוחתם, נשאר במחסן"""
    inventory = get_battalion_inventory()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ציוד מול הגדוד"
    ws.sheet_view.rightToLeft = True
    headers = ["פריט", "סה\"כ", "מוחתם", "נשאר במחסן", "אצל מי"]
    ws.append(headers)
    _style_header(ws, len(headers))
    for item in inventory:
        holders_text = ", ".join(f"{h['name']} ({h['quantity']})" for h in item["held_by"]) or "-"
        ws.append([item["name"], item["total"], item["issued"], item["available"], holders_text])
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Arial")
    ws.column_dimensions["E"].width = 40
    ws.freeze_panes = "A2"
    wb.save(output_path)
    return output_path
