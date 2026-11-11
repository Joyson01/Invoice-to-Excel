import os
import re
import logging
from typing import List
import pdfplumber

from app.models import InvoiceData, BoxItem, LineItem
from app.config import get_config
from app.ocr_provider import get_ocr_provider

log = logging.getLogger(__name__)

from app.document_layout import words_to_lines
from app.field_reader import label_values, identifier, invoice_amount, INVOICE_LABEL, PO_LABEL, BOX_LABEL

RE_DATED = [
    re.compile(r"Dated\s*:\s*([\d]{2}[-/][\d]{2}[-/][\d]{4})", re.I),
    re.compile(r"Date\s*:\s*([\d]{2}\.[\d]{2}\.[\d]{4})", re.I),
    re.compile(r"Invoice\s*Date\s*:\s*([\d]{2}[-/\.][\d]{2}[-/\.][\d]{4})", re.I),
]

RE_PINCODE = re.compile(r"\b([1-9]\d{5})\b")
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Line items matching
RE_ITEM_RAJPUTANA = re.compile(
    r"^\s*\d+\.\s+(?P<desc>.+?)\s+(?P<item_code>[A-Z]{1,3}\d{2,5})\s+"
    r"(?P<hsn>\d{4,8})\s+(?P<qty>\d+)\s+(?P<mrp>[\d,]+\.\d{2})"
)
RE_ITEM_RASHI = re.compile(
    r"^(?P<code>[A-Za-z0-9]+)\s+(?P<desc>[A-Za-z0-9_/\.\-\+ ]+?)\s+"
    r"(?P<hsn>\d{6,8})\s+(?P<qty>\d+)\s+[\d,]+\.\d{2}\s+(?P<total>[\d,]+\.\d{2})"
)

def clean_phone(raw: str) -> str:
    """Accept complete Indian mobile numbers; never take a slice of a longer number."""
    for chunk in re.split(r"[/,;|]|\s{2,}", raw or ""):
        if not re.fullmatch(r"[+\d().\s-]+", chunk.strip()):
            continue
        digits = re.sub(r"\D", "", chunk)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        if re.fullmatch(r"[6-9]\d{9}", digits):
            return digits
    return ""


def _key(text):
    return re.sub(r"[^a-z]", "", text.lower())


def _has_next_word(word, words, expected):
    height = word['bottom'] - word['top']
    return any(_key(other['text']) == expected
               and 0 <= other['x0'] - word['x1'] <= height * 2
               and abs(other['top'] - word['top']) < height * 0.5 for other in words)


def _extract_address_lines(page, prefer="shipped"):
    words = page.extract_words()
    shipping = [w for w in words if _key(w['text']) in ('shipto', 'shippedto', 'deliveryaddress')
                or (_key(w['text']) in ('ship', 'shipped') and _has_next_word(w, words, 'to'))]
    billing = [w for w in words if _key(w['text']) == 'billedto' or _key(w['text']).startswith('billto')
               or (_key(w['text']) in ('bill', 'billed') and _has_next_word(w, words, 'to'))]
    headings = shipping if prefer == 'shipped' else billing
    if not headings:
        return []
    heading = min(headings, key=lambda w: w['top'])
    height = heading['bottom'] - heading['top']
    left = max(0, heading['x0'] - height * 0.3)
    # Locate neighboring columns near the address, not a Bank label elsewhere on the page.
    neighbors = [w['x0'] for w in words
                 if w['x0'] > heading['x0'] + height * 3
                 and heading['top'] - height * 2 <= w['top'] <= heading['bottom'] + height * 10
                 and (_key(w['text']).startswith(('bank', 'payment')) or w in shipping + billing)]
    right = min(neighbors) - height * 0.3 if neighbors else page.width
    top = heading['bottom']
    stops = [w['top'] for w in words if left <= w['x0'] < right and w['top'] > top
             and _key(w['text']).startswith(('gstin', 'party', 'productcode', 'descriptionofgoods', 'hsn', 'invoicetotal', 'grandtotal', 'total'))]
    bottom = min(stops) if stops else min(page.height, top + height * 10)
    selected = [w for w in words if w['x0'] >= left and w['x1'] <= right
                and w['top'] >= top and w['bottom'] <= bottom]
    return [line.strip().rstrip(',') for line in words_to_lines(selected)]


def _receiver_contact_text(page, address_lines):
    words = page.extract_words()
    # A separately labelled Receiver Name / Contact block (as in the Rajputana invoice).
    receiver = next((w for w in words if _key(w['text']) == 'receivername'
                     or (_key(w['text']) == 'receiver' and _has_next_word(w, words, 'name'))), None)
    context = list(address_lines)
    if receiver:
        height = receiver['bottom'] - receiver['top']
        # Only contact labels aligned with the receiver column may supply values.
        labels = [w for w in words
            if abs(w['x0'] - receiver['x0']) <= height * 2
            and receiver['top'] <= w['top'] <= receiver['bottom'] + height * 4
            and _key(w['text']).startswith(('contact', 'phone', 'mobile', 'tel', 'email'))]
        for label in labels:
            row = [w for w in words if w['x0'] >= label['x0']
                   and abs((w['top'] + w['bottom']) / 2 - (label['top'] + label['bottom']) / 2) < height * 0.6]
            boundaries = [w['x0'] for w in row if w is not label
                          and _key(w['text']).startswith(('seller', 'supplier', 'bank', 'phone', 'mobile', 'email', 'contact'))]
            right = min(boundaries) if boundaries else page.width
            context += words_to_lines([w for w in row if w['x1'] <= right])
    return '\n'.join(context)


