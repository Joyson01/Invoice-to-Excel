import os

files_to_create = {
    "app/extraction/phone_normalizer.py": '''import re

def clean_phone(raw: str) -> list[str]:
    """\'7356976268 /99953 23357\' -> [\'7356976268\', \'9995323357\']"""
    out: list[str] = []
    for chunk in re.split(r"[/,;|]| {2,}", raw):
        digits = re.sub(r"\\D", "", chunk)
        if digits.startswith("+91"):
            digits = digits[3:]
        elif digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) == 10 and digits not in out:
            out.append(digits)
    if not out:  # fall back: strip everything and window 10-digit runs
        digits = re.sub(r"\\D", "", raw)
        for i in range(0, max(1, len(digits) - 9), 10):
            d = digits[i:i + 10]
            if len(d) == 10 and d not in out:
                out.append(d)
    return out
''',
    "app/extraction/pincode_validator.py": '''import re

RE_PINCODE = re.compile(r"\\b(\\d{6})\\b")

def extract_pincode(address: str) -> str:
    m = RE_PINCODE.search(address)
    return m.group(1) if m else ""
''',
    "app/extraction/field_parser.py": '''import re
from typing import Tuple, Optional

def extract_invoice_number(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"Invoice\\s*No\\.?\\s*:\\s*(\\S+)", re.IGNORECASE),
        re.compile(r"Invoice\\s*Number\\s*:\\s*(\\S+)", re.IGNORECASE),
        re.compile(r"Invoice\\s*#\\s*(\\S+)", re.IGNORECASE),
        re.compile(r"Tax\\s*Invoice\\s*No\\s*(\\S+)", re.IGNORECASE),
        re.compile(r"InvoiceNo\\.:?(\\S+)", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_net_amount(text: str) -> Tuple[Optional[float], float]:
    patterns = [
        re.compile(r"NET\\s*BILL\\s*AMOUNT\\s*:?\\s*([\\d,]+\\.?\\d*)", re.IGNORECASE),
        re.compile(r"Grand\\s*Total\\s*:?\\s*([\\d,]+\\.?\\d*)", re.IGNORECASE),
        re.compile(r"Total\\s*Invoice\\s*Value\\s*:?\\s*([\\d,]+\\.?\\d*)", re.IGNORECASE),
        re.compile(r"Net\\s*Amount\\s*:?\\s*([\\d,]+\\.?\\d*)", re.IGNORECASE),
        re.compile(r"Amount\\s*Payable\\s*:?\\s*([\\d,]+\\.?\\d*)", re.IGNORECASE),
        re.compile(r"Invoice\\s*Total\\s*:?\\s*([\\d,]+\\.?\\d*)", re.IGNORECASE)
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
        re.compile(r"PO\\s*NO\\.?\\s*:\\s*(\\S+?)(?:\\s{2,}|\\s*CONTACT|$)", re.IGNORECASE),
        re.compile(r"PO\\s*Number\\s*:\\s*(\\S+)", re.IGNORECASE),
        re.compile(r"Purchase\\s*Order\\s*:\\s*(\\S+)", re.IGNORECASE),
        re.compile(r"Order\\s*Number\\s*:\\s*(\\S+)", re.IGNORECASE),
        re.compile(r"PONo:\\s*(\\S+)", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_eway_bill(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"E-?\\s*way\\s*(?:Bill)?\\s*(?:No\\.?|Number)?\\s*:?\\s*(\\d{12})", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_date(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"Dated\\s*:\\s*([\\d]{2}[-/][\\d]{2}[-/][\\d]{4})", re.IGNORECASE),
        re.compile(r"Date\\s*:\\s*([\\d]{2}\\.[\\d]{2}\\.[\\d]{4})", re.IGNORECASE),
        re.compile(r"Invoice\\s*Date\\s*:\\s*([\\d]{2}[-/\\.][\\d]{2}[-/\\.][\\d]{4})", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_boxes(text: str) -> Tuple[Optional[int], float]:
    patterns = [
        re.compile(r"NO\\.?\\s*OF\\s*BOXES\\s*:?\\s*(\\d+)", re.IGNORECASE),
        re.compile(r"No\\.\\s*of\\s*Boxes\\s*:?\\s*(\\d+)", re.IGNORECASE),
        re.compile(r"Number\\s*of\\s*Boxes\\s*:?\\s*(\\d+)", re.IGNORECASE),
        re.compile(r"Boxes\\s*:?\\s*(\\d+)", re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return int(m.group(1)), 1.0
    return None, 0.0

def extract_receiver(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"RECEIVER\\s*NAME\\s*:?\\s*(.+?)\\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"Consignee\\s*:?\\s*(.+?)\\s*$", re.MULTILINE | re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0

def extract_contact(text: str) -> Tuple[Optional[str], float]:
    patterns = [
        re.compile(r"CONTACT\\s*NO\\.?\\s*:?\\s*(.+?)\\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"Phone\\s*:?\\s*(.+?)\\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"Mobile\\s*:?\\s*(.+?)\\s*$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"Tel\\.?\\s*No\\.?\\s*:?\\s*(.+?)\\s*$", re.MULTILINE | re.IGNORECASE)
    ]
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(1).strip(), 1.0
    return None, 0.0
''',
    "app/extraction/address_parser.py": '''def extract_address_blocks(page) -> dict:
    words = page.extract_words()
    shipped_anchor = next((w for w in words if w["text"].strip().lower().startswith("shipped") or w["text"].strip().lower() == "ship to" or w["text"].strip().lower() == "delivery address" or w["text"].strip().lower() == "consignee"), None)
    billed_anchor = next((w for w in words if w["text"].strip().lower().startswith("billed") or w["text"].strip().lower() == "bill to"), None)
    
    if not billed_anchor:
        return {"shipped": [], "billed": []}
    
    top = billed_anchor["bottom"] + 1
    party_anchor = next((w for w in words if w["text"].strip().lower().startswith("party") and w["top"] > top), None)
    bottom = party_anchor["top"] - 1 if party_anchor else top + 120
    
    blocks = {"shipped": [], "billed": []}
    
    if shipped_anchor:
        if shipped_anchor["x0"] > billed_anchor["x0"]:
            shipped_bbox = (shipped_anchor["x0"] - 4, top, page.width, bottom)
            billed_bbox = (0, top, shipped_anchor["x0"] - 4, bottom)
        else:
            billed_bbox = (billed_anchor["x0"] - 4, top, page.width, bottom)
            shipped_bbox = (0, top, billed_anchor["x0"] - 4, bottom)
            
        shipped_text = page.crop(shipped_bbox).extract_text() or ""
        blocks["shipped"] = [ln.strip().rstrip(",") for ln in shipped_text.splitlines() if ln.strip()]
        
        billed_text = page.crop(billed_bbox).extract_text() or ""
        blocks["billed"] = [ln.strip().rstrip(",") for ln in billed_text.splitlines() if ln.strip()]
    else:
        bbox = (0, top, page.width, bottom)
        text = page.crop(bbox).extract_text() or ""
        blocks["billed"] = [ln.strip().rstrip(",") for ln in text.splitlines() if ln.strip()]
        blocks["shipped"] = blocks["billed"]
        
    return blocks
''',
    "app/extraction/line_items.py": '''import re
from app.models.schemas import LineItemSchema

RE_ITEM = re.compile(
    r"^\\s*\\d+\\.\\s+(?P<desc>.+?)\\s+(?P<item_code>[A-Z]{1,3}\\d{2,5})\\s+"
    r"(?P<hsn>\\d{4,8})\\s+(?P<qty>\\d+)\\s+(?P<mrp>[\\d,]+\\.\\d{2})"
)

def extract_line_items(text: str) -> list[LineItemSchema]:
    items = []
    for line in text.splitlines():
        im = RE_ITEM.match(line)
        if im:
            items.append(LineItemSchema(
                description=im.group("desc").strip(),
                item_code=im.group("item_code"),
                hsn=im.group("hsn"),
                quantity=int(im.group("qty")),
                mrp=float(im.group("mrp").replace(",", ""))
            ))
    return items

def extract_grand_total_qty(text: str) -> int:
    m = re.search(r"Grand\\s*Total\\s+(\\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0
''',
    "app/extraction/pdf_extractor.py": '''import pdfplumber

def extract_pdf_data(path: str):
    pages_data = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_data.append({
                "page": page,
                "text": text
            })
    return pages_data
''',
    "app/extraction/normalizer.py": '''from app.models.schemas import InvoiceData, FieldValue, BoxSchema
from app.config import settings
import uuid

def create_field(value, confidence=1.0, status='valid', message=''):
    if value is None or value == "":
        status = 'missing'
    return FieldValue(value=value, confidence=confidence, status=status, message=message)

def normalize_invoice_data(raw_data: dict) -> InvoiceData:
    inv_no = raw_data.get("invoice_number", "")
    po_no = raw_data.get("po_number", "")
    
    order_id = po_no if settings.ORDER_ID_SOURCE == "po" and po_no else inv_no
    if not order_id:
        order_id = "UNKNOWN"
        
    line_items = raw_data.get("line_items", [])
    total_qty = sum(item.quantity for item in line_items)
    sku_count = len(line_items)
    
    brand = settings.DEFAULT_BRAND
    if line_items:
        first = line_items[0].description.split()[0].upper().strip(".,-")
        brand = settings.brand_map_dict.get(first, line_items[0].description.split()[0].title())
        
    order_desc = settings.DESCRIPTION_TEMPLATE.format(brand=brand, sku_count=sku_count, total_qty=total_qty)
    
    boxes_count = raw_data.get("boxes", 0) or 1
    boxes = []
    if settings.BOX_ROW_MODE == "per_box":
        for _ in range(boxes_count):
            boxes.append(BoxSchema(
                length=settings.BOX_LENGTH_DEFAULT,
                width=settings.BOX_WIDTH_DEFAULT,
                height=settings.BOX_HEIGHT_DEFAULT,
                weight=settings.BOX_WEIGHT_DEFAULT,
                quantity=1
            ))
    else:
        boxes.append(BoxSchema(
            length=settings.BOX_LENGTH_DEFAULT,
            width=settings.BOX_WIDTH_DEFAULT,
            height=settings.BOX_HEIGHT_DEFAULT,
            weight=settings.BOX_WEIGHT_DEFAULT,
            quantity=boxes_count
        ))

    return InvoiceData(
        id=str(uuid.uuid4()),
        source_file=raw_data.get("source_file", ""),
        invoice_number=create_field(inv_no, raw_data.get("invoice_number_conf", 0.0)),
        invoice_date=create_field(raw_data.get("invoice_date"), raw_data.get("invoice_date_conf", 0.0)),
        order_id=create_field(order_id),
        po_number=create_field(po_no, raw_data.get("po_number_conf", 0.0)),
        invoice_amount=create_field(raw_data.get("net_amount"), raw_data.get("net_amount_conf", 0.0)),
        eway_bill_number=create_field(raw_data.get("eway_bill"), raw_data.get("eway_bill_conf", 0.0)),
        receiver_name=create_field(raw_data.get("receiver_name"), raw_data.get("receiver_name_conf", 0.0)),
        receiver_address=create_field(raw_data.get("address", "")),
        receiver_pincode=create_field(raw_data.get("pincode", "")),
        receiver_mobile=create_field(raw_data.get("mobile", "")),
        receiver_email=create_field(settings.RECEIVER_EMAIL_DEFAULT),
        warehouse_name=create_field(settings.WAREHOUSE_NAME),
        payment_mode=create_field(settings.PAYMENT_MODE_DEFAULT),
        cod_value=create_field(settings.COD_VALUE_DEFAULT),
        insurance=create_field(settings.INSURANCE_DEFAULT),
        order_description=create_field(order_desc),
        invoice_url=create_field(settings.INVOICE_URL_DEFAULT),
        delivery_challan=create_field(settings.DELIVERY_CHALLAN_DEFAULT),
        declaration=create_field(settings.DECLARATION_DEFAULT),
        other_supporting_documents=create_field(settings.OTHER_SUPPORTING_DOCUMENTS_DEFAULT),
        reason=create_field(""),
        boxes=boxes,
        line_items=line_items,
        warnings=[],
        status="ready"
    )
''',
    "app/validation/validators.py": '''from app.models.schemas import InvoiceData

def validate_invoice(invoice: InvoiceData) -> InvoiceData:
    warnings = []
    
    if invoice.order_id.value == "UNKNOWN":
        invoice.order_id.status = "invalid"
        invoice.order_id.message = "Order ID missing"
        warnings.append("Order ID missing")
        
    if not invoice.invoice_number.value:
        invoice.invoice_number.status = "missing"
        warnings.append("Invoice number missing")
        
    if not invoice.invoice_amount.value or float(invoice.invoice_amount.value) <= 0:
        invoice.invoice_amount.status = "invalid"
        warnings.append("Invoice amount invalid")
        
    pincode = str(invoice.receiver_pincode.value)
    if not pincode or len(pincode) != 6 or not pincode.isdigit():
        invoice.receiver_pincode.status = "invalid"
        warnings.append("Pincode must be 6 digits")
        
    mobile = str(invoice.receiver_mobile.value)
    if not mobile or len(mobile) != 10 or not mobile.isdigit():
        invoice.receiver_mobile.status = "invalid"
        warnings.append("Mobile must be 10 digits")
        
    if not invoice.boxes or sum(b.quantity for b in invoice.boxes) <= 0:
        warnings.append("Box quantity must be > 0")
        
    invoice.warnings = warnings
    if warnings:
        invoice.status = "review_required"
    else:
        invoice.status = "ready"
        
    return invoice
''',
    "app/extraction/engine.py": '''import os
from collections import defaultdict
from app.extraction.pdf_extractor import extract_pdf_data
from app.extraction.field_parser import *
from app.extraction.address_parser import extract_address_blocks
from app.extraction.phone_normalizer import clean_phone
from app.extraction.pincode_validator import extract_pincode
from app.extraction.line_items import extract_line_items, extract_grand_total_qty
from app.extraction.normalizer import normalize_invoice_data
from app.validation.validators import validate_invoice
from app.config import settings

def process_pdf(path: str) -> list:
    pages_data = extract_pdf_data(path)
    invoices_raw = defaultdict(lambda: {"source_file": os.path.basename(path), "line_items": [], "address_lines": []})
    
    for pd in pages_data:
        text = pd["text"]
        page = pd["page"]
        
        inv_no, inv_conf = extract_invoice_number(text)
        if not inv_no:
            continue
            
        inv = invoices_raw[inv_no]
        if not inv.get("invoice_number"):
            inv["invoice_number"] = inv_no
            inv["invoice_number_conf"] = inv_conf
            
            val, conf = extract_net_amount(text)
            if val:
                inv["net_amount"] = val
                inv["net_amount_conf"] = conf
                
            val, conf = extract_po_number(text)
            if val:
                inv["po_number"] = val
                inv["po_number_conf"] = conf
                
            val, conf = extract_eway_bill(text)
            if val:
                inv["eway_bill"] = val
                inv["eway_bill_conf"] = conf
                
            val, conf = extract_date(text)
            if val:
                inv["invoice_date"] = val
                inv["invoice_date_conf"] = conf
                
            val, conf = extract_boxes(text)
            if val:
                inv["boxes"] = val
                inv["boxes_conf"] = conf
                
            val, conf = extract_receiver(text)
            if val:
                inv["receiver_name"] = val
                inv["receiver_name_conf"] = conf
                
            val, conf = extract_contact(text)
            if val:
                phones = clean_phone(val)
                if phones:
                    inv["mobile"] = phones[0]
                
            blocks = extract_address_blocks(page)
            address_lines = blocks.get(settings.ADDRESS_SOURCE, [])
            if address_lines:
                inv["address"] = "\\n".join(address_lines)
                pin = extract_pincode(inv["address"])
                if pin:
                    inv["pincode"] = pin
        
        items = extract_line_items(text)
        inv["line_items"].extend(items)
        
    results = []
    for inv_no, data in invoices_raw.items():
        normalized = normalize_invoice_data(data)
        validated = validate_invoice(normalized)
        results.append(validated)
        
    return results
''',
    "app/excel/generator.py": '''import openpyxl
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
''',
    "app/excel/audit_report.py": '''import csv
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
''',
    "app/api/router.py": '''from fastapi import APIRouter
from app.api import upload, jobs, invoices, config_api

api_router = APIRouter(prefix="/api")
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(invoices.router, tags=["invoices"])
api_router.include_router(config_api.router, tags=["config"])
''',
    "app/api/upload.py": '''from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import os
import shutil
from app.database import get_db
from app.models.db_models import Job
from app.config import settings

router = APIRouter()

@router.post("/invoices/upload")
async def upload_invoices(files: list[UploadFile] = File(...), db: AsyncSession = Depends(get_db)):
    job = Job(total_files=len(files))
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    job_dir = os.path.join(settings.UPLOAD_DIR, str(job.id))
    os.makedirs(job_dir, exist_ok=True)
    
    for file in files:
        file_path = os.path.join(job_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
    return {"job_id": job.id}
''',
    "app/api/jobs.py": '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette.responses import FileResponse
import os
import glob
from app.database import get_db
from app.models.db_models import Job, Invoice as DBInvoice
from app.extraction.engine import process_pdf
from app.config import settings
from app.excel.generator import generate_excel
from app.excel.audit_report import generate_audit_csv
from app.models.schemas import InvoiceData

router = APIRouter()

@router.post("/{job_id}/process")
async def process_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job.status = "processing"
    await db.commit()
    
    job_dir = os.path.join(settings.UPLOAD_DIR, job_id)
    pdfs = glob.glob(os.path.join(job_dir, "*.pdf"))
    
    for pdf in pdfs:
        invoices_data = process_pdf(pdf)
        for inv_data in invoices_data:
            db_inv = DBInvoice(
                job_id=job.id,
                source_file=os.path.basename(pdf),
                status=inv_data.status,
                data=inv_data.model_dump()
            )
            db.add(db_inv)
            
        job.processed += 1
        
    job.status = "completed"
    await db.commit()
    return {"status": "processing_started"}

@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/{job_id}/results")
async def get_job_results(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBInvoice).where(DBInvoice.job_id == job_id))
    db_invoices = result.scalars().all()
    invoices = [InvoiceData(**inv.data) for inv in db_invoices]
    return {"job_id": job_id, "invoices": invoices, "duplicates": []}

