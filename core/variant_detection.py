"""
Variant Detection Module
========================

Detects the presence of predefined variants (and their synonyms) in
preprocessed paper texts.

Strategy:
    • Pre-compile a mapping of variant → set of normalized search terms
      (the variant name itself + all synonyms).
    • For each paper text, check each term using substring matching.
    • A variant is "present" if any of its terms appears in the text
      at least `presence_threshold` times.
    • Return a binary presence dict per paper.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config.settings import PRESENCE_THRESHOLD, CASE_INSENSITIVE, VARIANTS_FILE
from core.preprocessing import TextPreprocessor
from utils.helpers import load_json, save_json

logger = logging.getLogger(__name__)


class VariantDetector:
    """
    Detects variant presence across a corpus of preprocessed texts.

    Attributes:
        variants:  Ordered list of variant definitions.
        preprocessor: TextPreprocessor for normalizing variant terms.
        threshold: Minimum occurrences to consider a variant "present".
    """

    def __init__(
        self,
        variants: Optional[List[Dict[str, Any]]] = None,
        preprocessor: Optional[TextPreprocessor] = None,
        threshold: int = PRESENCE_THRESHOLD,
    ):
        self.preprocessor = preprocessor or TextPreprocessor()
        self.threshold = threshold

        # Load from file if not provided
        if variants is not None:
            self.variants = variants
        else:
            self.variants = self._load_variants()

        # Build search index: variant_name → list of preprocessed terms
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

    def get_variant_details(self, variant_name: str) -> Optional[Dict[str, Any]]:
        """Return full definition for a named variant."""
        for v in self.variants:
            if v["name"] == variant_name:
                return v
        return None

    def count_occurrences(self, text: str, variant_name: str) -> int:
        """
        Count total occurrences of a variant (all terms) in text.

        Useful for the UI to show how strongly a variant is represented.
        """
        terms = self._search_index.get(variant_name, [])
        count = 0
        for term in terms:
            if term:
                # Use regex with word boundaries for more accurate counting
                pattern = re.compile(re.escape(term))
                count += len(pattern.findall(text))
        return count

    def reload_variants(self, variants: Optional[List[Dict[str, Any]]] = None):
        """Reload variant definitions and rebuild search index."""
        if variants is not None:
            self.variants = variants
        else:
            self.variants = self._load_variants()
        self._build_search_index()
        logger.info("Reloaded %d variant definitions", len(self.variants))

    # ── Internal Methods ─────────────────────────────────────────────────

    def _build_search_index(self):
        """
        Build the search index: for each variant, compile the list of
        preprocessed search terms (variant name + synonyms).
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

        Uses simple substring search (fast for moderate-length texts).
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
        """Load variant definitions from the JSON file."""
        try:
            data = load_json(VARIANTS_FILE)
            if isinstance(data, list):
                return data
            return data.get("variants", [])
        except FileNotFoundError:
            logger.info("No variants file found at %s — starting empty", VARIANTS_FILE)
            return []

    @staticmethod
    def save_variants(variants: List[Dict[str, Any]], filepath=VARIANTS_FILE):
        """Save variant definitions to the JSON file."""
        save_json({"variants": variants}, filepath)
        logger.info("Saved %d variant definitions to %s", len(variants), filepath)