def derive_order_description(line_items: List[LineItem]) -> str:
    """Generate Order_description from line items matching: '{brand} products - {sku_count} SKUs, {total_qty} units'."""
    if not line_items:
        return ""
    
    cfg = get_config()
    sku_count = len(line_items)
    total_qty = sum(it.quantity for it in line_items)
    
    # Identify brand from first item's description or code
    first_desc = line_items[0].description.strip()
    first_token = re.split(r"[\s_/\-]+", first_desc)[0].upper() if first_desc else ""
    
    brand = cfg.brand_map.get(first_token)
    summary = f"{sku_count} SKUs, {total_qty} units"
    return f"{brand} products - {summary}" if brand else summary


def parse_pdf(path: str) -> List[InvoiceData]:
    """Parse one PDF invoice, extracting structured data with OCR fallback."""
    cfg = get_config()
    filename = os.path.basename(path)
    
    try:
        pdf = pdfplumber.open(path)
    except Exception as exc:
        log.error("Failed to open PDF %s: %s", path, exc)
        return [InvoiceData(filename=filename, warnings=[f"Failed to open PDF: {str(exc)}"], status="Failed")]
        
    if not pdf.pages:
        pdf.close()
        return [InvoiceData(filename=filename, warnings=["PDF contains no pages"], status="Failed")]

    # Combine text from all pages
    total_text = ""
    for page in pdf.pages:
        t = '\n'.join(words_to_lines(page.extract_words()))
        total_text += t + "\n"

    layout_pages = pdf.pages
    inv = InvoiceData(filename=filename)
    used_ocr = False

    # Check for scanned/image PDF (insufficient native text)
    clean_total = "".join(total_text.split())
    if len(clean_total) < 25:
        log.info("Insufficient text in %s (%d chars). Running OCR fallback...", filename, len(clean_total))
        inv.is_scanned = True
        used_ocr = True
        
        ocr_provider = get_ocr_provider()
        layout_pages, ocr_conf = ocr_provider.extract_pages_from_pdf(path)
        ocr_text = "\n".join(page.extract_text() for page in layout_pages)
        
        if not ocr_text.strip():
            pdf.close()
            inv.warnings.append("Scanned PDF - OCR required. Unable to extract text.")
            inv.status = "Failed"
            return [inv]
            
        total_text = ocr_text
        if ocr_conf < 0.6:
            inv.warnings.append(f"OCR confidence is low ({ocr_conf:.2f}). Please review fields.")

    inv.invoice_number = identifier(total_text, INVOICE_LABEL, inv.warnings, 'Invoice Number')
    if any(w.startswith('Conflicting Invoice Number') for w in inv.warnings):
        inv.warnings.append('Multiple invoice numbers detected. Upload one invoice per PDF.')
        inv.status = 'Failed'
        pdf.close()
        return [inv]
    inv.po_number = identifier(total_text, PO_LABEL, inv.warnings, 'PO Number')

    # 3. Order_ID Priority:
    # 1. PO Number / Customer order number
    # 2. Order number
    # 3. Invoice reference if no order number exists
    if inv.po_number and inv.po_number.strip():
        inv.order_id = inv.po_number.strip()
    elif inv.invoice_number and inv.invoice_number.strip():
        inv.order_id = inv.invoice_number.strip()
        inv.warnings.append("PO number missing - using Invoice Number for Order_ID")
    else:
        inv.order_id = ""
        inv.warnings.append("Order_ID could not be identified - Review Required")

    inv.invoice_amount = invoice_amount(total_text, inv.warnings)

    # 5. Invoice Date
    for p in RE_DATED:
        m = p.search(total_text)
        if m:
            inv.invoice_date = m.group(1).strip()
            break

    eway = identifier(total_text, r'E-?\s*way\s*Bill\s*(?:No\.?|Number)?', inv.warnings, 'E-Way Bill')
    inv.eway_bill_number = eway if re.fullmatch(r"\d{12}", eway) else ''

    names = list(label_values(total_text, r'(?:Receiver\s*Name|Consignee|Ship\s*To\s*Name)'))
    if names:
        name = re.split(r'\s{2,}', names[0].strip())[0]
        if not re.search(r'[:]|signature', name, re.I):
            inv.receiver_name = name

    address_lines = _extract_address_lines(layout_pages[0], prefer='shipped')
    if not address_lines:
        address_lines = _extract_address_lines(layout_pages[0], prefer='billed')
        if address_lines:
            inv.warnings.append('Shipping address missing - billing address used; please confirm delivery address')
    contact_text = _receiver_contact_text(layout_pages[0], address_lines)
    cleaned_lines = [line for line in address_lines
                     if not re.match(r'(?:Tel|Phone|Mobile|Contact|Email)\b', line, re.I)]
    inv.receiver_address = '\n'.join(cleaned_lines)
    if not inv.receiver_name and cleaned_lines:
        inv.receiver_name = cleaned_lines[0]
    pins = set(RE_PINCODE.findall(inv.receiver_address))
    if len(pins) == 1:
        inv.receiver_pincode = pins.pop()
    elif len(pins) > 1:
        inv.warnings.append('Conflicting receiver pincodes - left blank for review')

    for value in label_values(contact_text, r'(?:Contact\s*No\.?|Phone|Mobile|Tel\.?\s*(?:No\.?)?)'):
        mobile = clean_phone(value)
        if mobile:
            inv.receiver_mobile = mobile
            break
    emails = set(RE_EMAIL.findall(contact_text))
    if len(emails) == 1:
        inv.receiver_email = emails.pop()

    applied_defaults = []
    if cfg.apply_business_defaults:
        for field, default in {
            'receiver_email': cfg.receiver_email_default,
            'warehouse_name': cfg.warehouse_name,
            'payment_mode': cfg.payment_mode_default,
            'cod_value': cfg.cod_value_default,
            'insurance': cfg.insurance_default,
            'invoice_url': cfg.invoice_url_default,
            'delivery_challan': cfg.delivery_challan_default,
            'declaration': cfg.declaration_default,
            'other_supporting_documents': cfg.other_supporting_documents_default,
        }.items():
            if getattr(inv, field) in ('', None) and default not in ('', None):
                setattr(inv, field, default)
                applied_defaults.append(field)

    # 12. Line Items & Order Description
    line_items = []
    for line in total_text.splitlines():
        im1 = RE_ITEM_RAJPUTANA.match(line)
        if im1:
            line_items.append(LineItem(
                description=im1.group("desc").strip(),
                item_code=im1.group("item_code").strip(),
                hsn=im1.group("hsn").strip(),
                quantity=int(im1.group("qty")),
                mrp=float(im1.group("mrp").replace(",", ""))
            ))
            continue
            
        im2 = RE_ITEM_RASHI.match(line)
        if im2:
            line_items.append(LineItem(
                description=im2.group("desc").strip(),
                item_code=im2.group("code").strip(),
                hsn=im2.group("hsn").strip(),
                quantity=int(im2.group("qty")),
                mrp=float(im2.group("total").replace(",", ""))
            ))

    inv.line_items = line_items
    inv.order_description = derive_order_description(line_items)

    # Only explicitly labelled packaging facts may populate Boxes.
    counts = {int(value) for value in label_values(total_text, BOX_LABEL) if re.fullmatch(r"\d+", value)}
    box_count = next(iter(counts)) if len(counts) == 1 else None
    if len(counts) > 1:
        inv.warnings.append('Conflicting box quantities - left blank for review')
    dimensions = set(label_values(total_text, r'(?:Box|Carton|Package)\s*Dimensions\s*(?:\(cm\))?'))
    weights = set(label_values(total_text, r'(?:Box|Carton|Package)\s*Weight\s*(?:\(kg\))?'))
    dim = re.fullmatch(r'(\d+(?:\.\d+)?)\s*[xX*]\s*(\d+(?:\.\d+)?)\s*[xX*]\s*(\d+(?:\.\d+)?)(?:\s*cm)?', next(iter(dimensions))) if len(dimensions) == 1 else None
    weight = re.fullmatch(r'(\d+(?:\.\d+)?)(?:\s*kg)?', next(iter(weights)), re.I) if len(weights) == 1 else None
    if dimensions and not dim:
        inv.warnings.append('Ambiguous box dimensions - left blank for review')
    if weights and not weight:
        inv.warnings.append('Ambiguous box weight - left blank for review')
    if box_count is not None or dimensions or weights:
        box = BoxItem(quantity=box_count,
            length=float(dim[1]) if dim else None, width=float(dim[2]) if dim else None,
            height=float(dim[3]) if dim else None, weight=float(weight[1]) if weight else None)
        if cfg.apply_business_defaults:
            for field in ('length', 'width', 'height', 'weight'):
                if getattr(box, field) is None:
                    if (field == 'weight' and weights) or (field != 'weight' and dimensions):
                        continue
                    setattr(box, field, getattr(cfg, f'box_{field}_default'))
                    applied_defaults.append(f'box_{field}')
        inv.boxes = [box]
    else:
        inv.warnings.append('Box data missing - left blank for review')
    if applied_defaults:
        inv.warnings.append('Business defaults applied (not extracted): ' + ', '.join(applied_defaults))

    if used_ocr:
        inv.warnings.append("Scanned PDF processed via OCR. Please verify extracted fields.")

    pdf.close()
    return [inv]
