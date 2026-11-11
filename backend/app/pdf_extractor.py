import os
import logging
from typing import List, Dict, Any, Optional
import pdfplumber

log = logging.getLogger(__name__)

class PDFPageData:
    def __init__(self, page_number: int, text: str, words: List[Dict[str, Any]], width: float, height: float):
        self.page_number = page_number
        self.text = text
        self.words = words
        self.width = width
        self.height = height

def extract_pdf_data(file_path: str) -> List[PDFPageData]:
    """Extract page text and word bounding boxes safely from PDF using pdfplumber."""
    pages_data: List[PDFPageData] = []
    
    with pdfplumber.open(file_path) as pdf:
        for idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            words = []
            try:
                raw_words = page.extract_words()
                # Copy word dicts to detach from closed pdfplumber context
                for w in raw_words:
                    words.append({
                        "text": w.get("text", ""),
                        "x0": float(w.get("x0", 0.0)),
                        "x1": float(w.get("x1", 0.0)),
                        "top": float(w.get("top", 0.0)),
                        "bottom": float(w.get("bottom", 0.0)),
                        "width": float(w.get("width", 0.0)),
                        "height": float(w.get("height", 0.0)),
                    })
            except Exception as e:
                log.warning("Could not extract words on page %d of %s: %s", idx + 1, file_path, e)
                
            pages_data.append(PDFPageData(
                page_number=idx + 1,
                text=text,
                words=words,
                width=float(page.width),
                height=float(page.height)
            ))
            
    return pages_data
