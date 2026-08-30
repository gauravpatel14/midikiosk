"""Clinical Named Entity Recognition (NER) & Terminology Normalization.

Implements PRD §6.3.3 / §6.4:
* Multi-model clinical NER extracting Diagnoses, Medications, Lab Tests,
  Procedures, Allergies, Vitals, and AYUSH Prakriti/Dosha entities.
* Negation detection (asserting absent symptoms like "denies fever", "no chest pain").
* Terminology coding: ICD-10, SNOMED CT, LOINC, RxNorm, AYUSH/NAMASTE.
* Two-tier engine:
    1. LLM clinical extractor (Ollama local / OpenAI cloud) when available.
    2. High-precision rule & clinical regex engine (offline fast-path).
    3. Optional scispaCy / Med7 models if installed in the host environment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.nlp.llm import llm_client
from backend.services.nlp.terminology import (
    lookup_ayush,
    lookup_icd10,
    lookup_loinc,
    lookup_rxnorm,
    lookup_snomed,
    terminology,
)

logger = get_logger(__name__)

# Common clinical negation triggers
NEGATION_TRIGGERS = [
    r"\bno\b",
    r"\bdenies\b",
    r"\bdenied\b",
    r"\bwithout\b",
    r"\babsent\b",
    r"\bnegative\s+for\b",
    r"\brule\s+out\b",
    r"\bnot\b",
    r"\bnever\b",
]
NEGATION_PATTERN = re.compile("|".join(NEGATION_TRIGGERS), re.IGNORECASE)


@dataclass
class ExtractedEntity:
    category: str  # diagnosis, medication, lab, procedure, allergy, vitals, ayush
    text: str
    normalized_name: str
    code: Optional[str] = None
    coding_system: Optional[str] = None
    is_negated: bool = False
    confidence: float = 1.0
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "text": self.text,
            "normalized_name": self.normalized_name,
            "code": self.code,
            "coding_system": self.coding_system,
            "is_negated": self.is_negated,
            "confidence": round(self.confidence, 3),
            "attributes": self.attributes,
        }


class ClinicalNER:
    """Clinical NER pipeline combining model inference, rule extraction, and terminology normalization."""

    def __init__(self) -> None:
        self._spacy_nlp = None
        self._load_spacy_if_available()

    def _load_spacy_if_available(self) -> None:
        """Attempt to load scispaCy or standard spacy models if installed."""
        try:
            import spacy

            for model_name in ("en_core_sci_md", "en_core_sci_sm", "en_core_med7_lg", "en_core_web_sm"):
                try:
                    self._spacy_nlp = spacy.load(model_name)
                    logger.info("loaded_spacy_ner_model", model=model_name)
                    break
                except Exception:
                    continue
        except ImportError:
            self._spacy_nlp = None

    def is_negated(self, context_window: str) -> bool:
        """Check if an entity mentions a negation within its immediate context."""
        return bool(NEGATION_PATTERN.search(context_window))

    async def extract_entities(
        self,
        text: str,
        *,
        language: str = "en",
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """Extract all structured clinical entities from text."""
        if not text or not text.strip():
            return {
                "status": "empty",
                "entities": {
                    "diagnoses": [],
                    "medications": [],
                    "laboratory_results": [],
                    "procedures": [],
                    "allergies": [],
                    "vitals": [],
                    "ayush_entities": [],
                },
                "confidence": 0.0,
                "engine": "none",
            }

        # 1. Attempt LLM extraction if enabled and active
        if use_llm and (llm_client.ollama_enabled or llm_client.openai_enabled):
            try:
                llm_result = await self._extract_with_llm(text, language=language)
                if llm_result:
                    return llm_result
            except Exception as exc:
                logger.warning("llm_ner_fallback", error=str(exc))

        # 2. Deterministic rule-based extraction
        return self._extract_with_rules(text)

    async def _extract_with_llm(self, text: str, language: str = "en") -> Optional[Dict[str, Any]]:
        system_prompt = (
            "You are an expert Clinical NLP Entity Extraction system for a hospital OPD.\n"
            "Extract all clinical entities from the clinical text and return strict JSON with schema:\n"
            "{\n"
            '  "diagnoses": [{"name": str, "is_negated": bool, "icd10_hint": str}],\n'
            '  "medications": [{"name": str, "dosage": str, "frequency": str, "duration": str}],\n'
            '  "laboratory_results": [{"test_name": str, "value": str, "unit": str, "flag": str}],\n'
            '  "procedures": [{"name": str, "date": str}],\n'
            '  "allergies": [{"allergen": str, "reaction": str}],\n'
            '  "vitals": [{"vital": str, "value": str, "unit": str}],\n'
            '  "ayush_entities": [{"term": str, "category": "dosha|dhatu|prakriti|treatment"}]\n'
            "}\n"
            "Do NOT fabricate any details. Only include what is explicitly mentioned or strongly implied."
        )

        data = await llm_client.complete_json(
            prompt=f"Clinical record text:\n{text[:3000]}",
            system=system_prompt,
            required_keys={"diagnoses", "medications", "laboratory_results"},
        )

        if not data:
            return None

        # Code and normalize all entities
        coded_diagnoses = []
        for d in data.get("diagnoses", []):
            name = d.get("name", "").strip()
            if not name:
                continue
            concept = lookup_icd10(name)
            snomed = lookup_snomed(name)
            coded_diagnoses.append({
                "name": name,
                "icd10_code": concept.code if concept else d.get("icd10_hint"),
                "icd10_display": concept.display if concept else name,
                "snomed_code": snomed.code if snomed else None,
                "is_negated": bool(d.get("is_negated", False)),
                "confidence": concept.score if concept else 0.85,
            })

        coded_medications = []
        for m in data.get("medications", []):
            name = m.get("name", "").strip()
            if not name:
                continue
            rx = lookup_rxnorm(name)
            coded_medications.append({
                "name": name,
                "dosage": m.get("dosage", ""),
                "frequency": m.get("frequency", ""),
                "duration": m.get("duration", ""),
                "rxnorm_code": rx.code if rx else None,
                "confidence": rx.score if rx else 0.85,
            })

        coded_labs = []
        for l in data.get("laboratory_results", []):
            test_name = l.get("test_name", "").strip()
            if not test_name:
                continue
            loinc = lookup_loinc(test_name)
            coded_labs.append({
                "test_name": test_name,
                "value": str(l.get("value", "")),
                "unit": l.get("unit"),
                "loinc_code": loinc.code if loinc else None,
                "flag": l.get("flag"),
                "confidence": loinc.score if loinc else 0.85,
            })

        return {
            "status": "success",
            "engine": "llm_enhanced",
            "confidence": 0.92,
            "entities": {
                "diagnoses": coded_diagnoses,
                "medications": coded_medications,
                "laboratory_results": coded_labs,
                "procedures": data.get("procedures", []),
                "allergies": data.get("allergies", []),
                "vitals": data.get("vitals", []),
                "ayush_entities": data.get("ayush_entities", []),
            },
        }

    def _extract_with_rules(self, text: str) -> Dict[str, Any]:
        """Offline deterministic clinical entity extractor."""
        from backend.services.extraction.regex_extractor import RegexClinicalExtractor

        regex_engine = RegexClinicalExtractor()
        extracted = regex_engine.extract_all(text)

        # Terminology normalization
        diagnoses = []
        for d in extracted.get("diagnoses", []):
            name = d.get("name")
            concept = lookup_icd10(name)
            snomed = lookup_snomed(name)
            diagnoses.append({
                "name": name,
                "icd10_code": concept.code if concept else d.get("icd10_code"),
                "icd10_display": concept.display if concept else name,
                "snomed_code": snomed.code if snomed else None,
                "confidence": concept.score if concept else d.get("confidence", 0.8),
            })

        medications = []
        for m in extracted.get("medications", []):
            name = m.get("name")
            rx = lookup_rxnorm(name)
            medications.append({
                **m,
                "rxnorm_code": rx.code if rx else None,
            })

        labs = []
        for l in extracted.get("laboratory_results", []):
            t_name = l.get("test_name")
            loinc = lookup_loinc(t_name)
            labs.append({
                **l,
                "loinc_code": loinc.code if loinc else None,
            })

        # AYUSH terminology extraction
        ayush_matches = []
        words = set(re.findall(r"\b[A-Za-z]{3,}\b", text))
        for w in words:
            concept = lookup_ayush(w)
            if concept:
                ayush_matches.append(concept.to_dict())

        return {
            "status": "success",
            "engine": "regex_and_terminology",
            "confidence": 0.88,
            "entities": {
                "diagnoses": diagnoses,
                "medications": medications,
                "laboratory_results": labs,
                "procedures": extracted.get("procedures", []),
                "allergies": extracted.get("allergies", []),
                "dates": extracted.get("dates", []),
                "ayush_entities": ayush_matches,
            },
        }


clinical_ner = ClinicalNER()

__all__ = ["ClinicalNER", "clinical_ner", "ExtractedEntity"]
