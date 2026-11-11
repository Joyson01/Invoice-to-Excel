#!/usr/bin/env python3
"""
Rajputana Agencies -> B2B bulk upload builder
=============================================

Reads a folder of Rajputana TAX INVOICE PDFs and produces the 3-sheet
B2B bulk upload workbook (Orders / Boxes / Invoice), preserving the
formatting of your existing template file.

Usage
-----
No arguments needed. Put the invoice PDFs in an "invoices" folder next to this
script, keep the template .xlsx alongside it, then:

    python rajputana_b2b_upload.py

    -> output/B2B_bulk_upload_05-09-2026_161230.xlsx
       output/B2B_bulk_upload_05-09-2026_161230_audit.csv

Every run writes a new, date-time stamped file, so nothing is ever overwritten.

Common options
--------------
    --input  PATH...       PDF file(s)/folder(s)     (default: ./invoices)
    --template FILE.xlsx   upload template           (default: auto-detected)
    --output PATH          file or folder            (default: ./output/)
    --workers 8            parallel PDF parsing      (default: CPU count)
    --split 500            write multiple workbooks, N orders each
    --overrides ov.csv     per-order overrides (see OVERRIDES below)
    --report report.csv    audit CSV path            (default: next to the workbook)
    --address billed       use Billed-to instead of Shipped-to
    --order-id invoice     key on invoice number instead of PO number

Dependencies:  pip install pdfplumber openpyxl
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import copy
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

import pdfplumber
import openpyxl

# ---------------------------------------------------------------------------
# CONFIG - static values that are not present on the invoice.
# Edit these once; they apply to every order.
# ---------------------------------------------------------------------------

VERSION = "1.4"

# --- paths / naming -------------------------------------------------------
# All three can be overridden on the command line, but with these defaults the
# script runs with no arguments at all:  python rajputana_b2b_upload.py
DEFAULT_INPUT_DIRNAME = "invoices"       # folder of PDFs to look for
DEFAULT_OUTPUT_DIRNAME = "output"        # where workbooks are written
OUTPUT_PREFIX = "B2B_bulk_upload"        # output file name prefix
TIMESTAMP_FORMAT = "%d-%m-%Y_%H%M%S"     # -> B2B_bulk_upload_05-09-2026_161230.xlsx
TEMPLATE_HINTS = ("b2b", "bulk", "template")   # used when auto-detecting the template

WAREHOUSE_NAME = "RAJPUTANA 001"
RECEIVER_EMAIL = "dummy@gmail.com"
PAYMENT_MODE = "Prepaid"
COD_VALUE = 0
INSURANCE = "Owner Risk"
INVOICE_URL = "https://cloud.mojoship.in/invoice_sample.png"
DELIVERY_CHALLAN = ""
DECLARATION = ""
OTHER_SUPPORTING_DOCUMENTS = ""

# Box dimensions are fixed for every box.
BOX_LENGTH, BOX_WIDTH, BOX_HEIGHT = 10, 10, 10
BOX_WEIGHT = 5              # KG

# How the Boxes sheet represents the box count:
#   "single"  -> one row per order (one AWB), Quantity = NO.OF BOXES   <-- current
#   "per_box" -> one row per box, Quantity = 1
BOX_ROW_MODE = "single"

# Order_description is synthesised from the line items.
DESCRIPTION_TEMPLATE = "{brand} products - {sku_count} SKUs, {total_qty} units"
BRAND_MAP = {                # first word of item description -> brand label
    "CET": "Cetaphil",
    "CETAPHIL": "Cetaphil",
}
DEFAULT_BRAND = "Assorted"

# OVERRIDES: optional CSV to supply real emails/COD/etc. per order.
# Header row must be: Order_ID plus any of the Orders sheet column names.
#   Order_ID,Receiver_Email,Payment_Mode,COD_Value
#   KOCPO140725,ops@scootsy.in,COD,169170

ORDER_COLUMNS = [
    "Order_ID", "Warehouse_Name", "Receiver_Name", "Receiver_Address",
    "Receiver_Pincode", "Receiver_Email", "Receiver_Mobile", "Order_description",
    "Payment_Mode", "COD_Value", "Insurance", "Invoice", "Delivery_Challan",
    "Declaration", "Other_Supporting_Documents",
]
BOX_COLUMNS = ["Order_ID", "Length", "Width", "Height", "Weight", "Quantity"]
INVOICE_COLUMNS = ["Order_ID", "Invoice_Number", "Invoice_Amount", "Invoice_Eway_Bill_Number"]

log = logging.getLogger("b2b")

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

RE_INVOICE_NO = re.compile(r"Invoice\s*No\.?\s*:\s*(\S+)")
RE_NET_BILL = re.compile(r"NET\s*BILL\s*AMOUNT\s*:?\s*([\d,]+\.?\d*)")
RE_DATED = re.compile(r"Dated\s*:\s*([\d]{2}[-/][\d]{2}[-/][\d]{4})")
RE_BOXES = re.compile(r"NO\.?\s*OF\s*BOXES\s*:?\s*(\d+)")
RE_PO_NO = re.compile(r"PO\s*NO\.?\s*:\s*(\S+?)(?:\s{2,}|\s*CONTACT|$)", re.I)
RE_RECEIVER = re.compile(r"RECEIVER\s*NAME\s*:?\s*(.+?)\s*$", re.M)
RE_CONTACT = re.compile(r"CONTACT\s*NO\.?\s*:?\s*(.+?)\s*$", re.M)
RE_PLACE = re.compile(r"Place\s*of\s*Supply\s*:\s*(.+?)\s*(?:WEIGHT|$)", re.M)
RE_EWAY = re.compile(r"E-?\s*way\s*(?:Bill)?\s*(?:No\.?|Number)?\s*:?\s*(\d{12})", re.I)
RE_GRAND_TOTAL_QTY = re.compile(r"Grand\s*Total\s+(\d+)")
RE_PINCODE = re.compile(r"\b(\d{6})\b")
# "1. CET GENTLE SKIN CLN 118ML C803 3304993 216 459.00 24 % 295.63 ..."
RE_ITEM = re.compile(
    r"^\s*\d+\.\s+(?P<desc>.+?)\s+(?P<item_code>[A-Z]{1,3}\d{2,5})\s+"
    r"(?P<hsn>\d{4,8})\s+(?P<qty>\d+)\s+(?P<mrp>[\d,]+\.\d{2})"
)


@dataclass
class LineItem:
    description: str
    item_code: str
    hsn: str
    qty: int
    mrp: float


@dataclass
class Invoice:
    source_file: str
    invoice_no: str = ""
    invoice_date: str = ""
    po_no: str = ""
    net_amount: float = 0.0
    boxes: int = 0
    receiver_name: str = ""
    contact_numbers: list[str] = field(default_factory=list)
    place_of_supply: str = ""
    address_lines: list[str] = field(default_factory=list)
    pincode: str = ""
    eway_bill: str = ""
    items: list[LineItem] = field(default_factory=list)
    grand_total_qty: int | None = None
    warnings: list[str] = field(default_factory=list)

    # -- derived -----------------------------------------------------------
    @property
    def order_id_from_po(self) -> str:
        return self.po_no or self.invoice_no

    @property
    def total_qty(self) -> int:
        s = sum(i.qty for i in self.items)
        return s or (self.grand_total_qty or 0)

    @property
    def sku_count(self) -> int:
        return len(self.items)

    @property
    def address(self) -> str:
        return "\n".join(self.address_lines)

    @property
    def mobile(self) -> str:
        return self.contact_numbers[0] if self.contact_numbers else ""

    @property
    def brand(self) -> str:
        for it in self.items:
            first = it.description.split()[0].upper().strip(".,-") if it.description else ""
            if first in BRAND_MAP:
                return BRAND_MAP[first]
        if self.items:
            return self.items[0].description.split()[0].title()
        return DEFAULT_BRAND

    @property
    def description(self) -> str:
        return DESCRIPTION_TEMPLATE.format(
            brand=self.brand, sku_count=self.sku_count, total_qty=self.total_qty
        )


def _clean_phone(raw: str) -> list[str]:
    """'7356976268 /99953 23357' -> ['7356976268', '9995323357']"""
    out: list[str] = []
    for chunk in re.split(r"[/,;|]| {2,}", raw):
        digits = re.sub(r"\D", "", chunk)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) == 10 and digits not in out:
            out.append(digits)
    if not out:  # fall back: strip everything and window 10-digit runs
        digits = re.sub(r"\D", "", raw)
        for i in range(0, max(1, len(digits) - 9), 10):
            d = digits[i:i + 10]
            if len(d) == 10:
                out.append(d)
    return out


def _extract_address(page, prefer: str = "shipped") -> list[str]:
    """Crop the Billed-to / Shipped-to block by x-position and read one column."""
    words = page.extract_words()
    anchor = next((w for w in words if w["text"].strip().lower().startswith("shipped")), None)
    header = next((w for w in words if w["text"].strip().lower().startswith("billed")), None)
    if not header:
        return []
    top = header["bottom"] + 1
    pan = next((w for w in words if w["text"].strip().lower().startswith("party") and w["top"] > top), None)
    bottom = pan["top"] - 1 if pan else top + 120

    if anchor:
        if prefer == "shipped":
            bbox = (anchor["x0"] - 4, top, page.width, bottom)
        else:
            bbox = (0, top, anchor["x0"] - 4, bottom)
    else:  # single column layout
        bbox = (0, top, page.width, bottom)

    text = page.crop(bbox).extract_text() or ""
    lines = [ln.strip().rstrip(",") for ln in text.splitlines() if ln.strip()]
    return lines


def parse_pdf(path: str, prefer_address: str = "shipped") -> list[Invoice]:
    """Parse one PDF. Returns one Invoice per distinct invoice number
    (multi-page invoices are merged; multi-invoice PDFs are split)."""
    found: dict[str, Invoice] = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            m = RE_INVOICE_NO.search(text)
            if not m:
                continue
            inv_no = m.group(1).strip()
            inv = found.get(inv_no)
            if inv is None:
                inv = Invoice(source_file=os.path.basename(path), invoice_no=inv_no)
                found[inv_no] = inv

                if (mm := RE_NET_BILL.search(text)):
                    inv.net_amount = float(mm.group(1).replace(",", ""))
                if (mm := RE_DATED.search(text)):
                    inv.invoice_date = mm.group(1)
                if (mm := RE_BOXES.search(text)):
                    inv.boxes = int(mm.group(1))
                if (mm := RE_PO_NO.search(text)):
                    inv.po_no = mm.group(1).strip()
                if (mm := RE_RECEIVER.search(text)):
                    inv.receiver_name = mm.group(1).strip()
                if (mm := RE_CONTACT.search(text)):
                    inv.contact_numbers = _clean_phone(mm.group(1))
                if (mm := RE_PLACE.search(text)):
                    inv.place_of_supply = mm.group(1).strip()
                if (mm := RE_EWAY.search(text)):
                    inv.eway_bill = mm.group(1)
                if (mm := RE_GRAND_TOTAL_QTY.search(text)):
                    inv.grand_total_qty = int(mm.group(1))

                inv.address_lines = _extract_address(page, prefer_address)
                joined = " ".join(inv.address_lines)
                if (mm := RE_PINCODE.search(joined)):
                    inv.pincode = mm.group(1)

            # line items may continue on later pages
            for line in text.splitlines():
                im = RE_ITEM.match(line)
                if im:
                    inv.items.append(LineItem(
                        description=im.group("desc").strip(),
                        item_code=im.group("item_code"),
                        hsn=im.group("hsn"),
                        qty=int(im.group("qty")),
                        mrp=float(im.group("mrp").replace(",", "")),
                    ))

    for inv in found.values():
        _validate(inv)
    return list(found.values())


def _validate(inv: Invoice) -> None:
    if not inv.po_no:
        inv.warnings.append("PO NO missing - falling back to invoice number for Order_ID")
    if not inv.boxes:
        inv.warnings.append("NO.OF BOXES missing or zero - no rows written to Boxes sheet")
    if not inv.net_amount:
        inv.warnings.append("NET BILL AMOUNT not found")
    if not inv.receiver_name:
        inv.warnings.append("RECEIVER NAME not found")
    if len(inv.mobile) != 10:
        inv.warnings.append(f"receiver mobile not a 10-digit number ({inv.mobile!r})")
    if not inv.pincode:
        inv.warnings.append("no 6-digit pincode found in address block")
    if not inv.address_lines:
        inv.warnings.append("address block empty")
    if not inv.items:
        inv.warnings.append("no line items parsed")
    if inv.grand_total_qty and inv.items and sum(i.qty for i in inv.items) != inv.grand_total_qty:
        inv.warnings.append(
            f"line-item qty {sum(i.qty for i in inv.items)} != Grand Total {inv.grand_total_qty}")


def _parse_worker(args: tuple[str, str]) -> tuple[str, list[dict[str, Any]], str]:
    path, prefer = args
    try:
        return path, [_to_dict(i) for i in parse_pdf(path, prefer)], ""
    except Exception as exc:                                   # noqa: BLE001
        return path, [], f"{type(exc).__name__}: {exc}"


def _to_dict(inv: Invoice) -> dict[str, Any]:
    d = asdict(inv)
    d["items"] = [asdict(i) for i in inv.items]
    return d


def _from_dict(d: dict[str, Any]) -> Invoice:
    items = [LineItem(**i) for i in d.pop("items", [])]
    inv = Invoice(**d)
    inv.items = items
    return inv


# ---------------------------------------------------------------------------
# Row building
# ---------------------------------------------------------------------------

def build_rows(invoices: list[Invoice], order_id_source: str = "po",
               overrides: dict[str, dict[str, Any]] | None = None
               ) -> tuple[list[list], list[list], list[list]]:
    overrides = overrides or {}
    orders, boxes, inv_rows = [], [], []
    seen: set[str] = set()

    for inv in invoices:
        oid = inv.invoice_no if order_id_source == "invoice" else inv.order_id_from_po
        if oid in seen:
            inv.warnings.append(f"duplicate Order_ID {oid} - skipped")
            log.warning("duplicate Order_ID %s (%s) - skipped", oid, inv.source_file)
            continue
        seen.add(oid)

        row = {
            "Order_ID": oid,
            "Warehouse_Name": WAREHOUSE_NAME,
            "Receiver_Name": inv.receiver_name,
            "Receiver_Address": inv.address,
            "Receiver_Pincode": int(inv.pincode) if inv.pincode.isdigit() else inv.pincode,
            "Receiver_Email": RECEIVER_EMAIL,
            "Receiver_Mobile": int(inv.mobile) if inv.mobile.isdigit() else inv.mobile,
            "Order_description": inv.description,
            "Payment_Mode": PAYMENT_MODE,
            "COD_Value": COD_VALUE,
            "Insurance": INSURANCE,
            "Invoice": INVOICE_URL,
            "Delivery_Challan": DELIVERY_CHALLAN,
            "Declaration": DECLARATION,
            "Other_Supporting_Documents": OTHER_SUPPORTING_DOCUMENTS,
        }
        row.update({k: v for k, v in overrides.get(oid, {}).items() if k in row})
        orders.append([row[c] for c in ORDER_COLUMNS])

        if BOX_ROW_MODE == "per_box":
            for _ in range(inv.boxes):
                boxes.append([oid, BOX_LENGTH, BOX_WIDTH, BOX_HEIGHT, BOX_WEIGHT, 1])
        elif inv.boxes:                       # "single": one AWB -> one row
            boxes.append([oid, BOX_LENGTH, BOX_WIDTH, BOX_HEIGHT, BOX_WEIGHT, inv.boxes])

        amount = round(inv.net_amount, 2)
        inv_rows.append([oid, inv.invoice_no,
                         int(amount) if amount == int(amount) else amount,
                         inv.eway_bill])

    return orders, boxes, inv_rows


def load_overrides(path: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            oid = (r.get("Order_ID") or "").strip()
            if not oid:
                continue
            vals = {}
            for k, v in r.items():
                if k == "Order_ID" or v in (None, ""):
                    continue
                if k in ("COD_Value", "Receiver_Pincode", "Receiver_Mobile"):
                    try:
                        v = int(str(v).strip())
                    except ValueError:
                        pass
                vals[k] = v
            out[oid] = vals
    log.info("loaded %d override rows from %s", len(out), path)
    return out


# ---------------------------------------------------------------------------
# Excel writing (preserves the template's styling)
# ---------------------------------------------------------------------------

def _fill_sheet(ws, rows: list[list], columns: list[str]) -> None:
    header = [c.value for c in ws[1]]
    if [h for h in header if h] != columns:
        log.warning("sheet %r header %s differs from expected %s", ws.title, header, columns)

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


def write_workbook(template: str, output: str, orders, boxes, invoices) -> None:
    wb = openpyxl.load_workbook(template)
    for name, rows, cols in (("Orders", orders, ORDER_COLUMNS),
                             ("Boxes", boxes, BOX_COLUMNS),
                             ("Invoice", invoices, INVOICE_COLUMNS)):
        ws = resolve_sheet(wb, name)
        if ws is None:
            raise SystemExit(f"template {template!r} has no sheet named {name!r} "
                             f"(it has: {wb.sheetnames})")
        _fill_sheet(ws, rows, cols)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)
    log.info("wrote %s  (%d orders, %d boxes, %d invoices)",
             output, len(orders), len(boxes), len(invoices))


def write_report(path: str, invoices: list[Invoice], order_id_source: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source_file", "invoice_no", "order_id", "date", "receiver_name",
                    "mobile", "pincode", "boxes", "skus", "units", "net_amount",
                    "eway_bill", "warnings"])
        for inv in invoices:
            oid = inv.invoice_no if order_id_source == "invoice" else inv.order_id_from_po
            w.writerow([inv.source_file, inv.invoice_no, oid, inv.invoice_date,
                        inv.receiver_name, inv.mobile, inv.pincode, inv.boxes,
                        inv.sku_count, inv.total_qty, inv.net_amount, inv.eway_bill,
                        " | ".join(inv.warnings)])
    log.info("wrote audit report %s", path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def find_pdfs(inputs: Iterable[str], recursive: bool = True) -> list[str]:
    files: list[str] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files.extend(str(f) for f in (p.rglob("*.pdf") if recursive else p.glob("*.pdf")))
        elif p.is_file():
            files.append(str(p))
        else:
            log.warning("not found: %s", item)
    return sorted(set(files))


def _chunk(seq: list, n: int) -> list[list]:
    return [seq[i:i + n] for i in range(0, len(seq), n)] or [[]]


BASE_DIR = Path(__file__).resolve().parent


def _search_dirs() -> list[Path]:
    """Look next to the script and in the current working directory."""
    seen, out = set(), []
    for d in (Path.cwd(), BASE_DIR):
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def default_input() -> list[str]:
    """<cwd>/invoices, <script dir>/invoices, then the folders themselves."""
    for d in _search_dirs():
        cand = d / DEFAULT_INPUT_DIRNAME
        if cand.is_dir() and any(cand.rglob("*.pdf")):
            return [str(cand)]
    for d in _search_dirs():
        if any(d.glob("*.pdf")):
            return [str(d)]
    # nothing found - return the conventional path so the error message is useful
    return [str(Path.cwd() / DEFAULT_INPUT_DIRNAME)]


REQUIRED_SHEETS = {"orders", "boxes", "invoice"}


def resolve_sheet(wb, name: str):
    """Sheet lookup that tolerates different capitalisation / stray spaces."""
    want = name.strip().lower()
    for actual in wb.sheetnames:
        if actual.strip().lower() == want:
            return wb[actual]
    return None


def _check_template(path: Path) -> tuple[bool, str]:
    """(usable, reason-if-not)"""
    try:
        wb = openpyxl.load_workbook(path, read_only=True)
    except Exception as exc:                                   # noqa: BLE001
        return False, f"could not be opened ({type(exc).__name__}) - is it open in Excel?"
    names = list(wb.sheetnames)
    wb.close()
    have = {n.strip().lower() for n in names}
    missing = REQUIRED_SHEETS - have
    if missing:
        return False, (f"sheets are {names} - missing "
                       + ", ".join(sorted(m.title() for m in missing)))
    return True, ""


def _looks_like_generated_output(name: str) -> bool:
    """Only skip files this script itself wrote, e.g.
    B2B_bulk_upload_05-09-2026_161230.xlsx  /  ..._part2.xlsx
    A file merely starting with the prefix (B2B_bulk_upload_file_filled.xlsx)
    is NOT excluded - it is perfectly usable as a template."""
    return bool(re.match(rf"^{re.escape(OUTPUT_PREFIX)}_\d{{2}}-\d{{2}}-\d{{4}}_\d{{6}}"
                         r"(_part\d+)?\.xls[xm]$", name, re.I))


def _template_candidates() -> list[Path]:
    """Spreadsheets next to the script / in the current folder, and one level down."""
    out: list[Path] = []
    for d in _search_dirs():
        dirs = [d] + [s for s in sorted(d.iterdir()) if s.is_dir()
                      and s.name not in (DEFAULT_OUTPUT_DIRNAME, DEFAULT_INPUT_DIRNAME)
                      and not s.name.startswith(".")] if d.is_dir() else [d]
        for sub in dirs:
            for pat in ("*.xlsx", "*.xlsm"):
                for f in sorted(sub.glob(pat)):
                    if f.name.startswith("~$") or _looks_like_generated_output(f.name):
                        continue
                    if f not in out:
                        out.append(f)
    out.sort(key=lambda f: 0 if any(h in f.name.lower() for h in TEMPLATE_HINTS) else 1)
    return out


def default_template() -> tuple[str | None, list[str]]:
    """Find a template with Orders/Boxes/Invoice sheets. Returns (path, notes)."""
    notes: list[str] = []
    candidates = _template_candidates()
    for f in candidates:
        ok, why = _check_template(f)
        if ok:
            return str(f), notes
        notes.append(f"skipped {f.name}: {why}")
    if not candidates:
        legacy = [f for d in _search_dirs() if d.is_dir() for f in sorted(d.glob("*.xls"))]
        if legacy:
            notes.append(f"found {legacy[0].name} - old .xls format; "
                         "open it in Excel and Save As .xlsx")
        else:
            notes.append("no .xlsx files at all in this folder")
    return None, notes


def _dump_folders(level=logging.ERROR) -> None:
    """Print what the script can actually see - the fastest way to spot a
    misplaced file, a wrong extension, or a folder the script isn't looking in."""
    for d in _search_dirs():
        log.log(level, "contents of %s:", d)
        try:
            entries = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as exc:
            log.log(level, "    <cannot list: %s>", exc)
            continue
        if not entries:
            log.log(level, "    <empty>")
        for p in entries:
            if p.is_dir():
                n = len(list(p.glob("*.pdf")))
                log.log(level, "    [DIR ] %s%s", p.name, f"   ({n} pdf)" if n else "")
            else:
                log.log(level, "    [FILE] %s   (%s bytes)", p.name, p.stat().st_size)


