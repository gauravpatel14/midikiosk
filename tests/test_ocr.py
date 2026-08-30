"""Automated test suite verifying MediKiosk DocumentOCR service."""

import os
import sys
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from PIL import Image, ImageDraw
import pypdf

from backend.services.ocr.document_ocr import DocumentOCR
from backend.services.ocr.handwriting_stub import handwriting_model


def create_test_assets() -> tuple[str, str, str, str]:
    """Generate real test image and PDF files in /tmp."""
    test_dir = "/tmp/medikiosk_ocr_tests"
    os.makedirs(test_dir, exist_ok=True)

    # 1. Test Prescription Image (PNG)
    img_path = os.path.join(test_dir, "test_rx_image.png")
    img = Image.new("RGB", (400, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "Rx: MediKiosk Hospital OPD", fill=(0, 0, 0))
    draw.text((20, 70), "Tab. Pantop 40mg OD", fill=(0, 0, 0))
    img.save(img_path)

    # 2. Test Lab Report PDF
    pdf_path = os.path.join(test_dir, "test_lab_report.pdf")
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    # Write sample pdf using pypdf annotation or simple page
    with open(pdf_path, "wb") as f:
        writer.write(f)

    # 3. Empty File
    empty_path = os.path.join(test_dir, "empty_file.pdf")
    with open(empty_path, "wb") as f:
        pass

    # 4. Corrupted / Unsupported file
    bad_path = os.path.join(test_dir, "unsupported.xyz")
    with open(bad_path, "w") as f:
        f.write("corrupt header data")

    return img_path, pdf_path, empty_path, bad_path


def test_document_ocr_suite():
    print("\n--- Running MediKiosk DocumentOCR Test Suite ---")
    img_path, pdf_path, empty_path, bad_path = create_test_assets()
    ocr = DocumentOCR()

    # 1. Process Scanned Prescription Image
    res_img = ocr.process(img_path)
    assert res_img["status"] == "success"
    assert res_img["page_count"] == 1
    assert "image_dimensions" in res_img["metadata"]
    assert res_img["document_type_hint"] in ("PRESCRIPTION", "UNKNOWN_CLINICAL_DOCUMENT")
    print(f"✔ 1. Process Image: OK (Type: {res_img['document_type_hint']}, Format: {res_img['metadata'].get('image_format')})")

    # 2. Process PDF Document
    res_pdf = ocr.process(pdf_path)
    assert res_pdf["status"] == "success"
    assert res_pdf["page_count"] == 1
    print(f"✔ 2. Process PDF: OK (Pages: {res_pdf['page_count']}, Engine: {res_pdf['metadata'].get('ocr_engine')})")

    # 3. Test Language Detection Logic
    langs_en, p_en = ocr.detect_languages("Blood Glucose Fasting 95 mg/dL")
    assert "eng" in langs_en and p_en == "eng"
    print(f"✔ 3a. Language Detection (English): {langs_en} (Primary: {p_en})")

    langs_hi, p_hi = ocr.detect_languages("दवा: अश्वगंधा चूर्ण 3 ग्राम सुबह शाम")
    assert "hin" in langs_hi and p_hi == "hin"
    print(f"✔ 3b. Language Detection (Hindi): {langs_hi} (Primary: {p_hi})")

    langs_mix, _ = ocr.detect_languages("Tab. Pantop 40mg OD. अश्वगंधा चूर्ण")
    assert "eng" in langs_mix and "hin" in langs_mix
    print(f"✔ 3c. Language Detection (Mixed eng+hin): {langs_mix}")

    # 4. Test Document Type Classification
    assert ocr.classify_document_type("Rx: Tab. Amoxicillin 500mg TDS x 5 days") == "PRESCRIPTION"
    assert ocr.classify_document_type("Pathology Report: Hemoglobin 12.5 g/dL, Platelets 2.5 Lakh") == "LAB_REPORT"
    assert ocr.classify_document_type("Hospital Discharge Summary: Admission Date 10/08/2026") == "DISCHARGE_SUMMARY"
    print("✔ 4. Document Type Classification: Verified Prescription, Lab Report, Discharge Summary")

    # 5. Test Error Handling
    # 5a. Non-existent file
    res_none = ocr.process("/tmp/non_existent_doc_12345.pdf")
    assert res_none["status"] == "error"
    assert res_none["error"] == "FILE_NOT_FOUND"
    print(f"✔ 5a. Error Handling (Non-existent): Caught {res_none['error']}")

    # 5b. Empty file
    res_empty = ocr.process(empty_path)
    assert res_empty["status"] == "error"
    assert res_empty["error"] == "EMPTY_FILE"
    print(f"✔ 5b. Error Handling (Empty file): Caught {res_empty['error']}")

    # 5c. Unsupported format
    res_bad = ocr.process(bad_path)
    assert res_bad["status"] == "error"
    assert res_bad["error"] == "UNSUPPORTED_FORMAT"
    print(f"✔ 5c. Error Handling (Unsupported format): Caught {res_bad['error']}")

    # 6. Test Handwritten Prescription Model Stub
    hw_res = handwriting_model.recognize_handwriting(img_path)
    assert "engine" in hw_res
    assert len(hw_res["medications_detected"]) > 0
    print(f"✔ 6. Handwriting Model Stub: Detected medications {hw_res['medications_detected']}")

    print("\n--- ALL DOCUMENT OCR TESTS PASSED 100% ---")


if __name__ == "__main__":
    test_document_ocr_suite()
