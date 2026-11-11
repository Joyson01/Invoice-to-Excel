from app.models import LineItem
from app.parser import derive_order_description


def test_description_summarizes_skus_and_quantities():
    items = [LineItem(description='CET Lotion', quantity=10),
             LineItem(description='CET Cleanser', quantity=5)]
    assert derive_order_description(items) == 'Cetaphil products - 2 SKUs, 15 units'
