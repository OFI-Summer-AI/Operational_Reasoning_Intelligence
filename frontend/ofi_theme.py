"""OFI company Streamlit theme — light mode: gold, black, white, yellow."""
from __future__ import annotations

import html as html_lib

import streamlit as st

OFI_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

/* Force light app shell */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {
  background-color: #F7F5F0 !important;
  color: #1A1A1A !important;
  font-family: 'DM Sans', 'Segoe UI', sans-serif !important;
}
[data-testid="stSidebar"] {
  background: #FFFFFF !important;
  border-right: 3px solid #C9A227 !important;
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  color: #1A1A1A !important;
}
h1, h2, h3, h4 { color: #1A1A1A !important; font-weight: 700 !important; }
p, li, span, label { color: #2D2D2D !important; }

.ofi-header {
  background: linear-gradient(135deg, #FFFFFF 0%, #FFF9E6 50%, #FFFFFF 100%);
  border: 2px solid #C9A227;
  border-radius: 12px;
  padding: 1.5rem 2rem;
  margin-bottom: 1.25rem;
  box-shadow: 0 2px 12px rgba(201, 162, 39, 0.15);
}
.ofi-header h1 {
  margin: 0;
  color: #1A1A1A !important;
  font-size: 1.85rem;
  border-bottom: 3px solid #C9A227;
  padding-bottom: 0.5rem;
  display: inline-block;
}
.ofi-header .ofi-tagline {
  margin: 0.75rem 0 0;
  color: #444 !important;
  font-size: 1rem;
}

.ofi-input-panel {
  background: #FFFFFF;
  border: 1px solid #E8D9A0;
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.ofi-input-panel h3 {
  color: #1A1A1A !important;
  border-left: 4px solid #C9A227;
  padding-left: 0.75rem;
  margin-top: 0 !important;
}

.ofi-card {
  background: #FFFFFF;
  border: 1px solid #E0E0E0;
  border-left: 4px solid #C9A227;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin: 0.75rem 0;
  color: #1A1A1A !important;
}
.ofi-rca-root {
  font-size: 1.05rem;
  line-height: 1.5;
  color: #1A1A1A !important;
}

.ofi-patch-green {
  background: #E8F5E9;
  border: 2px solid #2E7D32;
  border-radius: 10px;
  padding: 1.25rem;
  margin: 1rem 0;
  color: #1B5E20 !important;
}
.ofi-patch-green h3, .ofi-patch-green p { color: #1B5E20 !important; }

.ofi-patch-red {
  background: #FFEBEE;
  border: 2px solid #C62828;
  border-radius: 10px;
  padding: 1.25rem;
  margin: 1rem 0;
  color: #B71C1C !important;
}
.ofi-patch-red h3, .ofi-patch-red p { color: #B71C1C !important; }

.ofi-patch-amber {
  background: #FFF8E1;
  border: 2px solid #F9A825;
  border-radius: 10px;
  padding: 1rem;
  margin: 0.75rem 0;
  color: #5D4037 !important;
}

.ofi-section-title {
  color: #1A1A1A !important;
  font-size: 1.15rem;
  font-weight: 700;
  margin: 1.25rem 0 0.5rem;
  padding-bottom: 0.35rem;
  border-bottom: 2px solid #FFD54F;
}

/* Streamlit widgets — light */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
  background-color: #FFFFFF !important;
  color: #1A1A1A !important;
  border: 1px solid #C9A227 !important;
}
div[data-testid="stSelectbox"] > div > div {
  background-color: #FFFFFF !important;
  color: #1A1A1A !important;
}
div[data-testid="stMetric"] {
  background: #FFFFFF !important;
  border: 1px solid #E8D9A0 !important;
  border-radius: 8px !important;
  padding: 0.75rem !important;
}
div[data-testid="stMetric"] label { color: #666 !important; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: #1A1A1A !important;
}
.stButton > button[kind="primary"] {
  background: linear-gradient(90deg, #C9A227, #E8C547) !important;
  color: #1A1A1A !important;
  font-weight: 700 !important;
  border: 2px solid #1A1A1A !important;
  border-radius: 8px !important;
}
.stButton > button[kind="primary"]:hover {
  background: linear-gradient(90deg, #E8C547, #FFD54F) !important;
}
[data-testid="stExpander"] {
  background: #FFFFFF !important;
  border: 1px solid #E0E0E0 !important;
}
div[data-testid="stDataFrame"] {
  border: 1px solid #E8D9A0 !important;
  border-radius: 8px !important;
}
[data-testid="stAlert"] {
  border-radius: 10px !important;
}
.ofi-results-banner {
  font-size: 1.25rem;
  font-weight: 700;
  color: #1A1A1A;
  margin: 1.5rem 0 0.75rem;
  padding-bottom: 0.35rem;
  border-bottom: 3px solid #C9A227;
}
.ofi-sidebar-info {
  background: #FFF9E6;
  border: 1px solid #E8D9A0;
  border-left: 4px solid #C9A227;
  border-radius: 8px;
  padding: 0.85rem 1rem;
  margin: 0.5rem 0 1rem;
  font-size: 0.88rem;
  line-height: 1.45;
  color: #333 !important;
}
.ofi-sidebar-info p {
  margin: 0.35rem 0 !important;
  color: #333 !important;
}
.ofi-sidebar-info strong {
  color: #1A1A1A !important;
}
</style>
"""


def apply_ofi_theme() -> None:
    st.markdown(OFI_CSS, unsafe_allow_html=True)


def ofi_header(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="ofi-header">'
        f"<h1>{html_lib.escape(title)}</h1>"
        f'<p class="ofi-tagline">{html_lib.escape(subtitle)}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )


def patch_green(html: str) -> None:
    st.markdown(f'<div class="ofi-patch-green">{html}</div>', unsafe_allow_html=True)


def patch_red(html: str) -> None:
    st.markdown(f'<div class="ofi-patch-red">{html}</div>', unsafe_allow_html=True)


def patch_amber(html: str) -> None:
    st.markdown(f'<div class="ofi-patch-amber">{html}</div>', unsafe_allow_html=True)


def section_title(text: str) -> None:
    st.markdown(f'<div class="ofi-section-title">{html_lib.escape(text)}</div>', unsafe_allow_html=True)


def results_banner() -> None:
    st.markdown('<div class="ofi-results-banner">Analysis results</div>', unsafe_allow_html=True)


def display_text(text: str) -> str:
    """Normalize unicode dashes and repair mojibake for UI display."""
    from layers.ingestion.text_utils import normalize_unicode_text

    return normalize_unicode_text(text)
