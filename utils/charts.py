"""
utils/charts.py
──────────────────────────────────────────────────────────────────────
Reusable Plotly chart builders for PricePulse.
All charts use a dark theme consistent with the Streamlit dark config.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PLATFORM_COLORS = {
    "zepto":     "#9B59B6",
    "blinkit":   "#F39C12",
    "instamart": "#E74C3C",
    "bigbasket": "#27AE60",
}

PLATFORM_LABELS = {
    "zepto":     "Zepto",
    "blinkit":   "Blinkit",
    "instamart": "Swiggy Instamart",
    "bigbasket": "BigBasket",
}

DARK_LAYOUT = dict(
    paper_bgcolor = "#0f1117",
    plot_bgcolor  = "#0f1117",
    font          = dict(color="#ccc", family="Inter, sans-serif"),
    margin        = dict(l=10, r=10, t=40, b=10),
    legend        = dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#ccc")),
)


# ──────────────────────────────────────────────────────────────────────
# Price comparison bar chart
# ──────────────────────────────────────────────────────────────────────

def price_comparison_bar(
    comp_df: pd.DataFrame,
    product_name: str,
) -> go.Figure:
    """
    Grouped bar chart: price vs total cost per platform.
    comp_df must have columns: Platform, Price (₹), Total Cost (₹)
    """
    platforms = comp_df["Platform"].tolist()
    colors = [
        PLATFORM_COLORS.get(p.lower().replace(" ", "").replace("swiggy", ""), "#95A5A6")
        for p in platforms
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name        = "Item Price",
        x           = platforms,
        y           = comp_df["Price (₹)"],
        marker_color= colors,
        opacity     = 0.7,
        text        = comp_df["Price (₹)"].apply(lambda v: f"₹{v:.0f}"),
        textposition= "inside",
    ))
    fig.add_trace(go.Bar(
        name        = "Total Cost (incl. fees)",
        x           = platforms,
        y           = comp_df["Total Cost (₹)"],
        marker_color= colors,
        marker_line = dict(width=2, color="#fff"),
        text        = comp_df["Total Cost (₹)"].apply(lambda v: f"₹{v:.0f}"),
        textposition= "outside",
    ))
    fig.update_layout(
        **DARK_LAYOUT,
        title   = f"Price Comparison: {product_name}",
        barmode = "group",
        xaxis   = dict(title="Platform", gridcolor="#2d3144"),
        yaxis   = dict(title="Amount (₹)", gridcolor="#2d3144"),
        height  = 380,
    )
    return fig


# ──────────────────────────────────────────────────────────────────────
# Platform summary radar / polar chart
# ──────────────────────────────────────────────────────────────────────

def platform_radar(summary_df: pd.DataFrame) -> go.Figure:
    """
    Radar chart showing normalised scores for each platform on
    avg_discount_pct, avg_delivery_mins (inverted), stock_pct.
    """
    if summary_df.empty:
        return go.Figure()

    # Normalise columns to 0-100 scale
    def _norm(col: pd.Series) -> pd.Series:
        mn, mx = col.min(), col.max()
        return (col - mn) / (mx - mn + 1e-9) * 100 if mx > mn else col * 0 + 50

    df = summary_df.copy()
    df["score_discount"]  = _norm(df["avg_discount_pct"])
    df["score_speed"]     = 100 - _norm(df["avg_delivery_mins"])  # lower is better
    df["score_stock"]     = _norm(df["stock_pct"])
    df["score_cost"]      = 100 - _norm(df["avg_total_cost"])     # lower is better

    categories = ["Discount", "Speed", "Availability", "Affordability"]

    fig = go.Figure()
    for _, row in df.iterrows():
        plat = row["platform"]
        color = PLATFORM_COLORS.get(plat, "#95A5A6")
        values = [
            row["score_discount"],
            row["score_speed"],
            row["score_stock"],
            row["score_cost"],
        ]
        fig.add_trace(go.Scatterpolar(
            r      = values + [values[0]],
            theta  = categories + [categories[0]],
            fill   = "toself",
            name   = PLATFORM_LABELS.get(plat, plat.title()),
            line   = dict(color=color),
            fillcolor=color,
            opacity= 0.3,
        ))

    fig.update_layout(
        **DARK_LAYOUT,
        polar = dict(
            bgcolor    = "#0f1117",
            radialaxis = dict(visible=True, range=[0, 100], gridcolor="#2d3144"),
            angularaxis= dict(gridcolor="#2d3144"),
        ),
        title  = "Platform Performance Score",
        height = 420,
    )
    return fig


# ──────────────────────────────────────────────────────────────────────
# Category heatmap
# ──────────────────────────────────────────────────────────────────────

def category_price_heatmap(trend_df: pd.DataFrame) -> go.Figure:
    """
    Heatmap: rows = categories, columns = platforms, values = avg_total.
    """
    if trend_df.empty:
        return go.Figure()

    pivot = trend_df.pivot_table(
        index="category", columns="platform", values="avg_total", aggfunc="mean"
    ).fillna(0)

    # Rename columns to friendly labels
    pivot.columns = [PLATFORM_LABELS.get(c, c) for c in pivot.columns]

    fig = go.Figure(go.Heatmap(
        z          = pivot.values,
        x          = pivot.columns.tolist(),
        y          = pivot.index.tolist(),
        colorscale = "Viridis",
        text       = pivot.values,
        texttemplate="₹%{text:.0f}",
        hovertemplate="Category: %{y}<br>Platform: %{x}<br>Avg Total: ₹%{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        **DARK_LAYOUT,
        title  = "Average Total Cost by Category & Platform",
        xaxis  = dict(title="Platform"),
        yaxis  = dict(title="Category"),
        height = 450,
    )
    return fig


# ──────────────────────────────────────────────────────────────────────
# Savings waterfall chart
# ──────────────────────────────────────────────────────────────────────

def savings_waterfall(
    platform_costs: Dict[str, float],
    product_name: str,
) -> go.Figure:
    """Waterfall chart showing cost breakdown differences across platforms."""
    labels = [PLATFORM_LABELS.get(p, p.title()) for p in platform_costs]
    values = list(platform_costs.values())

    if not values:
        return go.Figure()

    baseline = max(values)
    savings   = [baseline - v for v in values]
    colors    = [
        PLATFORM_COLORS.get(p, "#95A5A6") for p in platform_costs
    ]

    fig = go.Figure(go.Bar(
        x           = labels,
        y           = values,
        marker_color= colors,
        text        = [f"₹{v:.0f}" for v in values],
        textposition= "outside",
    ))
    fig.update_layout(
        **DARK_LAYOUT,
        title  = f"Total Cost Comparison: {product_name}",
        xaxis  = dict(title="Platform"),
        yaxis  = dict(title="Total Cost (₹)", gridcolor="#2d3144"),
        height = 360,
    )
    return fig


# ──────────────────────────────────────────────────────────────────────
# Pie / donut: platform distribution
# ──────────────────────────────────────────────────────────────────────

def platform_share_pie(summary_df: pd.DataFrame) -> go.Figure:
    """Donut chart of product count per platform."""
    if summary_df.empty:
        return go.Figure()

    fig = go.Figure(go.Pie(
        labels    = summary_df["platform_label"] if "platform_label" in summary_df.columns
                    else summary_df["platform"].map(PLATFORM_LABELS),
        values    = summary_df["product_count"],
        hole      = 0.5,
        marker    = dict(colors=[PLATFORM_COLORS.get(p, "#95A5A6") for p in summary_df["platform"]]),
    ))
    fig.update_layout(
        **DARK_LAYOUT,
        title  = "Product Coverage per Platform",
        height = 350,
    )
    return fig


# ──────────────────────────────────────────────────────────────────────
# Basket cost breakdown stacked bar
# ──────────────────────────────────────────────────────────────────────

def basket_cost_breakdown(result_df: pd.DataFrame) -> go.Figure:
    """
    Stacked bar showing items subtotal, delivery fee, platform fee
    per platform (for basket comparison).
    """
    if result_df.empty:
        return go.Figure()

    grouped = result_df.groupby("Platform").agg(
        items_total   = ("Subtotal (₹)",     "sum"),
        delivery_fee  = ("Delivery Fee (₹)", "first"),
        platform_fee  = ("Platform Fee (₹)", "first"),
    ).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Items Total",   x=grouped["Platform"], y=grouped["items_total"],  marker_color="#4ECDC4"))
    fig.add_trace(go.Bar(name="Delivery Fee",  x=grouped["Platform"], y=grouped["delivery_fee"], marker_color="#F39C12"))
    fig.add_trace(go.Bar(name="Platform Fee",  x=grouped["Platform"], y=grouped["platform_fee"], marker_color="#E74C3C"))

    fig.update_layout(
        **DARK_LAYOUT,
        barmode= "stack",
        title  = "Basket Cost Breakdown per Platform",
        xaxis  = dict(title="Platform"),
        yaxis  = dict(title="Cost (₹)", gridcolor="#2d3144"),
        height = 380,
    )
    return fig
