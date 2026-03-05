"""
Variant Detection Module
========================

Detects the presence of predefined variants (and their synonyms) in
preprocessed paper texts.

Strategy:
    • Variants are organized by dimension:
        {
          "Product Energy Consumption": {
            "Energy Consuming": ["energy consuming", "energy-intensive"],
            "Non Energy Consuming": ["manual product", "non powered"]
          }
        }

    • Pre-compile a search index: variant → list of normalized search terms
      (the variant name itself + all synonyms).  Normalization uses the
      same TextPreprocessor.preprocess_variant_term() as paper text.

    • For each paper text, check each term via substring matching.
      A variant is "present" if any of its terms appears at least
      `presence_threshold` times.

    • Return a binary presence dict per paper:
      {paper_id: {variant_name: True/False}}

Dimension metadata is preserved so the matrix computation module
can skip same-dimension pairs when building the VIM.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config.settings import PRESENCE_THRESHOLD, CASE_INSENSITIVE, VARIANTS_FILE
from core.preprocessing import TextPreprocessor
from utils.helpers import (
    load_json,
    save_json,
    dimensions_to_flat_list,
    flat_list_to_dimensions,
)

logger = logging.getLogger(__name__)


class VariantDetector:
    """
    Detects variant presence across a corpus of preprocessed texts.

    Supports the new dimension-aware variant structure while remaining
    backwards-compatible with legacy flat lists.

    Attributes:
        variants:     Flat list of variant dicts, each with "dimension", "name", "synonyms".
        preprocessor: TextPreprocessor for normalizing variant terms.
        threshold:    Minimum occurrences to consider a variant "present".
    """

    def __init__(
        self,
        variants: Optional[List[Dict[str, Any]]] = None,
        preprocessor: Optional[TextPreprocessor] = None,
        threshold: int = PRESENCE_THRESHOLD,
    ):
        self.preprocessor = preprocessor or TextPreprocessor()
        self.threshold = threshold

        # Load variants (flat list with dimension info)
        if variants is not None:
            self.variants = self._ensure_dimension_fields(variants)
        else:
            self.variants = self._load_variants()

        # Build search index: variant_name → list of preprocessed search terms
        self._search_index: Dict[str, List[str]] = {}
        self._build_search_index()

    # ── Public API ───────────────────────────────────────────────────────

    def detect_all(
        self,
        preprocessed_texts: Dict[str, str],
        progress_callback=None,
    ) -> Dict[str, Dict[str, bool]]:
        """
        Detect variants in all papers.

        Args:
            preprocessed_texts: {paper_id: preprocessed_text}.
            progress_callback:  Optional callable(current, total).

        Returns:
            Nested dict: {paper_id: {variant_name: True/False}}.
        """
        total = len(preprocessed_texts)
        logger.info(
            "Detecting %d variants across %d papers",
            len(self.variants), total,
        )

        results: Dict[str, Dict[str, bool]] = {}
        for idx, (paper_id, text) in enumerate(preprocessed_texts.items()):
            results[paper_id] = self.detect_in_text(text)
            if progress_callback:
                progress_callback(idx + 1, total)

        return results

    def detect_in_text(self, text: str) -> Dict[str, bool]:
        """
        Check which variants are present in a single preprocessed text.

        Uses phrase-based substring matching on normalized text.
        The match is deterministic and consistent because both
        paper text and synonym terms pass through the same normalization.

        Args:
            text: Preprocessed text of a paper.

        Returns:
            Dict mapping each variant name to a boolean presence flag.
        """
        presence: Dict[str, bool] = {}
        for variant_name, terms in self._search_index.items():
            found = self._check_terms(text, terms)
            presence[variant_name] = found
        return presence

    def get_variant_names(self) -> List[str]:
        """Return ordered list of variant names."""
        return [v["name"] for v in self.variants]

    def get_dimension_map(self) -> Dict[str, str]:
        """
        Return a mapping of variant_name → dimension_name.

        This is used by MatrixComputer to know which variants belong
        to the same dimension (and thus should NOT be paired in the VIM).

        Returns:
            Dict mapping each variant name to its parent dimension.
        """
        return {v["name"]: v.get("dimension", "Uncategorized") for v in self.variants}

    def get_variant_details(self, variant_name: str) -> Optional[Dict[str, Any]]:
        """Return full definition for a named variant."""
        for v in self.variants:
            if v["name"] == variant_name:
                return v
        return None

    def count_occurrences(self, text: str, variant_name: str) -> int:
        """
        Count total occurrences of a variant (all synonym terms) in text.

        Useful for the UI to show how strongly a variant is represented.
        """
        terms = self._search_index.get(variant_name, [])
        count = 0
        for term in terms:
            if term:
                pattern = re.compile(re.escape(term))
                count += len(pattern.findall(text))
        return count

    def reload_variants(self, variants: Optional[List[Dict[str, Any]]] = None):
        """Reload variant definitions and rebuild search index."""
        if variants is not None:
            self.variants = self._ensure_dimension_fields(variants)
        else:
            self.variants = self._load_variants()
        self._build_search_index()
        logger.info("Reloaded %d variant definitions", len(self.variants))

    # ── Internal Methods ─────────────────────────────────────────────────

    def _ensure_dimension_fields(
        self, variants: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Ensure every variant dict has a 'dimension' field.

        Legacy data may not include dimensions — assign "Uncategorized".
        """
        for v in variants:
            if "dimension" not in v:
                v["dimension"] = "Uncategorized"
        return variants

    def _build_search_index(self):
        """
        Build the search index: for each variant, compile the list of
        preprocessed search terms (variant name + all synonyms).

        Both the variant name and each synonym are normalized with
        preprocess_variant_term() to match the normalization applied
        to the paper text.
        """
        self._search_index.clear()
        for variant in self.variants:
            name = variant["name"]
            synonyms = variant.get("synonyms", [])

            # Collect all terms: the name itself + synonyms
            raw_terms = [name] + synonyms
            processed_terms = []
            for term in raw_terms:
                processed = self.preprocessor.preprocess_variant_term(term)
                if processed:
                    processed_terms.append(processed)

            self._search_index[name] = processed_terms

        logger.debug(
            "Search index built: %d variants, %d total terms",
            len(self._search_index),
            sum(len(t) for t in self._search_index.values()),
        )

    def _check_terms(self, text: str, terms: List[str]) -> bool:
        """
        Check if any term from the list appears in the text at least
        `threshold` times.

        Uses simple substring search — fast and sufficient for
        moderate-length texts (research paper scale).
        """
        total_count = 0
        for term in terms:
            if not term:
                continue
            count = text.count(term)
            total_count += count
            # Early exit if threshold is met
            if total_count >= self.threshold:
                return True
        return total_count >= self.threshold

    def _load_variants(self) -> List[Dict[str, Any]]:
        """
        Load variant definitions from the JSON file.

        Handles both the new dimension-aware format:
            {"dimensions": {"DimName": {"VarName": ["syn1", ...]}}}

        And the legacy flat format:
            {"variants": [{"name": "...", "synonyms": [...]}]}
        """
        try:
            data = load_json(VARIANTS_FILE)

            # New dimension-aware format
            if isinstance(data, dict) and "dimensions" in data:
                return dimensions_to_flat_list(data["dimensions"])

            # Legacy flat format
            if isinstance(data, dict) and "variants" in data:
                variants = data["variants"]
                return self._ensure_dimension_fields(variants)

            if isinstance(data, list):
                return self._ensure_dimension_fields(data)

            return []
        except FileNotFoundError:
            logger.info("No variants file found at %s — starting empty", VARIANTS_FILE)
            return []

    @staticmethod
    def save_variants(
        variants: List[Dict[str, Any]],
        filepath=VARIANTS_FILE,
    ):
        """
        Save variant definitions using the new dimension-aware format.

        Converts the flat list to the canonical dimension dict:
            {"dimensions": {"DimName": {"VarName": ["syn1", ...]}}}
        """
        dimensions = flat_list_to_dimensions(variants)
        save_json({"dimensions": dimensions}, filepath)
        logger.info("Saved %d variant definitions to %s", len(variants), filepath)
