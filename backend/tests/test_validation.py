from app.validator import validate_invoice


def test_zero_invoice_amount_requires_correction(dummy_invoice):
    dummy_invoice.invoice_amount = 0
    result = validate_invoice(dummy_invoice)
    assert result.status == 'Failed'
    assert 'Invoice Amount must be greater than 0' in result.warnings
