import re
from typing import Tuple, Optional

def extract_invoice_number(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"Invoice\s*No\.?\s*:\s*(\S+)", re.IGNORECASE),
        re.compile(r"Invoice\s*Number\s*:\s*(\S+)", re.IGNORECASE),
        re.compile(r"Invoice\s*#\s*(\S+)", re.IGNORECASE),
        re.compile(r"Tax\s*Invoice\s*No\s*(\S+)", re.IGNORECASE),
        re.compile(r"InvoiceNo\.:?(\S+)", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_net_amount(text: str) -> Tuple[Optional[float], float]:
    patterns = [
        re.compile(r"NET\s*BILL\s*AMOUNT\s*:?\s*([\d,]+\.?\d*)", re.IGNORECASE),
        re.compile(r"Grand\s*Total\s*:?\s*([\d,]+\.?\d*)", re.IGNORECASE),
        re.compile(r"Total\s*Invoice\s*Value\s*:?\s*([\d,]+\.?\d*)", re.IGNORECASE),
        re.compile(r"Net\s*Amount\s*:?\s*([\d,]+\.?\d*)", re.IGNORECASE),
        re.compile(r"Amount\s*Payable\s*:?\s*([\d,]+\.?\d*)", re.IGNORECASE),
        re.compile(r"Invoice\s*Total\s*:?\s*([\d,]+\.?\d*)", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            val = m.group(1).replace(",", "")
            try:
                return float(val), 1.0
            except ValueError:
                pass
    return None, 0.0

def extract_po_number(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"PO\s*NO\.?\s*:\s*(\S+?)(?:\s{2,}|\s*CONTACT|$)", re.IGNORECASE),
        re.compile(r"PO\s*Number\s*:\s*(\S+)", re.IGNORECASE),
        re.compile(r"Purchase\s*Order\s*:\s*(\S+)", re.IGNORECASE),
        re.compile(r"Order\s*Number\s*:\s*(\S+)", re.IGNORECASE),
        re.compile(r"PONo:\s*(\S+)", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_eway_bill(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"E-?\s*way\s*(?:Bill)?\s*(?:No\.?|Number)?\s*:?\s*(\d{12})", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_date(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"Dated\s*:\s*([\d]{2}[-/][\d]{2}[-/][\d]{4})", re.IGNORECASE),
        re.compile(r"Date\s*:\s*([\d]{2}\.[\d]{2}\.[\d]{4})", re.IGNORECASE),
        re.compile(r"Invoice\s*Date\s*:\s*([\d]{2}[-/\.][\d]{2}[-/\.][\d]{4})", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_boxes(text: str) -> Tuple[Optional[int], float]:
    patterns = [
        re.compile(r"NO\.?\s*OF\s*BOXES\s*:?\s*(\d+)", re.IGNORECASE),
        re.compile(r"No\.\s*of\s*Boxes\s*:?\s*(\d+)", re.IGNORECASE),
        re.compile(r"Number\s*of\s*Boxes\s*:?\s*(\d+)", re.IGNORECASE),
        re.compile(r"Boxes\s*:?\s*(\d+)", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return int(m.group(1)), 1.0
    return None, 0.0

def extract_receiver(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"RECEIVER\s*NAME\s*:?\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"Consignee\s*:?\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_contact(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"CONTACT\s*NO\.?\s*:?\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"Phone\s*:?\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"Mobile\s*:?\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"Tel\.?\s*No\.?\s*:?\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0
