"""
database/db_manager.py
─────────────────────────────────────────────────────────────────────────
Thread-safe SQLite connection manager with WAL mode, context managers,
parameterised queries (preventing SQL injection), and helper utilities.
"""

import sqlite3
import threading
import os
import logging
from contextlib import contextmanager
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "pricepulse.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

# Thread-local storage so each thread gets its own connection
_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Return (or create) the per-thread SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -8000;")   # 8 MB cache
        _local.conn = conn
    return _local.conn


@contextmanager
def get_db():
    """
    Context manager that yields a (conn, cursor) tuple.
    Commits on success, rolls back on exception.

    Usage:
        with get_db() as (conn, cur):
            cur.execute("SELECT …", params)
    """
    conn = _get_connection()
    cur = conn.cursor()
    try:
        yield conn, cur
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("DB error – rolled back: %s", exc, exc_info=True)
        raise
    finally:
        cur.close()


def initialise_db() -> None:
    """
    Create all tables and indexes from schema.sql if they don't exist.
    Safe to call multiple times (idempotent).
    """
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        ddl = fh.read()

    conn = _get_connection()
    # executescript auto-commits, which is fine for DDL
    conn.executescript(ddl)
    logger.info("Database initialised at %s", DB_PATH)


def fetchall(sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
    """Execute *sql* with *params* and return all rows."""
    with get_db() as (_, cur):
        cur.execute(sql, params)
        return cur.fetchall()


def fetchone(sql: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
    """Execute *sql* with *params* and return a single row or None."""
    with get_db() as (_, cur):
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: Tuple = ()) -> int:
    """
    Execute a DML statement (INSERT / UPDATE / DELETE).
    Returns lastrowid for INSERT, otherwise rowcount.
    """
    with get_db() as (conn, cur):
        cur.execute(sql, params)
        return cur.lastrowid or cur.rowcount


def executemany(sql: str, param_seq: List[Tuple]) -> None:
    """Batch-execute a DML statement for a sequence of parameter tuples."""
    with get_db() as (_, cur):
        cur.executemany(sql, param_seq)
