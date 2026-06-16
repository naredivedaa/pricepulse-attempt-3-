"""
utils/auth.py
──────────────────────────────────────────────────────────────────────
Authentication utilities using bcrypt password hashing.
Session state keys:
    st.session_state["user_id"]   → int  (None if logged out)
    st.session_state["username"]  → str
    st.session_state["logged_in"] → bool
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import bcrypt
import streamlit as st

from database.db_manager import fetchone, execute

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Session helpers
# ──────────────────────────────────────────────────────────────────────

def init_session() -> None:
    """Initialise auth-related session state keys (idempotent)."""
    defaults = {
        "logged_in": False,
        "user_id":   None,
        "username":  None,
        "city":      None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)


def current_user_id() -> Optional[int]:
    return st.session_state.get("user_id")


def current_username() -> Optional[str]:
    return st.session_state.get("username")


# ──────────────────────────────────────────────────────────────────────
# Password helpers
# ──────────────────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def login(username_or_email: str, password: str) -> Tuple[bool, str]:
    """
    Attempt login.
    Returns (success: bool, message: str).
    Uses parameterised queries to prevent SQL injection.
    """
    if not username_or_email.strip() or not password:
        return False, "Username/email and password are required."

    row = fetchone(
        """
        SELECT id, username, password_hash, city
        FROM   users
        WHERE  LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)
        """,
        (username_or_email.strip(), username_or_email.strip()),
    )

    if not row:
        return False, "User not found."

    if not _verify_password(password, row["password_hash"]):
        return False, "Incorrect password."

    # Update last_login
    execute(
        "UPDATE users SET last_login = datetime('now') WHERE id = ?",
        (row["id"],),
    )

    # Set session
    st.session_state["logged_in"] = True
    st.session_state["user_id"]   = row["id"]
    st.session_state["username"]  = row["username"]
    st.session_state["city"]      = row["city"] or ""

    return True, f"Welcome back, {row['username']}!"


def register(username: str, email: str, password: str, city: str = "") -> Tuple[bool, str]:
    """
    Register a new user.
    Returns (success: bool, message: str).
    """
    username = username.strip()
    email    = email.strip().lower()

    if not username or not email or not password:
        return False, "All fields are required."

    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    if fetchone("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,)):
        return False, "Username already taken."

    if fetchone("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,)):
        return False, "Email already registered."

    pw_hash = _hash_password(password)
    try:
        user_id = execute(
            "INSERT INTO users (username, email, password_hash, city) VALUES (?,?,?,?)",
            (username, email, pw_hash, city),
        )
        # Auto-login
        st.session_state["logged_in"] = True
        st.session_state["user_id"]   = user_id
        st.session_state["username"]  = username
        st.session_state["city"]      = city
        return True, f"Account created! Welcome, {username}!"
    except Exception as exc:
        logger.error("Registration error: %s", exc)
        return False, "Registration failed. Please try again."


def logout() -> None:
    """Clear auth session state."""
    for key in ["logged_in", "user_id", "username", "city"]:
        st.session_state[key] = None if key != "logged_in" else False
