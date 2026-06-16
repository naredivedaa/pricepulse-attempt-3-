"""
pages/4_Alerts.py  –  Price Alerts
──────────────────────────────────────────────────────────────────────
Set price alerts for products; get notified when the price drops
below a user-defined target.
"""

import streamlit as st
import pandas as pd

from modules.alerts_manager import (
    create_alert,
    get_user_alerts,
    check_and_trigger_alerts,
    delete_alert,
    deactivate_alert,
)
from modules.search_engine import search_products
from utils.formatters import fmt_inr, page_header, alert_card
from utils.auth import is_logged_in, current_user_id
from utils.styles import inject_global_styles

st.set_page_config(
    page_title="Alerts – PricePulse",
    page_icon="🔔",
    layout="wide",
)
inject_global_styles()

st.markdown(
    page_header("🔔 Price Alerts", "Get notified when a product drops below your target price"),
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────
# Auth gate
# ──────────────────────────────────────────────────────────────────────
if not is_logged_in():
    st.warning("⚠️ Please log in to manage price alerts.")
    st.info("👉 Use the sidebar to log in or register.")
    st.stop()

user_id = current_user_id()

# ──────────────────────────────────────────────────────────────────────
# Check for triggered alerts
# ──────────────────────────────────────────────────────────────────────
triggered = check_and_trigger_alerts(user_id)
for t in triggered:
    st.balloons()
    st.success(
        f"🎉 Alert triggered! **{t['product']}** is now {fmt_inr(t['current'])} "
        f"(your target was {fmt_inr(t['target'])})"
    )

# ──────────────────────────────────────────────────────────────────────
# Create new alert
# ──────────────────────────────────────────────────────────────────────
with st.expander("➕ Create New Alert", expanded=True):
    alert_query = st.text_input("Search for a product", placeholder="e.g. Amul milk")
    if alert_query:
        results = search_products(alert_query, in_stock_only=False)
        if not results.empty:
            options = {
                f"{row['name']} ({row.get('brand','')} · {row.get('unit','')})": int(row["product_id"])
                for _, row in results.head(10).iterrows()
            }
            selected_label  = st.selectbox("Select product", list(options.keys()))
            selected_pid    = options[selected_label]

            col_price, col_plat = st.columns(2)
            with col_price:
                target_price = st.number_input(
                    "Target total cost (₹)", min_value=0.1, value=100.0, step=5.0,
                    help="Alert triggers when total cost (price + fees - coupons) ≤ this value",
                )
            with col_plat:
                platform_choice = st.selectbox(
                    "Platform",
                    ["any", "zepto", "blinkit", "instamart", "bigbasket"],
                    format_func=lambda x: "Any Platform" if x == "any" else x.title(),
                )

            if st.button("🔔 Set Alert"):
                try:
                    aid = create_alert(user_id, selected_pid, target_price, platform_choice)
                    st.success(f"Alert set! (ID #{aid}) — we'll notify you when the price drops.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        else:
            st.info("No products found.")

st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# Active alerts
# ──────────────────────────────────────────────────────────────────────
st.subheader("📋 Your Alerts")

alerts_df = get_user_alerts(user_id)

if alerts_df.empty:
    st.info("No alerts yet. Create one above!")
    st.stop()

# Render each alert
for _, row in alerts_df.iterrows():
    with st.container():
        col_card, col_actions = st.columns([5, 1])

        with col_card:
            current_price = float(row.get("current_best_price") or 0)
            triggered_val = bool(row.get("triggered", 0))
            st.markdown(
                alert_card(
                    product_name  = str(row["product_name"]),
                    target_price  = float(row["target_price"]),
                    current_price = current_price,
                    triggered     = triggered_val,
                ),
                unsafe_allow_html=True,
            )
            with st.expander("Details"):
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Platform", "Any" if row["platform"] == "any" else str(row["platform"]).title())
                d2.metric("Target",   fmt_inr(row["target_price"]))
                d3.metric("Best Now", fmt_inr(current_price))
                d4.metric("Status",   str(row.get("triggered_label", "Pending")))

        with col_actions:
            alert_id = int(row["id"])
            if st.button("🗑️", key=f"del_{alert_id}", help="Delete alert"):
                delete_alert(alert_id, user_id)
                st.success("Alert deleted.")
                st.rerun()
            if bool(row.get("is_active", 1)) and st.button("⏸️", key=f"pause_{alert_id}", help="Pause alert"):
                deactivate_alert(alert_id, user_id)
                st.info("Alert paused.")
                st.rerun()
