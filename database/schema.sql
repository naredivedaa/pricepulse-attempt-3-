-- PricePulse Database Schema
-- Production-grade SQLite schema with proper constraints and indexes

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

-- ─────────────────────────────────────────────
-- PRODUCTS TABLE
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT 'General',
    brand       TEXT,
    unit        TEXT    NOT NULL DEFAULT 'unit',
    image_url   TEXT,
    description TEXT,
    tags        TEXT,   -- JSON array stored as text
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_products_name     ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_brand    ON products(brand);

-- ─────────────────────────────────────────────
-- PLATFORM PRICES TABLE
-- platform must be one of: zepto | blinkit | instamart | bigbasket
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS platform_prices (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id       INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    platform         TEXT    NOT NULL CHECK (platform IN ('zepto','blinkit','instamart','bigbasket')),
    price            REAL    NOT NULL CHECK (price >= 0),
    mrp              REAL    CHECK (mrp >= 0),
    discount_pct     REAL    NOT NULL DEFAULT 0 CHECK (discount_pct >= 0 AND discount_pct <= 100),
    delivery_fee     REAL    NOT NULL DEFAULT 0 CHECK (delivery_fee >= 0),
    platform_fee     REAL    NOT NULL DEFAULT 0 CHECK (platform_fee >= 0),
    surge_fee        REAL    NOT NULL DEFAULT 0 CHECK (surge_fee >= 0),
    coupon_discount  REAL    NOT NULL DEFAULT 0 CHECK (coupon_discount >= 0),
    in_stock         INTEGER NOT NULL DEFAULT 1 CHECK (in_stock IN (0,1)),
    delivery_mins    INTEGER NOT NULL DEFAULT 30 CHECK (delivery_mins > 0),
    quantity_str     TEXT    NOT NULL DEFAULT '1 unit',
    scraped_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pp_product_id ON platform_prices(product_id);
CREATE INDEX IF NOT EXISTS idx_pp_platform   ON platform_prices(platform);
CREATE INDEX IF NOT EXISTS idx_pp_price      ON platform_prices(price);

-- Unique constraint: one row per product per platform
CREATE UNIQUE INDEX IF NOT EXISTS idx_pp_unique ON platform_prices(product_id, platform);

-- ─────────────────────────────────────────────
-- USERS TABLE
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT    NOT NULL UNIQUE,
    email        TEXT    NOT NULL UNIQUE,
    password_hash TEXT   NOT NULL,
    pincode      TEXT,
    city         TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login   TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ─────────────────────────────────────────────
-- ALERTS TABLE
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id   INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    platform     TEXT    CHECK (platform IN ('zepto','blinkit','instamart','bigbasket','any')),
    target_price REAL    NOT NULL CHECK (target_price >= 0),
    is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    triggered    INTEGER NOT NULL DEFAULT 0 CHECK (triggered IN (0,1)),
    triggered_at TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_user_id    ON alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_product_id ON alerts(product_id);
CREATE INDEX IF NOT EXISTS idx_alerts_active     ON alerts(is_active);

-- ─────────────────────────────────────────────
-- BASKET HISTORY TABLE
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS basket_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id   TEXT    NOT NULL,
    basket_json  TEXT    NOT NULL,   -- JSON: list of {product_id, qty}
    result_json  TEXT,               -- JSON: optimization result
    total_cost   REAL,
    platform     TEXT,               -- winning platform or 'split'
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bh_user_id    ON basket_history(user_id);
CREATE INDEX IF NOT EXISTS idx_bh_session_id ON basket_history(session_id);

-- ─────────────────────────────────────────────
-- SEARCH LOGS TABLE
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS search_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    query      TEXT    NOT NULL,
    results_n  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sl_query ON search_logs(query);

-- ─────────────────────────────────────────────
-- TRIGGER: auto-update products.updated_at
-- ─────────────────────────────────────────────
CREATE TRIGGER IF NOT EXISTS trg_products_updated
AFTER UPDATE ON products
BEGIN
    UPDATE products SET updated_at = datetime('now') WHERE id = NEW.id;
END;