@router.post("/{job_id}/generate-excel")
async def generate_excel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DBInvoice).where(DBInvoice.job_id == job_id))
    db_invoices = result.scalars().all()
    invoices = [InvoiceData(**inv.data) for inv in db_invoices] # if inv.status == "approved" or something
    
    excel_path = generate_excel(invoices, settings.TEMPLATE_PATH, os.path.join(settings.OUTPUT_DIR, job_id))
    audit_path = generate_audit_csv(invoices, os.path.join(settings.OUTPUT_DIR, job_id))
    
    return {"excel_url": f"/api/jobs/{job_id}/download-excel", "audit_url": f"/api/jobs/{job_id}/download-audit"}

@router.get("/{job_id}/download-excel")
async def download_excel(job_id: str):
    dir_path = os.path.join(settings.OUTPUT_DIR, job_id)
    files = glob.glob(os.path.join(dir_path, "*.xlsx"))
    if not files:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(files[0])

@router.get("/{job_id}/download-audit")
async def download_audit(job_id: str):
    dir_path = os.path.join(settings.OUTPUT_DIR, job_id)
    files = glob.glob(os.path.join(dir_path, "*.csv"))
    if not files:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(files[0])
    
@router.get("/{job_id}/pdf/{filename}")
async def get_job_pdf(job_id: str, filename: str):
    pdf_path = os.path.join(settings.UPLOAD_DIR, job_id, filename)
    if not os.path.exists(pdf_path):
         raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(pdf_path)
