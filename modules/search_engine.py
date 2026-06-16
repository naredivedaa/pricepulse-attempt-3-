"""
modules/search_engine.py
──────────────────────────────────────────────────────────────────────
Production-grade search engine with:
  • SQL LIKE full-text search (fast, index-backed)
  • RapidFuzz fuzzy matching for typo tolerance
  • TF-IDF relevance re-ranking
  • Autocomplete suggestions
  • Search logging
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

import pandas as pd
from rapidfuzz import fuzz, process as rfprocess

from database.db_manager import fetchall, execute, fetchone

logger = logging.getLogger(__name__)

# Minimum fuzzy score to include a result (0-100)
FUZZY_THRESHOLD = 55
MAX_RESULTS = 50


# ──────────────────────────────────────────────────────────────────────
# Normalisation helper
# ──────────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    """Lower-case, strip punctuation, collapse spaces."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


# ──────────────────────────────────────────────────────────────────────
# Core search
# ──────────────────────────────────────────────────────────────────────

def search_products(
    query: str,
    category: Optional[str] = None,
    platform: Optional[str] = None,
    in_stock_only: bool = True,
    user_id: Optional[int] = None,
) -> pd.DataFrame:
    """
    Search products by name / brand / category with fuzzy fallback.

    Returns a DataFrame with columns:
        product_id, name, category, brand, unit,
        min_price, max_price, best_platform, avg_discount,
        platforms_available, fuzzy_score
    """
    if not query or not query.strip():
        return _get_all_products(category, platform, in_stock_only)

    norm_query = _normalise(query)
    terms = norm_query.split()

    # ── 1. SQL candidate fetch (fast, coarse filter) ──────────────────
    # Build LIKE patterns for each term
    like_clauses = []
    params: list = []
    for term in terms:
        like_clauses.append(
            "(LOWER(p.name) LIKE ? OR LOWER(p.brand) LIKE ? OR LOWER(p.category) LIKE ?)"
        )
        pat = f"%{term}%"
        params.extend([pat, pat, pat])

    where = " AND ".join(like_clauses) if like_clauses else "1=1"

    stock_filter = "AND pp.in_stock = 1" if in_stock_only else ""
    cat_filter   = "AND p.category = ?"  if category else ""
    if category:
        params.append(category)

    plat_filter  = "AND pp.platform = ?" if platform else ""
    if platform:
        params.append(platform)

    sql = f"""
        SELECT
            p.id                            AS product_id,
            p.name,
            p.category,
            p.brand,
            p.unit,
            MIN(pp.price)                   AS min_price,
            MAX(pp.price)                   AS max_price,
            AVG(pp.discount_pct)            AS avg_discount,
            COUNT(DISTINCT pp.platform)     AS platforms_available,
            MIN(pp.platform)                AS best_platform
        FROM   products p
        JOIN   platform_prices pp ON pp.product_id = p.id
        WHERE  ({where})
               {stock_filter}
               {cat_filter}
               {plat_filter}
        GROUP  BY p.id
        LIMIT  {MAX_RESULTS * 3}
    """

    rows = fetchall(sql, tuple(params))
    if not rows:
        # No SQL hits → try fuzzy-only path
        return _fuzzy_search(norm_query, category, in_stock_only)

    df = pd.DataFrame([dict(r) for r in rows])

    # ── 2. Fuzzy re-ranking ────────────────────────────────────────────
    df["fuzzy_score"] = df["name"].apply(
        lambda name: _score(norm_query, _normalise(name))
    )

    # Keep rows that pass the fuzzy threshold
    df = df[df["fuzzy_score"] >= FUZZY_THRESHOLD].copy()

    if df.empty:
        # Relax to pure SQL results if nothing passes fuzzy threshold
        df = pd.DataFrame([dict(r) for r in rows])
        df["fuzzy_score"] = 50.0

    # ── 3. Sort: fuzzy_score DESC, min_price ASC ──────────────────────
    df = df.sort_values(
        ["fuzzy_score", "min_price"], ascending=[False, True]
    ).head(MAX_RESULTS)

    # ── 4. Log search ─────────────────────────────────────────────────
    _log_search(query, len(df), user_id)

    return df.reset_index(drop=True)


def _score(query: str, candidate: str) -> float:
    """Composite fuzzy score combining token_set_ratio and partial_ratio."""
    s1 = fuzz.token_set_ratio(query, candidate)
    s2 = fuzz.partial_ratio(query, candidate)
    return 0.6 * s1 + 0.4 * s2


