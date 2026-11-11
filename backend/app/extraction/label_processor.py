import re
import io
import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter

log = logging.getLogger(__name__)

AWB_PATTERNS = [
    r"Shipment\s*:\s*([A-Z]{0,3}\d{8,})",
    r"AWB\s*(?:No\.?|Number)?\s*:?\s*([A-Z]{0,3}\d{8,})",
    r"Waybill\s*(?:No\.?|Number)?\s*:?\s*([A-Z]{0,3}\d{8,})",
    r"Tracking\s*(?:ID|No\.?|Number)?\s*:?\s*([A-Z]{0,3}\d{8,})",
]
PACKAGE_PATTERN = r"\b([A-Z]{0,3}\d{8,})(\d{3})\b"
TOTAL_PACKAGES_PATTERN = r"Total\s*Packages\s*:\s*(\d+)"

@dataclass
class PageInfo:
    index: int
    awb: str = ""
    package: str = ""
    total_packages: str = ""
    note: str = ""

def _first_match(text: str, patterns: list[str]) -> str:
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).strip()
    return ""

def process_labels(input_path: str, output_pdf_path: str, output_csv_path: str) -> dict:
    pages_info = []
    
    with pdfplumber.open(input_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            p = PageInfo(index=i)

            if not text.strip():
                p.note = "no text layer - kept"
                pages_info.append(p)
                continue

            pkg_match = re.search(PACKAGE_PATTERN, text)
            if pkg_match:
                p.package = pkg_match.group(1) + pkg_match.group(2)

            p.awb = _first_match(text, AWB_PATTERNS)
            if not p.awb and pkg_match:
                p.awb = pkg_match.group(1)
                p.note = "AWB derived from package barcode"
            if not p.awb:
                p.note = "no AWB found - kept"

            tot = re.search(TOTAL_PACKAGES_PATTERN, text, re.I)
            if tot:
                p.total_packages = tot.group(1)

            pages_info.append(p)

    # Choose first label per AWB
    chosen = {}
    unkeyed = []
    for p in pages_info:
        if not p.awb:
            unkeyed.append(p)
            continue
        if p.awb not in chosen:
            chosen[p.awb] = p
            
    selected = list(chosen.values()) + unkeyed
    selected.sort(key=lambda p: p.index)
    sel_ids = {p.index for p in selected}

    # Write PDF
    writer = PdfWriter()
    reader = PdfReader(input_path)
    for p in selected:
        writer.add_page(reader.pages[p.index])
        
    with open(output_pdf_path, "wb") as fh:
        writer.write(fh)

    # Write Manifest
    with open(output_csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["page", "awb", "package", "total_packages", "kept", "note"])
        for p in pages_info:
            w.writerow([
                p.index + 1, p.awb, p.package, p.total_packages,
                "YES" if p.index in sel_ids else "", p.note
            ])

    return {
        "total_in": len(pages_info),
        "total_out": len(selected),
        "awbs_found": len(chosen)
    }
