"""
Variant Manager Component
=========================

Streamlit UI for defining, editing, and managing variants and their synonyms.
Supports:
    • Adding new variants with synonyms
    • Editing existing variants
    • Deleting variants
    • Importing/exporting variant definitions as JSON
    • Searching/filtering the variant list
"""

import json
import streamlit as st
from typing import Any, Dict, List, Optional

from config.settings import VARIANTS_FILE
from utils.helpers import load_json, save_json


def render_variant_manager():
    """Render the Variant Management section of the UI."""
    st.header("🧬 Variant & Synonym Manager")

    # Initialize session state for variants
    if "variants" not in st.session_state:
        st.session_state.variants = _load_variants()

    # ── Tabs ─────────────────────────────────────────────────────────
    tab_manage, tab_add, tab_import = st.tabs([
        "📋 Manage Variants",
        "➕ Add Variant",
        "📥 Import / Export",
    ])

    with tab_manage:
        _render_variant_list()

    with tab_add:
        _render_add_variant_form()

    with tab_import:
        _render_import_export()


def _render_variant_list():
    """Render the filterable list of existing variants."""
    variants = st.session_state.variants

    if not variants:
        st.info("No variants defined yet. Use the 'Add Variant' tab to create them.")
        return

    # Summary
    col1, col2 = st.columns(2)
    col1.metric("Total Variants", len(variants))
    total_synonyms = sum(len(v.get("synonyms", [])) for v in variants)
    col2.metric("Total Synonyms", total_synonyms)

    # Search filter
    search = st.text_input(
        "🔍 Search variants",
        placeholder="Type to filter variants...",
        key="variant_search",
    )

    # Filter variants
    filtered = variants
    if search:
        search_lower = search.lower()
        filtered = [
            v for v in variants
            if search_lower in v["name"].lower()
            or any(search_lower in s.lower() for s in v.get("synonyms", []))
        ]

    st.write(f"Showing {len(filtered)} of {len(variants)} variants")
    st.divider()

    # Render each variant
    for idx, variant in enumerate(filtered):
        _render_variant_card(variant, idx)


def _render_variant_card(variant: Dict[str, Any], idx: int):
    """Render a single variant card with edit/delete capabilities."""
    name = variant["name"]
    synonyms = variant.get("synonyms", [])
    edit_key = f"editing_{name}"

    # Check if in edit mode
    if st.session_state.get(edit_key, False):
        _render_edit_form(variant, idx)
        return

    with st.container():
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            st.markdown(f"**{name}**")
            if synonyms:
                synonym_tags = ", ".join(f"`{s}`" for s in synonyms)
                st.caption(f"Synonyms: {synonym_tags}")
            else:
                st.caption("_No synonyms defined_")
        with col2:
            if st.button("✏️", key=f"edit_{name}_{idx}", help="Edit variant"):
                st.session_state[edit_key] = True
                st.rerun()
        with col3:
            if st.button("🗑️", key=f"del_{name}_{idx}", help="Delete variant"):
                st.session_state.variants = [
                    v for v in st.session_state.variants if v["name"] != name
                ]
                _save_variants()
                st.rerun()
        st.divider()


