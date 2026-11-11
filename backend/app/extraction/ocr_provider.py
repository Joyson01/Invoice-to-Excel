"""OCR abstraction layer.

Provides a pluggable interface for OCR providers. The default implementation
is a no-op that returns empty text. Replace with Tesseract, Google Vision,
AWS Textract, or Azure Form Recognizer by implementing the OCRProvider interface.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class OCRProvider(ABC):
    """Abstract base class for OCR providers."""

    @abstractmethod
    def extract_text(self, image_path: str) -> str:
        """Extract text from an image file.

        Args:
            image_path: Path to the image file.

        Returns:
            Extracted text string.
        """
        ...

    @abstractmethod
    def extract_from_pdf_page(self, pdf_path: str, page_number: int) -> str:
        """Extract text from a specific PDF page using OCR.

        Args:
            pdf_path: Path to the PDF file.
            page_number: 1-based page number.

        Returns:
            Extracted text string.
        """
        ...


class NoOpOCRProvider(OCRProvider):
    """Default no-op OCR provider. Returns empty strings.

    Use this as a fallback when no OCR engine is configured.
    """

    def extract_text(self, image_path: str) -> str:
        log.debug("NoOp OCR called for %s - no OCR configured", image_path)
        return ""

    def extract_from_pdf_page(self, pdf_path: str, page_number: int) -> str:
        log.debug(
            "NoOp OCR called for %s page %d - no OCR configured",
            pdf_path, page_number,
        )
        return ""


class TesseractOCRProvider(OCRProvider):
    """Tesseract-based OCR provider (optional dependency).

    Install: pip install pytesseract Pillow
    Also requires tesseract-ocr system package.
    """

    def extract_text(self, image_path: str) -> str:
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            return pytesseract.image_to_string(img)
        except ImportError:
            log.warning("pytesseract not installed. Install with: pip install pytesseract Pillow")
            return ""
        except Exception as exc:
            log.error("Tesseract OCR failed for %s: %s", image_path, exc)
            return ""

    def extract_from_pdf_page(self, pdf_path: str, page_number: int) -> str:
        try:
            import pytesseract
            from PIL import Image
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                if page_number > len(pdf.pages):
                    return ""
                page = pdf.pages[page_number - 1]
                img = page.to_image(resolution=300)
                return pytesseract.image_to_string(img.original)
        except ImportError:
            log.warning("pytesseract not installed")
            return ""
        except Exception as exc:
            log.error("Tesseract OCR failed for %s page %d: %s", pdf_path, page_number, exc)
            return ""


def get_ocr_provider() -> OCRProvider:
    """Factory function to get the configured OCR provider."""
    # Future: read from settings which provider to use
    return NoOpOCRProvider()
