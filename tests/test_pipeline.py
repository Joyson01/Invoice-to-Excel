import os
import sys
import openpyxl
import pytest

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.models import InvoiceData, BoxItem
from app.parser import parse_pdf
from app.validator import validate_invoice, validate_batch
from app.excel_generator import generate_excel
from app.main import app
from fastapi.testclient import TestClient

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PDF_RAJPUTANA = os.path.join(BASE_DIR, "66075.pdf")
PDF_RASHI = os.path.join(BASE_DIR, "PDF.pdf")
PDF_SCANNED = os.path.join(BASE_DIR, "scanned_invoice.pdf")
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "B2B_bulk_upload_template.xlsx")

def test_template_existence_and_structure():
    assert os.path.exists(TEMPLATE_PATH), "Template file must exist"
    wb = openpyxl.load_workbook(TEMPLATE_PATH)
    sheet_names = [s.strip().lower() for s in wb.sheetnames]
    assert "orders" in sheet_names
    assert "boxes" in sheet_names
    assert "invoice" in sheet_names

def test_parse_rajputana_invoice():
    assert os.path.exists(PDF_RAJPUTANA), "66075.pdf must exist"
    invoices = parse_pdf(PDF_RAJPUTANA)
    assert len(invoices) >= 1
    inv = invoices[0]
    
    assert inv.is_scanned is False
    assert inv.invoice_number == "RA/66075"
    assert inv.po_number == "4800006886"
    assert inv.order_id == "4800006886"
    assert inv.invoice_amount == 1587440.0
    assert inv.receiver_name == "ABDULMATIN"
    assert inv.receiver_pincode == "683544"
    assert inv.receiver_mobile == "9029293242"
    assert len(inv.boxes) == 1
    assert inv.boxes[0].quantity == 145

def test_parse_rashi_invoice():
    assert os.path.exists(PDF_RASHI), "PDF.pdf must exist"
    invoices = parse_pdf(PDF_RASHI)
    assert len(invoices) >= 1
    inv = invoices[0]
    
    assert inv.is_scanned is False
    assert inv.invoice_number == "S2701684714"
    assert inv.order_id == "S2701684714"
    assert inv.invoice_amount == 592511.11
    assert "Rashi" in inv.receiver_name
    assert inv.receiver_pincode == "682015"

def test_parse_scanned_pdf_with_ocr():
    assert os.path.exists(PDF_SCANNED), "scanned_invoice.pdf must exist"
    invoices = parse_pdf(PDF_SCANNED)
    assert len(invoices) >= 1
    inv = invoices[0]
    
    assert inv.is_scanned is True
    assert inv.invoice_number == "RA/66075"
    assert inv.order_id == "4800006886"
    assert inv.invoice_amount == 1587440.0
    assert inv.receiver_name == "ABDULMATIN"
    assert inv.receiver_pincode == "683544"
    
    validated = validate_invoice(inv)
    assert inv.receiver_mobile == "9029293242"
    assert inv.boxes[0].quantity == 145
    assert inv.boxes[0].weight is None
    assert inv.receiver_address.count('MANASH') == 1
    assert validated.status == "Review Required"
    assert any("Scanned PDF processed via OCR" in w for w in validated.warnings)

def test_validation_logic():
    inv_valid = InvoiceData(
        order_id="ORD123",
        invoice_number="INV123",
        invoice_amount=500.0,
        receiver_name="John Doe",
        receiver_address="123 Street, City",
        receiver_pincode="123456",
        receiver_mobile="9876543210",
        eway_bill_number="123456789012",
        boxes=[BoxItem(quantity=1, length=10, width=10, height=10, weight=5)]
    )
    val = validate_invoice(inv_valid)
    assert val.status == "Ready"
    assert len(val.warnings) == 0

    inv_failed = InvoiceData(order_id="", invoice_number="", invoice_amount=None)
    val_failed = validate_invoice(inv_failed)
    assert val_failed.status == "Failed"
    assert "Invoice Number missing" in val_failed.warnings
    assert "Order ID missing" in val_failed.warnings
    assert "Invoice Amount missing" in val_failed.warnings

