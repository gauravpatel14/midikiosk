"""Clinical terminology service: ICD-10, SNOMED CT, LOINC, RxNorm and AYUSH.

MediKiosk must emit coded data (PRD §6.3.3) so summaries are machine-readable in
the HIS and FHIR-valid for ABDM. Full terminology distributions are licensed and
enormous, so this service uses a two-tier design:

1. **Bundled curated subsets** (``backend/data/*.json``) covering the conditions,
   drugs and lab tests that actually occur in Indian OPD practice. These ship
   with the code, work offline, and are the authoritative fast path.
2. **Optional local terminology server** (``TERMINOLOGY_DIR`` overrides, or a
   FHIR ``$lookup`` endpoint) for facilities that license the full releases.

Matching is normalisation + alias + fuzzy (difflib) so "T2DM", "type-2 diabetes"
and "diabetes mellitus type 2" all resolve to E11.9. AYUSH terms are mapped to
the Ministry of Ayush NAMASTE codes where a mapping exists.
"""

from __future__ import annotations

import difflib
import functools
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(settings.TERMINOLOGY_DIR)

FUZZY_CUTOFF = 0.86


@dataclass(slots=True)
class CodedConcept:
    """A resolved terminology concept."""

    code: str
    display: str
    system: str
    system_uri: str
    match_type: str = "exact"
    score: float = 1.0
    extra: Dict[str, Any] = None  # type: ignore[assignment]

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "code": self.code,
            "display": self.display,
            "system": self.system,
            "system_uri": self.system_uri,
            "match_type": self.match_type,
            "score": round(self.score, 3),
        }
        if self.extra:
            payload.update(self.extra)
        return payload

    # Backwards-compatible mapping access (old code used ``["code"]``/``["title"]``).
    def __getitem__(self, key: str) -> Any:
        if key == "title":
            return self.display
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


SYSTEM_URIS = {
    "ICD10": "http://hl7.org/fhir/sid/icd-10",
    "SNOMED_CT": "http://snomed.info/sct",
    "LOINC": "http://loinc.org",
    "RXNORM": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "NAMASTE_AYUSH": "https://namaste.ayush.gov.in/CodeSystem/namaste",
}


