"""Bounded selectable-text extraction for the local PDF-upload POC."""

from __future__ import annotations

from dataclasses import dataclass

import fitz  # PyMuPDF
import pytesseract
from PIL import Image


MAX_PAGES = 50
OCR_DPI = 150
MAX_OCR_PIXELS_PER_PAGE = 10_000_000
OCR_TIMEOUT_SECONDS = 15


class PdfExtractionError(ValueError):
    """A PDF cannot be processed safely by this local POC."""


@dataclass(frozen=True)
class ExtractionResult:
    status: str
    text: str
    page_count: int
    message: str | None = None


def _ocr_page(page: fitz.Page) -> str:
    """Rasterize and OCR one page with deliberate local-POC resource bounds."""
    scale = OCR_DPI / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    if pixmap.width * pixmap.height > MAX_OCR_PIXELS_PER_PAGE:
        raise PdfExtractionError("PDF page is too large for the local OCR limit.")
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    try:
        return pytesseract.image_to_string(
            image, lang="eng", config="--psm 6", timeout=OCR_TIMEOUT_SECONDS
        ).strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise PdfExtractionError(
            "OCR is not available: install Tesseract and make the tesseract command available on PATH."
        ) from exc
    except RuntimeError as exc:
        raise PdfExtractionError("OCR timed out or could not process this PDF page.") from exc


def extract_text_from_pdf(pdf_bytes: bytes, *, enable_ocr: bool = False) -> ExtractionResult:
    """Extract embedded text without saving the uploaded document.

    OCR is opt-in because it is slower and has different accuracy/privacy
    considerations. An empty text layer therefore remains explicit unless the
    caller asks to OCR it.
    """
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except (fitz.FileDataError, RuntimeError) as exc:
        raise PdfExtractionError("The uploaded file is not a readable PDF.") from exc

    try:
        if document.needs_pass:
            raise PdfExtractionError("Password-protected PDFs are not supported by this POC.")
        if document.page_count > MAX_PAGES:
            raise PdfExtractionError(f"PDFs may contain at most {MAX_PAGES} pages.")

        page_text = [page.get_text("text").strip() for page in document]
        text = "\n\n".join(part for part in page_text if part).strip()
        if not text:
            if enable_ocr:
                ocr_text = "\n\n".join(_ocr_page(page) for page in document).strip()
                if ocr_text:
                    return ExtractionResult(
                        status="ocr_extracted", text=ocr_text, page_count=document.page_count,
                        message="Text was extracted with local OCR; review it for recognition errors.",
                    )
            return ExtractionResult(
                status="ocr_required",
                text="",
                page_count=document.page_count,
                message=("No selectable text was found. This appears to be a scanned or "
                         "image-only PDF; OCR is a later POC step."),
            )
        return ExtractionResult(status="text_extracted", text=text, page_count=document.page_count)
    finally:
        document.close()
