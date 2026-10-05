# -*- coding: utf-8 -*-
"""
WAVEPICKS — Audit Searches Analytics Tracker
Records every deal audit search privately into SQLite for owner-only insights.
"""
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

DB_PATH = Path(__file__).resolve().parent / "output" / "wave_tracker.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_audit_tracker():
    with _get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS deal_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            asin TEXT,
            title TEXT,
            category TEXT,
            current_price REAL,
            mrp REAL,
            discount_pct REAL,
            savings_inr REAL,
            verdict TEXT,
            client_ip_hash TEXT,
            user_agent TEXT,
            status TEXT DEFAULT 'success'
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_searches_asin ON deal_searches(asin);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_searches_time ON deal_searches(timestamp);")


def log_search(
    asin: str = "",
    title: str = "",
    category: str = "",
    current_price: float = 0.0,
    mrp: float = 0.0,
    discount_pct: float = 0.0,
    savings_inr: float = 0.0,
    verdict: str = "",
    client_ip: str = "",
    user_agent: str = "",
    status: str = "success"
) -> None:
    try:
        init_audit_tracker()
        ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:12] if client_ip else "unknown"
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with _get_conn() as conn:
            conn.execute("""
            INSERT INTO deal_searches (
                timestamp, asin, title, category, current_price, mrp,
                discount_pct, savings_inr, verdict, client_ip_hash, user_agent, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now_iso,
                asin[:15] if asin else "",
                title[:255] if title else "",
                category[:60] if category else "General",
                float(current_price or 0.0),
                float(mrp or 0.0),
                float(discount_pct or 0.0),
                float(savings_inr or 0.0),
                verdict[:100] if verdict else "",
                ip_hash,
                user_agent[:150] if user_agent else "",
                status[:20]
            ))
    except Exception as e:
        # Analytics logging should never disrupt user audit flow
        print(f"[Audit Tracker Warning] Failed to log search: {e}")


def get_search_stats() -> Dict[str, Any]:
    init_audit_tracker()
    today_prefix = datetime.now().strftime("%Y-%m-%d")

    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM deal_searches").fetchone()[0]
        today = conn.execute("SELECT COUNT(*) FROM deal_searches WHERE timestamp LIKE ?", (f"{today_prefix}%",)).fetchone()[0]
        unique_asins = conn.execute("SELECT COUNT(DISTINCT asin) FROM deal_searches WHERE asin != ''").fetchone()[0]
        unique_users = conn.execute("SELECT COUNT(DISTINCT client_ip_hash) FROM deal_searches").fetchone()[0]

        top_rows = conn.execute("""
            SELECT asin, title, COUNT(*) as search_count, MAX(current_price) as price, MAX(mrp) as mrp
            FROM deal_searches
            WHERE asin != ''
            GROUP BY asin
            ORDER BY search_count DESC
            LIMIT 10
        """).fetchall()

        recent_rows = conn.execute("""
            SELECT id, timestamp, asin, title, current_price, mrp, discount_pct, verdict, status
            FROM deal_searches
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()

    return {
        "total_searches": total,
        "searches_today": today,
        "unique_products": unique_asins,
        "unique_users_approx": unique_users,
        "top_searched_products": [dict(r) for r in top_rows],
        "recent_searches": [dict(r) for r in recent_rows]
    }
