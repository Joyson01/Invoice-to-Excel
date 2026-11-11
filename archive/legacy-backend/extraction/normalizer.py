"""Normalize raw extracted data into the InvoiceData schema.

This is the bridge between raw extraction output and the validated,
structured InvoiceData model that the rest of the application uses.
"""

import logging
import uuid
from typing import Any

from app.config import settings
from app.models.schemas import BoxSchema, FieldValue, InvoiceData, LineItemSchema

log = logging.getLogger(__name__)


def create_field(
    value: Any,
    confidence: float = 1.0,
    status: str = "valid",
    message: str = "",
) -> FieldValue:
    """Create a FieldValue, auto-detecting missing values."""
    if value is None or value == "":
        return FieldValue(
            value=value if value is not None else "",
            confidence=0.0,
            status="missing",
            message=message or "Value not extracted",
        )
    return FieldValue(value=value, confidence=confidence, status=status, message=message)


def _ensure_line_item_schemas(items: list) -> list[LineItemSchema]:
    """Convert items to LineItemSchema if they aren't already."""
    result = []
    for item in items:
        if isinstance(item, LineItemSchema):
            result.append(item)
        elif isinstance(item, dict):
            result.append(LineItemSchema(**item))
        else:
            log.warning("Unknown line item type: %s", type(item))
    return result


def _compute_order_description(
    line_items: list[LineItemSchema],
    brand_map: dict[str, str],
    default_brand: str,
    template: str,
) -> str:
    """Generate order description from line items."""
    total_qty = sum(i.quantity for i in line_items)
    sku_count = len(line_items)

    # Detect brand from first item
    brand = default_brand
    for item in line_items:
        if item.description:
            parts = item.description.split()
            if parts:
                first_word = parts[0].upper().strip(".,-")
                if first_word in brand_map:
                    brand = brand_map[first_word]
                    break
                # Use first word title-cased as brand if not in map
                brand = parts[0].title()
                break

    try:
        return template.format(brand=brand, sku_count=sku_count, total_qty=total_qty)
    except (KeyError, IndexError):
        return f"{brand} products - {sku_count} SKUs, {total_qty} units"


def _build_boxes(raw_data: dict) -> list[BoxSchema]:
    """Build box schemas from raw data and settings."""
    boxes_count = raw_data.get("boxes", 0)
    if not boxes_count or boxes_count < 1:
        boxes_count = 1

    if settings.BOX_ROW_MODE == "per_box":
        return [
            BoxSchema(
                length=settings.BOX_LENGTH_DEFAULT,
                width=settings.BOX_WIDTH_DEFAULT,
                height=settings.BOX_HEIGHT_DEFAULT,
                weight=settings.BOX_WEIGHT_DEFAULT,
                quantity=1,
            )
            for _ in range(boxes_count)
        ]
    else:
        return [
            BoxSchema(
                length=settings.BOX_LENGTH_DEFAULT,
                width=settings.BOX_WIDTH_DEFAULT,
                height=settings.BOX_HEIGHT_DEFAULT,
                weight=settings.BOX_WEIGHT_DEFAULT,
                quantity=boxes_count,
            )
        ]


def normalize_invoice_data(raw_data: dict[str, Any]) -> InvoiceData:
    """Convert raw extraction dict into a fully-typed InvoiceData."""
    inv_no = raw_data.get("invoice_number", "")
    po_no = raw_data.get("po_number", "")

    # Order ID logic: use PO if configured and available, else invoice number
    if settings.ORDER_ID_SOURCE == "po" and po_no:
        order_id = po_no
    elif inv_no:
        order_id = inv_no
    else:
        order_id = ""

    # Process line items
    line_items = _ensure_line_item_schemas(raw_data.get("line_items", []))

    # Order description
    order_desc = _compute_order_description(
        line_items,
        settings.brand_map_dict,
        settings.DEFAULT_BRAND,
        settings.DESCRIPTION_TEMPLATE,
    )

    # Boxes
    boxes = _build_boxes(raw_data)

    # Warnings from extraction
    warnings = list(raw_data.get("warnings", []))

    # PO missing warning
    if not po_no and settings.ORDER_ID_SOURCE == "po":
        if "PO NO missing" not in " ".join(warnings):
            warnings.append("PO NO missing - falling back to invoice number for Order_ID")

    # Box count missing warning
    if not raw_data.get("boxes"):
        warnings.append("NO.OF BOXES missing or zero - defaulting to 1")

    # Build pincode field with validation context
    pincode_val = raw_data.get("pincode", "")
    mobile_val = raw_data.get("mobile", "")

    return InvoiceData(
        id=str(uuid.uuid4()),
        source_file=raw_data.get("source_file", ""),
        invoice_number=create_field(
            inv_no, raw_data.get("invoice_number_conf", 0.0)
        ),
        invoice_date=create_field(
            raw_data.get("invoice_date", ""),
            raw_data.get("invoice_date_conf", 0.0),
        ),
        order_id=create_field(order_id),
        po_number=create_field(
            po_no, raw_data.get("po_number_conf", 0.0)
        ),
        invoice_amount=create_field(
            raw_data.get("net_amount"),
            raw_data.get("net_amount_conf", 0.0),
        ),
        eway_bill_number=create_field(
            raw_data.get("eway_bill", ""),
            raw_data.get("eway_bill_conf", 0.0),
        ),
        receiver_name=create_field(
            raw_data.get("receiver_name", ""),
            raw_data.get("receiver_name_conf", 0.0),
        ),
        receiver_address=create_field(raw_data.get("address", "")),
        receiver_pincode=create_field(pincode_val),
        receiver_mobile=create_field(mobile_val),
        receiver_email=create_field(settings.RECEIVER_EMAIL_DEFAULT),
        warehouse_name=create_field(settings.WAREHOUSE_NAME),
        payment_mode=create_field(settings.PAYMENT_MODE_DEFAULT),
        cod_value=create_field(settings.COD_VALUE_DEFAULT),
        insurance=create_field(settings.INSURANCE_DEFAULT),
        order_description=create_field(order_desc),
        invoice_url=create_field(settings.INVOICE_URL_DEFAULT),
        delivery_challan=create_field(settings.DELIVERY_CHALLAN_DEFAULT),
        declaration=create_field(settings.DECLARATION_DEFAULT),
        other_supporting_documents=create_field(
            settings.OTHER_SUPPORTING_DOCUMENTS_DEFAULT
        ),
        reason=create_field(""),
        boxes=boxes,
        line_items=line_items,
        warnings=warnings,
        status="ready",
    )
