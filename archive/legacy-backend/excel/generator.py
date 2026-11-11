import openpyxl
from copy import copy
from datetime import datetime
import os
from app.models.schemas import InvoiceData
from app.config import settings

def _fill_sheet(ws, rows: list, columns: list):
    header = [c.value for c in ws[1]]
    styles = None
    if ws.max_row >= 2:
        styles = [(copy(c.font), copy(c.alignment), copy(c.border), copy(c.fill), c.number_format)
                  for c in ws[2]]
        ws.delete_rows(2, ws.max_row)

    for i, data in enumerate(rows, start=2):
        for j, v in enumerate(data, start=1):
            cell = ws.cell(row=i, column=j, value=(None if v == "" else v))
            if styles and j - 1 < len(styles):
                f, a, b, fl, nf = styles[j - 1]
                cell.font, cell.alignment, cell.border, cell.fill, cell.number_format = f, a, b, fl, nf

def generate_excel(invoices: list[InvoiceData], template_path: str, output_dir: str) -> str:
    wb = openpyxl.load_workbook(template_path)
    
    orders, boxes, inv_rows = [], [], []
    for inv in invoices:
        oid = inv.order_id.value
        orders.append([
            oid,
            inv.warehouse_name.value,
            inv.receiver_name.value,
            inv.receiver_address.value,
            inv.receiver_pincode.value,
            inv.receiver_email.value,
            inv.receiver_mobile.value,
            inv.order_description.value,
            inv.payment_mode.value,
            inv.cod_value.value,
            inv.insurance.value,
            inv.invoice_url.value,
            inv.delivery_challan.value,
            inv.declaration.value,
            inv.other_supporting_documents.value,
            inv.reason.value
        ])
        
        for b in inv.boxes:
            boxes.append([oid, b.length, b.width, b.height, b.weight, b.quantity])
            
        inv_rows.append([
            oid,
            inv.invoice_number.value,
            inv.invoice_amount.value,
            inv.eway_bill_number.value
        ])
        
    def resolve_sheet(wb, name):
        for s in wb.sheetnames:
            if s.strip().lower() == name.strip().lower():
                return wb[s]
        return None
        
    ws_orders = resolve_sheet(wb, "orders")
    ws_boxes = resolve_sheet(wb, "boxes")
    ws_invoices = resolve_sheet(wb, "invoice")
    
    # Ensure Orders has Reason column (16th)
    if ws_orders.cell(row=1, column=16).value != "Reason":
        ws_orders.cell(row=1, column=16, value="Reason")
        
    _fill_sheet(ws_orders, orders, [])
    _fill_sheet(ws_boxes, boxes, [])
    _fill_sheet(ws_invoices, inv_rows, [])
    
    stamp = datetime.now().strftime("%d-%m-%Y_%H%M%S")
    output_filename = f"B2B_bulk_upload_{stamp}.xlsx"
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, output_filename)
    wb.save(out_path)
    return out_path
