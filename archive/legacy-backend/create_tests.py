import os

files = {
    "tests/conftest.py": '''import pytest
from app.models.schemas import InvoiceData, BoxSchema
import uuid

@pytest.fixture
def dummy_invoice():
    # Return dummy InvoiceData
    pass
''',
    "tests/test_phone_normalizer.py": '''from app.extraction.phone_normalizer import clean_phone

def test_clean_phone():
    assert clean_phone("7356976268 /99953 23357") == ["7356976268", "9995323357"]
    assert clean_phone("+919876543210") == ["9876543210"]
    assert clean_phone("09876543210") == ["9876543210"]
''',
    "tests/test_pincode_validator.py": '''from app.extraction.pincode_validator import extract_pincode

def test_extract_pincode():
    assert extract_pincode("Some address 123456 here") == "123456"
    assert extract_pincode("No pincode here") == ""
''',
    "tests/test_field_parser.py": '''from app.extraction.field_parser import extract_invoice_number, extract_net_amount

def test_extract_invoice_number():
    val, conf = extract_invoice_number("Invoice No. : INV-123")
    assert val == "INV-123"
    
def test_extract_net_amount():
    val, conf = extract_net_amount("NET BILL AMOUNT: 1,234.50")
    assert val == 1234.50
''',
    "tests/test_address_parser.py": '''from app.extraction.address_parser import extract_address_blocks

# Requires mocked pdfplumber page for real tests
def test_placeholder():
    pass
''',
    "tests/test_line_items.py": '''from app.extraction.line_items import extract_line_items

def test_extract_line_items():
    text = "1. Item Name ABC01 1234 10 100.00"
    items = extract_line_items(text)
    assert len(items) == 1
    assert items[0].description == "Item Name"
    assert items[0].quantity == 10
''',
    "tests/test_excel_generator.py": '''from app.excel.generator import generate_excel

def test_placeholder():
    pass
''',
    "tests/test_validation.py": '''from app.validation.validators import validate_invoice
from app.extraction.normalizer import create_field
from app.models.schemas import InvoiceData

# Create basic tests
def test_placeholder():
    pass
'''
}

for rel, text in files.items():
    with open(os.path.join("/home/joyson/Documents/EEP/backend", rel), "w") as f:
        f.write(text)
