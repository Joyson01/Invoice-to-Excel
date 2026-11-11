"""PDF text and word extraction using pdfplumber.

Returns structured page data that can be consumed downstream even after
the pdfplumber file handle is closed.
"""

import logging
from typing import Any

import pdfplumber

log = logging.getLogger(__name__)


def extract_pdf_data(path: str) -> list[dict[str, Any]]:
    """Open a PDF and extract text + word-position data from each page.

    Returns a list of dicts, one per page:
        {
            "page_number": int,
            "text": str,
            "words": list[dict],      # pdfplumber word dicts
            "width": float,
            "height": float,
        }

    The returned data is fully self-contained (no references to the
    pdfplumber objects which become invalid after the file is closed).
    """
    pages_data: list[dict[str, Any]] = []

    try:
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                log.warning("PDF has no pages: %s", path)
                return pages_data

            for page in pdf.pages:
                text = page.extract_text() or ""
                words = page.extract_words() or []
                # Materialise the word dicts so they survive after close
                words = [dict(w) for w in words]

                pages_data.append({
                    "page_number": page.page_number,
                    "text": text,
                    "words": words,
                    "width": float(page.width),
                    "height": float(page.height),
                })

    except Exception as exc:
        log.error("Failed to open PDF %s: %s", path, exc)
        raise

    return pages_data
