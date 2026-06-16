"""
modules/comparison_engine.py
──────────────────────────────────────────────────────────────────────
Production-grade price comparison engine.

Total cost formula (used consistently throughout):
    total_cost = price + delivery_fee + platform_fee + surge_fee - coupon_discount

All values are validated to be ≥ 0 to avoid negative totals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from database.db_manager import fetchall, fetchone

logger = logging.getLogger(__name__)

PLATFORMS = ["zepto", "blinkit", "instamart", "bigbasket"]

PLATFORM_LABELS = {
    "zepto":     "Zepto",
    "blinkit":   "Blinkit",
    "instamart": "Swiggy Instamart",
    "bigbasket": "BigBasket",
}

PLATFORM_COLORS = {
    "zepto":     "#9B59B6",
    "blinkit":   "#F39C12",
    "instamart": "#E74C3C",
    "bigbasket": "#27AE60",
}


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class PlatformPrice:
    platform:        str
    price:           float
    mrp:             float
    discount_pct:    float
    delivery_fee:    float
    platform_fee:    float
    surge_fee:       float
    coupon_discount: float
    in_stock:        bool
    delivery_mins:   int
    quantity_str:    str
    total_cost:      float = field(init=False)

    def __post_init__(self) -> None:
        # Clamp all fee-like values to ≥ 0
        self.price           = max(0.0, float(self.price))
        self.delivery_fee    = max(0.0, float(self.delivery_fee))
        self.platform_fee    = max(0.0, float(self.platform_fee))
        self.surge_fee       = max(0.0, float(self.surge_fee))
        self.coupon_discount = max(0.0, float(self.coupon_discount))
        # Canonical total-cost formula
        self.total_cost = (
            self.price
            + self.delivery_fee
            + self.platform_fee
            + self.surge_fee
            - self.coupon_discount
        )
        # Ensure total_cost is never negative
        self.total_cost = max(0.0, self.total_cost)

    @property
    def savings_vs_mrp(self) -> float:
        return max(0.0, self.mrp - self.price)

    @property
    def label(self) -> str:
        return PLATFORM_LABELS.get(self.platform, self.platform.title())

    @property
    def color(self) -> str:
        return PLATFORM_COLORS.get(self.platform, "#95A5A6")


@dataclass
class ProductComparison:
    product_id:   int
    product_name: str
    category:     str
    brand:        str
    unit:         str
    prices:       Dict[str, PlatformPrice] = field(default_factory=dict)

    @property
    def cheapest(self) -> Optional[PlatformPrice]:
        in_stock = [p for p in self.prices.values() if p.in_stock]
        if not in_stock:
            return None
        return min(in_stock, key=lambda p: p.total_cost)

    @property
    def most_expensive(self) -> Optional[PlatformPrice]:
        in_stock = [p for p in self.prices.values() if p.in_stock]
        if not in_stock:
            return None
        return max(in_stock, key=lambda p: p.total_cost)

    @property
    def max_savings(self) -> float:
        """Difference in total_cost between most expensive and cheapest."""
        if self.cheapest and self.most_expensive:
            return max(0.0, self.most_expensive.total_cost - self.cheapest.total_cost)
        return 0.0

    @property
    def available_platforms(self) -> List[str]:
        return [p for p, v in self.prices.items() if v.in_stock]

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for platform, pp in self.prices.items():
            rows.append({
                "Platform":        pp.label,
                "Price (₹)":       pp.price,
                "Delivery (₹)":    pp.delivery_fee,
                "Platform Fee (₹)":pp.platform_fee,
                "Surge (₹)":       pp.surge_fee,
                "Coupon Off (₹)":  pp.coupon_discount,
                "Total Cost (₹)":  pp.total_cost,
                "Discount (%)":    pp.discount_pct,
                "MRP (₹)":         pp.mrp,
                "Delivery (mins)": pp.delivery_mins,
                "In Stock":        "✅" if pp.in_stock else "❌",
            })
        return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────────────
# Query helpers
# ──────────────────────────────────────────────────────────────────────

def _build_platform_price(row: dict) -> PlatformPrice:
    return PlatformPrice(
        platform        = row["platform"],
        price           = row["price"],
        mrp             = row["mrp"] or row["price"],
        discount_pct    = row["discount_pct"],
        delivery_fee    = row["delivery_fee"],
        platform_fee    = row["platform_fee"],
        surge_fee       = row["surge_fee"],
        coupon_discount = row["coupon_discount"],
        in_stock        = bool(row["in_stock"]),
        delivery_mins   = row["delivery_mins"],
        quantity_str    = row["quantity_str"],
    )


def get_product_comparison(product_id: int) -> Optional[ProductComparison]:
    """
    Fetch a ProductComparison for *product_id* containing pricing
    from all four platforms.
    """
    product = fetchone(
        "SELECT id, name, category, brand, unit FROM products WHERE id = ?",
        (product_id,),
    )
    if not product:
        return None

    rows = fetchall(
        """
        SELECT platform, price, mrp, discount_pct, delivery_fee,
               platform_fee, surge_fee, coupon_discount, in_stock,
               delivery_mins, quantity_str
        FROM   platform_prices
        WHERE  product_id = ?
        ORDER  BY total_cost ASC
        """.replace(
            "ORDER  BY total_cost ASC",
            # SQLite: compute total_cost inline for ordering
            "ORDER BY (price + delivery_fee + platform_fee + surge_fee - coupon_discount) ASC",
        ),
        (product_id,),
    )

    comp = ProductComparison(
        product_id   = product["id"],
        product_name = product["name"],
        category     = product["category"],
        brand        = product["brand"] or "",
        unit         = product["unit"],
    )

    for row in rows:
        pp = _build_platform_price(dict(row))
        comp.prices[pp.platform] = pp

    return comp


def compare_multiple_products(product_ids: List[int]) -> List[ProductComparison]:
    """Return a list of ProductComparison objects for the given IDs."""
    results = []
    for pid in product_ids:
        comp = get_product_comparison(pid)
        if comp:
            results.append(comp)
    return results


def get_best_deals(limit: int = 10) -> pd.DataFrame:
    """
    Return the top *limit* products ranked by maximum savings
    (total_cost difference between most and least expensive platform).
    """
    rows = fetchall(
        """
        SELECT
            p.id,
            p.name,
            p.category,
            p.brand,
            p.unit,
            MIN(pp.price + pp.delivery_fee + pp.platform_fee
                + pp.surge_fee - pp.coupon_discount)  AS min_total,
            MAX(pp.price + pp.delivery_fee + pp.platform_fee
                + pp.surge_fee - pp.coupon_discount)  AS max_total,
            MIN(pp.price)                             AS min_price,
            MAX(pp.discount_pct)                      AS max_discount
        FROM   products p
        JOIN   platform_prices pp ON pp.product_id = p.id
        WHERE  pp.in_stock = 1
        GROUP  BY p.id
        HAVING COUNT(DISTINCT pp.platform) >= 2
        ORDER  BY (max_total - min_total) DESC
        LIMIT  ?
        """,
        (limit,),
    )

    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def get_platform_summary() -> pd.DataFrame:
    """
    Aggregate stats per platform: avg total cost, avg discount %,
    number of products, avg delivery time.
    """
    rows = fetchall(
        """
        SELECT
            platform,
            COUNT(DISTINCT product_id)                                   AS product_count,
            ROUND(AVG(price + delivery_fee + platform_fee
                      + surge_fee - coupon_discount), 2)                 AS avg_total_cost,
            ROUND(AVG(discount_pct), 1)                                  AS avg_discount_pct,
            ROUND(AVG(delivery_mins), 0)                                 AS avg_delivery_mins,
            SUM(CASE WHEN in_stock = 1 THEN 1 ELSE 0 END) * 100.0
                / COUNT(*)                                               AS stock_pct
        FROM   platform_prices
        GROUP  BY platform
        ORDER  BY avg_total_cost ASC
        """
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["platform_label"] = df["platform"].map(PLATFORM_LABELS)
    return df


def get_category_price_trends() -> pd.DataFrame:
    """Average price per category per platform (for dashboard charts)."""
    rows = fetchall(
        """
        SELECT
            p.category,
            pp.platform,
            ROUND(AVG(pp.price), 2)                                 AS avg_price,
            ROUND(AVG(pp.price + pp.delivery_fee + pp.platform_fee
                      + pp.surge_fee - pp.coupon_discount), 2)      AS avg_total
        FROM   platform_prices pp
        JOIN   products p ON p.id = pp.product_id
        WHERE  pp.in_stock = 1
        GROUP  BY p.category, pp.platform
        ORDER  BY p.category, avg_total
        """
    )
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
