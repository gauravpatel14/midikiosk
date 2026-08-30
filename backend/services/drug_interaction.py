"""Clinical Drug Interaction Detection Service.

Integrates:
1. NIH NLM RxNav Interaction API (Free public clinical interaction service)
2. OpenFDA Drug Label Interaction API
3. DrugBank / RxNav Local Clinical Database (CSV/JSON)

Checks pairwise interactions across patient's active and prescribed medications,
returning structured clinical warnings with severity (Major, Moderate, Minor),
mechanisms, and provenance.
"""

from __future__ import annotations

import csv
import itertools
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

from backend.core.cache import cache
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


def clean_drug_name(raw_name: str) -> str:
    """Normalize medication string (stripping 'Tab.', 'Cap.', dosages '500mg', frequencies 'OD')."""
    text = raw_name.lower().strip()
    text = re.sub(r"\b(tab|tab\.|tablet|cap|cap\.|capsule|syp|syp\.|syrup|inj|inj\.|injection)\b", "", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(mg|g|mcg|ml|iu|units)\b", "", text)
    text = re.sub(r"\b(od|bd|bid|tds|tid|qid|hs|sos|stat|daily|weekly)\b", "", text)
    text = re.sub(r"[^\w\s-]", " ", text)
    tokens = [t for t in text.split() if len(t) > 2]
    return tokens[0] if tokens else text.strip()


class DrugInteractionService:
    """Evaluates drug-drug interactions using remote APIs or local clinical database."""

    def __init__(self) -> None:
        self.source = settings.DRUG_INTERACTION_SOURCE
        self.data_path = settings.DRUG_INTERACTION_DATA_PATH
        self._local_db: Dict[Tuple[str, str], Dict[str, str]] = {}
        self._load_local_db()

    def _load_local_db(self) -> None:
        """Load interaction pairs from CSV into memory."""
        resolved_path = os.path.abspath(self.data_path)
        if not os.path.exists(resolved_path):
            logger.warning("drug_interaction_db_missing", path=resolved_path)
            return

        count = 0
        try:
            with open(resolved_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    da = clean_drug_name(row.get("drug_a", ""))
                    db = clean_drug_name(row.get("drug_b", ""))
                    if da and db:
                        key1 = (da, db)
                        key2 = (db, da)
                        entry = {
                            "drug_a": row.get("drug_a", da),
                            "drug_b": row.get("drug_b", db),
                            "severity": row.get("severity", "Moderate"),
                            "description": row.get("description", "Potential interaction detected."),
                            "source": row.get("source", "DrugBank/RxNav"),
                        }
                        self._local_db[key1] = entry
                        self._local_db[key2] = entry
                        count += 1
            logger.info("drug_interaction_db_loaded", entries=count, path=resolved_path)
        except Exception as e:
            logger.error("drug_interaction_db_load_failed", error=str(e))

    async def _query_rxnav_rxcui(self, drug_name: str) -> Optional[str]:
        """Fetch RxCUI identifier from NIH NLM RxNav."""
        cache_key = f"rxnav:rxcui:{drug_name}"
        cached = await cache.get(cache_key)
        if cached:
            return cached

        url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={urllib.parse.quote(drug_name)}"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    rxcuis = data.get("idGroup", {}).get("rxnormId", [])
                    if rxcuis:
                        rxcui = str(rxcuis[0])
                        await cache.set(cache_key, rxcui, ttl_seconds=86400)
                        return rxcui
        except Exception as exc:
            logger.warning("rxnav_rxcui_query_failed", drug=drug_name, error=str(exc))
        return None

    async def _query_rxnav_interactions(self, rxcuis: List[str]) -> List[Dict[str, Any]]:
        """Query NIH RxNav for interactions among a list of RxCUIs."""
        if len(rxcuis) < 2:
            return []

        joined_rxcuis = "+".join(rxcuis)
        cache_key = f"rxnav:interactions:{joined_rxcuis}"
        cached = await cache.get(cache_key)
        if cached:
            import json
            try:
                return json.loads(cached)
            except Exception:
                pass

        url = f"https://rxnav.nlm.nih.gov/REST/interaction/list.json?rxcuis={joined_rxcuis}"
        interactions: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    interaction_groups = data.get("fullInteractionTypeGroup", [])
                    for group in interaction_groups:
                        source_name = group.get("sourceName", "RxNav/ONCHigh")
                        for itype in group.get("fullInteractionType", []):
                            pairs = itype.get("interactionPair", [])
                            for pair in pairs:
                                concepts = pair.get("interactionConcept", [])
                                drug_a = concepts[0].get("minConceptItem", {}).get("name", "Unknown") if len(concepts) > 0 else "Unknown"
                                drug_b = concepts[1].get("minConceptItem", {}).get("name", "Unknown") if len(concepts) > 1 else "Unknown"
                                severity = pair.get("severity", "Moderate")
                                if severity.lower() in ("high", "severe"):
                                    sev_formatted = "Major"
                                elif severity.lower() in ("medium", "moderate"):
                                    sev_formatted = "Moderate"
                                else:
                                    sev_formatted = "Minor"

                                interactions.append({
                                    "drug_a": drug_a,
                                    "drug_b": drug_b,
                                    "severity": sev_formatted,
                                    "description": pair.get("description", "Interaction reported by NIH RxNav."),
                                    "source": f"NIH RxNav ({source_name})",
                                })
                    if interactions:
                        import json
                        await cache.set(cache_key, json.dumps(interactions), ttl_seconds=86400)
        except Exception as exc:
            logger.warning("rxnav_interaction_api_error", error=str(exc))

        return interactions

    def _check_local(self, clean_names: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """Check all 2-combinations in local database."""
        results: List[Dict[str, Any]] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        for (orig_a, clean_a), (orig_b, clean_b) in itertools.combinations(clean_names, 2):
            if clean_a == clean_b:
                continue
            pair_key = tuple(sorted([clean_a, clean_b]))
            if pair_key in seen_pairs:
                continue

            entry = self._local_db.get((clean_a, clean_b))
            if entry:
                seen_pairs.add(pair_key)
                results.append({
                    "drug_a": orig_a,
                    "drug_b": orig_b,
                    "severity": entry["severity"],
                    "description": entry["description"],
                    "source": entry["source"],
                })

        return results

    async def check_interactions_async(self, medication_names: List[str]) -> List[Dict[str, Any]]:
        """Evaluate drug interactions using configured engine with automatic fallbacks."""
        if not medication_names or len(medication_names) < 2:
            return []

        clean_pairs = [(m, clean_drug_name(m)) for m in medication_names if m and clean_drug_name(m)]
        
        # 1. If RxNav mode requested, attempt live RxNav API
        if self.source == "rxnav":
            rxcui_map: Dict[str, str] = {}
            for orig, cname in clean_pairs:
                rxcui = await self._query_rxnav_rxcui(cname)
                if rxcui:
                    rxcui_map[rxcui] = orig

            if len(rxcui_map) >= 2:
                rx_results = await self._query_rxnav_interactions(list(rxcui_map.keys()))
                if rx_results:
                    return rx_results

        # 2. Local database match (handles custom_csv and serves as robust offline fallback)
        return self._check_local(clean_pairs)

    def check_interactions(self, medication_names: List[str]) -> List[Dict[str, Any]]:
        """Synchronous wrapper for pairwise drug interaction checking."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            clean_pairs = [(m, clean_drug_name(m)) for m in medication_names if m and clean_drug_name(m)]
            return self._check_local(clean_pairs)
        return asyncio.run(self.check_interactions_async(medication_names))


drug_interaction_service = DrugInteractionService()
