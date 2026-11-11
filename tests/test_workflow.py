from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.models import InvoiceData, BoxItem
from app.validator import validate_invoice, validate_batch
from app.excel_generator import generate_excel

ROOT = Path(__file__).resolve().parents[1]


def ready_invoice(**updates):
    data = dict(order_id='PO1', invoice_number='INV1', invoice_amount=100,
                receiver_name='Customer', receiver_address='Street, Kochi',
                receiver_pincode='682015', receiver_mobile='9876543210',
                eway_bill_number='123456789012', boxes=[BoxItem(quantity=1, length=10, width=10, height=10, weight=5)])
    data.update(updates)
    return InvoiceData(**data)


def test_defaults_apply_to_new_uploads_and_reject_invalid_changes():
    client = TestClient(main.app)
    assert client.get('/api/config').status_code == 200
    assert client.patch('/api/config', json={'warehouse_name': 'Company Warehouse', 'apply_business_defaults': True}).status_code == 200
    with (ROOT / '66075.pdf').open('rb') as pdf:
        response = client.post('/api/upload', files={'files': ('invoice.pdf', pdf, 'application/pdf')})
    assert response.json()['invoices'][0]['warehouse_name'] == 'Company Warehouse'
    response = client.patch('/api/config', json={'warehouse_name': 'Wrong', 'box_weight_default': -1})
    assert response.status_code == 422
    assert client.get('/api/config').json()['warehouse_name'] == 'Company Warehouse'


def test_corrections_clear_old_validation_but_keep_ocr_warning():
    inv = ready_invoice(eway_bill_number='', warnings=['Scanned PDF processed via OCR. Please verify extracted fields.'])
    validate_invoice(inv)
    inv.eway_bill_number = '123456789012'
    validate_invoice(inv)
    assert inv.warnings == ['Scanned PDF processed via OCR. Please verify extracted fields.']


def test_correcting_po_number_clears_fallback_warning():
    inv = ready_invoice(order_id='INV1', warnings=['PO number missing - using Invoice Number for Order_ID'])
    main.SESSIONS['test'] = [inv]
    response = TestClient(main.app).put(f'/api/invoices/test/{inv.id}', json={'po_number': 'PO1', 'order_id': 'PO1'})
    assert response.status_code == 200
    assert response.json()['warnings'] == []
    assert response.json()['status'] == 'Ready'


def test_duplicate_edit_revalidates_both_invoices():
    first, second = ready_invoice(), ready_invoice(invoice_number='INV2')
    main.SESSIONS['test'] = validate_batch([first, second])
    client = TestClient(main.app)
    response = client.put(f'/api/invoices/test/{second.id}', json={'order_id': 'PO2'})
    assert response.status_code == 200
    assert all(inv['status'] == 'Ready' for inv in client.get('/api/invoices/test').json()['invoices'])
    response = client.put(f'/api/invoices/test/{second.id}', json={'order_id': 'PO1'})
    assert response.status_code == 200
    assert all(any('Duplicate' in w for w in inv['warnings']) for inv in client.get('/api/invoices/test').json()['invoices'])


@pytest.mark.parametrize('name,content', [('notes.txt', b'hello'), ('fake.pdf', b'hello')])
def test_rejects_non_pdf_uploads(name, content):
    response = TestClient(main.app).post('/api/upload', files={'files': (name, content)})
    assert response.status_code == 400
    assert not main.SESSIONS


def test_upload_filename_cannot_escape_storage(tmp_path):
    destination = tmp_path / 'outside.pdf'
    with (ROOT / '66075.pdf').open('rb') as pdf:
        response = TestClient(main.app).post('/api/upload', files={'files': (str(destination), pdf, 'application/pdf')})
    assert response.status_code == 200
    assert not destination.exists()
    assert response.json()['invoices'][0]['filename'] == 'outside.pdf'


def test_rejects_oversized_pdf_without_partial_session(monkeypatch):
    monkeypatch.setattr(main, 'MAX_FILE_SIZE_BYTES', 10, raising=False)
    response = TestClient(main.app).post('/api/upload', files={'files': ('large.pdf', b'%PDF-1.4\n' + b'x' * 20)})
    assert response.status_code == 413
    assert not main.SESSIONS


def test_excel_treats_extracted_strings_as_literal_text(tmp_path):
    inv = ready_invoice(receiver_name='=1+2', order_id='001234')
    path = generate_excel([inv], str(ROOT / 'templates/B2B_bulk_upload_template.xlsx'), str(tmp_path))
    workbook = openpyxl.load_workbook(path)
    assert workbook['Orders']['C2'].value == '=1+2'
    assert workbook['Orders']['C2'].data_type == 's'
    assert workbook['Orders']['A2'].value == '001234'


@pytest.mark.parametrize('updates', [{'receiver_name': None}, {'boxes': None}])
def test_null_updates_rejected_without_corrupting_invoice(updates):
    inv = ready_invoice()
    main.SESSIONS['test'] = [inv]
    response = TestClient(main.app).put(f'/api/invoices/test/{inv.id}', json=updates)
    assert response.status_code == 422
    assert main.SESSIONS['test'][0].receiver_name == 'Customer'
    assert main.SESSIONS['test'][0].boxes
