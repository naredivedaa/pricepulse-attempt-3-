"""
pages/1_Search.py  –  Product Search & Price Comparison
──────────────────────────────────────────────────────────────────────
Streamlit page for searching products and comparing prices across
Zepto, Blinkit, Swiggy Instamart, and BigBasket.
"""

import streamlit as st
import pandas as pd

from modules.search_engine import (
    search_products,
    get_categories,
    get_autocomplete_suggestions,
    get_popular_searches,
)
from modules.comparison_engine import get_product_comparison, PLATFORM_LABELS
from modules.recommendation_engine import get_similar_products
from utils.formatters import (
    fmt_inr, fmt_pct, fmt_mins,
    metric_card, platform_badge, savings_badge, product_card, page_header,
)
from utils.charts import price_comparison_bar, savings_waterfall
from utils.auth import current_user_id
from utils.styles import inject_global_styles

st.set_page_config(
    page_title="Search – PricePulse",
    page_icon="🔍",
    layout="wide",
)
inject_global_styles()

# ──────────────────────────────────────────────────────────────────────
# Session state defaults
# ──────────────────────────────────────────────────────────────────────
if "selected_product_id" not in st.session_state:
    st.session_state["selected_product_id"] = None
if "search_results" not in st.session_state:
    st.session_state["search_results"] = pd.DataFrame()