def _render_edit_form(variant: Dict[str, Any], idx: int):
    """Render inline edit form for a variant."""
    name = variant["name"]
    edit_key = f"editing_{name}"
    synonyms = variant.get("synonyms", [])

    with st.container():
        st.markdown(f"**Editing: {name}**")
        new_name = st.text_input(
            "Variant Name",
            value=name,
            key=f"edit_name_{name}_{idx}",
        )
        new_synonyms = st.text_area(
            "Synonyms (one per line)",
            value="\n".join(synonyms),
            key=f"edit_syns_{name}_{idx}",
            height=100,
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save", key=f"save_{name}_{idx}"):
                parsed_synonyms = [
                    s.strip() for s in new_synonyms.split("\n") if s.strip()
                ]
                # Update variant
                for v in st.session_state.variants:
                    if v["name"] == name:
                        v["name"] = new_name.strip()
                        v["synonyms"] = parsed_synonyms
                        break
                _save_variants()
                st.session_state[edit_key] = False
                st.rerun()
        with col2:
            if st.button("❌ Cancel", key=f"cancel_{name}_{idx}"):
                st.session_state[edit_key] = False
                st.rerun()
        st.divider()


def _render_add_variant_form():
    """Render the form for adding a new variant."""
    with st.form("add_variant_form", clear_on_submit=True):
        st.subheader("Add New Variant")

        name = st.text_input(
            "Variant Name *",
            placeholder="e.g., BRCA1",
            help="The primary name for this variant.",
        )
        synonyms_text = st.text_area(
            "Synonyms (one per line)",
            placeholder="e.g.,\nBReast CAncer gene 1\nBRCA1 gene\nFANCO",
            help="Enter synonyms that should also be detected as this variant.",
            height=150,
        )

        submitted = st.form_submit_button("➕ Add Variant", type="primary")

        if submitted:
            if not name or not name.strip():
                st.error("Variant name is required.")
                return

            clean_name = name.strip()

            # Check for duplicates
            existing_names = {v["name"].lower() for v in st.session_state.variants}
            if clean_name.lower() in existing_names:
                st.error(f"A variant named '{clean_name}' already exists.")
                return

            synonyms = [s.strip() for s in synonyms_text.split("\n") if s.strip()]

            new_variant = {
                "name": clean_name,
                "synonyms": synonyms,
            }
            st.session_state.variants.append(new_variant)
            _save_variants()
            st.success(f"✅ Added variant '{clean_name}' with {len(synonyms)} synonym(s).")


def _render_import_export():
    """Render import/export functionality."""
    st.subheader("Export Variants")
    if st.session_state.variants:
        export_data = json.dumps(
            {"variants": st.session_state.variants},
            indent=2,
            ensure_ascii=False,
        )
        st.download_button(
            label="📥 Download variants.json",
            data=export_data,
            file_name="variants.json",
            mime="application/json",
        )

        # Preview
        with st.expander("Preview JSON"):
            st.json({"variants": st.session_state.variants})
    else:
        st.info("No variants to export.")

    st.divider()

    st.subheader("Import Variants")
    uploaded = st.file_uploader(
        "Upload a variants JSON file",
        type=["json"],
        key="variant_import",
        help='Expected format: {"variants": [{"name": "...", "synonyms": ["...", ...]}, ...]}',
    )

    if uploaded:
        try:
            data = json.loads(uploaded.read().decode("utf-8"))
            if isinstance(data, list):
                imported_variants = data
            elif isinstance(data, dict) and "variants" in data:
                imported_variants = data["variants"]
            else:
                st.error("Invalid format. Expected a list or {'variants': [...]}.")
                return

            # Validate structure
            for v in imported_variants:
                if "name" not in v:
                    st.error("Each variant must have a 'name' field.")
                    return
                if "synonyms" not in v:
                    v["synonyms"] = []

            import_mode = st.radio(
                "Import mode",
                ["Replace all", "Merge (add new, keep existing)"],
                key="import_mode",
            )

            if st.button("📥 Import", type="primary"):
                if import_mode == "Replace all":
                    st.session_state.variants = imported_variants
                else:
                    existing_names = {v["name"].lower() for v in st.session_state.variants}
                    new_variants = [
                        v for v in imported_variants
                        if v["name"].lower() not in existing_names
                    ]
                    st.session_state.variants.extend(new_variants)
                    st.info(f"Added {len(new_variants)} new variant(s). "
                            f"Skipped {len(imported_variants) - len(new_variants)} duplicate(s).")

                _save_variants()
                st.success(f"✅ Imported {len(imported_variants)} variant(s).")
                st.rerun()

        except json.JSONDecodeError:
            st.error("Invalid JSON file.")


def _load_variants() -> List[Dict[str, Any]]:
    """Load variants from disk."""
    try:
        data = load_json(VARIANTS_FILE)
        if isinstance(data, list):
            return data
        return data.get("variants", [])
    except FileNotFoundError:
        return []


def _save_variants():
    """Save current variants to disk."""
    save_json({"variants": st.session_state.variants}, VARIANTS_FILE)


def get_variant_count() -> int:
    """Return the number of defined variants."""
    try:
        data = load_json(VARIANTS_FILE)
        if isinstance(data, list):
            return len(data)
        return len(data.get("variants", []))
    except FileNotFoundError:
        return 0
