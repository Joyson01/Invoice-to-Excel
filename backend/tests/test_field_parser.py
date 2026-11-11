from app.extraction.field_parser import extract_invoice_number, extract_net_amount

def test_extract_invoice_number():
    val, conf = extract_invoice_number("Invoice No. : INV-123")
    assert val == "INV-123"
    
def test_extract_net_amount():
    val, conf = extract_net_amount("NET BILL AMOUNT: 1,234.50")
    assert val == 1234.50
