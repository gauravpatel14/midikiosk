#!/usr/bin/env python3
"""MediKiosk Management Script: Validate Clinical Knowledge Base Data Files.

Usage:
    python scripts/validate_data_files.py
"""

import os
import sys
from pathlib import Path

# Add project root and backend to python path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.services.data_validator import validate_all_data_files


def main():
    print("=" * 70)
    print("MEDIKIOSK CLINICAL KNOWLEDGE BASE DATA AUTHENTICITY VALIDATION")
    print("=" * 70)

    report = validate_all_data_files()

    print(f"\n[OVERALL SYSTEM STATUS] : {report['overall_status']}")
    print("-" * 70)

    # 1. Drug Interactions
    di = report["drug_interactions"]
    print(f"\n1. DRUG INTERACTIONS DATABASE ({di['file']})")
    print(f"   Status        : {di['status']}")
    print(f"   Record Count  : {di.get('record_count', 0)}")
    print(f"   Unique Pairs  : {di.get('unique_pairs', 0)}")
    print(f"   Threshold     : {di.get('threshold', 0)}")
    if di.get("errors"):
        print("   Notices/Warnings:")
        for err in di["errors"]:
            print(f"     - {err}")

    # 2. AYUSH Safety
    ay = report["ayush_safety"]
    print(f"\n2. AYUSH FORMULATION & HEAVY METALS ({ay['file']})")
    print(f"   Status        : {ay['status']}")
    print(f"   Formulations  : {ay.get('formulation_count', 0)}")
    print(f"   Threshold     : {ay.get('threshold', 0)}")
    if ay.get("errors"):
        print("   Notices/Warnings:")
        for err in ay["errors"]:
            print(f"     - {err}")

    print("\n" + "=" * 70)
    if report["overall_status"] == "HEALTHY":
        print("All clinical knowledge base data files verified AUTHENTIC and HEALTHY.")
        sys.exit(0)
    else:
        print("WARNING: Clinical data integrity status is DEGRADED. Review details above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
