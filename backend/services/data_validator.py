"""Clinical Knowledge Base Integrity & Authenticity Validator."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Global System Data Integrity Status Flag: "HEALTHY" | "DEGRADED"
DATA_INTEGRITY_STATUS = "HEALTHY"
LAST_VALIDATION_REPORT: Dict[str, Any] = {}

REQUIRED_CSV_COLUMNS = ["drug_a", "drug_b", "severity", "description"]
REQUIRED_HEAVY_METALS = ["lead_pb", "arsenic_as", "cadmium_cd", "mercury_hg"]


def get_data_integrity_status() -> str:
    """Return the current system health data integrity flag."""
    return DATA_INTEGRITY_STATUS


def validate_drug_interactions_file(
    path: str, min_records: Optional[int] = None
) -> Dict[str, Any]:
    """Validate drug interactions CSV file for required columns, non-null values, and record thresholds."""
    min_count = min_records if min_records is not None else settings.MIN_DRUG_INTERACTIONS
    file_path = Path(path)

    if not file_path.exists():
        msg = f"Drug interactions data file not found: {path}"
        logger.critical("data_validation_file_missing", file=path)
        return {
            "status": "DEGRADED",
            "file": str(path),
            "errors": [msg],
            "record_count": 0,
            "threshold": min_count,
        }

    errors: List[str] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    row_count = 0

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return {
                "status": "DEGRADED",
                "file": str(path),
                "errors": ["Empty or invalid CSV file"],
                "record_count": 0,
                "threshold": min_count,
            }

        missing_cols = [c for c in REQUIRED_CSV_COLUMNS if c not in reader.fieldnames]
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")

        for idx, row in enumerate(reader, start=1):
            row_count += 1
            # Check non-null values
            for col in REQUIRED_CSV_COLUMNS:
                val = (row.get(col) or "").strip()
                if not val:
                    errors.append(f"Row {idx}: missing required value for column '{col}'")

            drug_a = (row.get("drug_a") or "").strip().lower()
            drug_b = (row.get("drug_b") or "").strip().lower()

            if drug_a and drug_b:
                pair: Tuple[str, str] = (drug_a, drug_b) if drug_a <= drug_b else (drug_b, drug_a)
                if pair in seen_pairs:
                    errors.append(f"Row {idx}: duplicate interaction pair '{drug_a}' + '{drug_b}'")
                seen_pairs.add(pair)

    is_below_threshold = row_count < min_count
    status = "DEGRADED" if errors or is_below_threshold else "HEALTHY"

    if is_below_threshold:
        warning_msg = (
            f"Drug interaction database has {row_count} records, which is below the configured "
            f"production threshold of {min_count}. Clinical coverage may be limited."
        )
        logger.critical("drug_interactions_below_threshold", record_count=row_count, threshold=min_count)
        errors.append(warning_msg)

    return {
        "status": status,
        "file": str(path),
        "record_count": row_count,
        "unique_pairs": len(seen_pairs),
        "threshold": min_count,
        "errors": errors,
    }


def validate_ayush_safety_file(
    path: str, min_formulations: Optional[int] = None
) -> Dict[str, Any]:
    """Validate AYUSH safety JSON file for heavy metal limits, Rasa Shastra contraindications, and threshold."""
    min_count = min_formulations if min_formulations is not None else settings.MIN_AYUSH_FORMULATIONS
    file_path = Path(path)

    if not file_path.exists():
        msg = f"AYUSH safety data file not found: {path}"
        logger.critical("data_validation_file_missing", file=path)
        return {
            "status": "DEGRADED",
            "file": str(path),
            "errors": [msg],
            "formulation_count": 0,
            "threshold": min_count,
        }

    errors: List[str] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        return {
            "status": "DEGRADED",
            "file": str(path),
            "errors": [f"Malformed JSON: {exc}"],
            "formulation_count": 0,
            "threshold": min_count,
        }

    # Check heavy metal standards
    limits = data.get("permissible_limits_ppm")
    if not isinstance(limits, dict):
        errors.append("Missing or invalid 'permissible_limits_ppm' object")
    else:
        for metal in REQUIRED_HEAVY_METALS:
            m_data = limits.get(metal)
            if not isinstance(m_data, dict) or "limit_ppm" not in m_data:
                errors.append(f"Missing permissible limit specification for heavy metal '{metal}'")

    # Check formulations
    formulations = data.get("rasa_shastra_formulations")
    formulation_count = 0
    seen_names: Set[str] = set()

    if not isinstance(formulations, list):
        errors.append("Missing or invalid 'rasa_shastra_formulations' array")
    else:
        formulation_count = len(formulations)
        for idx, item in enumerate(formulations, start=1):
            if not isinstance(item, dict):
                errors.append(f"Formulation at index {idx} is not an object")
                continue
            name = (item.get("name") or "").strip()
            if not name:
                errors.append(f"Formulation at index {idx} missing non-empty 'name'")
            elif name.lower() in seen_names:
                errors.append(f"Duplicate formulation name: '{name}'")
            seen_names.add(name.lower())

            contra = item.get("contraindications") or item.get("contraindicated_conditions")
            if not isinstance(contra, list) or len(contra) == 0:
                errors.append(f"Formulation '{name}' missing 'contraindications' list")

            elements = item.get("herbo_mineral_elements") or item.get("elements")
            if not isinstance(elements, list) or len(elements) == 0:
                errors.append(f"Formulation '{name}' missing 'herbo_mineral_elements' list")

    is_below_threshold = formulation_count < min_count
    status = "DEGRADED" if errors or is_below_threshold else "HEALTHY"

    if is_below_threshold:
        warning_msg = (
            f"AYUSH safety database contains {formulation_count} formulations, below the configured "
            f"production threshold of {min_count}."
        )
        logger.critical("ayush_formulations_below_threshold", count=formulation_count, threshold=min_count)
        errors.append(warning_msg)

    return {
        "status": status,
        "file": str(path),
        "formulation_count": formulation_count,
        "threshold": min_count,
        "errors": errors,
    }


def validate_all_data_files(
    csv_path: Optional[str] = None,
    json_path: Optional[str] = None,
    min_drug_interactions: Optional[int] = None,
    min_ayush_formulations: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute complete validation across all clinical knowledge base files and set system status."""
    global DATA_INTEGRITY_STATUS, LAST_VALIDATION_REPORT

    drug_path = csv_path or settings.DRUG_INTERACTION_DATA_PATH
    ayush_path = json_path or settings.AYUSH_SAFETY_DATA_PATH

    drug_report = validate_drug_interactions_file(drug_path, min_records=min_drug_interactions)
    ayush_report = validate_ayush_safety_file(ayush_path, min_formulations=min_ayush_formulations)

    is_healthy = drug_report["status"] == "HEALTHY" and ayush_report["status"] == "HEALTHY"
    DATA_INTEGRITY_STATUS = "HEALTHY" if is_healthy else "DEGRADED"

    report = {
        "overall_status": DATA_INTEGRITY_STATUS,
        "drug_interactions": drug_report,
        "ayush_safety": ayush_report,
    }
    LAST_VALIDATION_REPORT = report

    if not is_healthy:
        logger.warning("clinical_data_integrity_degraded", report=report)
    else:
        logger.info("clinical_data_integrity_verified", drug_records=drug_report["record_count"], ayush_formulations=ayush_report["formulation_count"])

    return report
