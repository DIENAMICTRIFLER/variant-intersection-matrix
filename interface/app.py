"""
Variant Intersection Matrix Analyzer — Streamlit Application
=============================================================

Main application entry point. Configures the page, sets up navigation,
and delegates rendering to the component modules.
"""

import sys
import logging
from pathlib import Path

import streamlit as st

# ── Ensure project root is on sys.path ───────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import PAGE_TITLE, PAGE_ICON, PAGE_LAYOUT
from interface.components.paper_manager import render_paper_manager, get_paper_count
from interface.components.variant_manager import render_variant_manager, get_variant_count
from interface.components.analysis_runner import render_analysis_runner
from interface.components.matrix_viewer import render_matrix_viewer

# ── Logging Setup ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)

# ═══════════════════════════════════════════════════════════════════════════
# Page Configuration
# ═══════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=PAGE_LAYOUT,
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main container width */
    .block-container {
        max-width: 1200px;
        padding-top: 1rem;
    }

    /* Metric card styling */
    [data-testid="stMetric"] {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px 16px;
        border: 1px solid #e9ecef;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }

    /* Header styling */
    h1 {
        color: #1a237e;
    }
    h2 {
        color: #283593;
        border-bottom: 2px solid #e8eaf6;
        padding-bottom: 8px;
    }

    /* Divider */
    hr {
        border-color: #e8eaf6;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Sidebar Navigation
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title(f"{PAGE_ICON} VIM Analyzer")
    st.caption("Variant Intersection Matrix")
    st.divider()

    # Navigation
    page = st.radio(
        "Navigation",
        [
            "📄 Papers",
            "🧬 Variants",
            "⚙️ Run Analysis",
            "📊 View Results",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    # Status indicators
    st.markdown("### System Status")
    paper_count = get_paper_count()
    variant_count = get_variant_count()
    analysis_done = st.session_state.get("analysis_complete", False)

    st.markdown(f"- Papers: **{paper_count}**")
    st.markdown(f"- Variants: **{variant_count}**")
    st.markdown(f"- Analysis: **{'✅ Complete' if analysis_done else '⏳ Pending'}**")

    st.divider()
    st.caption("Built for research paper analysis")
    st.caption("Using Variant Intersection Matrices")


# ═══════════════════════════════════════════════════════════════════════════
# Main Content Area
# ═══════════════════════════════════════════════════════════════════════════

# Title
st.title(f"{PAGE_ICON} {PAGE_TITLE}")

# Route to selected page
if page == "📄 Papers":
    render_paper_manager()

elif page == "🧬 Variants":
    render_variant_manager()

elif page == "⚙️ Run Analysis":
    render_analysis_runner()

elif page == "📊 View Results":
    render_matrix_viewer()
