"""
modules/basket_optimizer.py
──────────────────────────────────────────────────────────────────────
Basket optimisation engine with two strategies:
  1. Single-platform  – find the one platform with the lowest TOTAL bill
     (item costs + one delivery fee + platform fee + surge).
  2. Split-basket     – assign each item to its cheapest individual
     platform, then add per-platform fixed fees only once.

Total cost formula (consistent with comparison_engine.py):
    item_total = price + surge_fee - coupon_discount
    platform_total = Σ item_totals + delivery_fee + platform_fee
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from database.db_manager import fetchall, execute

logger = logging.getLogger(__name__)

PLATFORMS = ["zepto", "blinkit", "instamart", "bigbasket"]

PLATFORM_LABELS = {
    "zepto":     "Zepto",
    "blinkit":   "Blinkit",
    "instamart": "Swiggy Instamart",
    "bigbasket": "BigBasket",
}


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class BasketItem:
    product_id:   int
    product_name: str
    qty:          int
    platform:     str
    price:        float
    delivery_fee: float
    platform_fee: float
    surge_fee:    float
    coupon_disc:  float
    in_stock:     bool
    unit:         str

    @property
    def item_subtotal(self) -> float:
        """Item cost before platform-level fixed fees."""
        return max(0.0, (self.price + self.surge_fee - self.coupon_disc) * self.qty)


@dataclass
class PlatformBasket:
    platform:     str
    items:        List[BasketItem] = field(default_factory=list)
    missing:      List[str]        = field(default_factory=list)  # product names not available

    @property
    def items_total(self) -> float:
        return sum(i.item_subtotal for i in self.items)

    @property
    def delivery_fee(self) -> float:
        return self.items[0].delivery_fee if self.items else 0.0

    @property
    def platform_fee(self) -> float:
        return self.items[0].platform_fee if self.items else 0.0

    @property
    def total_cost(self) -> float:
        return self.items_total + self.delivery_fee + self.platform_fee

    @property
    def label(self) -> str:
        return PLATFORM_LABELS.get(self.platform, self.platform.title())


@dataclass
class OptimisationResult:
    strategy:     str            # "single" | "split"
    total_cost:   float
    savings_vs_worst: float
    platform_baskets: Dict[str, PlatformBasket]
    missing_items:    List[str]  # products unavailable on any platform

    @property
    def winning_platform(self) -> Optional[str]:
        if self.strategy == "single":
            return next(iter(self.platform_baskets), None)
        return None


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _fetch_basket_prices(
    product_ids: List[int],
) -> Dict[int, Dict[str, dict]]:
    """
    Return {product_id: {platform: price_row}} for all requested products.
    Uses a single SQL query for efficiency.
    """
    if not product_ids:
        return {}

    placeholders = ",".join("?" * len(product_ids))
    rows = fetchall(
        f"""
        SELECT
            pp.product_id,
            pp.platform,
            p.name         AS product_name,
            p.unit,
            pp.price,
            pp.delivery_fee,
            pp.platform_fee,
            pp.surge_fee,
            pp.coupon_discount,
            pp.in_stock
        FROM   platform_prices pp
        JOIN   products p ON p.id = pp.product_id
        WHERE  pp.product_id IN ({placeholders})
        ORDER  BY pp.product_id, pp.platform
        """,
        tuple(product_ids),
    )

    result: Dict[int, Dict[str, dict]] = {}
    for row in rows:
        pid = row["product_id"]
        result.setdefault(pid, {})[row["platform"]] = dict(row)
    return result


def _make_basket_item(row: dict, qty: int) -> BasketItem:
    return BasketItem(
        product_id   = row["product_id"],
        product_name = row["product_name"],
        qty          = max(1, qty),
        platform     = row["platform"],
        price        = max(0.0, float(row["price"])),
        delivery_fee = max(0.0, float(row["delivery_fee"])),
        platform_fee = max(0.0, float(row["platform_fee"])),
        surge_fee    = max(0.0, float(row["surge_fee"])),
        coupon_disc  = max(0.0, float(row["coupon_discount"])),
        in_stock     = bool(row["in_stock"]),
        unit         = row["unit"],
    )


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def optimise_single_platform(
    basket: List[Tuple[int, int]],   # [(product_id, qty), …]
) -> OptimisationResult:
    """
    Find the single platform that minimises total basket cost.
    Products unavailable on a platform are listed in *missing*.
    """
    product_ids = [pid for pid, _ in basket]
    qty_map     = {pid: qty for pid, qty in basket}
    prices      = _fetch_basket_prices(product_ids)

    platform_baskets: Dict[str, PlatformBasket] = {}
    globally_missing: List[str] = []

    for pid in product_ids:
        if pid not in prices:
            name = f"Product #{pid}"
            globally_missing.append(name)

    for platform in PLATFORMS:
        pb = PlatformBasket(platform=platform)
        for pid, qty in basket:
            if pid not in prices:
                continue
            plat_prices = prices[pid]
            if platform not in plat_prices:
                # Product not listed on this platform
                name = plat_prices.get(
                    next(iter(plat_prices), None), {}
                ).get("product_name", f"Product #{pid}")
                if isinstance(name, dict):
                    name = f"Product #{pid}"
                pb.missing.append(str(name))
                continue
            row = plat_prices[platform]
            if not row["in_stock"]:
                pb.missing.append(row["product_name"])
                continue
            pb.items.append(_make_basket_item(row, qty))

        platform_baskets[platform] = pb

    # Rank platforms: prefer those with fewer missing items, then by cost
    def _rank(pb: PlatformBasket) -> Tuple[int, float]:
        return (len(pb.missing), pb.total_cost)

    sorted_platforms = sorted(platform_baskets.values(), key=_rank)
    best = sorted_platforms[0]
    worst = sorted_platforms[-1]

    savings = max(0.0, worst.total_cost - best.total_cost)

    return OptimisationResult(
        strategy          = "single",
        total_cost        = best.total_cost,
        savings_vs_worst  = savings,
        platform_baskets  = {best.platform: best},
        missing_items     = globally_missing + best.missing,
    )


def optimise_split_basket(
    basket: List[Tuple[int, int]],
) -> OptimisationResult:
    """
    Split-basket optimisation: each item is ordered from the cheapest
    platform that has it in stock. Fixed fees (delivery + platform)
    are counted once per platform used.
    """
    product_ids = [pid for pid, _ in basket]
    qty_map     = {pid: qty for pid, qty in basket}
    prices      = _fetch_basket_prices(product_ids)

    split_baskets: Dict[str, PlatformBasket] = {}
    missing_items: List[str] = []

    for pid, qty in basket:
        if pid not in prices:
            missing_items.append(f"Product #{pid}")
            continue

        plat_data = prices[pid]
        # Filter to in-stock rows, then pick cheapest by item_subtotal
        in_stock_rows = {
            plat: row
            for plat, row in plat_data.items()
            if row["in_stock"]
        }

        if not in_stock_rows:
            # Out of stock everywhere
            name = next(iter(plat_data.values()), {}).get("product_name", f"Product #{pid}")
            missing_items.append(str(name))
            continue

        # Item-level cost = price + surge - coupon (×qty)
        def item_cost(row: dict) -> float:
            p  = max(0.0, float(row["price"]))
            su = max(0.0, float(row["surge_fee"]))
            cd = max(0.0, float(row["coupon_discount"]))
            return (p + su - cd) * qty

        best_plat = min(in_stock_rows, key=lambda pl: item_cost(in_stock_rows[pl]))
        best_row  = in_stock_rows[best_plat]

        pb = split_baskets.setdefault(best_plat, PlatformBasket(platform=best_plat))
        pb.items.append(_make_basket_item(best_row, qty))

    # Total cost = sum of all item_subtotals + per-platform fixed fees
    total = sum(pb.total_cost for pb in split_baskets.values())

    # Savings vs single-worst
    single_result = optimise_single_platform(basket)
    worst_single  = single_result.savings_vs_worst + single_result.total_cost
    savings = max(0.0, worst_single - total)

    return OptimisationResult(
        strategy          = "split",
        total_cost        = total,
        savings_vs_worst  = savings,
        platform_baskets  = split_baskets,
        missing_items     = missing_items,
    )


def compare_strategies(
    basket: List[Tuple[int, int]],
) -> Dict[str, OptimisationResult]:
    """Run both strategies and return both results."""
    return {
        "single": optimise_single_platform(basket),
        "split":  optimise_split_basket(basket),
    }


def save_basket_history(
    session_id: str,
    basket: List[Tuple[int, int]],
    result: OptimisationResult,
    user_id: Optional[int] = None,
) -> None:
    """Persist basket + result to basket_history table."""
    try:
        basket_json = json.dumps([{"product_id": pid, "qty": qty} for pid, qty in basket])
        result_json = json.dumps({
            "strategy":   result.strategy,
            "total_cost": result.total_cost,
            "platforms":  list(result.platform_baskets.keys()),
        })
        execute(
            """
            INSERT INTO basket_history
                (user_id, session_id, basket_json, result_json, total_cost, platform)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                session_id,
                basket_json,
                result_json,
                result.total_cost,
                result.winning_platform or "split",
            ),
        )
    except Exception as exc:
        logger.warning("Could not save basket history: %s", exc)


def result_to_dataframe(result: OptimisationResult) -> pd.DataFrame:
    """Flatten an OptimisationResult into a product-level DataFrame."""
    rows = []
    for platform, pb in result.platform_baskets.items():
        for item in pb.items:
            rows.append({
                "Platform":         PLATFORM_LABELS.get(platform, platform),
                "Product":          item.product_name,
                "Qty":              item.qty,
                "Unit Price (₹)":   item.price,
                "Subtotal (₹)":     item.item_subtotal,
                "Surge (₹)":        item.surge_fee,
                "Coupon Off (₹)":   item.coupon_disc,
                "Delivery Fee (₹)": item.delivery_fee,
                "Platform Fee (₹)": item.platform_fee,
            })
    return pd.DataFrame(rows)
