import abc
import logging
from typing import Tuple, Optional
import numpy as np
import pdfplumber
from app.document_layout import OCRPage, words_to_lines

log = logging.getLogger(__name__)

class BaseOCRProvider(abc.ABC):
    """Abstract Base Class for OCR providers, allowing easy swapping of OCR backends."""
    
    @abc.abstractmethod
    def extract_text_from_image(self, image_np: np.ndarray) -> Tuple[str, float]:
        """Extract text and confidence score from a single image (numpy array).
        Returns: (extracted_text, confidence_score_0_to_1)
        """
        pass

    def extract_text_from_pdf(self, pdf_path: str, resolution: int = 200) -> Tuple[str, float]:
        """Render all pages of a PDF to images and extract text using OCR."""
        combined_text = []
        confidences = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    pil_img = page.to_image(resolution=resolution).original
                    img_np = np.array(pil_img)
                    text, conf = self.extract_text_from_image(img_np)
                    if text.strip():
                        combined_text.append(text)
                        confidences.append(conf)
        except Exception as exc:
            log.error("Failed to render and OCR PDF %s: %s", pdf_path, exc)
            return "", 0.0

        full_text = "\n".join(combined_text)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return full_text, avg_conf


class RapidOCRProvider(BaseOCRProvider):
    """Production-grade OCR provider using RapidOCR (ONNX runtime).
    Self-contained, fast, and does not require system tesseract binary.
    """
    def __init__(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr_engine = RapidOCR()
        except ImportError:
            log.warning("rapidocr-onnxruntime not installed. OCR fallback will be unavailable.")
            self.ocr_engine = None

    def _recognize(self, image_np):
        if not self.ocr_engine:
            return [], 0.0

        try:
            results, _ = self.ocr_engine(image_np)
            if not results:
                return [], 0.0

            words = []
            scores = []
            for item in results:
                line_text = item[1]
                try:
                    score = float(item[2])
                except (ValueError, TypeError):
                    continue
                scores.append(score)
                if score < 0.6:
                    continue
                polygon = item[0]
                words.append(dict(text=line_text,
                    x0=min(p[0] for p in polygon), x1=max(p[0] for p in polygon),
                    top=min(p[1] for p in polygon), bottom=max(p[1] for p in polygon)))
            avg_score = sum(scores) / len(scores) if scores else 0.0
            return words, avg_score
        except Exception as exc:
            log.error("RapidOCR error: %s", exc)
            return [], 0.0

    def extract_text_from_image(self, image_np: np.ndarray) -> Tuple[str, float]:
        words, score = self._recognize(image_np)
        return '\n'.join(words_to_lines(words)), score

    def extract_pages_from_pdf(self, pdf_path, resolution=200):
        pages, scores = [], []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                image = page.to_image(resolution=resolution).original
                words, score = self._recognize(np.array(image))
                # Use PDF units so native text and OCR share the same layout rules.
                for word in words:
                    for key in ('x0', 'x1'):
                        word[key] *= page.width / image.width
                    for key in ('top', 'bottom'):
                        word[key] *= page.height / image.height
                pages.append(OCRPage(page.width, page.height, words))
                scores.append(score)
        return pages, sum(scores) / len(scores) if scores else 0.0

    def extract_text_from_pdf(self, pdf_path, resolution=200):
        pages, score = self.extract_pages_from_pdf(pdf_path, resolution)
        return '\n'.join(page.extract_text() for page in pages), score


# Factory function to get active OCR provider
_active_ocr_provider: Optional[BaseOCRProvider] = None

def get_ocr_provider() -> BaseOCRProvider:
    """Return the configured OCR provider instance."""
    global _active_ocr_provider
    if _active_ocr_provider is None:
        _active_ocr_provider = RapidOCRProvider()
    return _active_ocr_provider
