"""
pages/2_Basket.py  –  Smart Basket Comparison
──────────────────────────────────────────────────────────────────────
Build a grocery basket and compare single-platform vs split-basket
optimisation strategies.
"""

import streamlit as st
import pandas as pd

from modules.basket_optimizer import (
    compare_strategies,
    result_to_dataframe,
    save_basket_history,
    PLATFORM_LABELS,
)
from modules.search_engine import search_products
from utils.formatters import fmt_inr, page_header, metric_card
from utils.charts import basket_cost_breakdown
from utils.auth import current_user_id
from utils.styles import inject_global_styles

st.set_page_config(
    page_title="Basket – PricePulse",
    page_icon="🛒",
    layout="wide",
)
inject_global_styles()

# ──────────────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────────────
if "basket" not in st.session_state:
    st.session_state["basket"] = {}   # {product_id: {"name": str, "qty": int}}

basket: dict = st.session_state["basket"]

# ──────────────────────────────────────────────────────────────────────
# Page header
# ──────────────────────────────────────────────────────────────────────
st.markdown(
    page_header("🛒 Smart Basket", "Add items and find the cheapest way to buy your groceries"),
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────
# Add items panel
# ──────────────────────────────────────────────────────────────────────
with st.expander("➕ Add Items to Basket", expanded=not basket):
    add_query = st.text_input("Search for a product", placeholder="e.g. Milk, Rice…")
    if add_query:
        results = search_products(add_query, in_stock_only=True)
        if not results.empty:
            for _, row in results.head(6).iterrows():
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.markdown(
                        f"**{row['name']}** — _{row.get('brand','')}_ "
                        f"· {row.get('category','')} · from {fmt_inr(float(row.get('min_price',0)))}"
                    )
                with c2:
                    qty = st.number_input(
                        "Qty", min_value=1, max_value=20, value=1,
                        key=f"qty_{row['product_id']}",
                        label_visibility="collapsed",
                    )
                with c3:
                    if st.button("Add", key=f"add_{row['product_id']}"):
                        pid   = int(row["product_id"])
                        name  = str(row["name"])
                        if pid in basket:
                            basket[pid]["qty"] += qty
                        else:
                            basket[pid] = {"name": name, "qty": qty}
                        st.session_state["basket"] = basket
                        st.success(f"Added {name} ×{qty}")
                        st.rerun()
        else:
            st.info("No products found.")

# ──────────────────────────────────────────────────────────────────────
# Current basket
# ──────────────────────────────────────────────────────────────────────
st.subheader("🧺 Your Basket")

if not basket:
    st.info("Your basket is empty. Add items using the panel above.")
    st.stop()

# Display and manage basket items
basket_list_data = []
remove_ids = []

for pid, item in basket.items():
    col_name, col_qty, col_remove = st.columns([5, 2, 1])
    with col_name:
        st.markdown(f"**{item['name']}**")
    with col_qty:
        new_qty = st.number_input(
            "qty", min_value=1, max_value=50, value=item["qty"],
            key=f"bqty_{pid}", label_visibility="collapsed",
        )
        basket[pid]["qty"] = new_qty
    with col_remove:
        if st.button("🗑️", key=f"rm_{pid}"):
            remove_ids.append(pid)

for rid in remove_ids:
    basket.pop(rid, None)
st.session_state["basket"] = basket

if remove_ids:
    st.rerun()

st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# Optimise
# ──────────────────────────────────────────────────────────────────────
col_opt, col_clear = st.columns([2, 1])
with col_opt:
    optimise_clicked = st.button("🚀 Optimise Basket", use_container_width=True)
with col_clear:
    if st.button("🗑️ Clear Basket", use_container_width=True):
        st.session_state["basket"] = {}
        st.rerun()

if not optimise_clicked:
    st.stop()

# Build basket tuple list
basket_tuples = [(int(pid), item["qty"]) for pid, item in basket.items()]

with st.spinner("Optimising your basket across 4 platforms…"):
    strategies = compare_strategies(basket_tuples)

single = strategies["single"]
split  = strategies["split"]

# Save history
import uuid
session_id = st.session_state.get("session_id", str(uuid.uuid4()))
st.session_state["session_id"] = session_id

save_basket_history(session_id, basket_tuples, single, current_user_id())

# ──────────────────────────────────────────────────────────────────────
# Results
# ──────────────────────────────────────────────────────────────────────
st.markdown("## 📊 Optimisation Results")

tab_single, tab_split, tab_compare = st.tabs(
    ["🏪 Single Platform", "✂️ Split Basket", "📈 Side-by-Side"]
)

# ── Single platform ─────────────────────────────────────────────────
with tab_single:
    if single.platform_baskets:
        plat_key = list(single.platform_baskets.keys())[0]
        pb       = single.platform_baskets[plat_key]

        st.markdown(
            f"""
<div style="background:#1e2130;border:2px solid #27AE60;border-radius:12px;
            padding:1.2rem;text-align:center;margin-bottom:1rem;">
  <div style="color:#27AE60;font-size:0.9rem;font-weight:700;">🏆 BEST SINGLE PLATFORM</div>
  <div style="color:#fff;font-size:2rem;font-weight:800;margin:6px 0;">{pb.label}</div>
  <div style="color:#4ECDC4;font-size:1.5rem;font-weight:700;">Total: {fmt_inr(single.total_cost)}</div>
  <div style="color:#aaa;font-size:0.85rem;">Save {fmt_inr(single.savings_vs_worst)} vs worst platform</div>
</div>
""",
            unsafe_allow_html=True,
        )

        m1, m2, m3 = st.columns(3)
        m1.markdown(metric_card("Items Subtotal", fmt_inr(pb.items_total), "", "#4ECDC4"), unsafe_allow_html=True)
        m2.markdown(metric_card("Delivery Fee",   fmt_inr(pb.delivery_fee), "", "#F39C12"), unsafe_allow_html=True)
        m3.markdown(metric_card("Platform Fee",   fmt_inr(pb.platform_fee), "", "#9B59B6"), unsafe_allow_html=True)

        single_df = result_to_dataframe(single)
        if not single_df.empty:
            st.dataframe(
                single_df.style.format({
                    "Unit Price (₹)":   "₹{:.2f}",
                    "Subtotal (₹)":     "₹{:.2f}",
                    "Surge (₹)":        "₹{:.2f}",
                    "Coupon Off (₹)":   "₹{:.2f}",
                    "Delivery Fee (₹)": "₹{:.2f}",
                    "Platform Fee (₹)": "₹{:.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

        if single.missing_items:
            st.warning(f"⚠️ Not available: {', '.join(single.missing_items)}")
    else:
        st.error("Could not find a valid single-platform solution.")

# ── Split basket ─────────────────────────────────────────────────────
with tab_split:
    st.markdown(
        f"""
<div style="background:#1e2130;border:2px solid #2196F3;border-radius:12px;
            padding:1.2rem;text-align:center;margin-bottom:1rem;">
  <div style="color:#2196F3;font-size:0.9rem;font-weight:700;">✂️ SPLIT BASKET TOTAL</div>
  <div style="color:#4ECDC4;font-size:1.8rem;font-weight:700;">{fmt_inr(split.total_cost)}</div>
  <div style="color:#aaa;font-size:0.85rem;">{len(split.platform_baskets)} platform(s) used</div>
</div>
""",
        unsafe_allow_html=True,
    )

    split_df = result_to_dataframe(split)
    if not split_df.empty:
        for plat_label, grp in split_df.groupby("Platform"):
            with st.expander(f"🛒 {plat_label} — {len(grp)} item(s)"):
                st.dataframe(
                    grp.style.format({
                        "Unit Price (₹)":   "₹{:.2f}",
                        "Subtotal (₹)":     "₹{:.2f}",
                        "Surge (₹)":        "₹{:.2f}",
                        "Coupon Off (₹)":   "₹{:.2f}",
                        "Delivery Fee (₹)": "₹{:.2f}",
                        "Platform Fee (₹)": "₹{:.2f}",
                    }),
                    use_container_width=True,
                    hide_index=True,
                )

    if split.missing_items:
        st.warning(f"⚠️ Not available: {', '.join(split.missing_items)}")

    # Chart
    if not split_df.empty:
        fig = basket_cost_breakdown(split_df)
        st.plotly_chart(fig, use_container_width=True)

# ── Side-by-side ────────────────────────────────────────────────────
with tab_compare:
    col_s, col_sp = st.columns(2)

    winner_label = "Split 🏆" if split.total_cost < single.total_cost else "Single 🏆"
    saving_amt   = abs(single.total_cost - split.total_cost)

    with col_s:
        st.markdown("### 🏪 Single Platform")
        best_pb_label = ""
        if single.platform_baskets:
            pk = list(single.platform_baskets.keys())[0]
            best_pb_label = PLATFORM_LABELS.get(pk, pk.title())
        st.metric("Platform",   best_pb_label)
        st.metric("Total Cost", fmt_inr(single.total_cost))
        st.metric("Missing Items", len(single.missing_items))

    with col_sp:
        st.markdown("### ✂️ Split Basket")
        st.metric("Platforms Used", len(split.platform_baskets))
        st.metric("Total Cost",     fmt_inr(split.total_cost))
        st.metric("Missing Items",  len(split.missing_items))

    st.success(
        f"💡 **{winner_label}** saves **{fmt_inr(saving_amt)}** over the other strategy."
    )
