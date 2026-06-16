"""
modules/alerts_manager.py
──────────────────────────────────────────────────────────────────────
Price alert management: create, list, trigger, and delete alerts.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import pandas as pd

from database.db_manager import fetchall, fetchone, execute

logger = logging.getLogger(__name__)


def create_alert(
    user_id: int,
    product_id: int,
    target_price: float,
    platform: str = "any",
) -> int:
    """Create a new price alert. Returns the alert ID."""
    if platform not in ("zepto", "blinkit", "instamart", "bigbasket", "any"):
        raise ValueError(f"Invalid platform: {platform!r}")
    if target_price < 0:
        raise ValueError("target_price must be ≥ 0")

    alert_id = execute(
        """
        INSERT INTO alerts (user_id, product_id, platform, target_price)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, product_id, platform, round(target_price, 2)),
    )
    return alert_id


def get_user_alerts(user_id: int) -> pd.DataFrame:
    """Return all active alerts for a user."""
    rows = fetchall(
        """
        SELECT
            a.id,
            p.name          AS product_name,
            p.unit,
            a.platform,
            a.target_price,
            a.is_active,
            a.triggered,
            a.triggered_at,
            a.created_at,
            MIN(pp.price + pp.delivery_fee + pp.platform_fee
                + pp.surge_fee - pp.coupon_discount) AS current_best_total,
            MIN(pp.price)                             AS current_best_price
        FROM   alerts a
        JOIN   products p        ON p.id   = a.product_id
        LEFT JOIN platform_prices pp ON pp.product_id = a.product_id
                                    AND pp.in_stock = 1
        WHERE  a.user_id = ?
        GROUP  BY a.id
        ORDER  BY a.created_at DESC
        """,
        (user_id,),
    )
    df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    if not df.empty:
        df["gap"] = (df["current_best_price"] - df["target_price"]).round(2)
        df["triggered_label"] = df["triggered"].map({0: "Pending", 1: "Triggered"})
    return df


def check_and_trigger_alerts(user_id: int) -> List[dict]:
    """
    Check all active alerts and mark as triggered if price ≤ target.
    Returns list of newly triggered alerts.
    """
    rows = fetchall(
        """
        SELECT
            a.id,
            a.product_id,
            a.platform,
            a.target_price,
            p.name       AS product_name,
            MIN(CASE WHEN (a.platform = 'any' OR pp.platform = a.platform)
                          AND pp.in_stock = 1
                     THEN pp.price + pp.delivery_fee + pp.platform_fee
                          + pp.surge_fee - pp.coupon_discount
                     ELSE NULL END) AS best_total
        FROM   alerts a
        JOIN   products p ON p.id = a.product_id
        JOIN   platform_prices pp ON pp.product_id = a.product_id
        WHERE  a.user_id = ?
          AND  a.is_active = 1
          AND  a.triggered = 0
        GROUP  BY a.id
        """,
        (user_id,),
    )

    triggered = []
    for row in rows:
        best = row["best_total"]
        if best is not None and best <= row["target_price"]:
            execute(
                "UPDATE alerts SET triggered = 1, triggered_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            triggered.append({
                "alert_id":    row["id"],
                "product":     row["product_name"],
                "target":      row["target_price"],
                "current":     best,
            })

    return triggered


def delete_alert(alert_id: int, user_id: int) -> bool:
    """Delete an alert (ensures ownership). Returns True if deleted."""
    rows_affected = execute(
        "DELETE FROM alerts WHERE id = ? AND user_id = ?",
        (alert_id, user_id),
    )
    return rows_affected > 0


def deactivate_alert(alert_id: int, user_id: int) -> bool:
    """Soft-delete an alert."""
    rows_affected = execute(
        "UPDATE alerts SET is_active = 0 WHERE id = ? AND user_id = ?",
        (alert_id, user_id),
    )
    return rows_affected > 0
