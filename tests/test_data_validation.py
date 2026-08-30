"""Test Clinical Knowledge Base Data Authenticity and Integrity Validator."""

import csv
import json
import tempfile
from pathlib import Path
import pytest

from backend.services.data_validator import (
    validate_all_data_files,
    validate_ayush_safety_file,
    validate_drug_interactions_file,
)


def test_drug_interactions_validation_insufficient_records():
    """Verify that a CSV with fewer rows than threshold is flagged as DEGRADED."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["drug_a", "drug_b", "severity", "description", "source"])
        writer.writerow(["aspirin", "warfarin", "Major", "Bleeding risk", "RxNav"])
        writer.writerow(["metformin", "contrast", "Major", "Lactic acidosis", "RxNav"])
        path = f.name

    try:
        # Require 10 records, but we only provided 2
        report = validate_drug_interactions_file(path, min_records=10)
        assert report["status"] == "DEGRADED"
        assert report["record_count"] == 2
        assert any("below the configured production threshold" in err for err in report["errors"])
    finally:
        Path(path).unlink(missing_ok=True)


def test_drug_interactions_validation_missing_columns():
    """Verify that a CSV missing required columns is rejected with DEGRADED status."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["drug_a", "wrong_col", "severity"])  # missing drug_b, description
        writer.writerow(["aspirin", "test", "Major"])
        path = f.name

    try:
        report = validate_drug_interactions_file(path, min_records=1)
        assert report["status"] == "DEGRADED"
        assert any("Missing required columns" in err for err in report["errors"])
    finally:
        Path(path).unlink(missing_ok=True)


def test_drug_interactions_validation_healthy():
    """Verify that a valid CSV exceeding threshold returns HEALTHY."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["drug_a", "drug_b", "severity", "description"])
        for i in range(5):
            writer.writerow([f"drugA_{i}", f"drugB_{i}", "Moderate", f"Interaction description {i}"])
        path = f.name

    try:
        report = validate_drug_interactions_file(path, min_records=3)
        assert report["status"] == "HEALTHY"
        assert report["record_count"] == 5
        assert len(report["errors"]) == 0
    finally:
        Path(path).unlink(missing_ok=True)


def test_ayush_safety_validation_insufficient_formulations():
    """Verify that JSON with fewer formulations than threshold is flagged DEGRADED."""
    data = {
        "pharmacopoeia": "API",
        "permissible_limits_ppm": {
            "lead_pb": {"limit_ppm": 10.0},
            "arsenic_as": {"limit_ppm": 3.0},
            "cadmium_cd": {"limit_ppm": 0.3},
            "mercury_hg": {"limit_ppm": 1.0},
        },
        "rasa_shastra_formulations": [
            {
                "name": "Formulation A",
                "herbo_mineral_elements": ["Parada"],
                "contraindications": ["Pregnancy"],
            }
        ],
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = f.name

    try:
        # Require 5 formulations, only 1 provided
        report = validate_ayush_safety_file(path, min_formulations=5)
        assert report["status"] == "DEGRADED"
        assert report["formulation_count"] == 1
        assert any("below the configured production threshold" in err for err in report["errors"])
    finally:
        Path(path).unlink(missing_ok=True)


def test_ayush_safety_validation_healthy():
    """Verify that valid JSON meeting thresholds returns HEALTHY."""
    data = {
        "pharmacopoeia": "API",
        "permissible_limits_ppm": {
            "lead_pb": {"limit_ppm": 10.0},
            "arsenic_as": {"limit_ppm": 3.0},
            "cadmium_cd": {"limit_ppm": 0.3},
            "mercury_hg": {"limit_ppm": 1.0},
        },
        "rasa_shastra_formulations": [
            {
                "name": f"Formulation_{i}",
                "herbo_mineral_elements": ["Bhasma"],
                "contraindications": ["Renal failure"],
            }
            for i in range(5)
        ],
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = f.name

    try:
        report = validate_ayush_safety_file(path, min_formulations=3)
        assert report["status"] == "HEALTHY"
        assert report["formulation_count"] == 5
        assert len(report["errors"]) == 0
    finally:
        Path(path).unlink(missing_ok=True)


def test_validate_all_data_files_orchestrator():
    """Test full orchestrator function with custom thresholds."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["drug_a", "drug_b", "severity", "description"])
        writer.writerow(["med1", "med2", "Major", "Severe risk"])
        csv_path = f_csv.name

    json_data = {
        "permissible_limits_ppm": {
            "lead_pb": {"limit_ppm": 10.0},
            "arsenic_as": {"limit_ppm": 3.0},
            "cadmium_cd": {"limit_ppm": 0.3},
            "mercury_hg": {"limit_ppm": 1.0},
        },
        "rasa_shastra_formulations": [
            {"name": "Form1", "elements": ["Parada"], "contraindications": ["None"]}
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_json:
        json.dump(json_data, f_json)
        json_path = f_json.name

    try:
        result = validate_all_data_files(
            csv_path=csv_path,
            json_path=json_path,
            min_drug_interactions=1,
            min_ayush_formulations=1,
        )
        assert result["overall_status"] == "HEALTHY"

        # Now test with impossible threshold -> must be DEGRADED
        result_degraded = validate_all_data_files(
            csv_path=csv_path,
            json_path=json_path,
            min_drug_interactions=9999,
            min_ayush_formulations=9999,
        )
        assert result_degraded["overall_status"] == "DEGRADED"
    finally:
        Path(csv_path).unlink(missing_ok=True)
        Path(json_path).unlink(missing_ok=True)
