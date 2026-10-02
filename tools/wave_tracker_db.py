"""
============================================================
 WAVEPICKS — Wave Validation & Tracking Database (SQLite)
 Tracks product lifecycle: Forming ➔ Surging ➔ Peak / Fluke
============================================================
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = Path(__file__).parent / "output" / "wave_tracker.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS tracked_products (
            asin TEXT PRIMARY KEY,
            title TEXT,
            category TEXT,
            amazon_url TEXT,
            initial_date TEXT,
            initial_rank INTEGER,
            initial_price REAL,
            initial_reviews INTEGER,
            initial_wave_score INTEGER,
            initial_wave_stage TEXT,
            status TEXT DEFAULT 'Tracking',
            rationale TEXT,
            max_observed_price REAL
        );

        CREATE TABLE IF NOT EXISTS daily_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asin TEXT,
            snapshot_date TEXT,
            current_rank INTEGER,
            current_price REAL,
            current_reviews INTEGER,
            est_monthly_revenue REAL,
            rank_delta INTEGER,       -- positive = improved rank
            trajectory TEXT,          -- '🚀 Surging' | '⏳ Holding' | '❌ Fluke'
            FOREIGN KEY (asin) REFERENCES tracked_products(asin)
        );
        """)

        # Migration: add rationale, max_observed_price, and image_url if missing
        cols = [c[1] for c in conn.execute("PRAGMA table_info(tracked_products)").fetchall()]
        if "rationale" not in cols:
            conn.execute("ALTER TABLE tracked_products ADD COLUMN rationale TEXT")
        if "max_observed_price" not in cols:
            conn.execute("ALTER TABLE tracked_products ADD COLUMN max_observed_price REAL")
        if "image_url" not in cols:
            conn.execute("ALTER TABLE tracked_products ADD COLUMN image_url TEXT")


init_db()


def add_tracked_product(p: dict) -> bool:
    asin = p.get("asin", "").strip()
    if not asin:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        conn.execute("""
        INSERT OR IGNORE INTO tracked_products (
            asin, title, category, amazon_url, initial_date,
            initial_rank, initial_price, initial_reviews,
            initial_wave_score, initial_wave_stage, status, rationale, max_observed_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Tracking', ?, ?)
        """, (
            asin,
            p.get("title", "")[:120],
            p.get("category", "General"),
            p.get("amazon_url", f"https://www.amazon.in/dp/{asin}"),
            today,
            p.get("rank", 0),
            p.get("price", 0.0),
            p.get("review_count", 0),
            p.get("wave_score", 0),
            p.get("wave_stage", "🌊 Forming"),
            p.get("rationale", ""),
            p.get("max_observed_price", p.get("price", 0.0))
        ))
    return True


def remove_tracked_product(asin: str) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM daily_snapshots WHERE asin = ?", (asin,))
        conn.execute("DELETE FROM tracked_products WHERE asin = ?", (asin,))


def get_all_tracked() -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.execute("""
        SELECT t.*, 
               (SELECT current_rank FROM daily_snapshots WHERE asin = t.asin ORDER BY id DESC LIMIT 1) as latest_rank,
               (SELECT current_price FROM daily_snapshots WHERE asin = t.asin ORDER BY id DESC LIMIT 1) as latest_price,
               (SELECT current_reviews FROM daily_snapshots WHERE asin = t.asin ORDER BY id DESC LIMIT 1) as latest_reviews,
               (SELECT trajectory FROM daily_snapshots WHERE asin = t.asin ORDER BY id DESC LIMIT 1) as latest_trajectory,
               (SELECT COUNT(*) FROM daily_snapshots WHERE asin = t.asin) as days_tracked
        FROM tracked_products t
        ORDER BY t.initial_date DESC
        """)
        return [dict(row) for row in cur.fetchall()]


