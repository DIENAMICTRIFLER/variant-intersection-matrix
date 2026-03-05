"""
Centralized configuration for the Variant Intersection Matrix system.

All paths, thresholds, and tunables are defined here so that no module
contains hard-coded magic values.
"""

import os
from pathlib import Path

# ─── Project Root ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ─── Data Directories ───────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
PAPERS_DIR = DATA_DIR / "papers"
VARIANTS_DIR = DATA_DIR / "variants"
OUTPUT_DIR = DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"

# Ensure directories exist at import time
for _dir in (PAPERS_DIR, VARIANTS_DIR, OUTPUT_DIR, CACHE_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ─── Variant Definitions File ───────────────────────────────────────────────
VARIANTS_FILE = VARIANTS_DIR / "variants.json"

# ─── Output Filenames ───────────────────────────────────────────────────────
PAPER_VARIANT_MATRIX_CSV = "paper_variant_matrix.csv"
VARIANT_INTERSECTION_MATRIX_CSV = "variant_intersection_matrix.csv"
PAIR_DETAILS_CSV = "pair_details.csv"
MANUAL_OVERRIDES_FILE = CACHE_DIR / "manual_overrides.json"

# ─── Processing Configuration ───────────────────────────────────────────────
# Batch size for PDF processing (number of papers per batch)
PDF_BATCH_SIZE = 25

# Maximum number of pages to extract per paper (None = all pages)
MAX_PAGES_PER_PAPER = None

# ─── Text Preprocessing ─────────────────────────────────────────────────────
# Minimum word length to keep during preprocessing
MIN_WORD_LENGTH = 2

# Whether to apply stemming (can reduce recall for multi-word variants)
APPLY_STEMMING = False

# ─── Variant Detection ──────────────────────────────────────────────────────
# Minimum number of occurrences to consider a variant "present" in a paper
PRESENCE_THRESHOLD = 1

# Whether to use case-insensitive matching (recommended)
CASE_INSENSITIVE = True

# ─── Streamlit Interface ────────────────────────────────────────────────────
# Page configuration
PAGE_TITLE = "Variant Intersection Matrix Analyzer"
PAGE_ICON = "🔬"
PAGE_LAYOUT = "wide"

# Matrix heatmap color scale
HEATMAP_COLORSCALE = "YlOrRd"
HEATMAP_ZERO_COLOR = "#f0f0f0"

# Maximum file upload size in MB
MAX_UPLOAD_SIZE_MB = 200
