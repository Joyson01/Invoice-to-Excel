"""Main extraction orchestrator.

Pipeline:
    PDF path
    → pdfplumber text extraction (per page)
    → invoice segmentation (group pages by invoice number)
    → field extraction (invoice no, amount, PO, etc.)
    → address extraction (shipped-to / billed-to)
    → phone normalization
    → pincode extraction
    → line item extraction (merged across pages)
    → normalization into InvoiceData
    → validation & confidence scoring
    → list[InvoiceData]
"""

import logging
import os
from collections import defaultdict
from typing import Any

from app.config import settings
from app.extraction.address_parser import extract_address_blocks
from app.extraction.field_parser import (
    extract_boxes,
    extract_contact,
    extract_date,
    extract_eway_bill,
    extract_invoice_number,
    extract_net_amount,
    extract_po_number,
    extract_receiver,
)
from app.extraction.line_items import extract_grand_total_qty, extract_line_items
from app.extraction.normalizer import normalize_invoice_data
from app.extraction.pdf_extractor import extract_pdf_data
from app.extraction.phone_normalizer import clean_phone
from app.extraction.pincode_validator import extract_pincode
from app.models.schemas import InvoiceData
from app.validation.validators import validate_invoice

log = logging.getLogger(__name__)


def process_pdf(path: str) -> list[InvoiceData]:
    """Process a single PDF file and return extracted invoice data.

    Handles:
    - Multi-page invoices (same invoice number → merged)
    - Multiple invoices in one PDF (different invoice numbers → separate)
    - Error isolation per page
    """
    try:
        pages_data = extract_pdf_data(path)
    except Exception as exc:
        log.error("Cannot extract PDF %s: %s", path, exc)
        return []

    if not pages_data:
        log.warning("No pages extracted from %s", path)
        return []

    source_file = os.path.basename(path)

    # Group pages by invoice number
    invoices_raw: dict[str, dict[str, Any]] = {}
    page_order: dict[str, list[int]] = defaultdict(list)

    for pd in pages_data:
        text = pd["text"]
        page_num = pd["page_number"]

        if not text.strip():
            log.debug("Page %d of %s has no text (may be scanned)", page_num, source_file)
            continue

        inv_no, inv_conf = extract_invoice_number(text)
        if not inv_no:
            log.debug("No invoice number found on page %d of %s", page_num, source_file)
            continue

        page_order[inv_no].append(page_num)

        if inv_no not in invoices_raw:
            # First page of this invoice - extract header fields
            inv: dict[str, Any] = {
                "source_file": source_file,
                "invoice_number": inv_no,
                "invoice_number_conf": inv_conf,
                "line_items": [],
                "warnings": [],
            }

            # Net amount
            val, conf = extract_net_amount(text)
            if val is not None:
                inv["net_amount"] = val
                inv["net_amount_conf"] = conf

            # PO number
            val, conf = extract_po_number(text)
            if val:
                inv["po_number"] = val
                inv["po_number_conf"] = conf
            else:
                inv.setdefault("warnings", []).append(
                    "PO NO missing - falling back to invoice number for Order_ID"
                )

            # E-Way Bill
            val, conf = extract_eway_bill(text)
            if val:
                inv["eway_bill"] = val
                inv["eway_bill_conf"] = conf

            # Date
            val, conf = extract_date(text)
            if val:
                inv["invoice_date"] = val
                inv["invoice_date_conf"] = conf

            # Box count
            val, conf = extract_boxes(text)
            if val is not None:
                inv["boxes"] = val
                inv["boxes_conf"] = conf

            # Receiver name
            val, conf = extract_receiver(text)
            if val:
                inv["receiver_name"] = val
                inv["receiver_name_conf"] = conf

            # Contact number
            val, conf = extract_contact(text)
            if val:
                phones = clean_phone(val)
                if phones:
                    inv["mobile"] = phones[0]

            # Address extraction (uses word positions)
            blocks = extract_address_blocks(pd)
            address_lines = blocks.get(settings.ADDRESS_SOURCE, [])
            if address_lines:
                inv["address"] = "\n".join(address_lines)
                pin = extract_pincode(inv["address"])
                if pin:
                    inv["pincode"] = pin

            # Grand total quantity
            gtq = extract_grand_total_qty(text)
            if gtq:
                inv["grand_total_qty"] = gtq

            invoices_raw[inv_no] = inv
        else:
            # Additional page - check for fields not found on first page
            inv = invoices_raw[inv_no]

            # E-Way Bill might be on a later page
            if not inv.get("eway_bill"):
                val, conf = extract_eway_bill(text)
                if val:
                    inv["eway_bill"] = val
                    inv["eway_bill_conf"] = conf

        # Line items from every page (they span pages)
        items = extract_line_items(text)
        invoices_raw[inv_no]["line_items"].extend(items)

    # Post-processing: validate grand total qty vs line items
    for inv_no, inv in invoices_raw.items():
        items = inv.get("line_items", [])
        gtq = inv.get("grand_total_qty")
        if gtq and items:
            item_total = sum(i.quantity for i in items)
            if item_total != gtq:
                inv.setdefault("warnings", []).append(
                    f"line-item qty {item_total} != Grand Total {gtq}"
                )

    # Normalize and validate
    results: list[InvoiceData] = []
    for inv_no, data in invoices_raw.items():
        try:
            normalized = normalize_invoice_data(data)
            validated = validate_invoice(normalized)
            results.append(validated)
        except Exception as exc:
            log.error("Failed to normalize invoice %s from %s: %s", inv_no, source_file, exc)

    return results


def process_multiple_pdfs(paths: list[str]) -> list[InvoiceData]:
    """Process multiple PDF files and detect duplicates across them."""
    all_invoices: list[InvoiceData] = []
    seen_order_ids: set[str] = set()

    for path in paths:
        try:
            invoices = process_pdf(path)
            for inv in invoices:
                oid = inv.order_id.value
                if oid in seen_order_ids:
                    inv.warnings.append(f"duplicate Order_ID {oid}")
                    inv.status = "review_required"
                else:
                    seen_order_ids.add(oid)
                all_invoices.append(inv)
        except Exception as exc:
            log.error("FAILED processing %s: %s", os.path.basename(path), exc)

    return all_invoices
