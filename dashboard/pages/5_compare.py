"""Compare page — side-by-side comparison between two subjects."""

import streamlit as st
import pandas as pd

from dashboard.subject_selector import get_dashboard_subject_state
from hda.db.query import count_snps, compare_subjects
from hda.analysis.panels import analyze_panel, list_panels


def render():
    st.title("🔀 HDA — Compare Subjects")

    try:
        _, subject_keys, _ = get_dashboard_subject_state()
    except RuntimeError as e:
        st.error(str(e))
        return

    if len(subject_keys) < 2:
        st.info("You need at least 2 subjects to compare. Add another subject to `config.yaml` and import their data.")
        st.markdown("""
        ```yaml
        # In config.yaml, add:
        subjects:
          another_person:
            name: Another Person
            sex: female
            date_of_birth: 1990-01-01
            source_file: dna-another.csv
            ...
        ```
        Then run: `hda import another_person`
        """)
        return

    col1, col2 = st.columns(2)
    with col1:
        subject_a = st.selectbox("Subject A", subject_keys, index=0, key="cmp_a")
    with col2:
        default_b = 1 if len(subject_keys) > 1 else 0
        subject_b = st.selectbox("Subject B", subject_keys, index=default_b, key="cmp_b")

    if subject_a == subject_b:
        st.warning("Select two different subjects to compare.")
        return

    tab1, tab2 = st.tabs(["Panel Comparison", "Raw SNP Differences"])

    # --- Tab 1: Panel comparison ---
    with tab1:
        panels = list_panels()
        panel_id = st.selectbox(
            "Panel",
            [p["id"] for p in panels],
            format_func=lambda x: next(p["name"] for p in panels if p["id"] == x),
            key="cmp_panel",
        )

        try:
            result_a = analyze_panel(panel_id, subject_a)
            result_b = analyze_panel(panel_id, subject_b)
        except FileNotFoundError as e:
            st.error(str(e))
            return

        rows = []
        for ra, rb in zip(result_a["results"], result_b["results"]):
            match = "✅" if ra.get("genotype") == rb.get("genotype") else "❌"
            rows.append({
                "Gene": ra["gene"],
                "Trait": ra["trait"],
                f"{subject_a} GT": ra.get("genotype") or "—",
                f"{subject_a} Effect": (ra.get("effect") or "—").replace("_", " "),
                f"{subject_b} GT": rb.get("genotype") or "—",
                f"{subject_b} Effect": (rb.get("effect") or "—").replace("_", " "),
                "Match": match,
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # --- Tab 2: Raw SNP differences ---
    with tab2:
        chrom_options = ["All"] + [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]
        chromosome = st.selectbox("Chromosome", chrom_options, key="cmp_chrom")
        limit = st.slider("Max results", 10, 500, 100, key="cmp_limit")

        if st.button("Find Differences", key="cmp_diff_btn"):
            try:
                diffs = compare_subjects(
                    subject_a=subject_a,
                    subject_b=subject_b,
                    only_different=True,
                    chromosome=chromosome if chromosome != "All" else None,
                    limit=limit,
                )
            except FileNotFoundError as e:
                st.error(str(e))
                return

            if diffs:
                df = pd.DataFrame(diffs)
                df.columns = ["rsid", "Chromosome", "Position", f"{subject_a}", f"{subject_b}"]
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption(f"Showing {len(diffs)} differences (limit: {limit})")
            else:
                st.info("No differences found with these filters.")


render()
