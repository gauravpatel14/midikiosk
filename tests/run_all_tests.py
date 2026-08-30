"""Unified test runner executing all MediKiosk test suites."""

import sys
from pathlib import Path

# Add root and backend to path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from tests.test_auth import test_auth_and_consent_suite
from tests.test_speech import test_speech_suite
from tests.test_dialogue import test_dialogue_manager_suite
from tests.test_ocr import test_document_ocr_suite
from tests.test_extraction import test_clinical_entity_extraction_suite
from tests.test_summary import test_summary_generator_suite
from tests.test_fhir import test_fhir_suite
from tests.test_red_flags import test_red_flag_suite
from tests.test_his import test_his_adapter_suite


def run_everything():
    print("==========================================================")
    print("      MEDIKIOSK ENTERPRISE SYSTEM TEST SUITE RUNNER       ")
    print("==========================================================")

    # 1. Auth & DPDP Consent Tests
    test_auth_and_consent_suite()

    # 2. Multimodal Speech (ASR/TTS) Tests
    test_speech_suite()

    # 3. Clinical Dialogue State Machine Tests
    test_dialogue_manager_suite()

    # 4. Document Processing & OCR Tests
    test_document_ocr_suite()

    # 5. Clinical Entity Extraction (ICD-10, Meds, Labs, Surgeries)
    test_clinical_entity_extraction_suite()

    # 6. Clinical Summary Generation (HTML & Plain Text)
    test_summary_generator_suite()

    # 7. ABDM FHIR R4 Health Information Exchange (HIE)
    test_fhir_suite()

    # 8. Emergency Red Flag Triage & Physiological Vitals
    test_red_flag_suite()

    # 9. Hospital Information System (HIS) Integration Adapters
    test_his_adapter_suite()

    print("\n==========================================================")
    print("  ALL 9 MEDIKIOSK TEST SUITES EXECUTED AND PASSED 100%!   ")
    print("==========================================================")


if __name__ == "__main__":
    run_everything()
