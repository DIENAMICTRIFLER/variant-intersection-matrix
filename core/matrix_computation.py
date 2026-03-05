"""
Matrix Computation Module
=========================

Builds and operates on the two core matrices:

    1. Paper × Variant binary matrix  (rows = papers, cols = variants)
       → Shows which variants appear in which papers.
       → Papers are identified by sequential IDs: P1, P2, P3, ...

    2. Variant × Variant intersection matrix  (symmetric)
       → Cell (i, j) = number of papers that mention BOTH variant i AND variant j.
       → CRITICAL: variants from the SAME dimension are NOT paired.
         E.g., "Energy Consuming" × "Non Energy Consuming" (both under
         "Product Energy Consumption") is skipped — such a cell is set to -1
         (or NaN in the DataFrame) to indicate an invalid/excluded pair.
       → Computed efficiently as M.T @ M with dimension masking applied.

    3. Pair details:  for every valid cross-dimension pair, lists the
       intersection count and the supporting papers.

How Dimension Exclusion Works:
    Each variant belongs to a dimension (e.g., "Product Energy Consumption").
    The dimension_map dict maps variant_name → dimension_name.

    When building the intersection matrix, any pair (v1, v2) where
    dimension_map[v1] == dimension_map[v2] is marked as excluded.
    This is because variants within the same dimension are mutually
    exclusive categories — pairing them is logically invalid.
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

# Sentinel value used in the intersection matrix for same-dimension pairs.
# These cells are excluded from counting, gaps analysis, etc.
EXCLUDED_PAIR_VALUE = -1


class MatrixComputer:
    """
    Builds the paper-variant binary matrix and computes the intersection matrix.

    Attributes:
        paper_variant_df:  DataFrame with papers as rows, variants as columns.
        intersection_df:   Symmetric DataFrame of variant-pair intersection counts.
                           Same-dimension cells contain EXCLUDED_PAIR_VALUE (-1).
        dimension_map:     Dict mapping variant_name → dimension_name.
    """

    def __init__(self):
        self.paper_variant_df: Optional[pd.DataFrame] = None
        self.intersection_df: Optional[pd.DataFrame] = None
        self.dimension_map: Dict[str, str] = {}
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
            DataFrame with paper_ids (P1,P2,...) as index and variant_names
            as columns. Values are 0 or 1.
        """
        logger.info(
            "Building paper–variant matrix: %d papers × %d variants",
            len(detection_results), len(variant_names),
        )

        # Construct matrix row by row
        rows = {}
        for paper_id, variant_presence in detection_results.items():
            row = {v: int(variant_presence.get(v, False)) for v in variant_names}
            rows[paper_id] = row

        df = pd.DataFrame.from_dict(rows, orient="index", columns=variant_names)
        df.index.name = "paper_id"
        df = df.sort_index()

        # Apply manual overrides (researcher corrections)
        df = self._apply_overrides(df)

        self.paper_variant_df = df
        logger.info("Paper–variant matrix shape: %s", df.shape)
        return df

    def compute_intersection_matrix(
        self,
        paper_variant_df: Optional[pd.DataFrame] = None,
        dimension_map: Optional[Dict[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Compute the Variant × Variant intersection matrix.

        Algorithm:
            1. Compute the raw intersection via matrix multiplication: M.T @ M
            2. Apply dimension masking: set cells where both variants share
               the same dimension to EXCLUDED_PAIR_VALUE (-1).

        The diagonal values represent the total papers for each variant.

        Args:
            paper_variant_df: Optional; uses stored matrix if not provided.
            dimension_map:    Dict mapping variant_name → dimension_name.
                              If None, uses the stored map (no exclusion if empty).

        Returns:
            Symmetric DataFrame of intersection counts.
            Same-dimension cells are set to -1 (excluded).
        """
        if paper_variant_df is not None:
            self.paper_variant_df = paper_variant_df
        if dimension_map is not None:
            self.dimension_map = dimension_map

        if self.paper_variant_df is None:
            raise ValueError("Paper-variant matrix has not been built yet.")

        # Step 1: Raw intersection via matrix multiplication
        M = self.paper_variant_df.values.astype(np.int32)
        raw_intersection = M.T @ M

        variant_names = list(self.paper_variant_df.columns)
        result = pd.DataFrame(
            raw_intersection,
            index=variant_names,
            columns=variant_names,
        )

        # Step 2: Apply dimension masking
        # If two variants belong to the same dimension, set their
        # intersection cell to EXCLUDED_PAIR_VALUE (-1).
        if self.dimension_map:
            n = len(variant_names)
            for i in range(n):
                for j in range(i + 1, n):
                    vi = variant_names[i]
                    vj = variant_names[j]
                    dim_i = self.dimension_map.get(vi, "")
                    dim_j = self.dimension_map.get(vj, "")
                    if dim_i and dim_j and dim_i == dim_j:
                        # Symmetric exclusion
                        result.iloc[i, j] = EXCLUDED_PAIR_VALUE
                        result.iloc[j, i] = EXCLUDED_PAIR_VALUE

        self.intersection_df = result
        logger.info("Intersection matrix computed: %s", result.shape)
        return result

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
            List of paper_id strings (P1, P2, ...).
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

    def is_same_dimension_pair(self, variant_a: str, variant_b: str) -> bool:
        """
        Check if two variants belong to the same dimension.

        Same-dimension pairs are excluded from the intersection matrix.

        Args:
            variant_a: First variant name.
            variant_b: Second variant name.

        Returns:
            True if both variants share the same (non-empty) dimension.
        """
        if not self.dimension_map:
            return False
        dim_a = self.dimension_map.get(variant_a, "")
        dim_b = self.dimension_map.get(variant_b, "")
        return bool(dim_a and dim_b and dim_a == dim_b)

    def get_research_gaps(self) -> List[Tuple[str, str]]:
        """
        Identify research gaps: CROSS-DIMENSION variant pairs
        with zero intersection.

        Same-dimension pairs (marked as -1) are excluded — they are
        not gaps, they are structurally invalid comparisons.

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
                value = self.intersection_df.iloc[i, j]
                # Skip excluded pairs (same dimension) and only
                # report genuine zeros
                if value == 0:
                    gaps.append((va, vb))

        logger.info("Found %d research gaps (zero cross-dimension pairs)", len(gaps))
        return gaps

    def generate_pair_details(self) -> pd.DataFrame:
        """
        Generate a flat DataFrame with one row per valid variant pair,
        showing the intersection count and the supporting papers.

        Same-dimension pairs are excluded from this listing.

        Columns: dimension_a, variant_a, dimension_b, variant_b,
                 intersection_count, supporting_papers

        Returns:
            DataFrame with pair details.
        """
        if self.paper_variant_df is None or self.intersection_df is None:
            raise ValueError("Matrices not computed yet.")

        variant_names = list(self.intersection_df.columns)
        rows = []

        for i, va in enumerate(variant_names):
            for j in range(i + 1, len(variant_names)):
                vb = variant_names[j]
                count = int(self.intersection_df.iloc[i, j])

                # Skip same-dimension pairs (marked as -1)
                if count == EXCLUDED_PAIR_VALUE:
                    continue

                papers = self.get_papers_for_pair(va, vb) if count > 0 else []
                dim_a = self.dimension_map.get(va, "Uncategorized")
                dim_b = self.dimension_map.get(vb, "Uncategorized")
                rows.append({
                    "dimension_a": dim_a,
                    "variant_a": va,
                    "dimension_b": dim_b,
                    "variant_b": vb,
                    "intersection_count": count,
                    "supporting_papers": "; ".join(papers),
                })

        return pd.DataFrame(rows)

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Return summary statistics about the matrices.

        Stats include:
            • total_papers, total_variants, total_detections
            • avg_variants_per_paper, avg_papers_per_variant
            • variants_never_detected
            • total_valid_pairs (cross-dimension only)
            • research_gaps, covered_pairs, max_intersection
            • excluded_pairs (same-dimension count)
        """
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
            total_all_pairs = n * (n - 1) // 2

            # Count same-dimension excluded pairs and genuine zeros
            excluded_count = 0
            zero_count = 0
            for i in range(n):
                for j in range(i + 1, n):
                    val = self.intersection_df.iloc[i, j]
                    if val == EXCLUDED_PAIR_VALUE:
                        excluded_count += 1
                    elif val == 0:
                        zero_count += 1

            valid_pairs = total_all_pairs - excluded_count
            stats["total_all_pairs"] = total_all_pairs
            stats["excluded_pairs"] = excluded_count
            stats["total_valid_pairs"] = valid_pairs
            stats["research_gaps"] = zero_count
            stats["covered_pairs"] = valid_pairs - zero_count

            # Max intersection (ignoring excluded cells and diagonal)
            values = self.intersection_df.values.copy()
            np.fill_diagonal(values, 0)
            values[values == EXCLUDED_PAIR_VALUE] = 0
            stats["max_intersection"] = int(np.triu(values, k=1).max()) if n > 1 else 0

        return stats

    # ── Manual Overrides ─────────────────────────────────────────────────

    def set_override(self, paper_id: str, variant_name: str, value: bool):
        """
        Manually override a paper-variant detection result.

        Args:
            paper_id: Paper identifier (P1, P2, ...).
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
        Export all CSV files to the output directory.

        Files generated:
            • paper_variant_matrix.csv
            • variant_intersection_matrix.csv
            • pair_details.csv  (excludes same-dimension pairs)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.paper_variant_df is not None:
            path = output_dir / PAPER_VARIANT_MATRIX_CSV
            self.paper_variant_df.to_csv(path)
            logger.info("Exported: %s", path)

        if self.intersection_df is not None:
            path = output_dir / VARIANT_INTERSECTION_MATRIX_CSV
            # Replace -1 with "EXCLUDED" in the CSV for clarity
            export_df = self.intersection_df.copy()
            export_df = export_df.replace(EXCLUDED_PAIR_VALUE, "EXCLUDED")
            export_df.to_csv(path)
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
