"""
Matrix Viewer Component
=======================

Interactive Streamlit component for viewing:
    • Paper × Variant binary matrix (heatmap)
    • Variant × Variant intersection matrix (heatmap)
    • Cell drill-down: click a cell to see which papers support that combination
    • Research gap highlighting
    • Manual validation/override of detections
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from typing import List, Optional, Tuple

from config.settings import HEATMAP_COLORSCALE, HEATMAP_ZERO_COLOR
from core.matrix_computation import MatrixComputer


def render_matrix_viewer():
    """Render the interactive matrix viewer."""
    st.header("📊 Matrix Viewer")

    if not st.session_state.get("analysis_complete", False):
        st.info("Run the analysis first to view matrices.")
        return

    computer: MatrixComputer = st.session_state.matrix_computer
    paper_variant_df: pd.DataFrame = st.session_state.paper_variant_df
    intersection_df: pd.DataFrame = st.session_state.intersection_df

    # ── Tabs ─────────────────────────────────────────────────────────
    tab_intersection, tab_paper_variant, tab_gaps, tab_validation = st.tabs([
        "🔗 Intersection Matrix",
        "📋 Paper × Variant Matrix",
        "🕳️ Research Gaps",
        "✏️ Manual Validation",
    ])

    with tab_intersection:
        _render_intersection_matrix(intersection_df, computer)

    with tab_paper_variant:
        _render_paper_variant_matrix(paper_variant_df)

    with tab_gaps:
        _render_research_gaps(computer)

    with tab_validation:
        _render_manual_validation(paper_variant_df, computer)


# ═══════════════════════════════════════════════════════════════════════════
# Intersection Matrix
# ═══════════════════════════════════════════════════════════════════════════

def _render_intersection_matrix(intersection_df: pd.DataFrame, computer: MatrixComputer):
    """Render the Variant × Variant intersection matrix as an interactive heatmap."""
    st.subheader("Variant × Variant Intersection Matrix")
    st.caption(
        "Each cell shows how many papers discuss **both** variants. "
        "Diagonal = total papers for that variant. "
        "Click a cell to see supporting papers."
    )

    # Create heatmap
    fig = _create_intersection_heatmap(intersection_df)
    st.plotly_chart(fig, use_container_width=True, key="intersection_heatmap")

    # ── Cell Drill-Down ──────────────────────────────────────────────
    st.divider()
    st.subheader("🔍 Drill Down into a Pair")

    variant_names = list(intersection_df.columns)
    col1, col2 = st.columns(2)

    with col1:
        va = st.selectbox("Variant A", variant_names, key="drilldown_va")
    with col2:
        vb = st.selectbox("Variant B", variant_names, key="drilldown_vb")

    if va and vb:
        if va == vb:
            papers = computer.get_papers_for_variant(va)
            count = len(papers)
            st.info(f"**{va}** appears in **{count}** paper(s).")
        else:
            papers = computer.get_papers_for_pair(va, vb)
            count = intersection_df.loc[va, vb]
            if count > 0:
                st.success(
                    f"**{count}** paper(s) discuss both **{va}** and **{vb}**:"
                )
            else:
                st.warning(
                    f"🕳️ **Research Gap:** No papers discuss both **{va}** and **{vb}**."
                )

        if papers:
            for paper_id in papers:
                st.markdown(f"- `{paper_id}`")


def _create_intersection_heatmap(df: pd.DataFrame) -> go.Figure:
    """Create a Plotly heatmap for the intersection matrix."""
    labels = list(df.columns)
    values = df.values

    # Custom hover text
    hover_text = []
    for i, row_label in enumerate(labels):
        row_texts = []
        for j, col_label in enumerate(labels):
            val = int(values[i][j])
            if i == j:
                row_texts.append(f"{row_label}: {val} papers total")
            else:
                row_texts.append(f"{row_label} ∩ {col_label}: {val} papers")
        hover_text.append(row_texts)

    fig = go.Figure(data=go.Heatmap(
        z=values,
        x=labels,
        y=labels,
        hovertext=hover_text,
        hoverinfo="text",
        colorscale=HEATMAP_COLORSCALE,
        showscale=True,
        colorbar=dict(title="Count"),
        text=values.astype(int).astype(str),
        texttemplate="%{text}",
        textfont=dict(size=9),
    ))

    fig.update_layout(
        height=max(600, len(labels) * 18),
        xaxis=dict(
            tickangle=45,
            side="bottom",
            tickfont=dict(size=9),
        ),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=9),
        ),
        margin=dict(l=10, r=10, t=30, b=10),
    )

    return fig


# ═══════════════════════════════════════════════════════════════════════════
# Paper × Variant Matrix
# ═══════════════════════════════════════════════════════════════════════════

def _render_paper_variant_matrix(df: pd.DataFrame):
    """Render the Paper × Variant binary matrix."""
    st.subheader("Paper × Variant Binary Matrix")
    st.caption("1 = variant detected in paper, 0 = not detected.")

    # Stats per variant (column sums)
    variant_counts = df.sum(axis=0).sort_values(ascending=False)

    col1, col2 = st.columns([2, 1])

    with col1:
        # Show as interactive heatmap
        fig = go.Figure(data=go.Heatmap(
            z=df.values,
            x=list(df.columns),
            y=list(df.index),
            colorscale=[[0, "#f5f5f5"], [1, "#2196F3"]],
            showscale=False,
            hovertemplate="Paper: %{y}<br>Variant: %{x}<br>Present: %{z}<extra></extra>",
        ))
        fig.update_layout(
            height=max(400, len(df) * 16),
            xaxis=dict(tickangle=45, tickfont=dict(size=8)),
            yaxis=dict(tickfont=dict(size=8), autorange="reversed"),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True, key="paper_variant_heatmap")

    with col2:
        st.markdown("**Variant Detection Counts**")
        for variant_name, count in variant_counts.items():
            pct = count / len(df) * 100 if len(df) > 0 else 0
            st.progress(pct / 100, text=f"{variant_name}: {int(count)} ({pct:.0f}%)")

    # Expandable raw data table
    with st.expander("📊 View Raw Data Table"):
        st.dataframe(df, use_container_width=True, height=400)


# ═══════════════════════════════════════════════════════════════════════════
# Research Gaps
# ═══════════════════════════════════════════════════════════════════════════

def _render_research_gaps(computer: MatrixComputer):
    """Show variant pairs with zero intersection (research gaps)."""
    st.subheader("🕳️ Research Gaps")
    st.caption(
        "These variant pairs have **no** papers that discuss both variants. "
        "They represent potential research opportunities."
    )

    gaps = computer.get_research_gaps()

    if not gaps:
        st.success("🎉 No research gaps found — all variant pairs are covered!")
        return

    st.metric("Total Research Gaps", len(gaps))

    # Filter by variant
    all_gap_variants = sorted(set(v for pair in gaps for v in pair))
    filter_variant = st.selectbox(
        "Filter by variant",
        ["(All)"] + all_gap_variants,
        key="gap_filter",
    )

    filtered_gaps = gaps
    if filter_variant != "(All)":
        filtered_gaps = [
            (a, b) for a, b in gaps
            if a == filter_variant or b == filter_variant
        ]

    st.write(f"Showing {len(filtered_gaps)} gap(s)")

    # Display as a dataframe
    gap_df = pd.DataFrame(filtered_gaps, columns=["Variant A", "Variant B"])
    gap_df.index = range(1, len(gap_df) + 1)
    gap_df.index.name = "#"
    st.dataframe(gap_df, use_container_width=True, height=400)

    # Download gaps
    csv = gap_df.to_csv()
    st.download_button(
        "📥 Download Research Gaps CSV",
        data=csv,
        file_name="research_gaps.csv",
        mime="text/csv",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Manual Validation
# ═══════════════════════════════════════════════════════════════════════════

def _render_manual_validation(df: pd.DataFrame, computer: MatrixComputer):
    """Allow manual override of variant detection results."""
    st.subheader("✏️ Manual Validation")
    st.caption(
        "Override automatic detection results. "
        "Changes will be applied when you re-run the analysis."
    )

    paper_ids = list(df.index)
    variant_names = list(df.columns)

    col1, col2 = st.columns(2)
    with col1:
        selected_paper = st.selectbox("Select Paper", paper_ids, key="val_paper")
    with col2:
        selected_variant = st.selectbox("Select Variant", variant_names, key="val_variant")

    if selected_paper and selected_variant:
        current_value = bool(df.at[selected_paper, selected_variant])
        st.write(f"Current detection: **{'✅ Present' if current_value else '❌ Not present'}**")

        new_value = st.toggle(
            "Variant is present in this paper",
            value=current_value,
            key="val_toggle",
        )

        if new_value != current_value:
            if st.button("💾 Save Override", type="primary"):
                computer.set_override(selected_paper, selected_variant, new_value)
                st.success(
                    f"Override saved: {selected_paper} × {selected_variant} "
                    f"= {'Present' if new_value else 'Absent'}"
                )
                st.info("Re-run the analysis for changes to take effect in the matrices.")

    # Show existing overrides
    st.divider()
    overrides = computer.get_overrides()
    if overrides:
        st.subheader("Current Overrides")
        override_rows = []
        for pid, vars_dict in overrides.items():
            for var_name, val in vars_dict.items():
                override_rows.append({
                    "Paper": pid,
                    "Variant": var_name,
                    "Override Value": "Present" if val else "Absent",
                })
        override_df = pd.DataFrame(override_rows)
        st.dataframe(override_df, use_container_width=True)

        if st.button("🗑️ Clear All Overrides"):
            from config.settings import MANUAL_OVERRIDES_FILE
            from utils.helpers import save_json
            save_json({}, MANUAL_OVERRIDES_FILE)
            st.success("All overrides cleared.")
            st.rerun()
    else:
        st.info("No manual overrides set.")
