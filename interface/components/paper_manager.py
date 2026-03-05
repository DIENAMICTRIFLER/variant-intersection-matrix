"""
Paper Manager Component
=======================

Streamlit UI component for uploading and managing research papers.
Handles PDF upload, validation, listing, and deletion.
"""

import os
import shutil
import streamlit as st
from pathlib import Path
from typing import List

from config.settings import PAPERS_DIR, MAX_UPLOAD_SIZE_MB
from utils.helpers import format_file_size, get_paper_id


def render_paper_manager():
    """Render the Paper Management section of the UI."""
    st.header("📄 Paper Management")

    # ── Upload Section ───────────────────────────────────────────────
    st.subheader("Upload Papers")
    uploaded_files = st.file_uploader(
        "Upload PDF research papers",
        type=["pdf"],
        accept_multiple_files=True,
        help=f"Maximum {MAX_UPLOAD_SIZE_MB} MB per file. Select multiple files at once.",
        key="paper_uploader",
    )

    if uploaded_files:
        _handle_uploads(uploaded_files)

    st.divider()

    # ── Paper Library ────────────────────────────────────────────────
    st.subheader("Paper Library")
    papers = _list_papers()

    if not papers:
        st.info("No papers uploaded yet. Upload PDF files above to get started.")
        return

    # Summary stats
    total_size = sum(p.stat().st_size for p in papers)
    col1, col2 = st.columns(2)
    col1.metric("Total Papers", len(papers))
    col2.metric("Total Size", format_file_size(total_size))

    # Paper list with delete option
    st.write("")
    for paper_path in papers:
        _render_paper_row(paper_path)

    # Bulk actions
    st.divider()
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🗑️ Delete All Papers", type="secondary"):
            st.session_state["confirm_delete_all"] = True

    if st.session_state.get("confirm_delete_all", False):
        st.warning("This will delete ALL uploaded papers. Are you sure?")
        c1, c2, c3 = st.columns([1, 1, 4])
        with c1:
            if st.button("Yes, delete all"):
                _delete_all_papers()
                st.session_state["confirm_delete_all"] = False
                st.rerun()
        with c2:
            if st.button("Cancel"):
                st.session_state["confirm_delete_all"] = False
                st.rerun()


def _handle_uploads(uploaded_files) -> None:
    """Process uploaded PDF files and save to papers directory."""
    saved_count = 0
    skipped_count = 0

    for uploaded_file in uploaded_files:
        dest_path = PAPERS_DIR / uploaded_file.name

        if dest_path.exists():
            skipped_count += 1
            continue

        with open(dest_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_count += 1

    if saved_count > 0:
        st.success(f"✅ Uploaded {saved_count} paper(s) successfully.")
    if skipped_count > 0:
        st.info(f"ℹ️ Skipped {skipped_count} paper(s) — already exist.")


def _list_papers() -> List[Path]:
    """Return sorted list of PDF files in papers directory."""
    return sorted(PAPERS_DIR.glob("*.pdf"))


def _render_paper_row(paper_path: Path) -> None:
    """Render a single paper row with metadata and delete button."""
    paper_id = get_paper_id(paper_path.name)
    file_size = format_file_size(paper_path.stat().st_size)

    col1, col2, col3 = st.columns([5, 2, 1])
    with col1:
        st.text(f"📑 {paper_path.name}")
    with col2:
        st.text(file_size)
    with col3:
        if st.button("🗑️", key=f"del_{paper_id}", help=f"Delete {paper_path.name}"):
            paper_path.unlink()
            st.rerun()


def _delete_all_papers() -> None:
    """Delete all PDF files from papers directory."""
    for pdf_file in PAPERS_DIR.glob("*.pdf"):
        pdf_file.unlink()
    st.success("All papers deleted.")


def get_paper_count() -> int:
    """Return the number of uploaded papers."""
    return len(list(PAPERS_DIR.glob("*.pdf")))
