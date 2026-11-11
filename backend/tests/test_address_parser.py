from pathlib import Path
from app.parser import parse_pdf


def test_shipping_address_keeps_receiver_pincode():
    invoice = parse_pdf(str(Path(__file__).resolve().parents[2] / '66075.pdf'))[0]
    assert '683544' in invoice.receiver_address
    assert '\n' in invoice.receiver_address
