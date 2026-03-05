"""
Core processing engine for the Variant Intersection Matrix system.

Modules:
    text_extraction    – PDF → raw text
    preprocessing      – text normalization and cleaning
    variant_detection  – variant presence detection in documents
    matrix_computation – binary matrix and intersection computation
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
