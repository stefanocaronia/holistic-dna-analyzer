"""SNP Explorer page."""

import asyncio

import streamlit as st
import pandas as pd

from dna.config import get_active_subject, list_subjects
from dna.db.query import get_snp, search_snps, count_snps


def render():
    st.title("🔍 SNP Explorer")

    subjects = list_subjects()
    active = get_active_subject()
    subject_keys = list(subjects.keys())

    selected = st.sidebar.selectbox(
        "Subject",
        subject_keys,
        index=subject_keys.index(active) if active in subject_keys else 0,
        key="explorer_subject",
    )

    tab1, tab2 = st.tabs(["Search by rsid", "Browse by Region"])

    # --- Tab 1: rsid lookup ---
    with tab1:
        rsid_input = st.text_input("Enter rsid (e.g. rs1801133)", key="rsid_input")

        if rsid_input:
            rsid = rsid_input.strip().lower()
            if not rsid.startswith("rs"):
                rsid = f"rs{rsid}"

            snp = get_snp(rsid, selected)

            if snp is None:
                st.warning(f"{rsid} not found in {selected}'s genome.")
            else:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("rsid", snp["rsid"])
                col2.metric("Chromosome", snp["chromosome"])
                col3.metric("Position", f"{snp['position']:,}")
                col4.metric("Genotype", snp["genotype"])

                # Online annotation
                st.divider()
                if st.button("🌐 Fetch Online Annotations", key="annotate_btn"):
                    from dna.api.annotator import annotate_snp

                    with st.spinner("Querying SNPedia, ClinVar, Ensembl..."):
                        result = asyncio.run(annotate_snp(rsid, selected))

                    if result.get("sources"):
                        st.subheader("Annotations")

                        for field in ("gene", "clinical_significance", "condition", "summary",
                                      "risk_allele", "population_frequency"):
                            value = result.get(field)
                            if value:
                                label = field.replace("_", " ").title()
                                st.markdown(f"**{label}:** {value}")

                        st.caption(f"Sources: {', '.join(result.get('sources', []))}")

                        # Show raw details in expander
                        with st.expander("Raw annotation data"):
                            st.json(result.get("details", {}))
                    else:
                        st.info(f"No annotations found online for {rsid}.")

    # --- Tab 2: Browse ---
    with tab2:
        col1, col2, col3 = st.columns(3)

        with col1:
            chrom_options = [""] + [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]
            chromosome = st.selectbox("Chromosome", chrom_options, key="browse_chrom")

        with col2:
            pos_start = st.number_input("Position from", min_value=0, value=0, step=100000, key="pos_start")

        with col3:
            pos_end = st.number_input("Position to", min_value=0, value=0, step=100000, key="pos_end")

        col4, col5 = st.columns(2)
        with col4:
            genotype_filter = st.text_input("Genotype filter (e.g. AA, CT)", key="gt_filter")
        with col5:
            rsid_pattern = st.text_input("rsid pattern (SQL LIKE, e.g. rs180%)", key="rsid_pattern")

        limit = st.slider("Max results", 10, 500, 100, key="browse_limit")

        if st.button("Search", key="browse_btn"):
            results = search_snps(
                chromosome=chromosome or None,
                position_start=pos_start or None,
                position_end=pos_end or None,
                genotype=genotype_filter or None,
                rsid_pattern=rsid_pattern or None,
                subject=selected,
                limit=limit,
            )

            if results:
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption(f"Showing {len(results)} results (limit: {limit})")
            else:
                st.info("No results matching your filters.")


render()
