"""Smoke test for the active PDF extraction entry point."""
from pathlib import Path
from app.parser import parse_pdf


def test_extraction():
    invoice = parse_pdf(str(Path(__file__).resolve().parents[1] / '66075.pdf'))[0]
    assert invoice.invoice_number == 'RA/66075'
    assert invoice.invoice_amount == 1587440.0