# ──────────────────────────────────────────────────────────────────────
# Page header
# ──────────────────────────────────────────────────────────────────────
st.markdown(
    page_header("🔍 Product Search", "Find the best price for any grocery across 4 platforms"),
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────
# Search bar + filters
# ──────────────────────────────────────────────────────────────────────
col_search, col_cat, col_plat = st.columns([3, 1.5, 1.5])

with col_search:
    query = st.text_input(
        "Search products",
        placeholder="e.g. Amul milk, Basmati rice, Banana…",
        label_visibility="collapsed",
    )

categories    = ["All Categories"] + get_categories()
platforms_map = {"All Platforms": None, "Zepto": "zepto", "Blinkit": "blinkit",
                 "Swiggy Instamart": "instamart", "BigBasket": "bigbasket"}

with col_cat:
    cat_choice = st.selectbox("Category", categories, label_visibility="collapsed")

with col_plat:
    plat_choice = st.selectbox("Platform", list(platforms_map.keys()), label_visibility="collapsed")

col_btn, col_stock, col_info = st.columns([1, 1.5, 4])
with col_btn:
    search_clicked = st.button("🔍 Search", use_container_width=True)
with col_stock:
    in_stock_only = st.checkbox("In-stock only", value=True)

# ──────────────────────────────────────────────────────────────────────
# Popular searches (shown when no search)
# ──────────────────────────────────────────────────────────────────────
if not query and not search_clicked:
    popular = get_popular_searches(6)
    if popular:
        st.markdown("**🔥 Popular searches:**")
        cols = st.columns(min(len(popular), 6))
        for i, term in enumerate(popular):
            with cols[i % 6]:
                if st.button(term, key=f"pop_{i}"):
                    query = term
                    search_clicked = True

# ──────────────────────────────────────────────────────────────────────
# Execute search
# ──────────────────────────────────────────────────────────────────────
if search_clicked or query:
    selected_category = None if cat_choice == "All Categories" else cat_choice
    selected_platform = platforms_map[plat_choice]

    with st.spinner("Searching…"):
        results = search_products(
            query        = query,
            category     = selected_category,
            platform     = selected_platform,
            in_stock_only= in_stock_only,
            user_id      = current_user_id(),
        )
    st.session_state["search_results"] = results

results = st.session_state["search_results"]

# ──────────────────────────────────────────────────────────────────────
# Search results
# ──────────────────────────────────────────────────────────────────────
if not results.empty:
    st.markdown(f"**{len(results)} product(s) found**")
    st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

    for _, row in results.iterrows():
        with st.container():
            # Product card HTML
            st.markdown(
                product_card(
                    name                = str(row["name"]),
                    brand               = str(row.get("brand") or ""),
                    category            = str(row.get("category") or ""),
                    min_price           = float(row.get("min_price") or 0),
                    max_price           = float(row.get("max_price") or 0),
                    platforms_available = int(row.get("platforms_available") or 0),
                ),
                unsafe_allow_html=True,
            )
            if st.button("📊 Compare Prices", key=f"cmp_{row['product_id']}"):
                st.session_state["selected_product_id"] = int(row["product_id"])

elif query or search_clicked:
    st.info("No products found. Try a different search term or remove filters.")

# ──────────────────────────────────────────────────────────────────────
# Price comparison detail panel
# ──────────────────────────────────────────────────────────────────────
pid = st.session_state.get("selected_product_id")
if pid:
    st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

    with st.spinner("Loading price comparison…"):
        comp = get_product_comparison(pid)

    if not comp:
        st.error("Could not load product details.")
    else:
        st.markdown(
            f"## 📦 {comp.product_name}",
        )
        st.caption(f"{comp.brand}  ·  {comp.unit}  ·  {comp.category}")

        # ── Key metrics row ─────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        cheapest = comp.cheapest
        if cheapest:
            m1.markdown(
                metric_card("Best Price", fmt_inr(cheapest.price), cheapest.label, "#27AE60"),
                unsafe_allow_html=True,
            )
            m2.markdown(
                metric_card("Best Total Cost", fmt_inr(cheapest.total_cost),
                            f"incl. all fees", "#4ECDC4"),
                unsafe_allow_html=True,
            )
            m3.markdown(
                metric_card("Max Savings", fmt_inr(comp.max_savings),
                            "vs most expensive", "#F39C12"),
                unsafe_allow_html=True,
            )
            m4.markdown(
                metric_card("Platforms Available",
                            str(len(comp.available_platforms)), "in stock", "#9B59B6"),
                unsafe_allow_html=True,
            )

        # ── Platform detail cards ───────────────────────────────────
        st.subheader("Platform Breakdown")
        plat_cols = st.columns(len(comp.prices))
        for i, (platform, pp) in enumerate(comp.prices.items()):
            with plat_cols[i]:
                is_best = cheapest and platform == cheapest.platform
                border  = "2px solid #27AE60" if is_best else "1px solid #2d3144"
                badge   = "🏆 BEST DEAL  " if is_best else ""
                stock   = "✅ In Stock" if pp.in_stock else "❌ Out of Stock"
                st.markdown(
                    f"""
<div style="background:#1e2130;border:{border};border-radius:12px;padding:1rem;text-align:center;">
  <div style="font-size:0.85rem;font-weight:700;color:{pp.color};">{badge}{pp.label}</div>
  <div style="font-size:1.4rem;font-weight:800;color:#fff;margin:6px 0;">₹{pp.price:.2f}</div>
  <div style="font-size:0.75rem;color:#aaa;">MRP: ₹{pp.mrp:.2f}</div>
  <div style="font-size:0.75rem;color:#27AE60;">{fmt_pct(pp.discount_pct)} off</div>
  <hr style="border-color:#2d3144;margin:8px 0;">
  <div style="font-size:0.75rem;color:#aaa;">Delivery: ₹{pp.delivery_fee:.0f}</div>
  <div style="font-size:0.75rem;color:#aaa;">Platform fee: ₹{pp.platform_fee:.0f}</div>
  <div style="font-size:0.75rem;color:#aaa;">Surge: ₹{pp.surge_fee:.0f}</div>
  <div style="font-size:0.75rem;color:#27AE60;">Coupon: -₹{pp.coupon_discount:.0f}</div>
  <hr style="border-color:#2d3144;margin:8px 0;">
  <div style="font-size:1rem;font-weight:700;color:#4ECDC4;">Total: ₹{pp.total_cost:.2f}</div>
  <div style="font-size:0.75rem;color:#aaa;">{fmt_mins(pp.delivery_mins)}</div>
  <div style="font-size:0.75rem;">{stock}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

        # ── Charts ─────────────────────────────────────────────────
        st.markdown("### 📊 Visual Comparison")
        tab_bar, tab_wf, tab_tbl = st.tabs(["Bar Chart", "Cost Comparison", "Data Table"])

        comp_df = comp.to_dataframe()

        with tab_bar:
            fig_bar = price_comparison_bar(comp_df, comp.product_name)
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab_wf:
            platform_costs = {
                plat: pp.total_cost
                for plat, pp in comp.prices.items()
                if pp.in_stock
            }
            fig_wf = savings_waterfall(platform_costs, comp.product_name)
            st.plotly_chart(fig_wf, use_container_width=True)

        with tab_tbl:
            st.dataframe(
                comp_df.style.format({
                    "Price (₹)":       "₹{:.2f}",
                    "Delivery (₹)":    "₹{:.2f}",
                    "Platform Fee (₹)":"₹{:.2f}",
                    "Surge (₹)":       "₹{:.2f}",
                    "Coupon Off (₹)":  "₹{:.2f}",
                    "Total Cost (₹)":  "₹{:.2f}",
                    "Discount (%)":    "{:.1f}%",
                    "MRP (₹)":         "₹{:.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

        # ── Similar products ────────────────────────────────────────
        with st.expander("🔗 Similar Products"):
            similar = get_similar_products(pid, n=4)
            if not similar.empty:
                sim_cols = st.columns(len(similar))
                for i, (_, srow) in enumerate(similar.iterrows()):
                    with sim_cols[i]:
                        st.markdown(
                            f"**{srow['name']}**\n\n"
                            f"_{srow['brand']}_ · {srow['category']}\n\n"
                            f"Similarity: {srow['similarity']:.0%}"
                        )
                        if st.button("View", key=f"sim_{srow['product_id']}"):
                            st.session_state["selected_product_id"] = int(srow["product_id"])
                            st.rerun()
            else:
                st.info("No similar products found.")
elif results.empty and not query:
    st.info("👆 Enter a product name above to start comparing prices.")
