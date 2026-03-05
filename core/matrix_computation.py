"""
Matrix Computation Module
=========================

Builds and operates on the two core matrices:

    1. Paper × Variant binary matrix  (rows = papers, cols = variants)
       → Shows which variants appear in which papers.

    2. Variant × Variant intersection matrix  (symmetric, nC2 pairs)
       → Cell (i, j) = number of papers that mention BOTH variant i AND variant j.
       → Computed efficiently as M.T @ M (matrix multiplication on binary matrix).

Also produces pair-detail listings: for each non-zero intersection cell,
list the supporting papers.
"""

import logging
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from config.settings import (
    OUTPUT_DIR,
    PAPER_VARIANT_MATRIX_CSV,
    VARIANT_INTERSECTION_MATRIX_CSV,
    PAIR_DETAILS_CSV,
    MANUAL_OVERRIDES_FILE,
)
from utils.helpers import load_json, save_json

logger = logging.getLogger(__name__)


class MatrixComputer:
    """
    Builds the paper-variant binary matrix and computes the intersection matrix.

    Attributes:
        paper_variant_df:  DataFrame with papers as rows, variants as columns.
        intersection_df:   Symmetric DataFrame of variant-pair intersection counts.
    """

    def __init__(self):
        self.paper_variant_df: Optional[pd.DataFrame] = None
        self.intersection_df: Optional[pd.DataFrame] = None
        self._manual_overrides: Dict[str, Dict[str, bool]] = {}
        self._load_overrides()

    # ── Public API ───────────────────────────────────────────────────────

    def build_paper_variant_matrix(
        self,
        detection_results: Dict[str, Dict[str, bool]],
        variant_names: List[str],
    ) -> pd.DataFrame:
        """
        Build the Paper × Variant binary matrix from detection results.

        Args:
            detection_results: {paper_id: {variant_name: bool}}.
            variant_names: Ordered list of variant names (columns).

        Returns:
            DataFrame with paper_ids as index and variant_names as columns.
            Values are 0 or 1.
        """
        logger.info(
            "Building paper–variant matrix: %d papers × %d variants",
            len(detection_results), len(variant_names),
        )

        # Construct matrix
        rows = {}
        for paper_id, variant_presence in detection_results.items():
            row = {v: int(variant_presence.get(v, False)) for v in variant_names}
            rows[paper_id] = row

        df = pd.DataFrame.from_dict(rows, orient="index", columns=variant_names)
        df.index.name = "paper_id"
        df = df.sort_index()

        # Apply manual overrides
        df = self._apply_overrides(df)

        self.paper_variant_df = df
        logger.info("Paper–variant matrix shape: %s", df.shape)
        return df

    def compute_intersection_matrix(
        self,
        paper_variant_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Compute the Variant × Variant intersection matrix.

        Uses matrix multiplication: intersection = M.T @ M
        where M is the binary paper-variant matrix.

        Diagonal values represent the total number of papers mentioning
        that variant.

        Args:
            paper_variant_df: Optional; uses stored matrix if not provided.

        Returns:
            Symmetric DataFrame of intersection counts.
        """
        if paper_variant_df is not None:
            self.paper_variant_df = paper_variant_df

        if self.paper_variant_df is None:
            raise ValueError("Paper-variant matrix has not been built yet.")

        M = self.paper_variant_df.values.astype(np.int32)
        intersection = M.T @ M

        variant_names = list(self.paper_variant_df.columns)
        self.intersection_df = pd.DataFrame(
            intersection,
            index=variant_names,
            columns=variant_names,
        )

        logger.info("Intersection matrix computed: %s", self.intersection_df.shape)
        return self.intersection_df

    def get_papers_for_pair(
        self,
        variant_a: str,
        variant_b: str,
    ) -> List[str]:
        """
        Get the list of paper IDs that mention both variant_a and variant_b.

        Args:
            variant_a: First variant name.
            variant_b: Second variant name.

        Returns:
            List of paper_id strings.
        """
        if self.paper_variant_df is None:
            return []

        df = self.paper_variant_df
        if variant_a not in df.columns or variant_b not in df.columns:
            return []

        mask = (df[variant_a] == 1) & (df[variant_b] == 1)
        return list(df[mask].index)

    def get_papers_for_variant(self, variant_name: str) -> List[str]:
        """Get all paper IDs that mention a specific variant."""
        if self.paper_variant_df is None:
            return []
        if variant_name not in self.paper_variant_df.columns:
            return []
        mask = self.paper_variant_df[variant_name] == 1
        return list(self.paper_variant_df[mask].index)

    def get_research_gaps(self) -> List[Tuple[str, str]]:
        """
        Identify research gaps: variant pairs with zero intersection.

        Returns:
            List of (variant_a, variant_b) tuples where no paper covers both.
        """
        if self.intersection_df is None:
            return []

        gaps = []
        variants = list(self.intersection_df.columns)
        for i, va in enumerate(variants):
            for j in range(i + 1, len(variants)):
                vb = variants[j]
                if self.intersection_df.loc[va, vb] == 0:
                    gaps.append((va, vb))

        logger.info("Found %d research gaps (zero-intersection pairs)", len(gaps))
        return gaps

    def generate_pair_details(self) -> pd.DataFrame:
        """
        Generate a flat DataFrame with one row per variant pair,
        showing the intersection count and the supporting papers.

        Returns:
            DataFrame with columns: variant_a, variant_b, count, papers.
        """
        if self.paper_variant_df is None or self.intersection_df is None:
            raise ValueError("Matrices not computed yet.")

        variant_names = list(self.intersection_df.columns)
        rows = []

        for i, va in enumerate(variant_names):
            for j in range(i + 1, len(variant_names)):
                vb = variant_names[j]
                count = int(self.intersection_df.loc[va, vb])
                papers = self.get_papers_for_pair(va, vb) if count > 0 else []
                rows.append({
                    "variant_a": va,
                    "variant_b": vb,
                    "intersection_count": count,
                    "supporting_papers": "; ".join(papers),
                })

        return pd.DataFrame(rows)

    def get_summary_stats(self) -> Dict[str, Any]:
        """Return summary statistics about the matrices."""
        stats: Dict[str, Any] = {}
        if self.paper_variant_df is not None:
            df = self.paper_variant_df
            stats["total_papers"] = len(df)
            stats["total_variants"] = len(df.columns)
            stats["total_detections"] = int(df.values.sum())
            stats["avg_variants_per_paper"] = float(df.sum(axis=1).mean())
            stats["avg_papers_per_variant"] = float(df.sum(axis=0).mean())
            stats["variants_never_detected"] = int((df.sum(axis=0) == 0).sum())

        if self.intersection_df is not None:
            n = len(self.intersection_df)
            total_pairs = n * (n - 1) // 2
            # Count zeros in upper triangle (excluding diagonal)
            upper = np.triu(self.intersection_df.values, k=1)
            zero_pairs = int((upper == 0).sum()) - (n * (n - 1) // 2 - total_pairs)
            # Recount properly
            zero_count = 0
            for i in range(n):
                for j in range(i + 1, n):
                    if self.intersection_df.iloc[i, j] == 0:
                        zero_count += 1
            stats["total_pairs"] = total_pairs
            stats["research_gaps"] = zero_count
            stats["covered_pairs"] = total_pairs - zero_count
            stats["max_intersection"] = int(np.triu(self.intersection_df.values, k=1).max())

        return stats

    # ── Manual Overrides ─────────────────────────────────────────────────

    def set_override(self, paper_id: str, variant_name: str, value: bool):
        """
        Manually override a paper-variant detection result.

        Args:
            paper_id: Paper identifier.
            variant_name: Variant name.
            value: True = variant present, False = absent.
        """
        if paper_id not in self._manual_overrides:
            self._manual_overrides[paper_id] = {}
        self._manual_overrides[paper_id][variant_name] = value
        self._save_overrides()
        logger.info("Override set: %s × %s = %s", paper_id, variant_name, value)

    def clear_override(self, paper_id: str, variant_name: str):
        """Remove a manual override."""
        if paper_id in self._manual_overrides:
            self._manual_overrides[paper_id].pop(variant_name, None)
            if not self._manual_overrides[paper_id]:
                del self._manual_overrides[paper_id]
            self._save_overrides()

    def get_overrides(self) -> Dict[str, Dict[str, bool]]:
        """Return all manual overrides."""
        return self._manual_overrides.copy()

    # ── Export ────────────────────────────────────────────────────────────

    def export_all(self, output_dir: Path = OUTPUT_DIR):
        """
        Export all three CSV files to the output directory.

        Files generated:
            • paper_variant_matrix.csv
            • variant_intersection_matrix.csv
            • pair_details.csv
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.paper_variant_df is not None:
            path = output_dir / PAPER_VARIANT_MATRIX_CSV
            self.paper_variant_df.to_csv(path)
            logger.info("Exported: %s", path)

        if self.intersection_df is not None:
            path = output_dir / VARIANT_INTERSECTION_MATRIX_CSV
            self.intersection_df.to_csv(path)
            logger.info("Exported: %s", path)

            pair_df = self.generate_pair_details()
            path = output_dir / PAIR_DETAILS_CSV
            pair_df.to_csv(path, index=False)
            logger.info("Exported: %s", path)

    # ── Internal ─────────────────────────────────────────────────────────

    def _apply_overrides(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply manual overrides to the paper-variant matrix."""
        for paper_id, overrides in self._manual_overrides.items():
            if paper_id in df.index:
                for variant_name, value in overrides.items():
                    if variant_name in df.columns:
                        df.at[paper_id, variant_name] = int(value)
        return df

    def _load_overrides(self):
        """Load manual overrides from disk."""
        try:
            self._manual_overrides = load_json(MANUAL_OVERRIDES_FILE)
        except (FileNotFoundError, Exception):
            self._manual_overrides = {}

    def _save_overrides(self):
        """Persist manual overrides to disk."""
        save_json(self._manual_overrides, MANUAL_OVERRIDES_FILE)
