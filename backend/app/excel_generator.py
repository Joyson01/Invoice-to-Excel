import os
from copy import copy
from datetime import datetime
from typing import List
import openpyxl

from app.models import InvoiceData

def _copy_cell_style(src_cell, target_cell):
    """Copy visual styling from source cell to target cell."""
    if src_cell.font:
        target_cell.font = copy(src_cell.font)
    if src_cell.alignment:
        target_cell.alignment = copy(src_cell.alignment)
    if src_cell.border:
        target_cell.border = copy(src_cell.border)
    if src_cell.fill:
        target_cell.fill = copy(src_cell.fill)
    if src_cell.number_format:
        target_cell.number_format = src_cell.number_format

def _populate_sheet(ws, rows: List[List], col_count: int):
    """Populate sheet rows while preserving formatting from template."""
    sample_styles = []
    
    # Capture style from row 2 if present, otherwise row 1
    style_row = 2 if ws.max_row >= 2 else 1
    for c in range(1, col_count + 1):
        cell = ws.cell(row=style_row, column=c)
        sample_styles.append((
            copy(cell.font) if cell.font else None,
            copy(cell.alignment) if cell.alignment else None,
            copy(cell.border) if cell.border else None,
            copy(cell.fill) if cell.fill else None,
            cell.number_format or "General"
        ))
        
    # Clear existing data rows below headers
    if ws.max_row >= 2:
        ws.delete_rows(2, ws.max_row)

    # Insert rows
    for r_idx, row_data in enumerate(rows, start=2):
        for c_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=(None if val == "" else val))
            if isinstance(val, str) and val:
                cell.data_type = "s"
            
            # Apply template styling
            if c_idx - 1 < len(sample_styles):
                f, a, b, fl, nf = sample_styles[c_idx - 1]
                if f: cell.font = f
                if a: cell.alignment = a
                if b: cell.border = b
                if fl: cell.fill = fl
                if nf and nf != "General":
                    cell.number_format = nf

def generate_excel(invoices: List[InvoiceData], template_path: str, output_dir: str) -> str:
    """Generate the B2B Excel workbook using the master template."""
    if not os.path.exists(template_path):
        alt_paths = [
            "templates/B2B_bulk_upload_template.xlsx",
            "../templates/B2B_bulk_upload_template.xlsx",
            "B2B_bulk_upload_template.xlsx",
            "../B2B_bulk_upload_template.xlsx",
        ]
        found = False
        for p in alt_paths:
            if os.path.exists(p):
                template_path = p
                found = True
                break
        if not found:
            raise FileNotFoundError(f"Master template not found at {template_path}")

    wb = openpyxl.load_workbook(template_path)
    
    # Resolve sheet names case-insensitively
    sheet_map = {s.strip().lower(): s for s in wb.sheetnames}
    if "orders" not in sheet_map or "boxes" not in sheet_map or "invoice" not in sheet_map:
        raise ValueError(f"Template missing required sheets: Orders, Boxes, Invoice. Found: {wb.sheetnames}")
        
    ws_orders = wb[sheet_map["orders"]]
    ws_boxes = wb[sheet_map["boxes"]]
    ws_invoice = wb[sheet_map["invoice"]]

    # Ensure Orders has Reason column (16th column)
    if ws_orders.cell(row=1, column=16).value != "Reason":
        ws_orders.cell(row=1, column=16, value="Reason")
        _copy_cell_style(ws_orders.cell(row=1, column=15), ws_orders.cell(row=1, column=16))
        ws_orders.column_dimensions["P"].width = 16.0

    # Build rows
    orders_data = []
    boxes_data = []
    invoice_data = []

    for inv in invoices:
        oid = inv.order_id or ""
        reason_val = inv.reason if inv.reason else ("; ".join(inv.warnings) if inv.warnings else "")
        
        # 1. Orders Sheet
        orders_data.append([
            oid,                                                    # 1: Order_ID
            inv.warehouse_name or None,                             # 2: Warehouse_Name
            inv.receiver_name or None,                              # 3: Receiver_Name
            inv.receiver_address or None,                           # 4: Receiver_Address
            inv.receiver_pincode or None,                           # 5: Receiver_Pincode
            inv.receiver_email or None,                             # 6: Receiver_Email
            inv.receiver_mobile or None,                            # 7: Receiver_Mobile
            inv.order_description or None,                          # 8: Order_description
            inv.payment_mode or None,                               # 9: Payment_Mode
            inv.cod_value if inv.cod_value is not None else None,   # 10: COD_Value
            inv.insurance or None,                                  # 11: Insurance
            inv.invoice_url or None,                                # 12: Invoice
            inv.delivery_challan or None,                           # 13: Delivery_Challan
            inv.declaration or None,                                # 14: Declaration
            inv.other_supporting_documents or None,                 # 15: Other_Supporting_Documents
            reason_val or None                                      # 16: Reason
        ])

        # 2. Boxes Sheet
        if inv.boxes and len(inv.boxes) > 0:
            for b in inv.boxes:
                boxes_data.append([
                    oid,
                    b.length if b.length is not None else None,
                    b.width if b.width is not None else None,
                    b.height if b.height is not None else None,
                    b.weight if b.weight is not None else None,
                    b.quantity if b.quantity is not None else None
                ])
        else:
            boxes_data.append([oid, None, None, None, None, None])

        # 3. Invoice Sheet
        amt = float(inv.invoice_amount) if (inv.invoice_amount is not None) else None
        invoice_data.append([
            oid,
            inv.invoice_number or None,
            amt,
            inv.eway_bill_number or None
        ])

    # Populate sheets
    _populate_sheet(ws_orders, orders_data, 16)
    _populate_sheet(ws_boxes, boxes_data, 6)
    _populate_sheet(ws_invoice, invoice_data, 4)

    # Format output filename: B2B_bulk_upload_YYYY-MM-DD_HHMMSS.xlsx
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"B2B_bulk_upload_{timestamp}.xlsx"
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)

    counter = 1
    base_name, ext = os.path.splitext(out_path)
    while os.path.exists(out_path):
        out_path = f"{base_name}_{counter}{ext}"
        counter += 1

    wb.save(out_path)
    return out_path