def normalise_term(term: str) -> str:
    """Case/diacritic/punctuation-insensitive key for matching."""
    if not term:
        return ""
    text = unicodedata.normalize("NFKD", str(term))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^\w\s+/-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class TerminologyService:
    """Loads and queries the bundled terminology subsets."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir or DATA_DIR)
        self._tables: Dict[str, Dict[str, Any]] = {}
        self._index: Dict[str, Dict[str, str]] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load(self, force: bool = False) -> None:
        if self._loaded and not force:
            return
        for name in ("icd10", "snomed", "loinc", "rxnorm", "ayush"):
            self._tables[name] = self._load_table(name)
            self._index[name] = self._build_index(self._tables[name])
        self._loaded = True
        logger.info(
            "terminology_loaded",
            counts={k: len(v) for k, v in self._tables.items()},
            data_dir=str(self.data_dir),
        )

    def _load_table(self, name: str) -> Dict[str, Any]:
        path = self.data_dir / f"{name}.json"
        if not path.exists():
            logger.warning("terminology_file_missing", file=str(path))
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("terminology_file_unreadable", file=str(path), error=str(exc))
            return {}
        concepts = payload.get("concepts", payload)
        return concepts if isinstance(concepts, dict) else {}

    @staticmethod
    def _build_index(table: Dict[str, Any]) -> Dict[str, str]:
        """Map normalised term/alias -> concept key."""
        index: Dict[str, str] = {}
        for key, entry in table.items():
            index.setdefault(normalise_term(key), key)
            display = entry.get("display") if isinstance(entry, dict) else None
            if display:
                index.setdefault(normalise_term(display), key)
            for alias in (entry.get("aliases") or []) if isinstance(entry, dict) else []:
                index.setdefault(normalise_term(alias), key)
        return index

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def lookup(
        self, system: str, term: str, *, fuzzy: bool = True
    ) -> Optional[CodedConcept]:
        """Resolve ``term`` in ``system`` (icd10/snomed/loinc/rxnorm/ayush)."""
        self.load()
        system = system.lower()
        table = self._tables.get(system) or {}
        index = self._index.get(system) or {}
        if not table or not term:
            return None

        needle = normalise_term(term)
        if not needle:
            return None

        # 1. exact / alias
        key = index.get(needle)
        match_type, score = "exact", 1.0

        # 2. containment (handles "type 2 diabetes mellitus without complication")
        if key is None:
            for candidate_norm, candidate_key in index.items():
                if len(candidate_norm) < 4:
                    continue
                if candidate_norm in needle or needle in candidate_norm:
                    key = candidate_key
                    match_type, score = "partial", 0.9
                    break

        # 3. fuzzy (handles OCR noise: "hypertenson")
        if key is None and fuzzy:
            close = difflib.get_close_matches(needle, list(index.keys()), n=1, cutoff=FUZZY_CUTOFF)
            if close:
                key = index[close[0]]
                match_type = "fuzzy"
                score = difflib.SequenceMatcher(None, needle, close[0]).ratio()

        if key is None:
            return None

        entry = table[key]
        canonical_system = entry.get("system", system.upper())
        extra = {
            k: v
            for k, v in entry.items()
            if k not in {"code", "display", "aliases", "system"}
        }
        return CodedConcept(
            code=str(entry.get("code", "")),
            display=str(entry.get("display", key.title())),
            system=canonical_system,
            system_uri=SYSTEM_URIS.get(canonical_system, ""),
            match_type=match_type,
            score=score,
            extra=extra or None,
        )

    def all_terms(self, system: str) -> List[str]:
        self.load()
        return sorted((self._tables.get(system.lower()) or {}).keys())

    def concepts(self, system: str) -> Dict[str, Any]:
        self.load()
        return self._tables.get(system.lower()) or {}

    def reference_range(self, test_name: str) -> Optional[Dict[str, Any]]:
        """Return the bundled reference interval for a lab test, if known."""
        concept = self.lookup("loinc", test_name)
        if concept and concept.extra:
            low = concept.extra.get("ref_low")
            high = concept.extra.get("ref_high")
            if low is not None or high is not None:
                return {
                    "low": low,
                    "high": high,
                    "unit": concept.extra.get("unit"),
                    "critical_low": concept.extra.get("critical_low"),
                    "critical_high": concept.extra.get("critical_high"),
                    "loinc": concept.code,
                    "display": concept.display,
                }
        return None

    def interpret_value(
        self, test_name: str, value: float, unit: Optional[str] = None
    ) -> Dict[str, Any]:
        """Classify a numeric lab value against the bundled reference range."""
        ref = self.reference_range(test_name)
        if not ref:
            return {"interpretation": "Unknown", "is_abnormal": False, "reference": None}

        low, high = ref.get("low"), ref.get("high")
        crit_low, crit_high = ref.get("critical_low"), ref.get("critical_high")

        interpretation = "Normal"
        if crit_low is not None and value < float(crit_low):
            interpretation = "Critical Low"
        elif crit_high is not None and value > float(crit_high):
            interpretation = "Critical High"
        elif low is not None and value < float(low):
            interpretation = "Low"
        elif high is not None and value > float(high):
            interpretation = "High"

        return {
            "interpretation": interpretation,
            "is_abnormal": interpretation != "Normal",
            "is_critical": interpretation.startswith("Critical"),
            "reference": ref,
            "reference_text": self.format_range(ref),
        }

    @staticmethod
    def format_range(ref: Dict[str, Any]) -> str:
        low, high, unit = ref.get("low"), ref.get("high"), ref.get("unit") or ""
        if low is not None and high is not None:
            return f"{low} - {high} {unit}".strip()
        if high is not None:
            return f"< {high} {unit}".strip()
        if low is not None:
            return f"> {low} {unit}".strip()
        return ""

    def health(self) -> Dict[str, Any]:
        self.load()
        return {
            "data_dir": str(self.data_dir),
            "concept_counts": {k: len(v) for k, v in self._tables.items()},
        }


terminology = TerminologyService()


# ---------------------------------------------------------------------------
# Convenience wrappers (keep the historical ``lookup_icd10`` signature)
# ---------------------------------------------------------------------------
def lookup_icd10(diagnosis_name: str) -> Optional[CodedConcept]:
    return terminology.lookup("icd10", diagnosis_name)


def lookup_snomed(term: str) -> Optional[CodedConcept]:
    return terminology.lookup("snomed", term)


def lookup_loinc(test_name: str) -> Optional[CodedConcept]:
    return terminology.lookup("loinc", test_name)


def lookup_rxnorm(drug_name: str) -> Optional[CodedConcept]:
    return terminology.lookup("rxnorm", drug_name)


def lookup_ayush(term: str) -> Optional[CodedConcept]:
    return terminology.lookup("ayush", term)


@functools.lru_cache(maxsize=1)
def icd10_terms() -> Tuple[str, ...]:
    return tuple(terminology.all_terms("icd10"))


__all__ = [
    "TerminologyService",
    "terminology",
    "CodedConcept",
    "normalise_term",
    "lookup_icd10",
    "lookup_snomed",
    "lookup_loinc",
    "lookup_rxnorm",
    "lookup_ayush",
    "icd10_terms",
    "SYSTEM_URIS",
]
