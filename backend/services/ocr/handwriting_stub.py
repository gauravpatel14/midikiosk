"""Deprecated shim — see :mod:`backend.services.ocr.handwriting`.

The previous implementation returned hardcoded fake prescription text, which is
unsafe in a clinical system. It has been replaced by a real TrOCR / Document AI
pipeline with an explicit human-review fallback.
"""

from backend.services.ocr.handwriting import (
    HandwritingRecogniser,
    HandwritingResult,
    handwriting_model,
)

HandwrittenPrescriptionModelStub = HandwritingRecogniser

__all__ = [
    "HandwritingRecogniser",
    "HandwrittenPrescriptionModelStub",
    "HandwritingResult",
    "handwriting_model",
]
