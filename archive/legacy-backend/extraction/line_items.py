import re
from app.models.schemas import LineItemSchema

RE_ITEM = re.compile(
    r"^\s*\d+\.\s+(?P<desc>.+?)\s+(?P<item_code>[A-Z]{1,3}\d{2,5})\s+"
    r"(?P<hsn>\d{4,8})\s+(?P<qty>\d+)\s+(?P<mrp>[\d,]+\.\d{2})"
)

def extract_line_items(text: str) -> list[LineItemSchema]:
    items = []
    for line in text.splitlines():
        im = RE_ITEM.match(line)
        if im:
            items.append(LineItemSchema(
                description=im.group("desc").strip(),
                item_code=im.group("item_code"),
                hsn=im.group("hsn"),
                quantity=int(im.group("qty")),
                mrp=float(im.group("mrp").replace(",", ""))
            ))
    return items

def extract_grand_total_qty(text: str) -> int:
    m = re.search(r"Grand\s*Total\s+(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0
