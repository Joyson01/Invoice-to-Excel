"""Comprehensive field validation and confidence scoring for invoice data."""

import logging

from app.models.schemas import InvoiceData

log = logging.getLogger(__name__)


def validate_invoice(invoice: InvoiceData) -> InvoiceData:
    """Validate all fields of an invoice and set status/warnings."""
    warnings = list(invoice.warnings)  # Preserve existing warnings

    # --- Order ID ---
    if not invoice.order_id.value or invoice.order_id.value == "UNKNOWN":
        invoice.order_id.status = "invalid"
        invoice.order_id.confidence = 0.0
        invoice.order_id.message = "Order ID could not be determined"
        warnings.append("Order ID missing")

    # --- Invoice Number ---
    if not invoice.invoice_number.value:
        invoice.invoice_number.status = "missing"
        invoice.invoice_number.confidence = 0.0
        invoice.invoice_number.message = "Invoice number not found"
        warnings.append("Invoice number missing")

    # --- Invoice Amount ---
    amt = invoice.invoice_amount.value
    if amt is None or amt == "":
        invoice.invoice_amount.status = "missing"
        invoice.invoice_amount.confidence = 0.0
        invoice.invoice_amount.message = "Invoice amount not extracted"
        warnings.append("NET BILL AMOUNT not found")
    else:
        try:
            numeric_amt = float(amt)
            if numeric_amt <= 0:
                invoice.invoice_amount.status = "warning"
                invoice.invoice_amount.message = "Invoice amount is zero or negative"
                warnings.append("Invoice amount is zero or negative")
        except (ValueError, TypeError):
            invoice.invoice_amount.status = "invalid"
            invoice.invoice_amount.message = "Invoice amount is not numeric"
            warnings.append("Invoice amount is not numeric")

    # --- Receiver Name ---
    if not invoice.receiver_name.value:
        invoice.receiver_name.status = "missing"
        invoice.receiver_name.confidence = 0.0
        invoice.receiver_name.message = "Receiver name not found"
        warnings.append("RECEIVER NAME not found")

    # --- Pincode ---
    pincode = str(invoice.receiver_pincode.value or "")
    if not pincode:
        invoice.receiver_pincode.status = "missing"
        invoice.receiver_pincode.confidence = 0.0
        invoice.receiver_pincode.message = "No pincode found in address block"
        warnings.append("no 6-digit pincode found in address block")
    elif len(pincode) != 6 or not pincode.isdigit():
        invoice.receiver_pincode.status = "invalid"
        invoice.receiver_pincode.confidence = 0.3
        invoice.receiver_pincode.message = f"Pincode '{pincode}' is not a valid 6-digit number"
        warnings.append(f"Pincode '{pincode}' is not a valid 6-digit number")

    # --- Mobile ---
    mobile = str(invoice.receiver_mobile.value or "")
    if not mobile:
        invoice.receiver_mobile.status = "missing"
        invoice.receiver_mobile.confidence = 0.0
        invoice.receiver_mobile.message = "Mobile number not found"
        warnings.append(f"receiver mobile not a 10-digit number ('{mobile}')")
    elif len(mobile) != 10 or not mobile.isdigit():
        invoice.receiver_mobile.status = "invalid"
        invoice.receiver_mobile.confidence = 0.3
        invoice.receiver_mobile.message = f"Mobile '{mobile}' is not a valid 10-digit number"
        warnings.append(f"receiver mobile not a 10-digit number ('{mobile}')")

    # --- Address ---
    if not invoice.receiver_address.value:
        invoice.receiver_address.status = "missing"
        invoice.receiver_address.confidence = 0.0
        invoice.receiver_address.message = "Address block empty"
        warnings.append("address block empty")

    # --- E-Way Bill ---
    if not invoice.eway_bill_number.value:
        invoice.eway_bill_number.status = "missing"
        invoice.eway_bill_number.confidence = 0.0
        invoice.eway_bill_number.message = "E-Way Bill number not found"
        warnings.append("E-Way Bill number not found")
    else:
        eway = str(invoice.eway_bill_number.value)
        if len(eway) != 12 or not eway.isdigit():
            invoice.eway_bill_number.status = "warning"
            invoice.eway_bill_number.confidence = 0.5
            invoice.eway_bill_number.message = "E-Way Bill may not be in expected format"

    # --- Boxes ---
    box_total = sum(b.quantity for b in invoice.boxes) if invoice.boxes else 0
    if box_total <= 0:
        warnings.append("Box quantity must be > 0")

    # --- Line Items ---
    if not invoice.line_items:
        warnings.append("no line items parsed")

    # --- Set overall status ---
    invoice.warnings = warnings

    has_critical = any(
        f.status in ("invalid", "missing")
        for f in [
            invoice.order_id,
            invoice.invoice_number,
            invoice.invoice_amount,
        ]
    )
    has_warnings = any(
        f.status in ("invalid", "missing", "warning")
        for f in [
            invoice.receiver_name,
            invoice.receiver_pincode,
            invoice.receiver_mobile,
            invoice.receiver_address,
            invoice.eway_bill_number,
        ]
    )

    if has_critical:
        invoice.status = "failed"
    elif has_warnings or warnings:
        invoice.status = "review_required"
    else:
        invoice.status = "ready"

    return invoice
