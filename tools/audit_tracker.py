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
        conn.execute("""
        CREATE TABLE IF NOT EXISTS site_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            page_path TEXT,
            referrer TEXT,
            client_ip_hash TEXT,
            visitor_id TEXT,
            user_agent TEXT
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_time ON site_visits(timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_visits_vid ON site_visits(visitor_id);")


def log_visit(
    page_path: str = "/",
    referrer: str = "",
    client_ip: str = "",
    visitor_id: str = "",
    user_agent: str = "",
) -> Dict[str, Any]:
    try:
        init_audit_tracker()
        ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:12] if client_ip else "unknown"
        vid = (visitor_id.strip()[:36] if visitor_id else ip_hash) or ip_hash
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _get_conn() as conn:
            conn.execute("""
            INSERT INTO site_visits (timestamp, page_path, referrer, client_ip_hash, visitor_id, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                now_iso,
                (page_path or "/")[:160],
                (referrer or "Direct")[:250],
                ip_hash,
                vid,
                (user_agent or "")[:150]
            ))
    except Exception as e:
        print(f"[Visitor Tracker Warning] Failed to log visit: {e}")
    return get_public_visitor_summary()


def get_public_visitor_summary() -> Dict[str, Any]:
    """Lightweight public summary for the live visitor badge on verifyfirst.co.in."""
    init_audit_tracker()
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    month_prefix = datetime.now().strftime("%Y-%m")
    with _get_conn() as conn:
        total_searches = conn.execute("SELECT COUNT(*) FROM deal_searches").fetchone()[0]
        searches_today = conn.execute("SELECT COUNT(*) FROM deal_searches WHERE timestamp LIKE ?", (f"{today_prefix}%",)).fetchone()[0]
        search_users_month = conn.execute("SELECT COUNT(DISTINCT client_ip_hash) FROM deal_searches WHERE timestamp LIKE ?", (f"{month_prefix}%",)).fetchone()[0]
        visit_users_month = conn.execute("SELECT COUNT(DISTINCT visitor_id) FROM site_visits WHERE timestamp LIKE ?", (f"{month_prefix}%",)).fetchone()[0]
        pageviews_month = conn.execute("SELECT COUNT(*) FROM site_visits WHERE timestamp LIKE ?", (f"{month_prefix}%",)).fetchone()[0]
        visits_today = conn.execute("SELECT COUNT(DISTINCT visitor_id) FROM site_visits WHERE timestamp LIKE ?", (f"{today_prefix}%",)).fetchone()[0]

    visitors_month = max(visit_users_month + search_users_month, 1)
    visitors_today = max(visits_today, 1)
    return {
        "visitors_today": visitors_today,
        "visitors_month": visitors_month,
        "pageviews_month": max(pageviews_month, visitors_month),
        "monthly_target": 500,
        "target_progress_pct": round(min(100.0, (visitors_month / 500.0) * 100.0), 1),
        "total_audits": total_searches,
        "audits_today": searches_today,
    }


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
    month_prefix = datetime.now().strftime("%Y-%m")

    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM deal_searches").fetchone()[0]
        today = conn.execute("SELECT COUNT(*) FROM deal_searches WHERE timestamp LIKE ?", (f"{today_prefix}%",)).fetchone()[0]
        unique_asins = conn.execute("SELECT COUNT(DISTINCT asin) FROM deal_searches WHERE asin != ''").fetchone()[0]
        unique_users = conn.execute("SELECT COUNT(DISTINCT client_ip_hash) FROM deal_searches").fetchone()[0]
        visit_users_month = conn.execute("SELECT COUNT(DISTINCT visitor_id) FROM site_visits WHERE timestamp LIKE ?", (f"{month_prefix}%",)).fetchone()[0]
        pageviews_month = conn.execute("SELECT COUNT(*) FROM site_visits WHERE timestamp LIKE ?", (f"{month_prefix}%",)).fetchone()[0]
        visits_today = conn.execute("SELECT COUNT(DISTINCT visitor_id) FROM site_visits WHERE timestamp LIKE ?", (f"{today_prefix}%",)).fetchone()[0]

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

        ref_rows = conn.execute("""
            SELECT referrer, COUNT(*) as hits
            FROM site_visits
            GROUP BY referrer
            ORDER BY hits DESC
            LIMIT 10
        """).fetchall()

    visitors_month = max(visit_users_month + unique_users, 1)
    return {
        "total_searches": total,
        "searches_today": today,
        "unique_products": unique_asins,
        "unique_users_approx": visitors_month,
        "visitors_today": max(visits_today, 1),
        "visitors_month": visitors_month,
        "pageviews_month": max(pageviews_month, visitors_month),
        "monthly_target": 500,
        "target_progress_pct": round(min(100.0, (visitors_month / 500.0) * 100.0), 1),
        "top_referrers": [dict(r) for r in ref_rows],
        "top_searched_products": [dict(r) for r in top_rows],
        "recent_searches": [dict(r) for r in recent_rows]
    }
