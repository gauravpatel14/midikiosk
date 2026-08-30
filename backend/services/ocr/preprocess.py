"""Image preprocessing for OCR: deskew, denoise, binarise, upscale.

PRD §6.3.1/§6.3.2 targets >95% printed-text accuracy at 300 DPI. Kiosk scans are
often skewed, shadowed phone photos, so preprocessing is what actually moves
accuracy. Uses OpenCV+NumPy when installed, and degrades to Pillow-only
operations otherwise so the pipeline never hard-fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except Exception:  # noqa: BLE001
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    CV2_AVAILABLE = False

MIN_OCR_WIDTH = 1200
MAX_OCR_WIDTH = 4000


@dataclass(slots=True)
class PreprocessResult:
    path: str
    steps: List[str] = field(default_factory=list)
    skew_angle: float = 0.0
    width: int = 0
    height: int = 0
    is_grayscale: bool = False
    estimated_dpi: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": self.steps,
            "skew_angle_deg": round(self.skew_angle, 2),
            "dimensions": [self.width, self.height],
            "grayscale": self.is_grayscale,
            "estimated_dpi": self.estimated_dpi,
        }


def deskew_image(image: "Image.Image") -> Tuple["Image.Image", float]:
    """Estimate and correct page rotation. Returns (image, angle_degrees)."""
    if not CV2_AVAILABLE:
        return image, 0.0
    try:
        array = np.array(image.convert("L"))
        inverted = cv2.bitwise_not(array)
        thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = cv2.findNonZero(thresh)
        if coords is None:
            return image, 0.0
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.35 or abs(angle) > 25:
            return image, float(angle)
        rotated = image.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor="white")
        return rotated, float(angle)
    except Exception as exc:  # noqa: BLE001
        logger.warning("deskew_failed", error=str(exc))
        return image, 0.0


def denoise_image(image: "Image.Image") -> "Image.Image":
    """Remove scanner speckle while preserving thin Devanagari strokes."""
    if CV2_AVAILABLE:
        try:
            array = np.array(image.convert("L"))
            denoised = cv2.fastNlMeansDenoising(array, None, h=7, templateWindowSize=7, searchWindowSize=21)
            return Image.fromarray(denoised)
        except Exception as exc:  # noqa: BLE001
            logger.warning("denoise_failed", error=str(exc))
    return image.convert("L").filter(ImageFilter.MedianFilter(size=3))


def binarise_image(image: "Image.Image") -> "Image.Image":
    """Adaptive threshold — critical for photos with uneven lighting."""
    if CV2_AVAILABLE:
        try:
            array = np.array(image.convert("L"))
            binary = cv2.adaptiveThreshold(
                array, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
            )
            return Image.fromarray(binary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("binarise_failed", error=str(exc))
    return ImageOps.autocontrast(image.convert("L"))


def preprocess_for_ocr(
    source_path: str,
    destination_path: Optional[str] = None,
    *,
    binarise: bool = False,
) -> PreprocessResult:
    """Full preprocessing chain, writing a PNG the OCR engines can consume."""
    src = Path(source_path)
    dest = Path(destination_path or src.with_name(f"{src.stem}_prep.png"))
    steps: List[str] = []

    with Image.open(src) as raw:
        raw.load()
        dpi = 0
        info_dpi = raw.info.get("dpi")
        if isinstance(info_dpi, (tuple, list)) and info_dpi:
            dpi = int(info_dpi[0] or 0)
        image = ImageOps.exif_transpose(raw)
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")
            steps.append("mode_normalised")

        image, angle = deskew_image(image)
        if abs(angle) >= 0.35:
            steps.append(f"deskew({angle:.2f})")

        # Upscale small captures so 8–10 pt prescription text is resolvable.
        if image.width < MIN_OCR_WIDTH:
            factor = min(3.0, MIN_OCR_WIDTH / max(1, image.width))
            image = image.resize(
                (int(image.width * factor), int(image.height * factor)), Image.LANCZOS
            )
            steps.append(f"upscale(x{factor:.2f})")
        elif image.width > MAX_OCR_WIDTH:
            factor = MAX_OCR_WIDTH / image.width
            image = image.resize(
                (MAX_OCR_WIDTH, int(image.height * factor)), Image.LANCZOS
            )
            steps.append("downscale")

        image = denoise_image(image)
        steps.append("denoise")

        image = ImageEnhance.Contrast(image).enhance(1.35)
        steps.append("contrast")
        image = image.filter(ImageFilter.UnsharpMask(radius=1.4, percent=130, threshold=3))
        steps.append("sharpen")

        if binarise:
            image = binarise_image(image)
            steps.append("adaptive_threshold")

        dest.parent.mkdir(parents=True, exist_ok=True)
        image.save(dest, format="PNG", dpi=(settings.OCR_DPI, settings.OCR_DPI))

        return PreprocessResult(
            path=str(dest),
            steps=steps,
            skew_angle=angle,
            width=image.width,
            height=image.height,
            is_grayscale=image.mode == "L",
            estimated_dpi=dpi or settings.OCR_DPI,
        )


def pdf_to_images(pdf_path: str, output_dir: str, max_pages: int) -> List[str]:
    """Rasterise a scanned PDF. Prefers PyMuPDF, falls back to pdf2image."""
    outputs: List[str] = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:  # PyMuPDF: no external binary needed
        import fitz  # type: ignore[import-not-found]

        with fitz.open(pdf_path) as doc:
            zoom = settings.OCR_DPI / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            for index, page in enumerate(doc):
                if index >= max_pages:
                    break
                target = Path(output_dir) / f"page_{index + 1:03d}.png"
                page.get_pixmap(matrix=matrix).save(str(target))
                outputs.append(str(target))
        return outputs
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("pymupdf_render_failed", error=str(exc))

    try:  # pdf2image requires poppler-utils
        from pdf2image import convert_from_path  # type: ignore[import-not-found]

        pages = convert_from_path(pdf_path, dpi=settings.OCR_DPI, last_page=max_pages)
        for index, page in enumerate(pages):
            target = Path(output_dir) / f"page_{index + 1:03d}.png"
            page.save(target, "PNG")
            outputs.append(str(target))
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdf_rasterise_unavailable", error=str(exc))
    return outputs


__all__ = [
    "PreprocessResult",
    "preprocess_for_ocr",
    "deskew_image",
    "denoise_image",
    "binarise_image",
    "pdf_to_images",
    "CV2_AVAILABLE",
]
