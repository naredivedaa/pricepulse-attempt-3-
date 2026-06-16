"""
pages/5_AI_Assistant.py  –  AI Shopping Assistant
──────────────────────────────────────────────────────────────────────
A rule-based AI assistant that uses TF-IDF semantic search to answer
grocery price queries, recommend products, and explain savings.
No external LLM API required – fully offline and free.
"""

import re
import streamlit as st
import pandas as pd

from modules.recommendation_engine import (
    search_by_query_vector,
    get_best_deals_recommendations,
)
from modules.comparison_engine import get_product_comparison, PLATFORM_LABELS
from modules.search_engine import search_products
from utils.formatters import fmt_inr, page_header, platform_badge, metric_card
from utils.styles import inject_global_styles

st.set_page_config(
    page_title="AI Assistant – PricePulse",
    page_icon="🤖",
    layout="wide",
)
inject_global_styles()

st.markdown(
    page_header("🤖 AI Shopping Assistant", "Ask me anything about grocery prices"),
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────
# Chat history
# ──────────────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = [
        {
            "role":    "assistant",
            "content": (
                "👋 Hi! I'm your PricePulse AI Assistant.\n\n"
                "You can ask me things like:\n"
                "- *Which platform has the cheapest milk?*\n"
                "- *Show me best deals on snacks*\n"
                "- *Where should I buy rice today?*\n"
                "- *Compare Amul butter prices*"
            ),
        }
    ]

chat_history: list = st.session_state["chat_history"]

# ──────────────────────────────────────────────────────────────────────
# Response engine
# ──────────────────────────────────────────────────────────────────────

def _format_comparison_reply(product_name: str, comp) -> str:
    """Build a markdown reply for a product comparison."""
    if not comp or not comp.prices:
        return f"Sorry, I couldn't find pricing data for **{product_name}**."

    cheapest = comp.cheapest
    lines = [f"### 📦 {comp.product_name} — {comp.unit}\n"]
    lines.append("| Platform | Price | Total Cost | Delivery | In Stock |")
    lines.append("|----------|-------|------------|----------|----------|")
    for plat, pp in sorted(comp.prices.items(), key=lambda x: x[1].total_cost):
        stock = "✅" if pp.in_stock else "❌"
        best  = " 🏆" if cheapest and plat == cheapest.platform else ""
        lines.append(
            f"| {pp.label}{best} | {fmt_inr(pp.price)} | {fmt_inr(pp.total_cost)} "
            f"| {fmt_inr(pp.delivery_fee)} | {stock} |"
        )

    if cheapest:
        lines.append(
            f"\n💡 **Best deal:** {cheapest.label} at **{fmt_inr(cheapest.total_cost)}** total "
            f"(save up to {fmt_inr(comp.max_savings)} vs most expensive platform)."
        )
    return "\n".join(lines)


def _generate_response(user_msg: str) -> str:
    """Rule-based + TF-IDF response generator."""
    msg_lower = user_msg.lower().strip()

    # ── Greeting ─────────────────────────────────────────────────────
    greetings = {"hi", "hello", "hey", "namaste", "sup", "howdy"}
    if any(g in msg_lower for g in greetings):
        return (
            "👋 Hello! I'm ready to help you save money on groceries.\n\n"
            "Try asking: *\"Which platform has cheapest milk?\"* or "
            "*\"Show best deals\"*"
        )

    # ── Best deals ────────────────────────────────────────────────────
    if re.search(r"best deal|top deal|cheapest|save money|discount", msg_lower):
        deals = get_best_deals_recommendations(6)
        if deals.empty:
            return "No deals data available right now."
        lines = ["### 🔥 Top Deals Right Now\n"]
        for _, row in deals.iterrows():
            savings = float(row.get("potential_savings", 0))
            lines.append(
                f"- **{row['name']}** ({row['category']}) — "
                f"from {fmt_inr(float(row['min_total']))} · "
                f"save up to {fmt_inr(savings)}"
            )
        return "\n".join(lines)

    # ── Platform comparison query ─────────────────────────────────────
    platform_kw = {
        "zepto": "zepto", "blinkit": "blinkit",
        "instamart": "instamart", "swiggy": "instamart",
        "bigbasket": "bigbasket", "big basket": "bigbasket",
    }
    detected_platform = next(
        (v for k, v in platform_kw.items() if k in msg_lower), None
    )

    # ── Product-specific query ─────────────────────────────────────────
    # Remove question words and search
    clean_query = re.sub(
        r"(where|what|which|how much|cheapest|price|platform|buy|find|compare|show me|tell me|is|are|the|of|for|on)",
        "", msg_lower
    ).strip()

    if len(clean_query) >= 3:
        # Try semantic search first
        semantic_df = search_by_query_vector(clean_query, n=3)
        if not semantic_df.empty:
            top_product_id = int(semantic_df.iloc[0]["product_id"])
            comp           = get_product_comparison(top_product_id)
            if comp:
                reply = _format_comparison_reply(clean_query, comp)
                # Append alternatives if multiple found
                if len(semantic_df) > 1:
                    alts = semantic_df.iloc[1:]["name"].tolist()
                    reply += f"\n\n_Also found: {', '.join(alts)}_"
                return reply

        # Fall back to keyword search
        results = search_products(clean_query, in_stock_only=False)
        if not results.empty:
            top_pid = int(results.iloc[0]["product_id"])
            comp    = get_product_comparison(top_pid)
            if comp:
                return _format_comparison_reply(clean_query, comp)

    # ── Help / fallback ───────────────────────────────────────────────
    return (
        "🤔 I didn't quite understand that. Here's what I can help with:\n\n"
        "- **Price comparison**: *\"Compare Amul milk prices\"*\n"
        "- **Best deals**: *\"Show best deals\"* or *\"What's cheapest?\"*\n"
        "- **Platform info**: *\"Prices on Blinkit\"*\n"
        "- **Category search**: *\"Show dairy deals\"*"
    )


# ──────────────────────────────────────────────────────────────────────
# Render chat
# ──────────────────────────────────────────────────────────────────────
chat_container = st.container()

with chat_container:
    for msg in chat_history:
        role = msg["role"]
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "🧑"):
            st.markdown(msg["content"])

# ──────────────────────────────────────────────────────────────────────
# User input
# ──────────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask about grocery prices…")

if user_input:
    # Append user message
    chat_history.append({"role": "user", "content": user_input})

    # Generate response
    with st.spinner("Thinking…"):
        reply = _generate_response(user_input)

    chat_history.append({"role": "assistant", "content": reply})
    st.session_state["chat_history"] = chat_history
    st.rerun()

# ──────────────────────────────────────────────────────────────────────
# Quick action buttons
# ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("**Quick Questions:**")
quick_cols = st.columns(4)
quick_questions = [
    "Show best deals",
    "Compare Amul milk",
    "Cheapest rice",
    "Top snack deals",
]
for i, qn in enumerate(quick_questions):
    with quick_cols[i]:
        if st.button(qn, key=f"quick_{i}"):
            chat_history.append({"role": "user", "content": qn})
            reply = _generate_response(qn)
            chat_history.append({"role": "assistant", "content": reply})
            st.session_state["chat_history"] = chat_history
            st.rerun()

# Clear chat
if st.button("🗑️ Clear Chat"):
    st.session_state["chat_history"] = [
        {"role": "assistant", "content": "Chat cleared. How can I help you?"}
    ]
    st.rerun()
