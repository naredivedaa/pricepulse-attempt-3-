"""
app.py  –  PricePulse Entry Point
──────────────────────────────────────────────────────────────────────
Main Streamlit application file.

Launch command:
    streamlit run app.py

Architecture:
    app.py            → entry point, sidebar, session init
    pages/            → multipage Streamlit pages
    modules/          → business logic (comparison, basket, search, recommendations, alerts)
    utils/            → formatting, charts, auth, styles
    database/         → SQLite manager, schema, seed data
"""

import os
import sys
import logging

# ── Ensure project root is on sys.path for relative imports ──────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st

# Configure logging before any module imports that use the logger
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── Database init (must happen before any module that queries DB) ─────
from database.db_manager import initialise_db
from database.seed_data  import run_all as seed_db

@st.cache_resource(show_spinner=False)
def _init_database():
    """Initialise and seed the database exactly once per process."""
    try:
        initialise_db()
        seed_db()
        logger.info("Database ready.")
    except Exception as exc:
        logger.error("Database initialisation failed: %s", exc, exc_info=True)
        st.error(f"Database error: {exc}")

_init_database()

# ── Streamlit page config ─────────────────────────────────────────────
st.set_page_config(
    page_title     = "PricePulse – Grocery Price Comparator",
    page_icon      = "💰",
    layout         = "wide",
    initial_sidebar_state = "expanded",
    menu_items     = {
        "Get Help":    "https://github.com/pricepulse",
        "Report a bug":"https://github.com/pricepulse/issues",
        "About":       "## PricePulse\nCompare grocery prices across Zepto, Blinkit, Swiggy Instamart & BigBasket.",
    },
)

# ── Global styles ─────────────────────────────────────────────────────
from utils.styles import inject_global_styles
inject_global_styles()

# ── Auth session ──────────────────────────────────────────────────────
from utils.auth import init_session, is_logged_in, login, logout, register, current_username
init_session()

# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    # Brand logo
    st.markdown(
        '<div class="pp-logo" style="font-size:1.8rem;margin-bottom:0.3rem;">💰 PricePulse</div>',
        unsafe_allow_html=True,
    )
    st.caption("Compare grocery prices · Save every rupee")
    st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

    # Navigation info
    st.markdown("### 📌 Navigation")
    st.markdown(
        """
- 🔍 **Search** — Find & compare products
- 🛒 **Basket** — Optimise your cart
- 📊 **Dashboard** — Price analytics
- 🔔 **Alerts** — Price drop alerts
- 🤖 **AI Assistant** — Smart recommendations
"""
    )
    st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

    # ── Auth section ────────────────────────────────────────────────
    if is_logged_in():
        username = current_username()
        st.markdown(f"### 👤 {username}")
        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()
    else:
        auth_tab = st.radio("Account", ["Login", "Register"], horizontal=True)

        if auth_tab == "Login":
            with st.form("login_form"):
                ue  = st.text_input("Username or Email")
                pwd = st.text_input("Password", type="password")
                sub = st.form_submit_button("Login", use_container_width=True)
                if sub:
                    ok, msg = login(ue, pwd)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            st.caption("Demo: username=**demo** · password=**Demo@1234**")

        else:  # Register
            with st.form("register_form"):
                ru   = st.text_input("Username")
                re_  = st.text_input("Email")
                rpwd = st.text_input("Password", type="password")
                rcty = st.text_input("City (optional)")
                rsub = st.form_submit_button("Create Account", use_container_width=True)
                if rsub:
                    ok, msg = register(ru, re_, rpwd, rcty)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

    # Platform legend
    st.markdown("### 🏪 Platforms")
    st.markdown(
        """
<div style="display:flex;flex-direction:column;gap:6px;">
  <span style="background:#9B59B6;color:#fff;padding:3px 10px;border-radius:12px;font-size:0.78rem;">⚡ Zepto</span>
  <span style="background:#F39C12;color:#fff;padding:3px 10px;border-radius:12px;font-size:0.78rem;">🛒 Blinkit</span>
  <span style="background:#E74C3C;color:#fff;padding:3px 10px;border-radius:12px;font-size:0.78rem;">🍴 Swiggy Instamart</span>
  <span style="background:#27AE60;color:#fff;padding:3px 10px;border-radius:12px;font-size:0.78rem;">🌿 BigBasket</span>
</div>
""",
        unsafe_allow_html=True,
    )

