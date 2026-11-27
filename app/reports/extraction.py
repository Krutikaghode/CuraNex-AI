"""Turn uploaded PDFs and images into plain text.

PDF pages with an embedded text layer are read directly (fast, exact). Pages without one,
which is what scanners produce, are rendered and passed to Tesseract OCR. Images go
straight to OCR.
"""

import io
import shutil
from dataclasses import dataclass, field

import pymupdf
import pytesseract
from PIL import Image, ImageOps

# A page with fewer characters than this is treated as scanned and sent to OCR.
MIN_TEXT_CHARS = 25
OCR_DPI = 300


class UnsupportedFileError(ValueError):
    """The upload is not a PDF, PNG or JPEG, judged by its bytes rather than its name."""


@dataclass
class ExtractionResult:
    text: str
    method: str  # text | ocr | mixed | none
    page_count: int
    warnings: list[str] = field(default_factory=list)


def sniff_content_type(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise UnsupportedFileError("Only PDF, PNG and JPEG files are supported.")


def ocr_available() -> bool:
    return shutil.which(pytesseract.pytesseract.tesseract_cmd) is not None


def _ocr(image: Image.Image) -> str:
    image = ImageOps.exif_transpose(image).convert("L")
    return pytesseract.image_to_string(image)


def _join(pages: list[str]) -> str:
    return "\n\n".join(
        f"--- Page {number} ---\n{text.strip()}" for number, text in enumerate(pages, 1)
    ).strip()


def extract_text(data: bytes, content_type: str) -> ExtractionResult:
    if content_type == "application/pdf":
        return _extract_pdf(data)
    return _extract_image(data)


def _extract_image(data: bytes) -> ExtractionResult:
    if not ocr_available():
        return ExtractionResult("", "none", 1, ["Tesseract is not installed; OCR skipped."])
    with Image.open(io.BytesIO(data)) as image:
        text = _ocr(image)
    return ExtractionResult(_join([text]), "ocr", 1)


def _extract_pdf(data: bytes) -> ExtractionResult:
    pages: list[str] = []
    used_text = used_ocr = False
    warnings: list[str] = []
    can_ocr = ocr_available()
    with pymupdf.open(stream=data, filetype="pdf") as document:
        if document.needs_pass:
            raise UnsupportedFileError("Password-protected PDFs are not supported.")
        for page in document:
            text = page.get_text("text")
            if len(text.strip()) >= MIN_TEXT_CHARS:
                used_text = True
            elif can_ocr:
                pixmap = page.get_pixmap(dpi=OCR_DPI)
                with Image.open(io.BytesIO(pixmap.tobytes("png"))) as image:
                    text = _ocr(image)
                used_ocr = True
            else:
                warnings.append(f"Page {page.number + 1} has no text layer and OCR is unavailable.")
            pages.append(text)
        page_count = document.page_count

    method = {
        (True, True): "mixed",
        (True, False): "text",
        (False, True): "ocr",
        (False, False): "none",
    }[(used_text, used_ocr)]
    return ExtractionResult(_join(pages), method, page_count, warnings)
