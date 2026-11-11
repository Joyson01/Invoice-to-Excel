from pathlib import Path

import openpyxl
import pytest

from app.config import update_config
from app.excel_generator import generate_excel
from app.models import LineItem
from app.parser import parse_pdf, clean_phone, derive_order_description
from app.models import InvoiceData, BoxItem
from app.validator import validate_invoice

ROOT = Path(__file__).resolve().parents[1]


def invoice_pdf(tmp_path, lines):
    """Write a small real text PDF with explicit positions, independent of the parser."""
    stream = '\n'.join(f'BT /F1 10 Tf {x} {y} Td ({text.replace(chr(92), chr(92)*2).replace("(", chr(92)+"(").replace(")", chr(92)+")")}) Tj ET'
                       for x, y, text in lines).encode('ascii')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
    data = b'%PDF-1.4\n'
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data += f'{number} 0 obj\n'.encode() + body + b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n'
    data += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
    data += f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()
    path = tmp_path / 'invoice.pdf'
    path.write_bytes(data)
    return str(path)


@pytest.mark.parametrize('raw,expected', [
    ('02502450261. Tel.No.:04844120202. Tel.No.:04844120202.', ''),
    ('12345678901234567890', ''),
    ('04844120202', ''),
    ('+91 90292 93242', '9029293242'),
    ('09029293242', '9029293242'),
    ('90292 93242 / 98765 43210', '9029293242'),
])
def test_mobile_normalization_never_splices_numbers(raw, expected):
    assert clean_phone(raw) == expected


def test_rashi_shipping_block_excludes_bank_and_product_columns():
    inv = parse_pdf(str(ROOT / 'PDF.pdf'))[0]
    assert inv.receiver_mobile == ''  # The printed receiver telephone is a landline.
    assert inv.receiver_email == ''
    assert inv.receiver_address.splitlines() == [
        'RashiPeripheralsLimited',
        'Ground&FirstFloorDoorN.61/1592&61/1593',
        'CEARSTOWERSAlappatCrossRdRavipuram',
        'Cochin- 682015-Kerala',
    ]


def test_missing_values_stay_blank_through_excel(tmp_path):
    inv = parse_pdf(str(ROOT / '66075.pdf'))[0]
    assert inv.receiver_email == ''
    assert inv.warehouse_name == ''
    assert inv.payment_mode == ''
    assert inv.insurance == ''
    assert inv.cod_value is None
    assert inv.boxes[0].quantity == 145
    assert inv.boxes[0].weight is None
    assert inv.boxes[0].length is None
    path = generate_excel([inv], str(ROOT / 'templates/B2B_bulk_upload_template.xlsx'), str(tmp_path))
    wb = openpyxl.load_workbook(path)
    assert wb['Orders']['F2'].value is None
    assert wb['Orders']['B2'].value is None
    assert wb['Boxes']['E2'].value is None
    assert wb['Boxes']['F2'].value == 145


def test_explicit_defaults_are_identified_as_defaults():
    update_config({'apply_business_defaults': True, 'warehouse_name': 'My warehouse', 'box_weight_default': 7})
    inv = parse_pdf(str(ROOT / '66075.pdf'))[0]
    assert inv.warehouse_name == 'My warehouse'
    assert inv.boxes[0].weight == 7
    assert any('Business defaults applied' in warning for warning in inv.warnings)
    assert inv.receiver_email == ''


def test_seller_contact_and_product_measurements_are_not_receiver_or_boxes(tmp_path):
    path = invoice_pdf(tmp_path, [
        (20,760,'Seller Ltd, Mumbai 400104'),
        (20,740,'Phone: 9876543210 Email: sales@seller.example'),
        (20,700,'Invoice No: INV-123'), (20,680,'Invoice Total: 250.00'),
        (20,650,'Product: Speaker 20 x 30 x 40 cm; 5 KG'),
    ])
    inv = parse_pdf(path)[0]
    assert inv.receiver_name == ''
    assert inv.receiver_address == ''
    assert inv.receiver_pincode == ''
    assert inv.receiver_mobile == ''
    assert inv.receiver_email == ''
    assert inv.boxes == []


def test_blank_labels_do_not_consume_next_field(tmp_path):
    path = invoice_pdf(tmp_path, [
        (20,760,'Invoice No:'), (20,740,'Date: 11-11-2026'),
        (20,720,'PO No:'), (20,700,'CONTACT NO: 9876543210'),
        (20,680,'RECEIVER NAME:'), (20,660,'GSTIN: 27AAMCR1219D1ZK'),
        (20,640,'NO.OF BOXES:'), (20,620,'Invoice Total: 250.00'),
    ])
    inv = parse_pdf(path)[0]
    assert inv.invoice_number == ''
    assert inv.po_number == ''
    assert inv.receiver_name == ''
    assert inv.boxes == []


def test_box_measurements_override_defaults_and_do_not_invent_count(tmp_path):
    update_config({'apply_business_defaults': True})
    path = invoice_pdf(tmp_path, [
        (20,760,'Invoice No: INV-123'), (20,740,'Invoice Total: 250.00'),
        (20,720,'Box dimensions (cm): 30 x 20 x 15'), (20,700,'Box weight (kg): 8'),
    ])
    inv = parse_pdf(path)[0]
    assert len(inv.boxes) == 1
    assert inv.boxes[0].model_dump() == dict(length=30.0,width=20.0,height=15.0,weight=8.0,quantity=None)


