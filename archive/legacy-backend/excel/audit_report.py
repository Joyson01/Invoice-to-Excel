import csv
import os
from datetime import datetime
from app.models.schemas import InvoiceData

def generate_audit_csv(invoices: list[InvoiceData], output_dir: str) -> str:
    stamp = datetime.now().strftime("%d-%m-%Y_%H%M%S")
    output_filename = f"B2B_bulk_upload_{stamp}_audit.csv"
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, output_filename)
    
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_file", "invoice_no", "order_id", "date", "receiver_name",
                    "mobile", "pincode", "boxes", "skus", "units", "invoice_amount",
                    "eway_bill", "warnings", "status"])
        for inv in invoices:
            boxes = sum(b.quantity for b in inv.boxes)
            skus = len(inv.line_items)
            units = sum(i.quantity for i in inv.line_items)
            w.writerow([
                inv.source_file,
                inv.invoice_number.value,
                inv.order_id.value,
                inv.invoice_date.value,
                inv.receiver_name.value,
                inv.receiver_mobile.value,
                inv.receiver_pincode.value,
                boxes,
                skus,
                units,
                inv.invoice_amount.value,
                inv.eway_bill_number.value,
                " | ".join(inv.warnings),
                inv.status
            ])
    return out_path
