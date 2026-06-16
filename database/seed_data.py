"""
database/seed_data.py
──────────────────────────────────────────────────────────────────────
Populates the database with realistic grocery data for all four
platforms: zepto | blinkit | instamart | bigbasket
"""

import random
import logging
from database.db_manager import get_db, fetchone

logger = logging.getLogger(__name__)

PLATFORMS = ["zepto", "blinkit", "instamart", "bigbasket"]

# Delivery / platform fees per platform
PLATFORM_CONFIG = {
    "zepto":      {"delivery_fee": 25, "platform_fee": 5,  "surge_range": (0, 10)},
    "blinkit":    {"delivery_fee": 30, "platform_fee": 5,  "surge_range": (0, 15)},
    "instamart":  {"delivery_fee": 20, "platform_fee": 3,  "surge_range": (0, 10)},
    "bigbasket":  {"delivery_fee": 40, "platform_fee": 0,  "surge_range": (0, 5)},
}

# (name, category, brand, unit, description, tags)
PRODUCTS = [
    # ── Fruits & Vegetables ──────────────────────────────────────────
    ("Banana",            "Fruits & Vegetables", "Fresh",        "1 dozen",   "Farm-fresh ripe bananas",          '["fruit","fresh","organic"]'),
    ("Apple (Red)",       "Fruits & Vegetables", "Fresh",        "1 kg",      "Crisp Himachal red apples",        '["fruit","fresh"]'),
    ("Tomato",            "Fruits & Vegetables", "Local Farm",   "500 g",     "Plump, ripe red tomatoes",         '["vegetable","fresh"]'),
    ("Onion",             "Fruits & Vegetables", "Local Farm",   "1 kg",      "Medium white onions",              '["vegetable","staple"]'),
    ("Potato",            "Fruits & Vegetables", "Local Farm",   "1 kg",      "Washed table potatoes",            '["vegetable","staple"]'),
    ("Spinach",           "Fruits & Vegetables", "Organic India","200 g",     "Baby spinach leaves",              '["vegetable","green","healthy"]'),
    ("Broccoli",          "Fruits & Vegetables", "Fresh",        "500 g",     "Fresh green broccoli florets",     '["vegetable","green","healthy"]'),
    ("Mango (Alphonso)",  "Fruits & Vegetables", "Ratnagiri",    "1 kg",      "Premium GI-tagged Alphonso mangoes",'["fruit","seasonal"]'),
    ("Grapes (Green)",    "Fruits & Vegetables", "Fresh",        "500 g",     "Seedless green grapes",            '["fruit","fresh"]'),
    ("Carrot",            "Fruits & Vegetables", "Local Farm",   "500 g",     "Crunchy orange carrots",           '["vegetable","healthy"]'),
    # ── Dairy & Eggs ────────────────────────────────────────────────
    ("Amul Gold Milk",    "Dairy & Eggs",        "Amul",         "1 L",       "Full cream toned milk",            '["dairy","milk","amul"]'),
    ("Paneer",            "Dairy & Eggs",        "Amul",         "200 g",     "Fresh cottage cheese",             '["dairy","protein"]'),
    ("Curd (Plain)",      "Dairy & Eggs",        "Mother Dairy", "500 g",     "Set curd / yogurt",                '["dairy","probiotic"]'),
    ("Eggs (White)",      "Dairy & Eggs",        "Nandini",      "6 pcs",     "Farm-fresh white eggs",            '["protein","egg"]'),
    ("Butter (Salted)",   "Dairy & Eggs",        "Amul",         "100 g",     "Pasteurised salted butter",        '["dairy","amul"]'),
    ("Cheese Slices",     "Dairy & Eggs",        "Amul",         "200 g",     "Processed cheese slices",          '["dairy","amul"]'),
    ("Ghee",              "Dairy & Eggs",        "Amul",         "500 ml",    "Pure cow ghee",                    '["dairy","cooking"]'),
    # ── Staples & Grains ────────────────────────────────────────────
    ("Basmati Rice",      "Staples & Grains",    "India Gate",   "5 kg",      "Aged long-grain basmati",          '["rice","staple","india_gate"]'),
    ("Atta (Wheat Flour)","Staples & Grains",    "Aashirvaad",   "5 kg",      "Whole wheat chakki-ground atta",   '["flour","staple"]'),
    ("Toor Dal",          "Staples & Grains",    "24 Mantra",    "1 kg",      "Split pigeon peas",                '["dal","staple","protein"]'),
    ("Moong Dal",         "Staples & Grains",    "24 Mantra",    "500 g",     "Split yellow moong lentils",       '["dal","staple","protein"]'),
    ("Mustard Oil",       "Staples & Grains",    "Patanjali",    "1 L",       "Cold-pressed mustard oil",         '["oil","cooking"]'),
    ("Sunflower Oil",     "Staples & Grains",    "Fortune",      "1 L",       "Refined sunflower oil",            '["oil","cooking"]'),
    ("Sugar",             "Staples & Grains",    "Uttam",        "1 kg",      "Refined white sugar",              '["sweetener","staple"]'),
    ("Salt (Iodised)",    "Staples & Grains",    "Tata",         "1 kg",      "Iodised table salt",               '["staple","tata"]'),
    # ── Beverages ────────────────────────────────────────────────────
    ("Tata Tea Gold",     "Beverages",           "Tata",         "500 g",     "Premium blended loose tea",        '["tea","beverage","tata"]'),
    ("Nescafé Classic",   "Beverages",           "Nescafé",      "100 g",     "Instant coffee powder",            '["coffee","beverage"]'),
    ("Frooti",            "Beverages",           "Parle",        "1 L",       "Mango fruit drink",                '["juice","drink","mango"]'),
    ("Minute Maid Orange","Beverages",           "Coca-Cola",    "1 L",       "100% orange juice drink",          '["juice","drink"]'),
    ("Bournvita",         "Beverages",           "Cadbury",      "500 g",     "Chocolate malt drink powder",      '["health_drink","chocolate"]'),
    # ── Snacks & Packaged ─────────────────────────────────────────────
    ("Maggi Noodles",     "Snacks & Packaged",   "Nestlé",       "4×70 g",   "Instant masala noodles",           '["noodles","instant","maggi"]'),
    ("Lays Classic",      "Snacks & Packaged",   "PepsiCo",      "50 g",      "Salted potato chips",              '["chips","snack"]'),
    ("Kurkure",           "Snacks & Packaged",   "PepsiCo",      "90 g",      "Masala corn puffs",                '["snack","kurkure"]'),
    ("Britannia Biscuits","Snacks & Packaged",   "Britannia",    "400 g",     "Cream cracker biscuits",           '["biscuit","snack"]'),
    ("Good Day Cashew",   "Snacks & Packaged",   "Britannia",    "200 g",     "Cashew flavour butter cookies",    '["cookie","biscuit"]'),
    # ── Personal Care ────────────────────────────────────────────────
    ("Dove Soap",         "Personal Care",       "HUL",          "3×100 g",  "Moisturising beauty bar",          '["soap","personal_care","dove"]'),
    ("Colgate Total",     "Personal Care",       "Colgate",      "200 g",     "Whitening toothpaste",             '["toothpaste","oral_care"]'),
    ("Head & Shoulders",  "Personal Care",       "P&G",          "340 ml",    "Anti-dandruff shampoo",            '["shampoo","hair_care"]'),
    ("Dettol Handwash",   "Personal Care",       "Reckitt",      "250 ml",    "Original antibacterial handwash",  '["handwash","hygiene"]'),
    # ── Frozen & Meat ────────────────────────────────────────────────
    ("McCain Fries",      "Frozen Foods",        "McCain",       "420 g",     "Classic golden shoestring fries",  '["frozen","fries","snack"]'),
    ("Chicken Breast",    "Meat & Seafood",      "Suguna",       "500 g",     "Fresh skinless boneless chicken",  '["meat","protein","chicken"]'),
]