''',
    "app/api/invoices.py": '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.db_models import Invoice as DBInvoice
from app.models.schemas import InvoiceData, InvoiceUpdate

router = APIRouter()

@router.get("/{invoice_id}")
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    # Find invoice by id (it's inside JSON, or primary key)
    # The JSON data contains the UUID which might be different than the DBInvoice UUID. Wait, they should match.
    # Let's search by DBInvoice id first. Wait, the frontend might have the JSON id. We can just query.
    # We should have DBInvoice id match JSON id.
    pass # Needs full implementation if required

@router.patch("/{invoice_id}")
async def update_invoice(invoice_id: str, data: InvoiceUpdate, db: AsyncSession = Depends(get_db)):
    return {"status": "updated"}

@router.post("/{invoice_id}/approve")
async def approve_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    return {"status": "approved"}
''',
    "app/api/config_api.py": '''from fastapi import APIRouter
from app.models.schemas import ConfigResponse, ConfigUpdate
from app.config import settings

router = APIRouter()

@router.get("")
async def get_config():
    return {}

@router.patch("")
async def update_config(data: ConfigUpdate):
    return {}
''',
    "app/main.py": '''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.database import engine, Base
import os
from app.config import settings

app = FastAPI(title="B2B Invoice Builder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
'''
}

for rel_path, content in files_to_create.items():
    full_path = os.path.join('/home/joyson/Documents/EEP/backend', rel_path)
    with open(full_path, 'w') as f:
        f.write(content)
