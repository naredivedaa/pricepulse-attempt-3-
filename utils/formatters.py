"""
utils/formatters.py
──────────────────────────────────────────────────────────────────────
Currency, percentage, and HTML card formatters for the Streamlit UI.
All st.markdown() calls that render HTML require unsafe_allow_html=True.
"""

from __future__ import annotations

PLATFORM_COLORS = {
    "zepto":     "#9B59B6",
    "blinkit":   "#F39C12",
    "instamart": "#E74C3C",
    "bigbasket": "#27AE60",
}

PLATFORM_EMOJIS = {
    "zepto":     "⚡",
    "blinkit":   "🛒",
    "instamart": "🍴",
    "bigbasket": "🌿",
}

PLATFORM_LABELS = {
    "zepto":     "Zepto",
    "blinkit":   "Blinkit",
    "instamart": "Swiggy Instamart",
    "bigbasket": "BigBasket",
}


# ──────────────────────────────────────────────────────────────────────
# Currency / number
# ──────────────────────────────────────────────────────────────────────

def fmt_inr(value: float) -> str:
    """Format a float as Indian Rupee string, e.g. ₹ 1,234.50"""
    try:
        return f"₹ {float(value):,.2f}"
    except (TypeError, ValueError):
        return "₹ —"


def fmt_pct(value: float) -> str:
    """Format as percentage string, e.g. 12.5%"""
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—%"


def fmt_mins(mins: int) -> str:
    """Format delivery minutes, e.g. 30 min | 1 h 15 min"""
    try:
        mins = int(mins)
        if mins < 60:
            return f"{mins} min"
        return f"{mins // 60} h {mins % 60} min"
    except (TypeError, ValueError):
        return "—"


# ──────────────────────────────────────────────────────────────────────
# HTML card generators  (safe: no user-supplied raw HTML injected)
# ──────────────────────────────────────────────────────────────────────

def metric_card(title: str, value: str, delta: str = "", color: str = "#4ECDC4") -> str:
    """
    Return an HTML string for a metric card.
    Callers must pass this to st.markdown(..., unsafe_allow_html=True).
    """
    delta_html = (
        f'<div style="font-size:0.85rem;color:#aaa;margin-top:4px;">{delta}</div>'
        if delta
        else ""
    )
    return f"""
<div style="
    background: #1e2130;
    border-left: 4px solid {color};
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
">
  <div style="color:#aaa;font-size:0.8rem;text-transform:uppercase;letter-spacing:1px;">{title}</div>
  <div style="color:#fff;font-size:1.6rem;font-weight:700;margin-top:4px;">{value}</div>
  {delta_html}
</div>
"""


def platform_badge(platform: str) -> str:
    """Return a coloured HTML badge for a platform key."""
    color = PLATFORM_COLORS.get(platform, "#95A5A6")
    emoji = PLATFORM_EMOJIS.get(platform, "🏪")
    label = PLATFORM_LABELS.get(platform, platform.title())
    return (
        f'<span style="background:{color};color:#fff;padding:3px 10px;'
        f'border-radius:12px;font-size:0.78rem;font-weight:600;">'
        f'{emoji} {label}</span>'
    )


def savings_badge(savings: float) -> str:
    """Return a green savings badge HTML string."""
    if savings <= 0:
        return ""
    return (
        f'<span style="background:#27AE60;color:#fff;padding:3px 10px;'
        f'border-radius:12px;font-size:0.78rem;font-weight:600;">'
        f'💰 Save {fmt_inr(savings)}</span>'
    )


def product_card(
    name: str,
    brand: str,
    category: str,
    min_price: float,
    max_price: float,
    platforms_available: int,
) -> str:
    """Return an HTML product card."""
    price_range = (
        fmt_inr(min_price)
        if abs(max_price - min_price) < 0.01
        else f"{fmt_inr(min_price)} – {fmt_inr(max_price)}"
    )
    return f"""
<div style="
    background:#1e2130;
    border-radius:12px;
    padding:1rem 1.2rem;
    margin-bottom:0.6rem;
    border:1px solid #2d3144;
    transition: transform 0.2s;
">
  <div style="font-size:1.05rem;font-weight:700;color:#fff;">{name}</div>
  <div style="font-size:0.82rem;color:#aaa;margin-top:2px;">{brand} &bull; {category}</div>
  <div style="display:flex;justify-content:space-between;margin-top:0.6rem;align-items:center;">
    <span style="color:#4ECDC4;font-size:1rem;font-weight:600;">{price_range}</span>
    <span style="background:#2d3144;color:#aaa;padding:2px 8px;border-radius:8px;font-size:0.75rem;">
      {platforms_available} platforms
    </span>
  </div>
</div>
"""


def alert_card(
    product_name: str,
    target_price: float,
    current_price: float,
    triggered: bool,
) -> str:
    """Return an HTML alert card."""
    gap   = current_price - target_price
    color = "#27AE60" if triggered else ("#E74C3C" if gap > 0 else "#F39C12")
    status = "✅ Triggered" if triggered else ("🔴 Above Target" if gap > 0 else "🟡 Near Target")
    return f"""
<div style="
    background:#1e2130;
    border-left:4px solid {color};
    border-radius:10px;
    padding:0.9rem 1.1rem;
    margin-bottom:0.6rem;
">
  <div style="font-weight:700;color:#fff;">{product_name}</div>
  <div style="color:#aaa;font-size:0.82rem;margin-top:4px;">
    Target: {fmt_inr(target_price)} &nbsp;|&nbsp; Current best: {fmt_inr(current_price)}
  </div>
  <div style="color:{color};font-size:0.82rem;margin-top:4px;">{status}</div>
</div>
"""


def page_header(title: str, subtitle: str = "") -> str:
    """Return page header HTML."""
    sub = f'<p style="color:#aaa;font-size:1rem;margin:0;">{subtitle}</p>' if subtitle else ""
    return f"""
<div style="margin-bottom:1.5rem;">
  <h1 style="color:#fff;font-size:2rem;font-weight:800;margin:0;">{title}</h1>
  {sub}
</div>
"""