# Price ranges per category (min_mrp, max_mrp)
PRICE_RANGES = {
    "Fruits & Vegetables": (15,  200),
    "Dairy & Eggs":        (20,  600),
    "Staples & Grains":    (50,  700),
    "Beverages":           (30,  500),
    "Snacks & Packaged":   (10,  300),
    "Personal Care":       (40,  500),
    "Frozen Foods":        (100, 400),
    "Meat & Seafood":      (150, 700),
}


def _rand_price(mrp: float, platform: str) -> dict:
    """Generate realistic per-platform pricing from an MRP."""
    cfg = PLATFORM_CONFIG[platform]
    # Each platform discounts differently
    discount_pct = round(random.uniform(2, 25), 1)
    price = round(mrp * (1 - discount_pct / 100), 2)
    surge = round(random.uniform(*cfg["surge_range"]), 2)
    coupon = round(random.uniform(0, min(price * 0.10, 20)), 2)
    return {
        "price":           price,
        "mrp":             mrp,
        "discount_pct":    discount_pct,
        "delivery_fee":    cfg["delivery_fee"],
        "platform_fee":    cfg["platform_fee"],
        "surge_fee":       surge,
        "coupon_discount": coupon,
        "in_stock":        1 if random.random() > 0.05 else 0,
        "delivery_mins":   random.choice([10, 15, 20, 30, 45, 60]),
    }


