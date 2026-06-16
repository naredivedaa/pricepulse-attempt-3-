"""
utils/styles.py
──────────────────────────────────────────────────────────────────────
Global CSS injector for the dark PricePulse theme.
Called once in app.py via inject_global_styles().
"""

import streamlit as st


GLOBAL_CSS = """
<style>
/* ── Base ──────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #13151f !important;
    border-right: 1px solid #2d3144;
}
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] p {
    color: #ccc !important;
}

/* ── Buttons ────────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #4ECDC4, #2196F3);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.5rem 1.4rem;
    transition: opacity 0.2s;
}
.stButton > button:hover {
    opacity: 0.88;
}

/* ── Inputs ─────────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stSelectbox > div > div > div,
.stNumberInput > div > div > input {
    background: #1e2130 !important;
    color: #fff !important;
    border: 1px solid #2d3144 !important;
    border-radius: 8px !important;
}

/* ── Metric widget ──────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #1e2130;
    border-radius: 10px;
    padding: 1rem;
    border: 1px solid #2d3144;
}
[data-testid="metric-container"] label {
    color: #aaa !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #4ECDC4 !important;
    font-weight: 700;
}

/* ── Dataframe ──────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* ── Tabs ───────────────────────────────────────────────────────────── */
.stTabs [role="tab"] {
    color: #aaa;
    font-weight: 600;
}
.stTabs [role="tab"][aria-selected="true"] {
    color: #4ECDC4;
    border-bottom: 2px solid #4ECDC4;
}

/* ── Expander ───────────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: #1e2130 !important;
    border-radius: 8px !important;
    color: #fff !important;
    font-weight: 600 !important;
}
.streamlit-expanderContent {
    background: #161923 !important;
    border: 1px solid #2d3144 !important;
    border-radius: 0 0 8px 8px !important;
}

/* ── Alert boxes ────────────────────────────────────────────────────── */
.stAlert {
    border-radius: 10px !important;
}

/* ── Scrollbar ──────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f1117; }
::-webkit-scrollbar-thumb { background: #2d3144; border-radius: 3px; }

/* ── Logo / brand ───────────────────────────────────────────────────── */
.pp-logo {
    font-size: 1.6rem;
    font-weight: 800;
    background: linear-gradient(135deg, #4ECDC4, #2196F3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
}

/* ── Section divider ─────────────────────────────────────────────────── */
.pp-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, #2d3144, transparent);
    margin: 1.5rem 0;
}

/* ── Responsive: hide sidebar toggle on mobile ───────────────────────── */
@media (max-width: 640px) {
    [data-testid="stSidebar"] { width: 100% !important; }
}
</style>
"""


def inject_global_styles() -> None:
    """Inject global CSS into the Streamlit app. Call once in app.py."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