# ── Home page content ──────────────────────────────────────────────────
st.markdown(
    """
<div style="text-align:center;padding:2rem 0 1rem;">
  <div style="font-size:3.5rem;margin-bottom:0.5rem;">💰</div>
  <h1 style="font-size:2.8rem;font-weight:900;background:linear-gradient(135deg,#4ECDC4,#2196F3);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0;">
    PricePulse
  </h1>
  <p style="color:#aaa;font-size:1.2rem;margin-top:0.5rem;">
    Compare grocery prices across <strong>Zepto · Blinkit · Swiggy Instamart · BigBasket</strong>
  </p>
</div>
""",
    unsafe_allow_html=True,
)

# ── Stats row ─────────────────────────────────────────────────────────
from database.db_manager import fetchone as _fetchone
product_count  = (_fetchone("SELECT COUNT(*) AS n FROM products")  or {}).get("n", 0)
platform_count = 4
price_count    = (_fetchone("SELECT COUNT(*) AS n FROM platform_prices") or {}).get("n", 0)

col1, col2, col3 = st.columns(3)
col1.metric("🛍️ Products Tracked",  f"{product_count:,}")
col2.metric("🏪 Platforms Covered", platform_count)
col3.metric("💲 Price Datapoints",  f"{price_count:,}")

st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

# ── Feature cards ─────────────────────────────────────────────────────
st.markdown("### 🚀 What PricePulse Can Do")
f1, f2, f3, f4, f5 = st.columns(5)

features = [
    ("🔍", "Product Search",    "Fuzzy search with typo tolerance across all platforms"),
    ("🛒", "Basket Optimiser",  "Find the cheapest single platform or split across multiple"),
    ("📊", "Price Dashboard",   "Category heatmaps, platform radar, and best-deal tables"),
    ("🔔", "Price Alerts",      "Get notified the moment a product hits your target price"),
    ("🤖", "AI Assistant",      "Natural language price queries powered by TF-IDF semantic search"),
]

for col, (emoji, title, desc) in zip([f1, f2, f3, f4, f5], features):
    with col:
        st.markdown(
            f"""
<div style="background:#1e2130;border-radius:12px;padding:1rem;text-align:center;
            border:1px solid #2d3144;height:140px;display:flex;flex-direction:column;
            align-items:center;justify-content:center;">
  <div style="font-size:1.8rem;">{emoji}</div>
  <div style="color:#fff;font-weight:700;font-size:0.9rem;margin:4px 0;">{title}</div>
  <div style="color:#aaa;font-size:0.75rem;">{desc}</div>
</div>
""",
            unsafe_allow_html=True,
        )

st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

# ── Quick-search on home ──────────────────────────────────────────────
st.markdown("### ⚡ Quick Search")
qs_col, qs_btn = st.columns([5, 1])
with qs_col:
    home_query = st.text_input(
        "Quick search",
        placeholder="Search any product…",
        label_visibility="collapsed",
    )
with qs_btn:
    if st.button("Search →", use_container_width=True) and home_query:
        # Switch to Search page with query pre-filled via session state
        st.session_state["_home_query"] = home_query
        st.switch_page("pages/1_Search.py")

st.markdown(
    '<p style="color:#555;font-size:0.8rem;text-align:center;margin-top:2rem;">'
    'PricePulse v1.0 · Built with Streamlit · SQLite · Plotly · scikit-learn'
    '</p>',
    unsafe_allow_html=True,
)
