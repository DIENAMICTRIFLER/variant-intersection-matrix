# 🔬 Variant Intersection Matrix Analyzer

A structured Python system for analyzing research papers using a **Variant Intersection Matrix**. The system detects predefined variants (with synonyms) across academic papers and computes pairwise intersection counts to identify research coverage and gaps.

---

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  PDF Papers  │────▶│  Text Extraction │────▶│   Preprocessing    │
└──────────────┘     └──────────────────┘     └────────┬───────────┘
                                                       │
┌──────────────┐                                       ▼
│   Variant    │────▶┌──────────────────┐     ┌────────────────────┐
│ Definitions  │     │ Variant Detection│◀────│  Preprocessed Text │
└──────────────┘     └────────┬─────────┘     └────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐     ┌────────────────────┐
                    │ Paper × Variant  │────▶│  Intersection      │
                    │  Binary Matrix   │     │  Matrix (M.T @ M)  │
                    └──────────────────┘     └────────┬───────────┘
                                                      │
                                                      ▼
                                             ┌────────────────────┐
                                             │  Streamlit UI      │
                                             │  • Heatmaps        │
                                             │  • Drill-downs     │
                                             │  • Research Gaps   │
                                             │  • CSV Export       │
                                             └────────────────────┘
```

## 📁 Project Structure

```
Model/
├── config/
│   ├── __init__.py
│   └── settings.py              # Centralized configuration
├── core/
│   ├── __init__.py
│   ├── text_extraction.py       # PDF → raw text (pdfplumber)
│   ├── preprocessing.py         # Text normalization & cleaning
│   ├── variant_detection.py     # Variant presence detection
│   └── matrix_computation.py    # Matrix operations & export
├── data/
│   ├── papers/                  # Uploaded PDFs
│   ├── variants/                # Variant definitions (JSON)
│   ├── output/                  # Generated CSVs
│   └── cache/                   # Extracted text cache
├── interface/
│   ├── __init__.py
│   ├── app.py                   # Main Streamlit application
│   └── components/
│       ├── __init__.py
│       ├── paper_manager.py     # Paper upload & management
│       ├── variant_manager.py   # Variant/synonym CRUD
│       ├── analysis_runner.py   # Analysis orchestration
│       └── matrix_viewer.py     # Interactive matrix display
├── utils/
│   ├── __init__.py
│   └── helpers.py               # Shared utility functions
├── requirements.txt
├── README.md
└── run.py                       # Entry point
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Launch the Application

```bash
python run.py
```

Or directly with Streamlit:

```bash
streamlit run interface/app.py
```

### 3. Use the Application

1. **📄 Papers** — Upload your PDF research papers
2. **🧬 Variants** — Define variants and their synonyms
3. **⚙️ Run Analysis** — Execute the detection pipeline
4. **📊 View Results** — Explore the interactive matrices

## 📊 Outputs

The system generates three CSV files:

| File | Description |
|------|-------------|
| `paper_variant_matrix.csv` | Binary matrix showing which variants appear in each paper |
| `variant_intersection_matrix.csv` | Symmetric matrix of pairwise intersection counts |
| `pair_details.csv` | Flat listing of all variant pairs with counts and supporting papers |

## ⚡ Performance

- **Batch processing** for PDF extraction (configurable batch size)
- **File-hash caching** — re-extraction only when PDFs change
- **Efficient intersection** via matrix multiplication (`M.T @ M`)
- Handles **150 papers × 54 variants × ~1,431 pairs** efficiently

## ✏️ Manual Validation

The system supports manual overrides:
- Select a paper and variant
- Toggle the detection result
- Overrides persist across sessions
- Re-run analysis to apply overrides to the matrices

## 🔧 Configuration

All settings are in `config/settings.py`:
- `PDF_BATCH_SIZE` — papers processed per batch (default: 25)
- `PRESENCE_THRESHOLD` — minimum occurrences to count as "present"
- `HEATMAP_COLORSCALE` — Plotly color scale for heatmaps
- `MAX_PAGES_PER_PAPER` — page limit per PDF (None = all)
