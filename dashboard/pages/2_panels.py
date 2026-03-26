"""Panel Reports page."""

import streamlit as st
import pandas as pd

from hda.config import get_active_subject, list_subjects
from hda.analysis.panels import list_panels, analyze_panel


def effect_color(effect: str) -> str:
    if not effect:
        return "gray"
    if effect in ("normal", "lower_risk", "no_e4", "no_e2", "lactose_tolerant"):
        return "green"
    if "significantly" in effect or "higher" in effect or "poor" in effect or "at_risk" in effect:
        return "red"
    return "orange"


def effect_emoji(effect: str) -> str:
    color = effect_color(effect)
    return {"green": "🟢", "orange": "🟡", "red": "🔴", "gray": "⚪"}.get(color, "⚪")


def render():
    st.title("📋 HDA — Panel Reports")

    subjects = list_subjects()
    active = get_active_subject()
    subject_keys = list(subjects.keys())

    selected = st.sidebar.selectbox(
        "Subject",
        subject_keys,
        index=subject_keys.index(active) if active in subject_keys else 0,
        key="panel_subject",
    )

    panels = list_panels()
    panel_names = {p["id"]: p["name"] for p in panels}

    panel_id = st.selectbox(
        "Select Panel",
        [p["id"] for p in panels],
        format_func=lambda x: f"{panel_names[x]} ({x})",
    )

    if not panel_id:
        return

    try:
        result = analyze_panel(panel_id, selected)
    except FileNotFoundError as e:
        st.error(str(e))
        return

    st.markdown(f"**{result['panel_name']}** — {result['description']}")
    st.caption(f"{result['found_in_genome']}/{result['total_variants']} variants found in genome")

    for r in result["results"]:
        if not r["found"]:
            with st.expander(f"⚪ **{r['gene']}** — {r['trait']} *(not in chip)*", expanded=False):
                st.caption(f"{r['rsid']} — not available on this genotyping chip")
        else:
            emoji = effect_emoji(r.get("effect", ""))
            effect_label = (r.get("effect") or "unknown").replace("_", " ")
            with st.expander(
                f"{emoji} **{r['gene']}** — {r['trait']}  |  `{r['genotype']}`  |  {effect_label}",
                expanded=(effect_color(r.get("effect", "")) == "red"),
            ):
                st.markdown(f"**rsid:** `{r['rsid']}`  **Genotype:** `{r['genotype']}`  **Effect:** {effect_label}")
                if r.get("description"):
                    st.info(r["description"])


render()