def record_snapshot(asin: str, rank: int, price: float, reviews: int, rev: float) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        # Get initial rank to determine trajectory
        row = conn.execute("SELECT initial_rank, initial_reviews, initial_date FROM tracked_products WHERE asin = ?", (asin,)).fetchone()
        if not row:
            return "Unknown"
        init_rank = row["initial_rank"] or 100
        init_revs = row["initial_reviews"] or 0

        # Check how many historical snapshots exist for this ASIN
        existing_count = conn.execute(
            "SELECT COUNT(*) FROM daily_snapshots WHERE asin = ?", (asin,)
        ).fetchone()[0]

        # Rank delta: positive means rank improved (e.g., #80 to #40 is +40 improvement)
        rank_delta = init_rank - rank

        if existing_count == 0:
            # Day 0: Baseline initialization — cannot claim Surging yet!
            trajectory = "📍 Baseline (Day 0)"
            rank_delta = 0
        else:
            # Day 1+: Compare with initial baseline
            if rank_delta >= 8:
                trajectory = f"🚀 Surging (+{rank_delta})"
            elif rank_delta <= -25 or (rank > init_rank + 35):
                trajectory = f"❌ Fluke (-{abs(rank_delta)})"
            else:
                trajectory = "⏳ Holding (Stable)"

        conn.execute("""
        INSERT INTO daily_snapshots (
            asin, snapshot_date, current_rank, current_price,
            current_reviews, est_monthly_revenue, rank_delta, trajectory
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (asin, today, rank, price, reviews, rev, rank_delta, trajectory))

        # Update parent status
        conn.execute("UPDATE tracked_products SET status = ? WHERE asin = ?", (trajectory, asin))

    return trajectory


def get_validation_summary() -> Dict[str, Any]:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tracked_products").fetchone()[0]
        surging = conn.execute("SELECT COUNT(*) FROM tracked_products WHERE status LIKE '%Surging%'").fetchone()[0]
        holding = conn.execute("SELECT COUNT(*) FROM tracked_products WHERE status LIKE '%Holding%'").fetchone()[0]
        fluke = conn.execute("SELECT COUNT(*) FROM tracked_products WHERE status LIKE '%Fluke%'").fetchone()[0]
        baseline = conn.execute("SELECT COUNT(*) FROM tracked_products WHERE status LIKE '%Baseline%' OR status = 'Tracking'").fetchone()[0]

    rate = (surging / total * 100) if total > 0 else 0
    return {
        "total": total,
        "surging": surging,
        "holding": holding,
        "fluke": fluke,
        "baseline": baseline,
        "success_rate": round(rate, 1)
    }


# ═════════════════════════════════════════════════════════
#  AMAZON INDIA AFFILIATE COMMISSION MATRIX & CREATOR ENGINE
# ═════════════════════════════════════════════════════════

AMAZON_IN_COMMISSIONS: Dict[str, float] = {
    "beauty": 0.08,
    "skincare": 0.08,
    "haircare": 0.08,
    "personal care": 0.08,
    "luxury beauty": 0.09,
    "health": 0.05,
    "health & personal care": 0.05,
    "apparel": 0.09,
    "clothing": 0.09,
    "shoes": 0.09,
    "jewelry": 0.08,
    "home & kitchen": 0.06,
    "kitchen": 0.06,
    "sports": 0.05,
    "baby": 0.06,
    "toys": 0.06,
    "books": 0.05,
    "electronics": 0.025,
    "computers": 0.025,
    "mobiles": 0.015,
    "grocery": 0.04,
    "general": 0.05,
}


def get_category_commission(cat: str) -> float:
    c = (cat or "").lower().strip()
    for k, v in AMAZON_IN_COMMISSIONS.items():
        if k in c:
            return v
    return 0.05  # Default 5%


def extract_brand(title: str) -> str:
    known = [
        "Dot & Key", "L'Oréal Paris", "L'Oreal Paris", "Alps Goodness",
        "Ghar Soaps", "Tiger Shroff", "PROWL", "Cetaphil", "Foxtale",
        "Aqueria", "Minimalist", "The Derma Co", "Plum", "Mamaearth",
        "Neutrogena", "Biotique", "MCaffeine", "WOW Skin Science"
    ]
    for k in known:
        if k.lower() in title.lower():
            return k
    parts = title.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "Brand")


def get_creator_products() -> List[Dict[str, Any]]:
    """Returns products tailored for affiliate bloggers, SEO writers, and review creators."""
    items = get_all_tracked()
    enriched = []

    for p in items:
        price = p.get("latest_price") or p.get("initial_price") or 0.0
        max_price = p.get("max_observed_price") or price
        category = p.get("category", "Beauty")
        comm_rate = get_category_commission(category)
        comm_per_sale = round(price * comm_rate, 2)
        comm_per_100 = round(comm_per_sale * 100, 0)
        trajectory = p.get("latest_trajectory") or "⏳ Holding"
        rank = p.get("latest_rank") or p.get("initial_rank") or 100
        reviews = p.get("latest_reviews") or p.get("initial_reviews") or 0
        savings_inr = round(max(0.0, max_price - price), 0)
        savings_pct = round((savings_inr / max_price * 100), 1) if max_price > 0 else 0.0

        # Calculate Creator Opportunity Score (15 to 99)
        score = p.get("initial_wave_score", 65)
        if "Surging" in trajectory:
            score += 18
        elif "Holding" in trajectory:
            score += 6
        elif "Fluke" in trajectory:
            score -= 22

        if comm_rate >= 0.08:
            score += 10
        if 299 <= price <= 899:
            score += 8  # Sweet impulse buy spot for Indian online shoppers
        score = max(15, min(99, score))

        # Strategic Content Angle & Title Hooks
        title_clean = p.get("title", "")[:60].strip()
        brand = extract_brand(p.get("title", ""))

        if "Surging" in trajectory:
            content_angle = f"🔥 Early Breakout Wave: Surging {trajectory}. High affiliate conversion window before competitor blogs cover it."
            titles = [
                f"{brand} Review: Why Everyone on Amazon India is Buying This in 2026",
                f"Is {brand} Actually Worth It? Hands-On 14-Day Test & Price Breakdown",
                f"Top 5 Trending {category} Products You Need Before Next Month"
            ]
        elif "Fluke" in trajectory:
            content_angle = f"⚠️ Overhype Watchdog: Post-promo drop {trajectory}. Angle as 'Honest Review: Is {brand} Hype or Reality?'"
            titles = [
                f"Don't Buy {brand} Until You Read This: Honest Review & Real Flaws",
                f"{brand} Review: Why It Spiked on Amazon and Dropped Fast",
                f"3 Better Alternatives to {brand} Under ₹{int(price * 1.2)}"
            ]
        else:
            content_angle = f"🛡️ Evergreen Authority: Stable BSR #{rank:,}. High search volume keyword pillar for steady passive commissions."
            titles = [
                f"{brand} Long-Term Review: Does It Still Hold Up in 2026?",
                f"Best {category} Products on Amazon India: Tested & Ranked",
                f"{brand} vs Competitors: Which One Gives You Real Value for ₹{int(price)}?"
            ]

        seo_keywords = [
            f"{brand.lower()} review 2026",
            f"best {category.lower()} amazon india",
            f"buy {brand.lower()} price",
            f"{brand.lower()} pros and cons"
        ]

        item_data = dict(p)
        item_data.update({
            "commission_rate": comm_rate,
            "commission_pct_str": f"{comm_rate * 100:.1f}%",
            "commission_per_sale": comm_per_sale,
            "commission_per_100": comm_per_100,
            "creator_score": score,
            "content_angle": content_angle,
            "suggested_titles": titles,
            "seo_keywords": seo_keywords,
            "savings_inr": savings_inr,
            "savings_pct": savings_pct,
            "current_price": price,
            "max_price": max_price,
            "trajectory": trajectory
        })
        enriched.append(item_data)

    # Sort by creator score descending
    enriched.sort(key=lambda x: x["creator_score"], reverse=True)
    return enriched


def get_creator_brief(asin: str) -> Optional[Dict[str, Any]]:
    """Returns a full SEO Content Brief & Writing Blueprint for a given ASIN."""
    products = get_creator_products()
    matched = [p for p in products if p["asin"] == asin]
    if not matched:
        return None
    p = matched[0]

    return {
        "asin": p["asin"],
        "title": p["title"],
        "brand": p["title"].split()[0] if p["title"] else "Brand",
        "category": p["category"],
        "current_price": p["current_price"],
        "max_observed_price": p["max_price"],
        "commission_rate_str": p["commission_pct_str"],
        "commission_per_sale": p["commission_per_sale"],
        "commission_per_100": p["commission_per_100"],
        "creator_score": p["creator_score"],
        "trajectory": p["trajectory"],
        "content_angle": p["content_angle"],
        "suggested_titles": p["suggested_titles"],
        "seo_keywords": p["seo_keywords"],
        "outline_h2": [
            f"1. Quick Verdict: Who Should Buy and Who Should Skip {p['title'][:30]}?",
            f"2. Real-World Performance & Hands-On Testing (BSR #{p.get('latest_rank', 0)} Analysis)",
            f"3. Price vs Value: Is ₹{p['current_price']} a Real Deal? (Keepa Historical Breakdown)",
            f"4. Key Pros & Genuine Downsides You Must Know Before Buying",
            f"5. Final Score & Best Available Amazon India Deal"
        ],
        "amazon_url": p["amazon_url"],
        "rationale": p.get("rationale", "")
    }


def get_buyer_deals() -> List[Dict[str, Any]]:
    """Returns consumer-facing deal cards with verified price integrity and organic momentum."""
    items = get_all_tracked()
    deals = []

    for p in items:
        price = p.get("latest_price") or p.get("initial_price") or 0.0
        max_price = p.get("max_observed_price") or price
        savings_inr = round(max(0.0, max_price - price), 0)
        savings_pct = round((savings_inr / max_price * 100), 0) if max_price > 0 else 0.0
        trajectory = p.get("latest_trajectory") or "⏳ Holding"
        rank = p.get("latest_rank") or p.get("initial_rank") or 100
        reviews = p.get("latest_reviews") or p.get("initial_reviews") or 0

        # Consumer Badge
        if "Surging" in trajectory:
            badge = "🔥 Genuine Demand Surge"
            badge_class = "badge-surging"
            buyer_note = f"Ranked #{rank:,} on Amazon India. Organic buyer surge verified over 3+ days — genuine consumer favorite."
            is_recommended = True
        elif "Fluke" in trajectory:
            badge = "⚠️ Promo Fluke Alert"
            badge_class = "badge-fluke"
            buyer_note = f"Rank fell to #{rank:,}. Temporary discount caused a short spike, but ratings or reorder velocity didn't hold."
            is_recommended = False
        else:
            badge = "⭐ Verified Bestseller"
            badge_class = "badge-stable"
            buyer_note = f"Rock-solid #{rank:,} category bestseller. Established favorite with proven repeat customer loyalty."
            is_recommended = True

        deals.append({
            "asin": p["asin"],
            "title": p["title"],
            "category": p["category"],
            "amazon_url": p["amazon_url"],
            "current_price": price,
            "max_price": max_price,
            "savings_inr": savings_inr,
            "savings_pct": savings_pct,
            "badge": badge,
            "badge_class": badge_class,
            "buyer_note": buyer_note,
            "is_recommended": is_recommended,
            "rank": rank,
            "reviews": reviews,
            "rationale": p.get("rationale", "")
        })

    # Sort recommended & highest savings first
    deals.sort(key=lambda x: (x["is_recommended"], x["savings_pct"]), reverse=True)
    return deals

