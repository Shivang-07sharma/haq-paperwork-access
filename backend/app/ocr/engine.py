"""OCR with a provider chain.

Input here is a phone photo of a worn government document, not a clean scan, so
the pipeline is: normalise the image (EXIF rotation, greyscale, upscale) then run
a local ONNX text detector/recogniser. Nothing calls out to a cloud service --
these documents carry identity numbers and must not leave the machine.

Providers are tried in order and the first one that can handle the file wins.
If none can, we still return a result with warnings so the caller can fall back
to asking the person to type the fields in. OCR failing is never fatal.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Phone photos are often smaller than the detector likes; anything under this on
# the long edge gets upscaled before detection.
MIN_LONG_EDGE = 1000
MAX_LONG_EDGE = 2600


@dataclass
class OcrLine:
    text: str
    confidence: float
    box: list | None = None


@dataclass
class OcrResult:
    text: str = ""
    lines: list[OcrLine] = field(default_factory=list)
    confidence: float = 0.0
    engine: str = "none"
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.text.strip())


# --------------------------------------------------------------------------
# image normalisation
# --------------------------------------------------------------------------

def _prepare_image(raw: bytes):
    """EXIF-rotate, flatten to greyscale, and resize into the detector's sweet spot."""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)            # phone photos are usually rotated
    img = img.convert("L")                        # greyscale: colour adds nothing here
    img = ImageOps.autocontrast(img)              # faded print, poor lighting

    long_edge = max(img.size)
    if long_edge < MIN_LONG_EDGE:
        scale = MIN_LONG_EDGE / long_edge
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    elif long_edge > MAX_LONG_EDGE:
        scale = MAX_LONG_EDGE / long_edge
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)

    return img.convert("RGB")


# --------------------------------------------------------------------------
# providers
# --------------------------------------------------------------------------

class RapidOcrProvider:
    """PP-OCR models via onnxruntime. Self-contained: no system binary needed."""

    name = "rapidocr-onnx"
    _engine = None

    def can_handle(self, mime: str) -> bool:
        return mime.startswith("image/")

    @classmethod
    def _get_engine(cls):
        # Model load costs about a second, so keep one instance around.
        if cls._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            cls._engine = RapidOCR()
        return cls._engine

    def run(self, raw: bytes, mime: str) -> OcrResult:
        import numpy as np

        img = _prepare_image(raw)
        engine = self._get_engine()
        detections, _elapsed = engine(np.array(img))

        if not detections:
            return OcrResult(engine=self.name, warnings=["no_text_detected"])

        lines: list[OcrLine] = []
        for det in detections:
            # RapidOCR yields [box, text, score]
            box, text, score = det[0], det[1], float(det[2])
            lines.append(OcrLine(text=str(text).strip(), confidence=score, box=_flatten_box(box)))

        lines = [ln for ln in lines if ln.text]
        confidence = sum(ln.confidence for ln in lines) / len(lines) if lines else 0.0
        return OcrResult(
            text="\n".join(ln.text for ln in lines),
            lines=lines,
            confidence=round(confidence, 4),
            engine=self.name,
        )


class PdfTextProvider:
    """Many government PDFs already carry a text layer -- read it rather than guess."""

    name = "pdf-text"

    def can_handle(self, mime: str) -> bool:
        return mime == "application/pdf"

    def run(self, raw: bytes, mime: str) -> OcrResult:
        import pdfplumber

        chunks: list[str] = []
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages[:10]:   # an ID document is never longer than this
                chunks.append(page.extract_text() or "")

        text = "\n".join(c for c in chunks if c.strip()).strip()
        if not text:
            return OcrResult(engine=self.name, warnings=["pdf_has_no_text_layer"])

        lines = [OcrLine(text=ln.strip(), confidence=0.99) for ln in text.splitlines() if ln.strip()]
        return OcrResult(text=text, lines=lines, confidence=0.99, engine=self.name)


class TesseractProvider:
    """Used only when a system Tesseract happens to be installed."""

    name = "tesseract"

    def can_handle(self, mime: str) -> bool:
        if not mime.startswith("image/"):
            return False
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def run(self, raw: bytes, mime: str) -> OcrResult:
        import pytesseract

        img = _prepare_image(raw)
        # Devanagari and Tamil packs are often absent; English still lifts the
        # numbers and Latin-script names, which is what eligibility needs.
        text = pytesseract.image_to_string(img, lang="eng")
        lines = [OcrLine(text=ln.strip(), confidence=0.8) for ln in text.splitlines() if ln.strip()]
        return OcrResult(
            text="\n".join(ln.text for ln in lines),
            lines=lines,
            confidence=0.8 if lines else 0.0,
            engine=self.name,
        )


PROVIDERS = [RapidOcrProvider(), PdfTextProvider(), TesseractProvider()]


def _flatten_box(box) -> list | None:
    try:
        return [[float(x), float(y)] for x, y in box]
    except Exception:
        return None


def run_ocr(raw: bytes, mime: str) -> OcrResult:
    """Try each provider that claims the mime type; return the first real result."""
    attempted: list[str] = []
    for provider in PROVIDERS:
        try:
            if not provider.can_handle(mime):
                continue
        except Exception:            # a provider probe should never break ingest
            continue

        attempted.append(provider.name)
        try:
            result = provider.run(raw, mime)
        except Exception as exc:
            logger.warning("OCR provider %s failed: %s", provider.name, exc)
            continue

        if result.ok:
            return result

    return OcrResult(
        engine=attempted[0] if attempted else "none",
        warnings=["ocr_unavailable_enter_manually"],
    )


def ocr_available() -> dict:
    """Reported on the health endpoint so the UI can warn before someone uploads."""
    status = {}
    for provider in PROVIDERS:
        try:
            if provider.name == "rapidocr-onnx":
                import rapidocr_onnxruntime  # noqa: F401

                status[provider.name] = True
            elif provider.name == "pdf-text":
                import pdfplumber  # noqa: F401

                status[provider.name] = True
            else:
                status[provider.name] = provider.can_handle("image/png")
        except Exception:
            status[provider.name] = False
    return status