def seed_products_and_prices() -> None:
    """Insert products + platform_prices rows (skips if already seeded)."""
    existing = fetchone("SELECT COUNT(*) AS n FROM products")
    if existing and existing["n"] > 0:
        logger.info("Seed data already present – skipping.")
        return

    with get_db() as (_, cur):
        for (name, category, brand, unit, desc, tags) in PRODUCTS:
            cur.execute(
                """
                INSERT INTO products (name, category, brand, unit, description, tags)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, category, brand, unit, desc, tags),
            )
            product_id = cur.lastrowid
            lo, hi = PRICE_RANGES.get(category, (30, 300))
            mrp = round(random.uniform(lo, hi), 2)

            for platform in PLATFORMS:
                p = _rand_price(mrp, platform)
                cur.execute(
                    """
                    INSERT OR IGNORE INTO platform_prices
                        (product_id, platform, price, mrp, discount_pct,
                         delivery_fee, platform_fee, surge_fee, coupon_discount,
                         in_stock, delivery_mins, quantity_str)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        product_id, platform,
                        p["price"], p["mrp"], p["discount_pct"],
                        p["delivery_fee"], p["platform_fee"], p["surge_fee"],
                        p["coupon_discount"], p["in_stock"], p["delivery_mins"],
                        unit,
                    ),
                )

    logger.info("Seeded %d products with prices across 4 platforms.", len(PRODUCTS))


def seed_demo_user() -> None:
    """Insert a demo user (skips if already exists)."""
    import bcrypt
    existing = fetchone("SELECT id FROM users WHERE username = 'demo'")
    if existing:
        return
    pw_hash = bcrypt.hashpw(b"Demo@1234", bcrypt.gensalt()).decode()
    with get_db() as (_, cur):
        cur.execute(
            "INSERT INTO users (username, email, password_hash, city) VALUES (?,?,?,?)",
            ("demo", "demo@pricepulse.app", pw_hash, "Mumbai"),
        )
    logger.info("Demo user created (username=demo, password=Demo@1234).")


def run_all() -> None:
    seed_products_and_prices()
    seed_demo_user()


if __name__ == "__main__":
    from database.db_manager import initialise_db
    initialise_db()
    run_all()
    print("Database seeded successfully.")