def test_duplicate_order_id_detection():
    inv1 = InvoiceData(order_id="DUP1", invoice_number="INV1", invoice_amount=100.0)
    inv2 = InvoiceData(order_id="DUP1", invoice_number="INV2", invoice_amount=200.0)
    
    batch = validate_batch([inv1, inv2])
    assert len(batch) == 2
    assert any("Duplicate Order_ID 'DUP1'" in w for w in batch[1].warnings)

def test_excel_generation_preserves_template_and_columns(tmp_path):
    inv1 = InvoiceData(
        order_id="PO999",
        invoice_number="RA/66075",
        invoice_amount=1587440.0,
        receiver_name="ABDULMATIN",
        receiver_address="Kerala 683544",
        receiver_pincode="683544",
        receiver_mobile="9029293242",
        order_description="Skin Cream",
        eway_bill_number="111222333444",
        boxes=[BoxItem(quantity=145)]
    )
    inv2 = InvoiceData(
        order_id="S2701684714",
        invoice_number="S2701684714",
        invoice_amount=592511.11,
        receiver_name="Rashi Peripherals",
        receiver_address="Cochin 682015",
        receiver_pincode="682015",
        receiver_mobile="04844120202",
        order_description="Speakers",
        boxes=[]
    )
    
    out_file = generate_excel([inv1, inv2], TEMPLATE_PATH, str(tmp_path))
    assert os.path.exists(out_file)
    
    wb = openpyxl.load_workbook(out_file)
    assert wb.sheetnames == ["Orders", "Boxes", "Invoice"]
    
    # Orders Sheet
    ws_orders = wb["Orders"]
    expected_orders_cols = [
        "Order_ID", "Warehouse_Name", "Receiver_Name", "Receiver_Address", 
        "Receiver_Pincode", "Receiver_Email", "Receiver_Mobile", "Order_description", 
        "Payment_Mode", "COD_Value", "Insurance", "Invoice", "Delivery_Challan", 
        "Declaration", "Other_Supporting_Documents", "Reason"
    ]
    assert [c.value for c in ws_orders[1]] == expected_orders_cols
    assert ws_orders.cell(row=2, column=1).value == "PO999"
    assert ws_orders.cell(row=3, column=1).value == "S2701684714"
    
    # Boxes Sheet
    ws_boxes = wb["Boxes"]
    expected_boxes_cols = ["Order_ID", "Length", "Width", "Height", "Weight", "Quantity"]
    assert [c.value for c in ws_boxes[1]] == expected_boxes_cols
    assert ws_boxes.cell(row=2, column=1).value == "PO999"
    assert ws_boxes.cell(row=2, column=6).value == 145
    assert ws_boxes.cell(row=3, column=1).value == "S2701684714"
    assert ws_boxes.cell(row=3, column=6).value is None
    
    # Invoice Sheet
    ws_invoice = wb["Invoice"]
    expected_inv_cols = ["Order_ID", "Invoice_Number", "Invoice_Amount", "Invoice_Eway_Bill_Number"]
    assert [c.value for c in ws_invoice[1]] == expected_inv_cols
    assert ws_invoice.cell(row=2, column=1).value == "PO999"
    assert ws_invoice.cell(row=2, column=2).value == "RA/66075"
    assert ws_invoice.cell(row=2, column=3).value == 1587440.0
    assert isinstance(ws_invoice.cell(row=2, column=3).value, (int, float))

def test_end_to_end_api_workflow():
    client = TestClient(app)
    
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    
    with open(PDF_RAJPUTANA, "rb") as f1, open(PDF_RASHI, "rb") as f2:
        res = client.post("/api/upload", files=[
            ("files", ("66075.pdf", f1, "application/pdf")),
            ("files", ("PDF.pdf", f2, "application/pdf")),
        ])
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert len(data["invoices"]) == 2
    session_id = data["session_id"]
    
    inv_id = data["invoices"][0]["id"]
    update_res = client.put(f"/api/invoices/{session_id}/{inv_id}", json={
        "eway_bill_number": "123456789012"
    })
    assert update_res.status_code == 200
    assert update_res.json()["eway_bill_number"] == "123456789012"
    
    gen_res = client.post(f"/api/generate/{session_id}")
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["success"] is True
    assert gen_data["filename"].startswith("B2B_bulk_upload_")
    assert gen_data["filename"].endswith(".xlsx")
    
    dl_res = client.get(gen_data["download_url"])
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 1000
