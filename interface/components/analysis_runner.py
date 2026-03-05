"""
Analysis Runner Component
=========================

Orchestrates the full analysis pipeline from the Streamlit UI:
    1. Text extraction from PDFs
    2. Text preprocessing
    3. Variant detection
    4. Matrix computation
    5. CSV export

Shows real-time progress bars and caches results in session state.
"""

import logging
import streamlit as st
from pathlib import Path

from config.settings import PAPERS_DIR, OUTPUT_DIR
from core.text_extraction import TextExtractor
from core.preprocessing import TextPreprocessor
from core.variant_detection import VariantDetector
from core.matrix_computation import MatrixComputer

logger = logging.getLogger(__name__)


def render_analysis_runner():
    """Render the Analysis Runner section of the UI."""
    st.header("⚙️ Run Analysis")

    # Pre-check: are papers and variants ready?
    papers = list(PAPERS_DIR.glob("*.pdf"))
    variants = st.session_state.get("variants", [])

    col1, col2 = st.columns(2)
    with col1:
        papers_ready = len(papers) > 0
        st.metric("Papers Loaded", len(papers))
        if not papers_ready:
            st.warning("Upload at least one paper before running analysis.")
    with col2:
        variants_ready = len(variants) > 0
        st.metric("Variants Defined", len(variants))
        if not variants_ready:
            st.warning("Define at least one variant before running analysis.")

    can_run = papers_ready and variants_ready

    st.divider()

    # ── Run Button ───────────────────────────────────────────────────
    if st.button(
        "🚀 Run Full Analysis",
        type="primary",
        disabled=not can_run,
        use_container_width=True,
    ):
        _run_full_pipeline(variants)

    # ── Show cached results summary ─────────────────────────────────
    if "matrix_computer" in st.session_state and st.session_state.matrix_computer is not None:
        st.divider()
        _show_results_summary()


def _run_full_pipeline(variants):
    """Execute the complete analysis pipeline with progress tracking."""
    status = st.status("Running analysis pipeline...", expanded=True)

    try:
        # ── Step 1: Text Extraction ──────────────────────────────────
        status.write("**Step 1/4:** Extracting text from PDFs...")
        progress_bar = st.progress(0, text="Extracting PDFs...")

        extractor = TextExtractor()

        def extraction_progress(current, total):
            progress_bar.progress(
                current / total,
                text=f"Extracting PDFs... ({current}/{total})",
            )

        raw_texts = extractor.extract_all(progress_callback=extraction_progress)
        progress_bar.progress(1.0, text="✅ Extraction complete")

        if not raw_texts:
            st.error("No text could be extracted from the uploaded papers.")
            status.update(label="Analysis failed", state="error")
            return

        status.write(f"  → Extracted text from {len(raw_texts)} papers")

        # ── Step 2: Preprocessing ────────────────────────────────────
        status.write("**Step 2/4:** Preprocessing texts...")
        preprocessor = TextPreprocessor()
        preprocessed = preprocessor.preprocess_all(raw_texts)
        status.write(f"  → Preprocessed {len(preprocessed)} documents")

        # ── Step 3: Variant Detection ────────────────────────────────
        status.write("**Step 3/4:** Detecting variants...")
        progress_bar2 = st.progress(0, text="Detecting variants...")

        detector = VariantDetector(variants=variants, preprocessor=preprocessor)

        def detection_progress(current, total):
            progress_bar2.progress(
                current / total,
                text=f"Detecting variants... ({current}/{total})",
            )

        detection_results = detector.detect_all(
            preprocessed,
            progress_callback=detection_progress,
        )
        progress_bar2.progress(1.0, text="✅ Detection complete")
        status.write(f"  → Scanned {len(detection_results)} papers × {len(variants)} variants")

        # ── Step 4: Matrix Computation ───────────────────────────────
        status.write("**Step 4/4:** Computing matrices...")
        computer = MatrixComputer()
        variant_names = detector.get_variant_names()

        paper_variant_df = computer.build_paper_variant_matrix(
            detection_results, variant_names
        )
        intersection_df = computer.compute_intersection_matrix()

        # Export CSVs
        computer.export_all()
        status.write(f"  → Exported CSVs to `{OUTPUT_DIR}`")

        # ── Store results in session state ───────────────────────────
        st.session_state.matrix_computer = computer
        st.session_state.paper_variant_df = paper_variant_df
        st.session_state.intersection_df = intersection_df
        st.session_state.detection_results = detection_results
        st.session_state.preprocessed_texts = preprocessed
        st.session_state.variant_detector = detector
        st.session_state.analysis_complete = True

        status.update(label="✅ Analysis complete!", state="complete")
        st.balloons()

    except Exception as e:
        logger.exception("Analysis pipeline failed")
        status.update(label="❌ Analysis failed", state="error")
        st.error(f"An error occurred: {str(e)}")


def _show_results_summary():
    """Display summary statistics from the last analysis run."""
    st.subheader("📊 Results Summary")

    computer: MatrixComputer = st.session_state.matrix_computer
    stats = computer.get_summary_stats()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Papers Analyzed", stats.get("total_papers", 0))
    col2.metric("Variants Tracked", stats.get("total_variants", 0))
    col3.metric("Total Detections", stats.get("total_detections", 0))
    col4.metric("Research Gaps", stats.get("research_gaps", 0))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Avg Variants/Paper", f"{stats.get('avg_variants_per_paper', 0):.1f}")
    col6.metric("Avg Papers/Variant", f"{stats.get('avg_papers_per_variant', 0):.1f}")
    col7.metric("Total Pairs", stats.get("total_pairs", 0))
    col8.metric("Covered Pairs", stats.get("covered_pairs", 0))

    # Download buttons for output files
    st.divider()
    st.subheader("📥 Download Results")

    output_files = list(OUTPUT_DIR.glob("*.csv"))
    if output_files:
        cols = st.columns(len(output_files))
        for i, file_path in enumerate(sorted(output_files)):
            with cols[i]:
                with open(file_path, "r") as f:
                    csv_data = f.read()
                st.download_button(
                    label=f"📄 {file_path.name}",
                    data=csv_data,
                    file_name=file_path.name,
                    mime="text/csv",
                    use_container_width=True,
                )
