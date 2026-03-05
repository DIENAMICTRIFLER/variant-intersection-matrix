"""
Core processing engine for the Variant Intersection Matrix system.

Modules:
    text_extraction    – PDF/TXT → raw text, with P1/P2/P3 paper IDs
    preprocessing      – text normalization and cleaning
    variant_detection  – dimension-aware variant presence detection
    matrix_computation – binary matrix and dimension-aware intersection
"""

from .text_extraction import TextExtractor
from .preprocessing import TextPreprocessor
from .variant_detection import VariantDetector
from .matrix_computation import MatrixComputer

__all__ = [
    "TextExtractor",
    "TextPreprocessor",
    "VariantDetector",
    "MatrixComputer",
]
