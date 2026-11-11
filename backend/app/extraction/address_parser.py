"""Address block extraction from PDF page word-position data.

Works with pre-extracted word dicts (not live pdfplumber page objects)
so it can be used after the PDF file handle is closed.
"""

import logging
from typing import Any

log = logging.getLogger(__name__)


def _find_word(words: list[dict], *prefixes: str) -> dict | None:
    """Find the first word whose text starts with any of the given prefixes."""
    for w in words:
        text = w.get("text", "").strip().lower()
        for prefix in prefixes:
            if text.startswith(prefix):
                return w
    return None


def _crop_text_from_words(
    words: list[dict], x0: float, top: float, x1: float, bottom: float
) -> str:
    """Simulate pdfplumber crop: filter words inside a bounding box and
    reconstruct text line by line."""
    in_box = []
    for w in words:
        wx0 = w.get("x0", 0)
        wtop = w.get("top", 0)
        wx1 = w.get("x1", 0)
        wbottom = w.get("bottom", 0)
        # Word is inside if its centre falls within the box
        cx = (wx0 + wx1) / 2
        cy = (wtop + wbottom) / 2
        if x0 <= cx <= x1 and top <= cy <= bottom:
            in_box.append(w)

    if not in_box:
        return ""

    # Sort by vertical then horizontal position
    in_box.sort(key=lambda w: (w.get("top", 0), w.get("x0", 0)))

    # Group into lines (words within 3pt vertical tolerance)
    lines: list[list[dict]] = []
    current_line: list[dict] = [in_box[0]]
    for w in in_box[1:]:
        if abs(w.get("top", 0) - current_line[-1].get("top", 0)) < 5:
            current_line.append(w)
        else:
            lines.append(current_line)
            current_line = [w]
    lines.append(current_line)

    text_lines = []
    for line in lines:
        line.sort(key=lambda w: w.get("x0", 0))
        text_lines.append(" ".join(w.get("text", "") for w in line))

    return "\n".join(text_lines)


def extract_address_blocks(page_data: dict) -> dict[str, list[str]]:
    """Extract Billed-to and Shipped-to address blocks from page word data.

    Args:
        page_data: dict with 'words', 'width', 'height' keys

    Returns:
        {"shipped": [...], "billed": [...]}
    """
    words = page_data.get("words", [])
    page_width = page_data.get("width", 600)

    if not words:
        return {"shipped": [], "billed": []}

    # Find anchors
    shipped_anchor = _find_word(
        words, "shipped", "ship to", "shipto", "consignee", "delivery address"
    )
    billed_anchor = _find_word(words, "billed", "bill to", "billto")

    if not billed_anchor and not shipped_anchor:
        return {"shipped": [], "billed": []}

    # Determine the top of the address block
    anchor = billed_anchor or shipped_anchor
    top = anchor["bottom"] + 1

    # Find the bottom boundary (usually "Party PAN" or similar)
    party_anchor = None
    for w in words:
        text = w.get("text", "").strip().lower()
        if text.startswith("party") and w.get("top", 0) > top:
            party_anchor = w
            break
    # Also look for "GSTIN" as alternate bottom boundary
    if not party_anchor:
        for w in words:
            text = w.get("text", "").strip().lower()
            if text.startswith("gstin") and w.get("top", 0) > top + 20:
                party_anchor = w
                break

    bottom = party_anchor["top"] - 1 if party_anchor else top + 120

    blocks: dict[str, list[str]] = {"shipped": [], "billed": []}

    if shipped_anchor and billed_anchor:
        # Both exist - determine which is left/right
        if shipped_anchor["x0"] > billed_anchor["x0"]:
            # Shipped is on the right
            split_x = shipped_anchor["x0"] - 4
            shipped_bbox = (split_x, top, page_width, bottom)
            billed_bbox = (0, top, split_x, bottom)
        else:
            # Billed is on the right
            split_x = billed_anchor["x0"] - 4
            billed_bbox = (split_x, top, page_width, bottom)
            shipped_bbox = (0, top, split_x, bottom)

        shipped_text = _crop_text_from_words(words, *shipped_bbox)
        blocks["shipped"] = [
            ln.strip().rstrip(",") for ln in shipped_text.splitlines() if ln.strip()
        ]

        billed_text = _crop_text_from_words(words, *billed_bbox)
        blocks["billed"] = [
            ln.strip().rstrip(",") for ln in billed_text.splitlines() if ln.strip()
        ]
    elif billed_anchor:
        # Only billed-to found
        bbox = (0, top, page_width, bottom)
        text = _crop_text_from_words(words, *bbox)
        lines = [ln.strip().rstrip(",") for ln in text.splitlines() if ln.strip()]
        blocks["billed"] = lines
        blocks["shipped"] = lines
    elif shipped_anchor:
        # Only shipped-to found
        bbox = (0, top, page_width, bottom)
        text = _crop_text_from_words(words, *bbox)
        lines = [ln.strip().rstrip(",") for ln in text.splitlines() if ln.strip()]
        blocks["shipped"] = lines
        blocks["billed"] = lines

    return blocks
