"""Notable Findings page."""

import streamlit as st
import pandas as pd

from hda.config import get_active_subject, list_subjects
from hda.analysis.panels import get_risk_summary


ACTIONABLE_ADVICE = {
    "MTHFR": "Consider methylfolate (5-MTHF) supplementation. Check homocysteine levels with your doctor.",
    "MCM6/LCT": "Reduce dairy or use lactase enzyme supplements. Consider calcium from non-dairy sources.",
    "FTO": "Regular exercise is especially effective for you. Focus on consistent activity rather than diet alone.",
    "CYP1A2": "Fast caffeine metabolizer — coffee is well-tolerated and may be cardioprotective for you.",
    "GSTP1": "Increase cruciferous vegetables (broccoli, kale, cabbage) to support detoxification pathways.",
    "TCF7L2": "Low-glycemic diet is particularly beneficial. Monitor blood sugar periodically.",
    "DRD2/ANKK1": "Structured reward systems help with motivation. Be mindful of addictive behavior patterns.",
    "COMT": "Balanced dopamine — you handle stress reasonably well. Mindfulness practices complement your profile.",
    "IL6": "Anti-inflammatory diet helps (omega-3, turmeric, berries). Allow longer recovery between intense workouts.",
    "HFE": "Monitor ferritin and iron levels regularly. Avoid iron-fortified foods if levels are high.",
    "SCN5A": "Inform your cardiologist about this variant before taking antiarrhythmic medications.",
    "9p21 region": "Standard cardiovascular prevention: exercise, healthy diet, avoid smoking, monitor BP and lipids.",
    "HERC2/OCA2": "Higher UV sensitivity possible with lighter eye color. Use UV-protective sunglasses.",
    "ACTN3": "Your muscle fiber profile suggests optimal training type. Tailor exercise to your genetic strength.",
}


def render():
    st.title("⚠️ HDA — Notable Findings")

    subjects = list_subjects()
    active = get_active_subject()
    subject_keys = list(subjects.keys())

    selected = st.sidebar.selectbox(
        "Subject",
        subject_keys,
        index=subject_keys.index(active) if active in subject_keys else 0,
        key="findings_subject",
    )

    try:
        findings = get_risk_summary(selected)
    except FileNotFoundError:
        st.error(f"Database not found for '{selected}'. Run `hda import {selected}` first.")
        return

    if not findings:
        st.success("No notable findings across all panels! All variants within normal range.")
        return

    st.markdown(f"**{len(findings)} variants** with non-normal effects found across all panels.")

    # Group by category
    by_panel = {}
    for f in findings:
        panel = f["panel"]
        by_panel.setdefault(panel, []).append(f)

    for panel, variants in by_panel.items():
        st.subheader(panel)

        for v in variants:
            effect = v.get("effect", "")
            if "significantly" in effect or "higher" in effect or "poor" in effect or "at_risk" in effect:
                emoji = "🔴"
            else:
                emoji = "🟡"

            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"{emoji} **{v['gene']}** — {v['trait']}")
                st.caption(v.get("description", ""))
            with col2:
                st.code(f"{v['rsid']}  {v['genotype']}")

            # Actionable advice
            advice = ACTIONABLE_ADVICE.get(v["gene"])
            if advice:
                st.markdown(f"> 💡 **Suggestion:** {advice}")

            st.divider()

    st.caption("⚕️ This is for personal exploration only. Consult a healthcare professional for medical decisions.")


render()