def doctor() -> int:
    """--doctor: report everything needed to diagnose a failing run."""
    log.info("--- doctor ---")
    for mod in ("pdfplumber", "openpyxl"):
        try:
            m = __import__(mod)
            log.info("%-12s %s", mod, getattr(m, "__version__", "installed"))
        except Exception as exc:                               # noqa: BLE001
            log.error("%-12s NOT INSTALLED (%s)", mod, exc)
    log.info("cwd          %s", Path.cwd())
    log.info("script dir   %s", BASE_DIR)
    _dump_folders(logging.INFO)
    pdfs = find_pdfs(default_input())
    log.info("PDFs found   %d", len(pdfs))
    for p in pdfs[:10]:
        log.info("    %s", p)
    cands = _template_candidates()
    log.info("spreadsheets considered as template: %d", len(cands))
    for c in cands:
        ok, why = _check_template(c)
        log.info("    %s  ->  %s", c, "OK" if ok else why)
    return 0


def build_output_path(arg: str | None, stamp: str) -> str:
    """Always datestamp the file name; honour a folder or a name if given."""
    if arg is None:
        return str(Path.cwd() / DEFAULT_OUTPUT_DIRNAME / f"{OUTPUT_PREFIX}_{stamp}.xlsx")
    p = Path(arg)
    if p.is_dir() or arg.endswith(("/", os.sep)) or p.suffix == "":
        return str(p / f"{OUTPUT_PREFIX}_{stamp}.xlsx")
    return str(p.with_name(f"{p.stem}_{stamp}{p.suffix or '.xlsx'}"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build the B2B bulk upload workbook from Rajputana invoice PDFs.",
        epilog=f"With no arguments: reads ./{DEFAULT_INPUT_DIRNAME}, auto-detects the template "
               f"and writes ./{DEFAULT_OUTPUT_DIRNAME}/{OUTPUT_PREFIX}_<date>_<time>.xlsx",
    )
    ap.add_argument("--input", "-i", nargs="+",
                    help=f"PDF file(s) and/or folder(s). Default: ./{DEFAULT_INPUT_DIRNAME}")
    ap.add_argument("--template", "-t",
                    help="B2B bulk upload template .xlsx. Default: auto-detected")
    ap.add_argument("--output", "-o",
                    help="output .xlsx path or folder. A date-time stamp is always appended "
                         f"to the file name. Default: ./{DEFAULT_OUTPUT_DIRNAME}/")
    ap.add_argument("--workers", "-w", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--split", type=int, default=0, help="orders per output file (0 = single file)")
    ap.add_argument("--overrides", help="CSV of per-Order_ID overrides")
    ap.add_argument("--report", help="audit CSV path (default: alongside the workbook)")
    ap.add_argument("--no-report", action="store_true", help="skip the audit CSV")
    ap.add_argument("--address", choices=["shipped", "billed"], default="shipped")
    ap.add_argument("--order-id", choices=["po", "invoice"], default="po")
    ap.add_argument("--no-recursive", action="store_true")
    ap.add_argument("--doctor", action="store_true",
                    help="print what the script can see, then exit")
    ap.add_argument("--version", action="version", version=f"rajputana_b2b_upload {VERSION}")
    ap.add_argument("--quiet", "-q", action="store_true")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING if a.quiet else logging.INFO,
                        format="%(levelname)-7s %(message)s")

    log.info("rajputana_b2b_upload v%s  |  python %s  |  running from %s",
             VERSION, sys.version.split()[0], Path(__file__).resolve())

    if a.doctor:
        return doctor()

    stamp = datetime.now().strftime(TIMESTAMP_FORMAT)

    inputs = a.input or default_input()
    if not a.input:
        log.info("input folder   : %s", inputs[0])

    template = a.template
    if template:
        if not Path(template).exists():
            log.error("template not found: %s", template)
            return 1
        ok, why = _check_template(Path(template))
        if not ok:
            log.error("template %s %s", template, why)
            return 1
    else:
        template, notes = default_template()
        if not template:
            log.error("no usable template found.")
            for n in notes:
                log.error("  %s", n)
            log.error("")
            _dump_folders()
            log.error("Fix: put the 'B2B bulk upload file.xlsx' template in that folder, "
                      "or run:  python %s --template \"C:\\path\\to\\template.xlsx\"",
                      Path(__file__).name)
            return 1
        for n in notes:
            log.warning("  %s", n)
        log.info("template       : %s", template)

    output = build_output_path(a.output, stamp)
    log.info("output workbook: %s", output)

    pdfs = find_pdfs(inputs, recursive=not a.no_recursive)
    if not pdfs:
        log.error("no PDFs found in: %s", ", ".join(inputs))
        log.error("create that folder and drop the invoice PDFs in, or pass --input PATH")
        return 1
    log.info("parsing %d PDF(s) with %d worker(s)", len(pdfs), a.workers)

    invoices: list[Invoice] = []
    failures: list[tuple[str, str]] = []
    tasks = [(p, a.address) for p in pdfs]

    if a.workers > 1 and len(pdfs) > 1:
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(_parse_worker, t): t[0] for t in tasks}
            for n, fut in enumerate(as_completed(futs), 1):
                path, dicts, err = fut.result()
                if err:
                    failures.append((path, err))
                    log.error("FAILED %s: %s", os.path.basename(path), err)
                invoices.extend(_from_dict(d) for d in dicts)
                if not a.quiet and n % 100 == 0:
                    log.info("  ... %d/%d parsed", n, len(pdfs))
    else:
        for t in tasks:
            path, dicts, err = _parse_worker(t)
            if err:
                failures.append((path, err))
                log.error("FAILED %s: %s", os.path.basename(path), err)
            invoices.extend(_from_dict(d) for d in dicts)

    invoices.sort(key=lambda i: (i.invoice_date, i.invoice_no))
    log.info("parsed %d invoice(s) from %d file(s); %d file(s) failed",
             len(invoices), len(pdfs), len(failures))

    overrides = load_overrides(a.overrides) if a.overrides else {}
    orders, boxes, inv_rows = build_rows(invoices, a.order_id, overrides)

    written: list[str] = []
    if a.split and len(orders) > a.split:
        stem, ext = os.path.splitext(output)
        for n, chunk in enumerate(_chunk(orders, a.split), 1):
            ids = {r[0] for r in chunk}
            part = f"{stem}_part{n}{ext}"
            write_workbook(template, part, chunk,
                           [b for b in boxes if b[0] in ids],
                           [r for r in inv_rows if r[0] in ids])
            written.append(part)
    else:
        write_workbook(template, output, orders, boxes, inv_rows)
        written.append(output)

    if not a.no_report:
        report = a.report or str(Path(output).with_suffix("")) + "_audit.csv"
        write_report(report, invoices, a.order_id)

    warned = [i for i in invoices if i.warnings]
    if warned:
        log.warning("%d invoice(s) parsed with warnings - see the audit CSV", len(warned))
    print(f"\nDone. {len(orders)} order(s) written to:")
    for w in written:
        print(f"  {w}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
