"""Profile & Overview page."""

import streamlit as st
import plotly.express as px
import pandas as pd

from dna.config import get_active_subject, get_subject_profile, list_subjects
from dna.db.query import count_snps, chromosome_summary
from dna.analysis.panels import get_risk_summary


def render():
    st.title("👤 Profile & Overview")

    # Subject selector
    subjects = list_subjects()
    active = get_active_subject()
    subject_keys = list(subjects.keys())

    selected = st.sidebar.selectbox(
        "Subject",
        subject_keys,
        index=subject_keys.index(active) if active in subject_keys else 0,
        key="profile_subject",
    )

    profile = get_subject_profile(selected)

    # Profile card
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader(f"{profile.get('name', '')} {profile.get('surname', '')}")
        st.markdown(f"""
        | | |
        |---|---|
        | **Sex** | {profile.get('sex', 'N/A')} |
        | **Date of Birth** | {profile.get('date_of_birth', 'N/A')} |
        | **Chip** | {profile.get('chip', 'N/A')} |
        | **Reference** | {profile.get('reference', 'N/A')} |
        | **Source** | {profile.get('source_format', 'N/A')} |
        """)

    with col2:
        try:
            total = count_snps(selected)
            st.metric("Total SNPs", f"{total:,}")
        except FileNotFoundError:
            st.warning(f"Database not found for '{selected}'. Run `dna import {selected}` first.")
            return

    # Quick badges from notable findings
    st.divider()
    st.subheader("Quick Profile")

    try:
        findings = get_risk_summary(selected)
        if findings:
            badge_cols = st.columns(4)
            for i, f in enumerate(findings[:12]):
                with badge_cols[i % 4]:
                    effect = f.get("effect", "")
                    if "significantly" in effect or "higher" in effect or "poor" in effect or "at_risk" in effect:
                        color = "🔴"
                    elif effect in ("normal", "lower_risk"):
                        color = "🟢"
                    else:
                        color = "🟡"
                    st.markdown(f"{color} **{f['gene']}** — {f['trait'].split('—')[0].strip()}")
                    st.caption(f"{f['genotype']}: {f['effect'].replace('_', ' ')}")
        else:
            st.success("No notable findings across all panels.")
    except FileNotFoundError:
        st.info("Import data to see quick profile badges.")

    # Chromosome chart
    st.divider()
    st.subheader("SNPs per Chromosome")

    try:
        summary = chromosome_summary(selected)
        df = pd.DataFrame(summary)

        # Sort chromosomes naturally
        chrom_order = [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]
        df["chromosome"] = pd.Categorical(df["chromosome"], categories=chrom_order, ordered=True)
        df = df.sort_values("chromosome")

        fig = px.bar(
            df,
            x="chromosome",
            y="count",
            labels={"chromosome": "Chromosome", "count": "SNPs"},
            color="count",
            color_continuous_scale="Viridis",
        )
        fig.update_layout(showlegend=False, coloraxis_showscale=False, height=400)
        st.plotly_chart(fig, use_container_width=True)
    except FileNotFoundError:
        pass


render()
