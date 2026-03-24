"""HDA — Holistic DNA Analyzer Dashboard."""

import streamlit as st

st.set_page_config(
    page_title="HDA — Holistic DNA Analyzer",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Navigation
pages = {
    "Profile & Overview": "pages/1_profile.py",
    "Panel Reports": "pages/2_panels.py",
    "Notable Findings": "pages/3_findings.py",
    "SNP Explorer": "pages/4_explorer.py",
    "Compare": "pages/5_compare.py",
}

pg = st.navigation([
    st.Page("pages/1_profile.py", title="Profile & Overview", icon="👤"),
    st.Page("pages/2_panels.py", title="Panel Reports", icon="📋"),
    st.Page("pages/3_findings.py", title="Notable Findings", icon="⚠️"),
    st.Page("pages/4_explorer.py", title="SNP Explorer", icon="🔍"),
    st.Page("pages/5_compare.py", title="Compare", icon="🔀"),
])

pg.run()
