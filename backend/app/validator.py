import re
from collections import Counter
from typing import List, Set
from app.models import InvoiceData

def validate_invoice(invoice: InvoiceData, existing_order_ids: Set[str] = None) -> InvoiceData:
    """Validate extracted invoice data and assign warnings and status."""
    warnings: List[str] = []
    
    # 1. Invoice Number missing
    if not invoice.invoice_number or not invoice.invoice_number.strip():
        warnings.append("Invoice Number missing")

    # 2. Order ID missing
    if not invoice.order_id or not invoice.order_id.strip():
        warnings.append("Order ID missing")
    elif existing_order_ids is not None and invoice.order_id in existing_order_ids:
        # duplicate Order_ID
        warnings.append(f"Duplicate Order_ID '{invoice.order_id}'")

    # 3. Invoice Amount missing or invalid
    if invoice.invoice_amount is None:
        warnings.append("Invoice Amount missing")
    elif invoice.invoice_amount <= 0:
        warnings.append("Invoice Amount must be greater than 0")

    # 4. Receiver Name missing
    if not invoice.receiver_name or not invoice.receiver_name.strip():
        warnings.append("Receiver Name missing")

    # 5. Receiver Address missing
    if not invoice.receiver_address or not invoice.receiver_address.strip():
        warnings.append("Receiver Address missing")

    # 6. Pincode missing / invalid
    pincode = str(invoice.receiver_pincode or "").strip()
    if not pincode:
        warnings.append("Pincode missing")
    elif not (len(pincode) == 6 and pincode.isdigit()):
        warnings.append(f"Invalid Pincode '{pincode}' (must be 6 digits)")

    # 7. Mobile missing / invalid
    mobile = str(invoice.receiver_mobile or "").strip()
    if not mobile:
        warnings.append("Mobile number missing")
    elif not (len(mobile) == 10 and mobile.isdigit()):
        warnings.append(f"Invalid Mobile '{mobile}' (must be 10 digits)")

    # 8. E-Way Bill missing
    if not invoice.eway_bill_number or not invoice.eway_bill_number.strip():
        warnings.append("E-Way Bill missing")

    # 9. Box information missing
    if not invoice.boxes or len(invoice.boxes) == 0:
        warnings.append("Box information missing")
    else:
        if any(b.quantity is None or b.quantity <= 0 for b in invoice.boxes):
            warnings.append("Box quantity missing")
        for index, box in enumerate(invoice.boxes, 1):
            if any(value is None or value <= 0 for value in (box.length, box.width, box.height, box.weight)):
                warnings.append(f"Box {index} dimensions/weight missing or invalid")

    # Validation warnings describe current fields; recompute them after edits.
    validation_prefixes = (
        "Invoice Number missing", "Order ID missing", "Duplicate Order_ID",
        "Invoice Amount missing", "Invoice Amount must", "Receiver Name missing",
        "Receiver Address missing", "Pincode missing", "Invalid Pincode",
        "Mobile number missing", "Invalid Mobile", "E-Way Bill missing",
        "Box information missing", "Box quantity missing",
    )
    for w in invoice.warnings:
        if w.startswith(validation_prefixes):
            continue
        if re.fullmatch(r'Box \d+ dimensions/weight missing or invalid', w):
            continue
        if w.startswith("Box data missing") and invoice.boxes:
            continue
        if w.startswith("Order_ID could not be identified") and invoice.order_id:
            continue
        if w.startswith("PO number missing - using Invoice Number") and invoice.po_number.strip():
            continue
        if w not in warnings:
            warnings.append(w)
            
    invoice.warnings = warnings

    # Assign Status:
    # Failed if critical fields (Invoice No, Order ID, Invoice Amount) are missing
    critical_missing = (
        not invoice.invoice_number or 
        not invoice.order_id or 
        invoice.invoice_amount is None or 
        invoice.invoice_amount <= 0
    )
    
    if critical_missing:
        invoice.status = "Failed"
    elif len(warnings) > 0:
        invoice.status = "Review Required"
    else:
        invoice.status = "Ready"

    return invoice


def validate_batch(invoices: List[InvoiceData]) -> List[InvoiceData]:
    """Validate a batch of invoices and detect cross-batch duplicate Order_IDs."""
    counts = Counter(inv.order_id for inv in invoices if inv.order_id)
    duplicate_ids = {order_id for order_id, count in counts.items() if count > 1}
    validated: List[InvoiceData] = []
    
    for inv in invoices:
        val_inv = validate_invoice(inv, duplicate_ids)
        validated.append(val_inv)
        
    return validated