def test_conflicting_invoice_totals_are_flagged_instead_of_guessed(tmp_path):
    path = invoice_pdf(tmp_path, [(20,760,'Invoice No: INV-123'),
        (20,740,'Invoice Total: 250.00'), (20,720,'Invoice Total: 300.00')])
    inv = parse_pdf(path)[0]
    assert inv.invoice_amount is None
    assert any('Conflicting' in warning for warning in inv.warnings)


def test_grand_total_quantity_is_not_invoice_amount(tmp_path):
    path = invoice_pdf(tmp_path, [(20,760,'Invoice No: INV-123'),
        (20,740,'Grand Total 12 Rs. 250.00')])
    assert parse_pdf(path)[0].invoice_amount == 250


def test_unknown_brand_is_not_invented_from_first_word():
    result = derive_order_description([LineItem(description='Skin cream',quantity=3)])
    assert result == '1 SKUs, 3 units'


def test_ocr_reconstructs_rows_before_matching_labels():
    from app.ocr_provider import RapidOCRProvider
    provider = object.__new__(RapidOCRProvider)
    # Recorded layout class: neighboring labels returned before their values.
    provider.ocr_engine = lambda image: ([
        ([[0,0],[40,0],[40,10],[0,10]], 'PO NO', 0.9),
        ([[200,1],[280,1],[280,11],[200,11]], 'CONTACT NO.', 0.9),
        ([[60,2],[140,2],[140,12],[60,12]], '4800006886', 0.9),
        ([[300,1],[400,1],[400,11],[300,11]], '90292 93242', 0.9),
    ], None)
    text, _ = provider.extract_text_from_image(None)
    assert text.splitlines() == ['PO NO   4800006886   CONTACT NO.   90292 93242']


def test_incomplete_box_measurements_remain_flagged_after_other_fixes():
    inv = InvoiceData(boxes=[BoxItem(quantity=145)])
    assert 'Box 1 dimensions/weight missing or invalid' in validate_invoice(inv).warnings
    inv.boxes[0] = BoxItem(quantity=145, length=10, width=10, height=10, weight=5)
    assert 'Box 1 dimensions/weight missing or invalid' not in validate_invoice(inv).warnings


def test_invoice_number_conflict_does_not_mix_two_invoices(tmp_path):
    path = invoice_pdf(tmp_path, [(20,760,'Invoice No: FIRST-1'), (20,740,'Invoice Total: 100.00'),
        (20,700,'Invoice No: SECOND-2'), (20,680,'Invoice Total: 200.00')])
    inv = parse_pdf(path)[0]
    assert inv.status == 'Failed'
    assert inv.invoice_amount is None
    assert inv.order_id == ''


def test_eway_bill_label_is_not_a_billing_address(tmp_path):
    path = invoice_pdf(tmp_path, [(20,760,'E-Way Bill No: 123456789012'),
        (20,740,'Seller Limited'), (20,720,'Seller Road Mumbai 400104'),
        (20,700,'Phone:9876543210'), (20,680,'GSTIN:27AAMCR1219D1ZK'),
        (20,660,'Invoice No:INV-123'), (20,640,'Invoice Total:250')])
    inv = parse_pdf(path)[0]
    assert inv.receiver_address == ''
    assert inv.receiver_name == ''
    assert inv.receiver_pincode == ''
    assert inv.receiver_mobile == ''


def test_receiver_label_does_not_claim_adjacent_seller_column(tmp_path):
    path = invoice_pdf(tmp_path, [(20,760,'Invoice No:INV-123'), (20,740,'Invoice Total:250'),
        (20,700,'RECEIVER NAME: Buyer Ltd'), (350,700,'Seller Contact'),
        (350,680,'Phone:9876543210'), (350,660,'Email:seller@example.com')])
    inv = parse_pdf(path)[0]
    assert inv.receiver_name == 'Buyer Ltd'
    assert inv.receiver_mobile == ''
    assert inv.receiver_email == ''


def test_decimal_quantity_does_not_disambiguate_total(tmp_path):
    path = invoice_pdf(tmp_path, [(20,760,'Invoice No:INV-123'), (20,740,'Grand Total 12.00 250')])
    inv = parse_pdf(path)[0]
    assert inv.invoice_amount is None
    assert any('ambiguous' in w for w in inv.warnings)


@pytest.mark.parametrize('second,expected', [('8',8),('9',None)])
def test_repeated_or_conflicting_box_weights_never_fall_back_to_defaults(tmp_path, second, expected):
    update_config({'apply_business_defaults': True, 'box_weight_default':5})
    path = invoice_pdf(tmp_path, [(20,760,'Invoice No:INV-123'), (20,740,'Invoice Total:250'),
        (20,720,'Total Boxes:2'), (20,700,'Box Weight (kg):8'), (20,680,f'Box Weight (kg):{second}')])
    inv = parse_pdf(path)[0]
    assert inv.boxes[0].weight == expected
    if expected is None:
        assert any('box weight' in w.lower() for w in inv.warnings)


def test_disagreeing_total_labels_are_not_silently_prioritized(tmp_path):
    path = invoice_pdf(tmp_path, [(20,760,'Invoice No:INV-123'),
        (20,740,'Net Bill Amount:100'),(20,720,'Invoice Total:200')])
    inv = parse_pdf(path)[0]
    assert inv.invoice_amount is None
    assert any('Conflicting' in w for w in inv.warnings)