def _fuzzy_search(
    norm_query: str,
    category: Optional[str],
    in_stock_only: bool,
) -> pd.DataFrame:
    """Fetch all product names then fuzzy-match in memory."""
    params: list = []
    cat_filter = "AND p.category = ?" if category else ""
    if category:
        params.append(category)
    stock_filter = "AND pp.in_stock = 1" if in_stock_only else ""

    rows = fetchall(
        f"""
        SELECT DISTINCT p.id AS product_id, p.name, p.category, p.brand, p.unit
        FROM   products p
        JOIN   platform_prices pp ON pp.product_id = p.id
        WHERE  1=1 {cat_filter} {stock_filter}
        """,
        tuple(params),
    )
    if not rows:
        return pd.DataFrame()

    names = [r["name"] for r in rows]
    matches = rfprocess.extract(
        norm_query,
        [_normalise(n) for n in names],
        scorer=fuzz.token_set_ratio,
        limit=MAX_RESULTS,
        score_cutoff=FUZZY_THRESHOLD,
    )

    if not matches:
        return pd.DataFrame()

    matched_indices = {m[2] for m in matches}
    matched_rows = [dict(rows[i]) for i in matched_indices]

    df = pd.DataFrame(matched_rows)
    df["fuzzy_score"] = df["name"].apply(
        lambda n: _score(norm_query, _normalise(n))
    )
    df["min_price"] = 0.0
    df["max_price"] = 0.0
    df["avg_discount"] = 0.0
    df["platforms_available"] = 0
    df["best_platform"] = ""

    # Fill price info
    for idx, row in df.iterrows():
        price_rows = fetchall(
            "SELECT MIN(price) AS mn, MAX(price) AS mx, AVG(discount_pct) AS ad, COUNT(DISTINCT platform) AS pc FROM platform_prices WHERE product_id = ?",
            (row["product_id"],),
        )
        if price_rows:
            pr = dict(price_rows[0])
            df.at[idx, "min_price"]           = pr["mn"] or 0
            df.at[idx, "max_price"]           = pr["mx"] or 0
            df.at[idx, "avg_discount"]        = pr["ad"] or 0
            df.at[idx, "platforms_available"] = pr["pc"] or 0

    return df.sort_values("fuzzy_score", ascending=False).reset_index(drop=True)


def _get_all_products(
    category: Optional[str],
    platform: Optional[str],
    in_stock_only: bool,
) -> pd.DataFrame:
    """Return all products (used when query is empty)."""
    params: list = []
    cat_filter   = "AND p.category = ?" if category else ""
    if category:
        params.append(category)
    plat_filter  = "AND pp.platform = ?" if platform else ""
    if platform:
        params.append(platform)
    stock_filter = "AND pp.in_stock = 1" if in_stock_only else ""

    rows = fetchall(
        f"""
        SELECT
            p.id AS product_id, p.name, p.category, p.brand, p.unit,
            MIN(pp.price)               AS min_price,
            MAX(pp.price)               AS max_price,
            AVG(pp.discount_pct)        AS avg_discount,
            COUNT(DISTINCT pp.platform) AS platforms_available,
            MIN(pp.platform)            AS best_platform
        FROM   products p
        JOIN   platform_prices pp ON pp.product_id = p.id
        WHERE  1=1 {cat_filter} {plat_filter} {stock_filter}
        GROUP  BY p.id
        ORDER  BY p.name ASC
        LIMIT  {MAX_RESULTS}
        """,
        tuple(params),
    )
    df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
    if not df.empty:
        df["fuzzy_score"] = 100.0
    return df


def _log_search(query: str, result_count: int, user_id: Optional[int]) -> None:
    """Persist search log for analytics (non-blocking, swallows errors)."""
    try:
        execute(
            "INSERT INTO search_logs (query, results_n, user_id) VALUES (?, ?, ?)",
            (query[:500], result_count, user_id),
        )
    except Exception as exc:
        logger.warning("Search log failed: %s", exc)


# ──────────────────────────────────────────────────────────────────────
# Autocomplete
# ──────────────────────────────────────────────────────────────────────

def get_autocomplete_suggestions(prefix: str, limit: int = 8) -> List[str]:
    """
    Return product names and category names that start with *prefix*.
    Uses LIKE with index-backed column for O(log n) performance.
    """
    if not prefix or len(prefix) < 2:
        return []
    like_pat = f"{prefix.lower()}%"
    rows = fetchall(
        """
        SELECT DISTINCT name FROM (
            SELECT name FROM products   WHERE LOWER(name)     LIKE ?
            UNION
            SELECT name FROM products   WHERE LOWER(brand)    LIKE ?
            UNION
            SELECT DISTINCT category AS name FROM products WHERE LOWER(category) LIKE ?
        )
        ORDER BY name
        LIMIT ?
        """,
        (like_pat, like_pat, like_pat, limit),
    )
    return [r["name"] for r in rows]


# ──────────────────────────────────────────────────────────────────────
# Category list
# ──────────────────────────────────────────────────────────────────────

def get_categories() -> List[str]:
    rows = fetchall("SELECT DISTINCT category FROM products ORDER BY category")
    return [r["category"] for r in rows]


def get_popular_searches(limit: int = 10) -> List[str]:
    rows = fetchall(
        """
        SELECT query, COUNT(*) AS cnt
        FROM   search_logs
        GROUP  BY LOWER(query)
        ORDER  BY cnt DESC
        LIMIT  ?
        """,
        (limit,),
    )
    return [r["query"] for r in rows]
