"""
modules/recommendation_engine.py
──────────────────────────────────────────────────────────────────────
Content-based recommendation engine using TF-IDF on product
name + category + brand + tags.

Design principles:
  • No data leakage – similarity is computed only on product metadata,
    not on prices (which would be circular / misleading).
  • TF-IDF matrix is built lazily and cached in-process.
  • Thread-safe singleton via a module-level lock.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database.db_manager import fetchall

logger = logging.getLogger(__name__)

_lock   = threading.Lock()
_cache: Optional[Dict] = None   # {df, matrix, vectorizer, id_to_idx, idx_to_id}


# ──────────────────────────────────────────────────────────────────────
# Internal: build / retrieve TF-IDF cache
# ──────────────────────────────────────────────────────────────────────

def _build_corpus_text(row: dict) -> str:
    """
    Concatenate product fields into a single document for TF-IDF.
    Repeat important fields (name, category) for weighting.
    """
    import json as _json
    name     = str(row.get("name",        "") or "")
    category = str(row.get("category",    "") or "")
    brand    = str(row.get("brand",       "") or "")
    desc     = str(row.get("description", "") or "")
    tags_raw = row.get("tags", "") or ""
    try:
        tags = " ".join(_json.loads(tags_raw)) if tags_raw else ""
    except Exception:
        tags = str(tags_raw)

    # Weight: name×3, category×2, brand×2, tags×1, desc×1
    return f"{name} {name} {name} {category} {category} {brand} {brand} {tags} {desc}".lower()


def _get_cache() -> Optional[Dict]:
    """Return the in-memory TF-IDF cache, building it if needed."""
    global _cache
    if _cache is not None:
        return _cache

    with _lock:
        if _cache is not None:
            return _cache  # double-check after acquiring lock

        rows = fetchall(
            "SELECT id, name, category, brand, description, tags FROM products"
        )
        if not rows:
            logger.warning("No products found – recommendation engine not initialised.")
            return None

        df = pd.DataFrame([dict(r) for r in rows])
        corpus = df.apply(_build_corpus_text, axis=1).tolist()

        vectorizer = TfidfVectorizer(
            ngram_range  = (1, 2),
            min_df       = 1,
            max_features = 5000,
            sublinear_tf = True,
        )
        matrix = vectorizer.fit_transform(corpus)

        id_to_idx = {int(pid): idx for idx, pid in enumerate(df["id"])}
        idx_to_id = {idx: int(pid) for idx, pid in enumerate(df["id"])}

        _cache = {
            "df":         df,
            "matrix":     matrix,
            "vectorizer": vectorizer,
            "id_to_idx":  id_to_idx,
            "idx_to_id":  idx_to_id,
        }
        logger.info(
            "TF-IDF recommendation engine built: %d products, matrix %s",
            len(df), matrix.shape,
        )
        return _cache


def invalidate_cache() -> None:
    """Call this when product catalogue changes."""
    global _cache
    with _lock:
        _cache = None


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def get_similar_products(
    product_id: int,
    n: int = 6,
    same_category: bool = False,
) -> pd.DataFrame:
    """
    Return the *n* most similar products to *product_id*.

    Parameters
    ----------
    product_id    : anchor product
    n             : number of recommendations (excluding the anchor)
    same_category : if True, restrict to the same category
    """
    cache = _get_cache()
    if cache is None:
        return pd.DataFrame()

    idx = cache["id_to_idx"].get(product_id)
    if idx is None:
        logger.warning("product_id %d not found in TF-IDF index.", product_id)
        return pd.DataFrame()

    # Row cosine similarity against the whole matrix
    query_vec = cache["matrix"][idx]
    sims      = cosine_similarity(query_vec, cache["matrix"]).flatten()

    # Sort descending; skip index 0 (self) if it's the anchor
    order = np.argsort(sims)[::-1]

    results = []
    for i in order:
        if i == idx:
            continue   # skip self
        pid  = cache["idx_to_id"][i]
        meta = cache["df"].iloc[i]

        if same_category and meta["category"] != cache["df"].iloc[idx]["category"]:
            continue

        results.append({
            "product_id": pid,
            "name":       meta["name"],
            "category":   meta["category"],
            "brand":      meta["brand"] or "",
            "similarity": round(float(sims[i]), 4),
        })

        if len(results) >= n:
            break

    return pd.DataFrame(results)


def get_category_recommendations(
    category: str,
    n: int = 8,
    exclude_ids: Optional[List[int]] = None,
) -> pd.DataFrame:
    """
    Return the *n* top products in *category* ranked by best deal
    (highest average discount across platforms).
    """
    exclude_ids = exclude_ids or []
    placeholders = ",".join("?" * len(exclude_ids)) if exclude_ids else "0"

    rows = fetchall(
        f"""
        SELECT
            p.id            AS product_id,
            p.name,
            p.category,
            p.brand,
            p.unit,
            MIN(pp.price)   AS min_price,
            AVG(pp.discount_pct) AS avg_discount
        FROM   products p
        JOIN   platform_prices pp ON pp.product_id = p.id
        WHERE  p.category = ?
          AND  pp.in_stock = 1
          AND  p.id NOT IN ({placeholders if exclude_ids else '0'})
        GROUP  BY p.id
        ORDER  BY avg_discount DESC
        LIMIT  ?
        """,
        (category, *exclude_ids, n) if exclude_ids else (category, n),
    )

    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def get_best_deals_recommendations(n: int = 10) -> pd.DataFrame:
    """
    Top *n* products with the highest savings (max_total - min_total)
    across platforms.  No data leakage: uses price differences, not
    user behaviour (which we don't track).
    """
    rows = fetchall(
        """
        SELECT
            p.id   AS product_id,
            p.name,
            p.category,
            p.brand,
            p.unit,
            MIN(pp.price + pp.delivery_fee + pp.platform_fee
                + pp.surge_fee - pp.coupon_discount) AS min_total,
            MAX(pp.price + pp.delivery_fee + pp.platform_fee
                + pp.surge_fee - pp.coupon_discount) AS max_total,
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
        (n,),
    )
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])
    df["potential_savings"] = (df["max_total"] - df["min_total"]).clip(lower=0)
    return df


def search_by_query_vector(
    query: str,
    n: int = 8,
) -> pd.DataFrame:
    """
    Use TF-IDF to find products semantically similar to a free-text
    query string (used by the AI Assistant page).
    """
    cache = _get_cache()
    if cache is None:
        return pd.DataFrame()

    query_vec = cache["vectorizer"].transform([query.lower()])
    sims      = cosine_similarity(query_vec, cache["matrix"]).flatten()
    order     = np.argsort(sims)[::-1][:n]

    results = []
    for i in order:
        if sims[i] < 0.05:
            break
        pid  = cache["idx_to_id"][i]
        meta = cache["df"].iloc[i]
        results.append({
            "product_id": pid,
            "name":       meta["name"],
            "category":   meta["category"],
            "brand":      meta["brand"] or "",
            "relevance":  round(float(sims[i]), 4),
        })

    return pd.DataFrame(results)
