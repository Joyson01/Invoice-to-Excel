"""Fixtures for the active flat app.models schema."""
import pytest
from app.models import InvoiceData


@pytest.fixture
def dummy_invoice():
    return InvoiceData(order_id='PO-1', invoice_number='INV-1', invoice_amount=100)
