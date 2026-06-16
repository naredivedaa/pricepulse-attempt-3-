"""
pages/3_Dashboard.py  –  Analytics Dashboard
──────────────────────────────────────────────────────────────────────
Platform-wide price analytics, category trends, and deal discovery.
"""

import streamlit as st
import pandas as pd

from modules.comparison_engine import (
    get_best_deals,
    get_platform_summary,
    get_category_price_trends,
    PLATFORM_LABELS,
    PLATFORM_COLORS,
)
from modules.recommendation_engine import get_best_deals_recommendations
from utils.formatters import fmt_inr, fmt_pct, fmt_mins, metric_card, page_header, platform_badge
from utils.charts import platform_radar, category_price_heatmap, platform_share_pie
from utils.styles import inject_global_styles

st.set_page_config(
    page_title="Dashboard – PricePulse",
    page_icon="📊",
    layout="wide",
)
inject_global_styles()

st.markdown(
    page_header("📊 Price Intelligence Dashboard", "Market-wide analytics across all 4 platforms"),
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────
# Load data
# ──────────────────────────────────────────────────────────────────────
with st.spinner("Loading analytics…"):
    summary_df = get_platform_summary()
    trends_df  = get_category_price_trends()
    deals_df   = get_best_deals(10)

# ──────────────────────────────────────────────────────────────────────
# Platform KPI row
# ──────────────────────────────────────────────────────────────────────
st.subheader("🏪 Platform Overview")

if not summary_df.empty:
    kpi_cols = st.columns(len(summary_df))
    for i, (_, row) in enumerate(summary_df.iterrows()):
        plat  = row["platform"]
        color = PLATFORM_COLORS.get(plat, "#95A5A6")
        with kpi_cols[i]:
            st.markdown(
                f"""
<div style="background:#1e2130;border-top:4px solid {color};border-radius:10px;
            padding:1rem;text-align:center;margin-bottom:0.5rem;">
  <div style="color:{color};font-weight:700;font-size:0.85rem;">{PLATFORM_LABELS.get(plat, plat.title())}</div>
  <div style="color:#fff;font-size:1.4rem;font-weight:800;margin:4px 0;">
    {fmt_inr(row['avg_total_cost'])}
  </div>
  <div style="color:#aaa;font-size:0.75rem;">avg total cost</div>
  <div style="color:#4ECDC4;font-size:0.8rem;margin-top:4px;">{fmt_pct(row['avg_discount_pct'])} avg discount</div>
  <div style="color:#aaa;font-size:0.75rem;">{int(row['avg_delivery_mins'])} min delivery</div>
  <div style="color:#aaa;font-size:0.75rem;">{int(row['product_count'])} products</div>
</div>
""",
                unsafe_allow_html=True,
            )
else:
    st.warning("Platform summary data not available.")

st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# Charts row
# ──────────────────────────────────────────────────────────────────────
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    if not summary_df.empty:
        fig_radar = platform_radar(summary_df)
        st.plotly_chart(fig_radar, use_container_width=True)
    else:
        st.info("Radar chart unavailable.")

with chart_col2:
    if not summary_df.empty:
        fig_pie = platform_share_pie(summary_df)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Pie chart unavailable.")

# ──────────────────────────────────────────────────────────────────────
# Category heatmap
# ──────────────────────────────────────────────────────────────────────
st.subheader("🌡️ Category Price Heatmap")
if not trends_df.empty:
    fig_heat = category_price_heatmap(trends_df)
    st.plotly_chart(fig_heat, use_container_width=True)
else:
    st.info("Category trend data not available.")

st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# Best deals table
# ──────────────────────────────────────────────────────────────────────
st.subheader("🔥 Top 10 Best Deals")
if not deals_df.empty:
    # Format for display
    display_df = deals_df.copy()
    display_df["savings"]       = (display_df["max_total"] - display_df["min_total"]).clip(lower=0).round(2)
    display_df["min_total"]     = display_df["min_total"].round(2)
    display_df["max_discount"]  = display_df["max_discount"].round(1)

    display_df = display_df.rename(columns={
        "name":         "Product",
        "category":     "Category",
        "brand":        "Brand",
        "min_total":    "Best Total (₹)",
        "savings":      "Potential Savings (₹)",
        "max_discount": "Max Discount (%)",
    })

    cols_show = ["Product", "Category", "Brand", "Best Total (₹)", "Potential Savings (₹)", "Max Discount (%)"]
    existing  = [c for c in cols_show if c in display_df.columns]

    st.dataframe(
        display_df[existing].style.format({
            "Best Total (₹)":         "₹{:.2f}",
            "Potential Savings (₹)":  "₹{:.2f}",
            "Max Discount (%)":       "{:.1f}%",
        }).background_gradient(subset=["Potential Savings (₹)"], cmap="Greens"),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Best deals data not available.")

st.markdown('<div class="pp-divider"></div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# Platform comparison table
# ──────────────────────────────────────────────────────────────────────
st.subheader("📋 Platform Statistics")
if not summary_df.empty:
    tbl = summary_df.copy()
    tbl["platform"] = tbl["platform"].map(PLATFORM_LABELS)
    tbl = tbl.rename(columns={
        "platform":          "Platform",
        "product_count":     "Products",
        "avg_total_cost":    "Avg Total Cost (₹)",
        "avg_discount_pct":  "Avg Discount (%)",
        "avg_delivery_mins": "Avg Delivery (min)",
        "stock_pct":         "In-Stock (%)",
    })
    cols_show = ["Platform","Products","Avg Total Cost (₹)","Avg Discount (%)","Avg Delivery (min)","In-Stock (%)"]
    existing  = [c for c in cols_show if c in tbl.columns]

    st.dataframe(
        tbl[existing].style.format({
            "Avg Total Cost (₹)": "₹{:.2f}",
            "Avg Discount (%)":   "{:.1f}%",
            "Avg Delivery (min)": "{:.0f}",
            "In-Stock (%)":       "{:.1f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )
