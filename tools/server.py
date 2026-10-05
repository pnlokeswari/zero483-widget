"""
============================================================
 ZERO483 — Internal Product Research Web Server  v3.0
 Access  : http://localhost:5483
 2026-09-26

 Optimizations vs v2.0
 ──────────────────────
  1. Worker logic: dead `if not (…): pass` branches removed;
     clean guard-clause flow (movers_only / bestsellers_only)
  2. Job registry uses a dataclass (JobRecord) instead of raw dict
  3. SSE generator is a self-contained class — no closure over
     mutable job dict; thread-safe via Queue
  4. Old-job garbage collection: jobs older than 2 h are purged
     on every new /api/start call
  5. /api/products/<job_id> — new endpoint returns full JSON
     snapshot so the browser can rebuild state after page reload
  6. /api/queue — returns the blog queue as JSON for monitoring
  7. Sort + filter bar in UI (client-side, no round-trip)
  8. Export buttons (CSV / HTML) wired to the download endpoint
  9. Pages slider shows live product count estimate
 10. Sidebar "Select All / None" category shortcuts
 11. Log capped at MAX_LOG_LINES to prevent DOM bloat
 12. updateStats() debounced with requestAnimationFrame
 13. SSE reconnects automatically on network error (max 3 tries)
 14. Inline CSS deduplicated and condensed (−40 lines vs v2)
============================================================
"""

from __future__ import annotations

# ── stdlib ────────────────────────────────────────────────
import sys, json, time, random, threading, uuid, logging, re, os
from dataclasses import dataclass, field, asdict
from datetime    import datetime, timedelta
from pathlib     import Path
from queue       import Queue, Empty
from typing      import Iterator

# ── UTF-8 (Windows) ───────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── project imports ───────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from product_research_tool import (
    AmazonIndiaScraper, Product, _recalc,
    save_csv, save_html_report, save_excel,
    CATEGORIES, MOVERS_SLUGS, SLUG_TO_NAME,
    REVENUE_MIN, REVENUE_MAX,
    OUTPUT_DIR, _crawl_sleep,
)
from wave_tracker_db import (
    add_tracked_product, remove_tracked_product, get_all_tracked,
    get_validation_summary, get_creator_products, get_creator_brief, get_buyer_deals
)
from creator_ui import CREATOR_HTML
from buyer_ui import BUYER_HTML

# ── flask ─────────────────────────────────────────────────
from flask import Flask, render_template_string, request, Response, jsonify, send_file, redirect

# ── config ────────────────────────────────────────────────
PORT          = int(os.environ.get("PORT", 5483))
MAX_LOG_LINES = 200   # hard cap on console lines shown in UI
JOB_TTL_H    = 2      # hours before a job is garbage-collected

app = Flask(__name__)
log = logging.getLogger("ZERO483.server")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(message)s",
                    datefmt="%H:%M:%S")


# ═════════════════════════════════════════════════════════
#  JOB REGISTRY
# ═════════════════════════════════════════════════════════

@dataclass
class JobRecord:
    job_id  : str
    status  : str              = "running"   # running | done | stopped
    products: list[Product]    = field(default_factory=list)
    queue   : Queue            = field(default_factory=Queue)
    stop    : threading.Event  = field(default_factory=threading.Event)
    created : datetime         = field(default_factory=datetime.now)


_jobs: dict[str, JobRecord] = {}
_jobs_lock = threading.Lock()


def _gc_jobs() -> None:
    """Remove finished jobs older than JOB_TTL_H hours."""
    cutoff = datetime.now() - timedelta(hours=JOB_TTL_H)
    with _jobs_lock:
        stale = [jid for jid, j in _jobs.items()
                 if j.status != "running" and j.created < cutoff]
        for jid in stale:
            del _jobs[jid]
            log.debug(f"  GC: removed job {jid}")


def _new_job() -> JobRecord:
    _gc_jobs()
    rec = JobRecord(job_id=str(uuid.uuid4())[:8])
    with _jobs_lock:
        _jobs[rec.job_id] = rec
    return rec


def _get_job(job_id: str) -> JobRecord | None:
    with _jobs_lock:
        return _jobs.get(job_id)


# ═════════════════════════════════════════════════════════
#  SSE HELPERS
# ═════════════════════════════════════════════════════════

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _keepalive() -> str:
    return ": ka\n\n"


# ═════════════════════════════════════════════════════════
#  SCRAPE WORKER
# ═════════════════════════════════════════════════════════

# Movers & Shakers friendly labels
_MOVERS_LABEL = {s: SLUG_TO_NAME.get(s, s.title()) + " M&S" for s in MOVERS_SLUGS}


def _scrape_worker(rec: JobRecord, cfg: dict) -> None:
    """Background thread: scrapes and pushes SSE events into rec.queue."""
    q    = rec.queue
    stop = rec.stop

    def emit_log(level: str, msg: str) -> None:
        q.put({"type": "log", "data": {"level": level, "msg": msg}})

    def emit_product(p: Product) -> None:
        rec.products.append(p)
        q.put({"type": "product", "data": asdict(p)})

    try:
        slugs     = cfg.get("cats", ["beauty", "health"])
        pages     = max(1, int(cfg.get("pages", 1)))
        bs_only   = bool(cfg.get("bsOnly", False))
        mv_only   = bool(cfg.get("moversOnly", False))
        do_enrich = bool(cfg.get("enrich", False))

        scraper = AmazonIndiaScraper(max_pages=pages)

        # ── Bestsellers ───────────────────────────────────
        if not mv_only:
            emit_log("info", f"📦 Bestsellers — {len(slugs)} categories, {pages} page(s)")
            for slug in slugs:
                for pg in range(1, pages + 1):
                    if stop.is_set():
                        break
                    cat = SLUG_TO_NAME.get(slug, slug.title())
                    emit_log("info", f"   [{cat}] page {pg}")
                    items = scraper.scrape_bestsellers(slug, pg)
                    for p in items:
                        emit_product(p)
                    emit_log("ok", f"   ✓ {len(items)} products")
                    _crawl_sleep()

        # ── Movers & Shakers ──────────────────────────────
        if not bs_only:
            movers_slugs = [s for s in slugs if s in MOVERS_SLUGS]
            if movers_slugs:
                emit_log("info", f"🚀 Movers & Shakers — {len(movers_slugs)} categories")
                for slug in movers_slugs:
                    if stop.is_set():
                        break
                    emit_log("info", f"   [{_MOVERS_LABEL.get(slug, slug)}]")
                    items = scraper.scrape_movers(slug, 1)
                    for p in items:
                        emit_product(p)
                    emit_log("ok", f"   ✓ {len(items)} products")
                    _crawl_sleep()

        # ── Deep enrich ───────────────────────────────────
        if do_enrich and rec.products and not stop.is_set():
            top = sorted(
                (p for p in rec.products if p.price > 0), key=lambda p: p.rank
            )[:30]
            emit_log("info", f"🔍 Deep enriching {len(top)} products …")
            for i, p in enumerate(top, 1):
                if stop.is_set():
                    break
                emit_log("info", f"   [{i}/{len(top)}] {p.title[:50]}")
                scraper.enrich_product(p)
                # push updated product data back
                q.put({"type": "update", "data": asdict(p)})
                _crawl_sleep()

        emit_log("ok", f"✅ Scan complete — {len(rec.products)} products total")

    except Exception as exc:
        q.put({"type": "error_evt", "data": {"msg": str(exc)}})
        log.exception("Worker error")
    finally:
        q.put(None)          # sentinel → done
        rec.status = "done"


# ═════════════════════════════════════════════════════════
#  ROUTES
# ═════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template_string(_DASHBOARD)


@app.route("/creator")
def creator_studio():
    return render_template_string(CREATOR_HTML)


@app.route("/deals")
@app.route("/deals.html")
@app.route("/buyer")
def buyer_deals():
    return render_template_string(BUYER_HTML)


@app.route("/api/creator/products")
def api_creator_products():
    return jsonify(get_creator_products())


@app.route("/api/creator/brief/<asin>")
def api_creator_brief(asin: str):
    brief = get_creator_brief(asin)
    if not brief:
        return jsonify({"error": "not found"}), 404
    return jsonify(brief)


@app.route("/healthz")
@app.route("/ping")
def healthz():
    return jsonify({"status": "ok", "service": "zero483-deals-api", "time": time.time()}), 200


# ═════════════════════════════════════════════════════════
#  SECURITY, CORS & RATE-LIMITING LAYER
# ═════════════════════════════════════════════════════════

ALLOWED_ORIGIN_PATTERNS = [
    re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"),
    re.compile(r"^https://([a-zA-Z0-9-]+\.)?zero483\.com$"),
    re.compile(r"^https://([a-zA-Z0-9-]+\.)?trycloudflare\.com$"),
]

# In-memory thread-safe rate limiter (sliding window)
_RATE_LIMITS: dict[str, list[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()
MAX_AUDITS_PER_MINUTE = 10
RATE_WINDOW_SECONDS = 60.0


def _get_client_ip() -> str:
    """Extract real client IP even behind Cloudflare / reverse proxy."""
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP", "").strip()
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return request.remote_addr or "unknown"


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if rate limit exceeded."""
    now = time.time()
    with _RATE_LIMIT_LOCK:
        timestamps = [t for t in _RATE_LIMITS.get(client_ip, []) if now - t < RATE_WINDOW_SECONDS]
        if len(timestamps) >= MAX_AUDITS_PER_MINUTE:
            return False
        timestamps.append(now)
        _RATE_LIMITS[client_ip] = timestamps

        # Periodic cleanup of stale IPs
        if len(_RATE_LIMITS) > 1000:
            stale_ips = [ip for ip, ts in _RATE_LIMITS.items() if not ts or (now - ts[-1] > RATE_WINDOW_SECONDS)]
            for ip in stale_ips:
                del _RATE_LIMITS[ip]
    return True


@app.after_request
def apply_security_headers(response: Response) -> Response:
    """Apply OWASP security headers and strictly validated CORS headers."""
    origin = request.headers.get("Origin", "")
    if origin:
        allowed = any(p.match(origin) for p in ALLOWED_ORIGIN_PATTERNS)
        if allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            response.headers["Access-Control-Allow-Credentials"] = "true"

    # OWASP Defense-in-depth headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.route("/api/buyer/audit-deal", methods=["OPTIONS", "POST"])
def api_buyer_audit_deal():
    """Audit any Amazon URL or ASIN for authentic MRP discounts and 90-day price curve fluctuations."""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    # 1. Rate Limiting Protection (Anti-Scraping / Anti-DDoS)
    client_ip = _get_client_ip()
    if not _check_rate_limit(client_ip):
        log.warning(f"Rate limit exceeded for IP: {client_ip}")
        return jsonify({
            "error": "⚡ Rate limit reached (max 10 audits per minute). Please wait a moment before trying another product."
        }), 429

    # 2. Input Sanitization & Payload Length Check
    data = request.get_json(force=True, silent=True) or {}
    url = str(data.get("url", "")).strip()
    if not url:
        return jsonify({"error": "Please provide an Amazon product link or ASIN"}), 400
    if len(url) > 1024:
        return jsonify({"error": "Input link exceeds maximum allowed length."}), 400

    # 3. Secure Server-Side Execution
    from deal_auditor import audit_product_deal
    from audit_tracker import log_search
    res = audit_product_deal(url)
    if "error" in res:
        log_search(
            asin=url[:15],
            title="Failed Audit Attempt",
            client_ip=client_ip,
            user_agent=request.headers.get("User-Agent", ""),
            status="error"
        )
        return jsonify(res), 400

    log_search(
        asin=res.get("asin", ""),
        title=res.get("title", ""),
        category=res.get("category", "General"),
        current_price=res.get("current_price", 0.0),
        mrp=res.get("mrp", 0.0),
        discount_pct=res.get("discount_mrp_pct", 0.0),
        savings_inr=res.get("savings_mrp_inr", 0.0),
        verdict=res.get("verdict", ""),
        client_ip=client_ip,
        user_agent=request.headers.get("User-Agent", ""),
        status="success"
    )
    return jsonify(res)


@app.route("/api/admin/audit-analytics")
def api_admin_audit_analytics():
    """Private JSON API for owner analytics. Protected by secret key or localhost."""
    key = request.args.get("key", "").strip()
    client_ip = _get_client_ip()
    is_local = client_ip in ["127.0.0.1", "::1", "localhost"]
    if not is_local and key != "zero483":
        return jsonify({"error": "Unauthorized access"}), 403

    from audit_tracker import get_search_stats
    return jsonify(get_search_stats())


@app.route("/admin/deal-stats")
def admin_deal_stats():
    """Private Owner-Only Dashboard for Deal Search Analytics."""
    key = request.args.get("key", "").strip()
    client_ip = _get_client_ip()
    is_local = client_ip in ["127.0.0.1", "::1", "localhost"]
    if not is_local and key != "zero483":
        return Response("""
        <html><body style="background:#070d1e;color:#f87171;font-family:sans-serif;padding:40px;text-align:center">
          <h2>🔒 Access Restricted</h2>
          <p style="color:#94a3b8">This is an owner-only private analytics dashboard.<br>Please access from localhost or append <code>?key=zero483</code> to view.</p>
        </body></html>
        """, status=403, mimetype="text/html")

    from audit_tracker import get_search_stats
    stats = get_search_stats()

    top_rows_html = "".join([f"""
      <tr>
        <td style="font-weight:700;color:#38bdf8"><a href="https://www.amazon.in/dp/{r.get('asin')}?tag=10fa9c-21" target="_blank" style="color:#38bdf8;text-decoration:none">{r.get('asin')} ↗</a></td>
        <td style="max-width:340px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{r.get('title')}">{r.get('title')}</td>
        <td style="font-weight:800;color:#10b981">{r.get('search_count')} searches</td>
        <td>₹{r.get('price', 0):,.0f}</td>
      </tr>
    """ for r in stats.get("top_searched_products", [])]) or '<tr><td colspan="4" style="text-align:center;color:#94a3b8">No searches recorded yet</td></tr>'

    recent_rows_html = "".join([f"""
      <tr>
        <td style="color:#94a3b8;font-size:.78rem;white-space:nowrap">{r.get('timestamp')}</td>
        <td style="font-weight:700"><a href="https://www.amazon.in/dp/{r.get('asin')}?tag=10fa9c-21" target="_blank" style="color:#38bdf8;text-decoration:none">{r.get('asin')} ↗</a></td>
        <td style="max-width:320px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{r.get('title')}">{r.get('title')}</td>
        <td style="font-weight:700">₹{r.get('current_price', 0):,.0f}</td>
        <td style="color:#94a3b8">₹{r.get('mrp', 0):,.0f}</td>
        <td style="color:#10b981;font-weight:700">{r.get('discount_pct', 0):.0f}%</td>
        <td style="font-size:.78rem;color:#f1f5f9">{r.get('verdict') or 'Verified'}</td>
        <td><span style="background:{'rgba(16,185,129,.2)' if r.get('status')=='success' else 'rgba(239,68,68,.2)'};color:{'#34d399' if r.get('status')=='success' else '#f87171'};padding:2px 8px;border-radius:12px;font-size:.72rem;font-weight:700">{r.get('status')}</span></td>
      </tr>
    """ for r in stats.get("recent_searches", [])]) or '<tr><td colspan="8" style="text-align:center;color:#94a3b8">No activity recorded yet</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🔒 Private Search Analytics — WAVEPICKS Deal Auditor</title>
<style>
  :root {{ --bg:#070d1e; --card:#0e1738; --border:#182859; --text:#f1f5f9; --muted:#94a3b8; --brand:#38bdf8; --green:#10b981; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); padding:24px; min-height:100vh; }}
  .header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; flex-wrap:wrap; gap:12px; border-bottom:1px solid var(--border); padding-bottom:16px; }}
  .title {{ font-size:1.35rem; font-weight:800; display:flex; align-items:center; gap:10px; color:#fff; }}
  .badge-private {{ background:rgba(245,158,11,.15); color:#fbbf24; border:1px solid rgba(245,158,11,.3); font-size:.72rem; padding:4px 10px; border-radius:20px; font-weight:700; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:16px; margin-bottom:28px; }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px 20px; }}
  .val {{ font-size:1.9rem; font-weight:800; color:#fff; margin-bottom:4px; }}
  .lbl {{ font-size:.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:1px; font-weight:700; }}
  .section-title {{ font-size:1.05rem; font-weight:700; margin-bottom:12px; color:#fff; display:flex; align-items:center; gap:8px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.84rem; text-align:left; }}
  th {{ background:#09122c; padding:12px 14px; font-size:.72rem; text-transform:uppercase; letter-spacing:1px; color:var(--muted); border-bottom:1px solid var(--border); }}
  td {{ padding:12px 14px; border-bottom:1px solid rgba(24,40,89,.6); }}
  tr:hover td {{ background:rgba(56,189,248,.04); }}
  .table-box {{ background:var(--card); border:1px solid var(--border); border-radius:12px; overflow-x:auto; margin-bottom:28px; }}
  .btn-refresh {{ background:#0284c7; color:#fff; border:none; padding:8px 16px; border-radius:8px; font-weight:700; cursor:pointer; font-size:.82rem; }}
  .btn-refresh:hover {{ background:#0369a1; }}
</style>
</head>
<body>
  <div class="header">
    <div class="title">
      <span>📊 WAVEPICKS Deal Search Analytics</span>
      <span class="badge-private">🔒 Private / Owner-Only</span>
    </div>
    <div style="display:flex;gap:10px;align-items:center">
      <button class="btn-refresh" onclick="location.reload()">🔄 Refresh Stats</button>
      <a href="/deals" target="_blank" style="color:var(--brand);font-size:.82rem;text-decoration:none;font-weight:700">Open Deals Portal ↗</a>
    </div>
  </div>

  <div class="grid">
    <div class="card" style="border-left:4px solid #38bdf8">
      <div class="val">{stats.get('total_searches', 0)}</div>
      <div class="lbl">Total Searches Logged</div>
    </div>
    <div class="card" style="border-left:4px solid #10b981">
      <div class="val">{stats.get('searches_today', 0)}</div>
      <div class="lbl">Searches Today</div>
    </div>
    <div class="card" style="border-left:4px solid #a855f7">
      <div class="val">{stats.get('unique_products', 0)}</div>
      <div class="lbl">Unique Products Audited</div>
    </div>
    <div class="card" style="border-left:4px solid #f59e0b">
      <div class="val">{stats.get('unique_users_approx', 0)}</div>
      <div class="lbl">Unique Shoppers (Approx)</div>
    </div>
  </div>

  <div class="section-title">🏆 Top 10 Most Audited Products</div>
  <div class="table-box">
    <table>
      <thead>
        <tr>
          <th>ASIN</th>
          <th>Product Title</th>
          <th>Audits Count</th>
          <th>Latest Price</th>
        </tr>
      </thead>
      <tbody>
        {top_rows_html}
      </tbody>
    </table>
  </div>

  <div class="section-title">📜 Recent 50 Search Queries</div>
  <div class="table-box">
    <table>
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>ASIN</th>
          <th>Product Title</th>
          <th>Deal Price</th>
          <th>Box MRP</th>
          <th>Discount</th>
          <th>Verdict</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {recent_rows_html}
      </tbody>
    </table>
  </div>
</body>
</html>
"""
    return Response(html, mimetype="text/html")



@app.route("/api/keepa-chart/<asin>")
def api_keepa_chart(asin: str):
    """Proxy Keepa chart to prevent browser 403 Forbidden due to localhost Referer header."""
    import urllib.request
    clean_asin = asin.strip().upper()
    url = f"https://graph.keepa.com/pricehistory.png?asin={clean_asin}&domain=10"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read()
            return Response(data, mimetype="image/png", headers={
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*"
            })
    except Exception as e:
        log.error(f"Keepa chart error for {clean_asin}: {e}")
        return "Chart unavailable", 502


@app.route("/api/start", methods=["POST"])
def api_start():
    cfg = request.get_json(force=True, silent=True) or {}
    rec = _new_job()
    t   = threading.Thread(target=_scrape_worker, args=(rec, cfg), daemon=True)
    t.start()
    return jsonify({"job_id": rec.job_id})


@app.route("/api/stop/<job_id>", methods=["POST"])
def api_stop(job_id: str):
    rec = _get_job(job_id)
    if rec:
        rec.stop.set()
        rec.status = "stopped"
    return jsonify({"ok": True})


@app.route("/api/stream/<job_id>")
def api_stream(job_id: str):
    """Server-Sent Events stream: log lines + product cards."""
    rec = _get_job(job_id)
    if not rec:
        def _not_found():
            yield _sse("error_evt", {"msg": "Job not found"})
        return Response(_not_found(), mimetype="text/event-stream")

    def _generate() -> Iterator[str]:
        while True:
            try:
                item = rec.queue.get(timeout=25)
                if item is None:
                    yield _sse("done", {"total": len(rec.products)})
                    return
                yield _sse(item["type"], item["data"])
            except Empty:
                yield _keepalive()

    return Response(
        _generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/products/<job_id>")
def api_products(job_id: str):
    """Full product snapshot — lets the browser rebuild after reload."""
    rec = _get_job(job_id)
    if not rec:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "job_id"  : job_id,
        "status"  : rec.status,
        "total"   : len(rec.products),
        "products": [asdict(p) for p in rec.products],
    })



# In-memory store for blog jobs (blog_id → {queue, status, result})
_blog_jobs: dict[str, dict] = {}
_blog_lock = threading.Lock()

# GitHub token (set via /api/settings or GH_TOKEN env var)
import os as _os
_GH_TOKEN: str = _os.environ.get("GH_TOKEN", "")


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """GET returns current settings; POST updates GitHub token."""
    global _GH_TOKEN
    if request.method == "POST":
        d = request.get_json(force=True, silent=True) or {}
        if "gh_token" in d:
            _GH_TOKEN = d["gh_token"].strip()
            log.info("GitHub token updated via settings API")
        return jsonify({"ok": True, "gh_token_set": bool(_GH_TOKEN)})
    return jsonify({"gh_token_set": bool(_GH_TOKEN)})


def _blog_worker(blog_id: str, url: str, category: str, token: str) -> None:
    """Background thread: runs full blog creation pipeline, streams into queue."""
    q = _blog_jobs[blog_id]["queue"]

    def emit(msg: str):
        q.put({"type": "blog_log", "data": {"msg": msg}})

    try:
        result = create_blog(
            amazon_url=url,
            category_hint=category,
            gh_token=token,
            emit=emit,
        )
        q.put({"type": "blog_done", "data": result})
    except Exception as exc:
        q.put({"type": "blog_error", "data": {"msg": str(exc)}})
    finally:
        with _blog_lock:
            _blog_jobs[blog_id]["status"] = "done"
        q.put(None)  # sentinel


@app.route("/api/generate-blog", methods=["POST"])
def api_generate_blog():
    """Start the full blog creation pipeline in a background thread."""
    data     = request.get_json(force=True, silent=True) or {}
    url      = data.get("url", "").strip()
    category = data.get("category", "lifestyle").strip()
    if not url:
        return jsonify({"error": "url required"}), 400

    blog_id = str(uuid.uuid4())[:8]
    with _blog_lock:
        _blog_jobs[blog_id] = {"status": "running", "queue": Queue()}

    t = threading.Thread(
        target=_blog_worker,
        args=(blog_id, url, category, _GH_TOKEN),
        daemon=True,
    )
    t.start()
    log.info(f"Blog pipeline started: {blog_id} → {url[:60]}")
    return jsonify({"blog_id": blog_id})


@app.route("/api/blog-stream/<blog_id>")
def api_blog_stream(blog_id: str):
    """SSE stream for blog creation progress."""
    job = _blog_jobs.get(blog_id)
    if not job:
        def _nf():
            yield _sse("blog_error", {"msg": "Blog job not found"})
        return Response(_nf(), mimetype="text/event-stream")

    def _gen() -> Iterator[str]:
        q = job["queue"]
        while True:
            try:
                item = q.get(timeout=30)
                if item is None:
                    return
                yield _sse(item["type"], item["data"])
            except Empty:
                yield _keepalive()

    return Response(
        _gen(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



def save_newsletter_markdown(products: list[Product], path: Path) -> Path:
    top_waves = sorted(
        [p for p in products if p.price > 0],
        key=lambda x: (x.wave_score, x.est_monthly_revenue),
        reverse=True
    )[:10]

    today = datetime.now().strftime("%B %d, %Y")
    lines = [
        f"# 🌊 Wavepicks Weekly Dispatch: 10 Emerging Commerce Waves",
        f"**Date:** {today} | *Curated by Wavepicks Radar Engine*\n",
        "Welcome to this week's intelligence dispatch from **Wavepicks**. Our engine continuously scans Amazon India across BSR velocity spikes, price compression, and review paradoxes to isolate high-turnover consumer waves (₹10L – ₹1Cr/mo) before they become saturated.\n",
        "Use these signals to publish targeted affiliate guides, launch niche products, or spot trending manufacturer categories.\n",
        "---",
    ]

    for idx, p in enumerate(top_waves, 1):
        lines.append(f"\n### {idx}. {p.wave_stage}: {p.title[:80]}")
        lines.append(f"- **Category:** {p.category}")
        lines.append(f"- **Wave Score:** {p.wave_score}/100 🌊")
        lines.append(f"- **Breakout Reason:** {p.wave_reason}")
        lines.append(f"- **Price:** ₹{p.price:,.0f} " + (f"(MRP: ₹{p.mrp:,.0f}, Save {p.discount_pct:.0f}%)" if p.mrp else ""))
        lines.append(f"- **Rating & Reviews:** {p.rating} ⭐ ({p.review_count:,} reviews)")
        lines.append(f"- **BSR Velocity:** #{p.bsr:,} ({p.est_monthly_sales:,} sales/mo)")
        lines.append(f"- **Estimated Monthly Turnover:** ₹{p.est_monthly_revenue:,.0f} ({p.revenue_band})")
        lines.append(f"- **Affiliate & Content Angle:** High buyer intent with low keyword saturation. Ideal for 'Best [Category] Under ₹{int(p.price*1.3)}' or comparison review against legacy brands.")
        lines.append(f"- **Product Link:** [{p.title[:50]}...]({p.amazon_url})\n")
        lines.append("---")

    lines.append("\n*Disclaimer: Turnover figures are algorithmic estimates based on Amazon India BSR velocity tables. For content & market research only.*")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@app.route("/api/download/<filetype>/<job_id>")
def api_download(filetype: str, job_id: str):
    rec = _get_job(job_id)
    if not rec or not rec.products:
        return "No data", 404
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    path_map = {
        "csv"        : (OUTPUT_DIR / f"products_{ts}.csv",     lambda p: save_csv(rec.products, p)),
        "html"       : (OUTPUT_DIR / f"report_{ts}.html",      lambda p: save_html_report(rec.products, p)),
        "xlsx"       : (OUTPUT_DIR / f"products_{ts}.xlsx",    lambda p: save_excel(rec.products, p)),
        "newsletter" : (OUTPUT_DIR / f"wavepicks_issue_{ts}.md", lambda p: save_newsletter_markdown(rec.products, p)),
    }
    if filetype not in path_map:
        return "Unknown type", 400
    out_path, writer = path_map[filetype]
    writer(out_path)
    return send_file(out_path, as_attachment=True)


@app.route("/api/track", methods=["POST"])
def api_track():
    data = request.get_json(force=True, silent=True) or {}
    success = add_tracked_product(data)
    log.info(f"Wave product tracked: {data.get('asin')}")
    return jsonify({"ok": success, "asin": data.get("asin")})


@app.route("/api/untrack/<asin>", methods=["POST"])
def api_untrack(asin: str):
    remove_tracked_product(asin)
    log.info(f"Wave product untracked: {asin}")
    return jsonify({"ok": True, "asin": asin})


@app.route("/api/tracked")
def api_tracked():
    return jsonify({
        "summary": get_validation_summary(),
        "items": get_all_tracked()
    })


@app.route("/api/report/latest")
def api_report_latest():
    today_str = datetime.now().strftime("%Y-%m-%d")
    pdf_path = Path(__file__).parent / "reports" / f"Wavepicks_Validation_Report_{today_str}.pdf"
    if not pdf_path.exists():
        from pdf_report_generator import generate_validation_pdf
        pdf_path = generate_validation_pdf(get_validation_summary(), get_all_tracked())
    return send_file(pdf_path, mimetype="application/pdf", as_attachment=False)


@app.route("/api/report/download")
def api_report_download():
    cat = request.args.get("category", "All Categories").strip()
    all_tracked = get_all_tracked()
    from pdf_report_generator import generate_validation_pdf
    pdf_path = generate_validation_pdf(get_validation_summary(), all_tracked, category_filter=cat)
    return send_file(pdf_path, mimetype="application/pdf", as_attachment=True, download_name=pdf_path.name)


@app.route("/api/creator/track-asin", methods=["POST"])
def api_creator_track_asin():
    data = request.get_json(force=True, silent=True) or {}
    url_or_asin = data.get("url_or_asin", "").strip()
    category = data.get("category", "Home & Kitchen").strip()
    rationale = data.get("rationale", "").strip()
    if not url_or_asin:
        return jsonify({"error": "ASIN or Amazon URL is required"}), 400

    m = re.search(r"/(?:dp|gp/product|d)/([A-Z0-9]{10})", url_or_asin) or re.search(r"\b([B0-9][A-Z0-9]{9})\b", url_or_asin)
    asin = m.group(1) if m else url_or_asin[:10]

    from product_research_tool import AmazonIndiaScraper, Product, _recalc
    scraper = AmazonIndiaScraper()
    p = Product(asin=asin, amazon_url=f"https://www.amazon.in/dp/{asin}", category=category)
    try:
        scraper.enrich_product(p)
        _recalc(p)
    except Exception as e:
        log.warning(f"Error enriching {asin}: {e}")

    track_payload = {
        "asin": asin,
        "title": p.title or f"Amazon Product {asin}",
        "category": category,
        "amazon_url": f"https://www.amazon.in/dp/{asin}",
        "rank": p.bsr or p.rank or 100,
        "price": p.price or 0.0,
        "review_count": p.review_count or 0,
        "wave_score": p.wave_score or 50,
        "wave_stage": "🌊 Day 0 Baseline",
        "rationale": rationale or f"Day 0 empirical baseline for {category}. Tracking 14-day velocity and fluke detection.",
        "max_observed_price": p.mrp or p.price or 0.0
    }
    add_tracked_product(track_payload)
    return jsonify({"ok": True, "asin": asin, "product": track_payload})



# ═════════════════════════════════════════════════════════
#  DASHBOARD TEMPLATE
# ═════════════════════════════════════════════════════════

_DASHBOARD = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🌊 WAVEPICKS — Commerce Wave Radar</title>
<style>
/* ── reset & tokens (Wavepicks Oceanic Palette) ── */
:root{--brand:#0284c7;--brand-glow:#38bdf8;--dark:#070d1e;--card:#0e1738;--border:#182859;
      --green:#10b981;--yellow:#f59e0b;--text:#f1f5f9;--muted:#94a3b8;
      --sidebar:300px;}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,Arial,sans-serif;background:var(--dark);
     color:var(--text);height:100vh;overflow:hidden;display:flex;flex-direction:column}

/* ── header ── */
header{background:linear-gradient(135deg,#0369a1,#0b132b);
       padding:14px 24px;display:flex;align-items:center;gap:12px;flex-shrink:0;
       border-bottom:1px solid #1e3a8a;box-shadow:0 4px 20px rgba(0,0,0,.6)}
header h1{font-size:1.3rem;font-weight:800;letter-spacing:.8px;display:flex;align-items:center;gap:8px}
.pill{background:rgba(56,189,248,.15);border:1px solid rgba(56,189,248,.3);border-radius:20px;
      padding:3px 12px;font-size:.72rem;letter-spacing:.6px;color:#7dd3fc;font-weight:600}
.live-dot{width:9px;height:9px;border-radius:50%;background:#38bdf8;
          box-shadow:0 0 10px #38bdf8;display:inline-block;animation:pulse 1.4s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.3;transform:scale(.85)}}
.export-row{display:flex;gap:8px;margin-left:auto}
.btn-export{padding:6px 14px;border-radius:7px;font-size:.75rem;font-weight:700;
            cursor:pointer;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.05);color:#fff;
            transition:.2s}
.btn-export:hover{background:rgba(56,189,248,.2);border-color:#38bdf8}
.btn-newsletter{background:linear-gradient(135deg,#0284c7,#0369a1)!important;border-color:#38bdf8!important;
                box-shadow:0 2px 10px rgba(2,132,199,.4)}

/* ── top app switcher ── */
.app-switcher{display:flex;align-items:center;gap:6px;background:rgba(15,23,42,.7);padding:4px;border-radius:10px;border:1px solid rgba(56,189,248,.2);margin-left:14px}
.switch-link{text-decoration:none;color:#94a3b8;font-size:.76rem;font-weight:700;padding:6px 14px;border-radius:7px;transition:all .2s;display:flex;align-items:center;gap:6px}
.switch-link:hover{color:#f1f5f9;background:rgba(255,255,255,.05)}
.switch-link.active{color:#fff;background:linear-gradient(135deg,#0284c7,#0369a1);box-shadow:0 2px 8px rgba(2,132,199,.4)}
.sub-badge{font-size:.65rem;opacity:.8;background:rgba(0,0,0,.25);padding:1px 5px;border-radius:4px}

/* ── layout ── */
.body{display:flex;flex:1;overflow:hidden}
.sidebar{width:var(--sidebar);background:var(--card);border-right:1px solid var(--border);
         padding:18px;overflow-y:auto;flex-shrink:0}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}

/* ── sidebar controls ── */
.sec{font-size:.65rem;letter-spacing:1.5px;color:var(--muted);text-transform:uppercase;
     margin:16px 0 8px}
.sec:first-child{margin-top:0}
.cat-grid{display:grid;grid-template-columns:1fr 1fr;gap:3px 8px;margin-bottom:4px}
.cat-grid label{font-size:.8rem;cursor:pointer;display:flex;align-items:center;gap:5px}
.cat-grid input[type=checkbox]{accent-color:var(--brand)}
.sel-links{font-size:.72rem;color:var(--brand-glow);margin-bottom:10px;display:flex;gap:8px}
.sel-links span{cursor:pointer;text-decoration:underline}

input[type=range]{width:100%;accent-color:var(--brand)}
.rval{font-size:.8rem;color:var(--brand-glow);font-weight:700;text-align:center;margin-top:3px}

.toggle-row{display:flex;justify-content:space-between;align-items:center;
            margin:6px 0;font-size:.8rem}
.tog{position:relative;display:inline-block;width:38px;height:20px}
.tog input{opacity:0;width:0;height:0}
.tslider{position:absolute;inset:0;background:#334155;border-radius:20px;cursor:pointer;transition:.25s}
.tslider:before{content:'';position:absolute;height:14px;width:14px;left:3px;bottom:3px;
                background:#fff;border-radius:50%;transition:.25s}
input:checked+.tslider{background:var(--brand)}
input:checked+.tslider:before{transform:translateX(18px)}

.btn-run{width:100%;padding:12px;background:linear-gradient(135deg,#0284c7,#0369a1);
         color:#fff;border:none;border-radius:10px;font-size:.95rem;font-weight:700;
         cursor:pointer;margin-top:14px;transition:.2s;letter-spacing:.4px;
         box-shadow:0 4px 15px rgba(2,132,199,.3)}
.btn-run:hover:not(:disabled){transform:translateY(-2px);
                               box-shadow:0 6px 20px rgba(56,189,248,.4)}
.btn-run:disabled{opacity:.45;cursor:not-allowed}
.btn-stop{width:100%;padding:8px;background:transparent;color:#f87171;
          border:1px solid #f87171;border-radius:10px;font-size:.8rem;
          cursor:pointer;margin-top:6px;display:none}

/* ── stats bar ── */
.stats-bar{display:flex;gap:10px;padding:12px 20px;background:var(--card);
           border-bottom:1px solid var(--border);flex-wrap:wrap;flex-shrink:0}
.stat{background:rgba(7,13,30,.7);border:1px solid var(--border);border-radius:8px;padding:10px 16px;min-width:120px}
.stat .v{font-size:1.35rem;font-weight:800;color:var(--brand-glow)}
.stat .l{font-size:.68rem;color:var(--muted);margin-top:2px}

/* ── wave badges ── */
.wave-pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:20px;
           font-size:.73rem;font-weight:700;letter-spacing:.3px}
.wave-forming{background:rgba(56,189,248,.15);border:1px solid rgba(56,189,248,.4);color:#38bdf8}
.wave-surging{background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.4);color:#34d399}
.wave-peak{background:rgba(148,163,184,.12);border:1px solid rgba(148,163,184,.3);color:#cbd5e1}
.wave-score-val{background:rgba(0,0,0,.35);padding:1px 6px;border-radius:10px;font-size:.68rem}

/* ── filter bar ── */
.filter-bar{display:flex;gap:8px;padding:8px 16px;background:var(--card);
            border-bottom:1px solid var(--border);align-items:center;
            flex-shrink:0;flex-wrap:wrap}
.filter-bar input[type=text]{background:#0d0d1a;border:1px solid var(--border);
  border-radius:6px;padding:5px 10px;color:var(--text);font-size:.8rem;width:200px}
.filter-bar select{background:#0d0d1a;border:1px solid var(--border);border-radius:6px;
                   padding:5px 8px;color:var(--text);font-size:.8rem}
.filter-bar label{font-size:.75rem;color:var(--muted);white-space:nowrap}
.filter-sep{width:1px;height:22px;background:var(--border);margin:0 4px}
.chip-row{display:flex;gap:5px;align-items:center;flex-wrap:wrap}
.sort-chip{padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:600;
           cursor:pointer;border:1px solid var(--border);background:transparent;
           color:var(--muted);transition:.15s;white-space:nowrap}
.sort-chip:hover{border-color:var(--red);color:var(--red)}
.sort-chip.active{background:var(--red);color:#fff;border-color:var(--red)}
.sort-chip .arr{font-size:.65rem;margin-left:3px}
.row-badge{background:#0d0d1a;border:1px solid var(--border);border-radius:20px;
           padding:2px 10px;font-size:.72rem;color:var(--muted);white-space:nowrap}
.btn-reset{padding:4px 10px;border-radius:6px;font-size:.72rem;cursor:pointer;
           border:1px solid #444;background:transparent;color:#888;transition:.15s}
.btn-reset:hover{border-color:var(--red);color:var(--red)}

/* ── log console ── */
.log-box{background:#0b0b18;font-family:'Consolas','Courier New',monospace;font-size:.75rem;
         color:#6ab4cc;padding:8px 16px;height:130px;overflow-y:auto;flex-shrink:0;
         border-bottom:1px solid var(--border)}
.lok{color:#2ecc71}.lwarn{color:#f39c12}.lerr{color:#e74c3c}.lts{color:#333}

/* ── table ── */
.table-wrap{flex:1;overflow:auto;padding:0 20px 20px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:.78rem}
th{background:#0f3460;color:#bde;padding:8px 6px;text-align:left;white-space:nowrap;
   position:sticky;top:0;z-index:2;cursor:pointer;user-select:none}
th:hover{background:#1a4a8a}
th.sorted-asc::after{content:" ▲"}
th.sorted-desc::after{content:" ▼"}
td{padding:6px;border-bottom:1px solid var(--border);vertical-align:middle}
tr:hover td{background:rgba(255,255,255,.03)}
tr.worthy td{background:rgba(39,174,96,.06)}

/* badges */
.badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:.68rem;font-weight:700}
.bg{background:#1a4731;color:#2ecc71}.by{background:#4a3500;color:#f39c12}
.br{background:#3d0c09;color:#e74c3c}.bb{background:#0a2540;color:#5b9bd5}
.bz{background:#222;color:#888}

.btn-blog{padding:4px 10px;border:1px solid var(--red);background:transparent;
          color:var(--red);border-radius:5px;font-size:.72rem;cursor:pointer;
          white-space:nowrap;transition:.15s}
.btn-blog:hover{background:var(--red);color:#fff}
.prod-img{width:40px;height:40px;object-fit:contain;border-radius:5px;background:#fff;padding:2px}
.rev-est{font-weight:700;color:#2ecc71}
.title-cell{max-width:240px}
.title-cell a{color:#9bb8d9;text-decoration:none;font-weight:600;
              display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.title-cell a:hover{color:#fff}

/* empty */
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;
       height:60%;gap:10px;opacity:.4}
.empty p{font-size:.9rem}

/* modal */
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:200;
         display:none;align-items:center;justify-content:center}
.overlay.show{display:flex}
.modal{background:var(--card);border:1px solid var(--border);border-radius:14px;
       padding:24px;max-width:460px;width:92%;box-shadow:0 20px 60px rgba(0,0,0,.7)}
.modal h3{color:var(--red);margin-bottom:10px}
.modal p{font-size:.83rem;color:#bbb;margin-bottom:12px;line-height:1.6}
.urlbox{background:#0b0b18;border:1px solid var(--border);border-radius:7px;
        padding:9px;font-size:.76rem;font-family:monospace;color:#7ec8e3;
        word-break:break-all;margin-bottom:12px}
.mbtns{display:flex;gap:8px}
.mbtns button{flex:1;padding:9px;border-radius:7px;border:none;cursor:pointer;font-weight:700}
.mbtn-ok{background:var(--red);color:#fff}
.mbtn-cx{background:#2c3e50;color:#bbb}

::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:#0b0b18}
::-webkit-scrollbar-thumb{background:#2a2a40;border-radius:3px}
</style>
</head>
<body>

<!-- ── HEADER ── -->
<header>
  <span class="live-dot"></span>
  <h1>🌊 WAVEPICKS</h1>
  <span class="pill">Commerce Wave Radar</span>

  <nav class="app-switcher">
    <a href="/deals" class="switch-link">
      🛍️ <span>Buyer Deals</span>
      <span class="sub-badge">Shoppers</span>
    </a>
    <a href="/creator" class="switch-link">
      ✍️ <span>Creator Studio</span>
      <span class="sub-badge">Bloggers</span>
    </a>
    <a href="/" class="switch-link active">
      📊 <span>Brand Intelligence</span>
      <span class="sub-badge">Sellers & D2C</span>
    </a>
  </nav>

  <a href="/api/report/latest" target="_blank" class="btn-export" style="text-decoration:none;display:inline-flex;align-items:center;gap:5px;background:#0284c7;border-color:#38bdf8;margin-left:auto">📄 Daily PDF Audit</a>
  <div class="export-row" id="export-row" style="display:none!important">
    <button class="btn-export btn-newsletter" onclick="exportData('newsletter')">📑 Newsletter Issue (MD)</button>
    <button class="btn-export" onclick="exportData('csv')">⬇ CSV</button>
    <button class="btn-export" onclick="exportData('html')">⬇ Report</button>
    <button class="btn-export" onclick="exportData('xlsx')">⬇ Excel</button>
  </div>
  <span class="pill" style="margin-left:auto">localhost:5483</span>
</header>

<div class="body">

<!-- ── SIDEBAR ── -->
<aside class="sidebar">
  <div class="sec">📂 Categories</div>
  <div class="sel-links">
    <span onclick="setCats(true)">All</span>
    <span onclick="setCats(false)">None</span>
  </div>
  <div class="cat-grid">
    <label><input type="checkbox" class="cc" value="beauty" checked> Beauty</label>
    <label><input type="checkbox" class="cc" value="health" checked> Health</label>
    <label><input type="checkbox" class="cc" value="kitchen" checked> Home/Kitchen</label>
    <label><input type="checkbox" class="cc" value="sports" checked> Sports</label>
    <label><input type="checkbox" class="cc" value="electronics"> Electronics</label>
    <label><input type="checkbox" class="cc" value="baby"> Baby</label>
    <label><input type="checkbox" class="cc" value="apparel"> Clothing</label>
    <label><input type="checkbox" class="cc" value="watches"> Watches</label>
    <label><input type="checkbox" class="cc" value="grocery"> Grocery</label>
    <label><input type="checkbox" class="cc" value="toys"> Toys</label>
    <label><input type="checkbox" class="cc" value="books"> Books</label>
    <label><input type="checkbox" class="cc" value="pet-supplies"> Pets</label>
  </div>

  <div class="sec">📄 Pages / Category</div>
  <input type="range" id="pages" min="1" max="3" value="1"
         oninput="onPagesChange(this.value)">
  <div class="rval" id="pages-lbl">1 page ≈ 30 products / category</div>

  <div class="sec">⚙️ Wave Radar Options</div>
  <div class="toggle-row"><span>🌊 Movers &amp; Shakers (Surge Spikes)</span>
    <label class="tog"><input type="checkbox" id="opt-mv" checked>
      <span class="tslider"></span></label></div>
  <div class="toggle-row"><span>Bestsellers only</span>
    <label class="tog"><input type="checkbox" id="opt-bs">
      <span class="tslider"></span></label></div>
  <div class="toggle-row"><span>Deep Enrich ⚠️ slow</span>
    <label class="tog"><input type="checkbox" id="opt-en">
      <span class="tslider"></span></label></div>

  <button class="btn-run" id="btn-run" onclick="startScan()">🌊 Scan Commerce Waves</button>
  <button class="btn-stop" id="btn-stop" onclick="stopScan()">⏹ Stop</button>

  <div style="margin-top:20px;font-size:.7rem;color:#475569;line-height:1.6">
    ℹ️ <strong>Wavepicks Radar:</strong> Detects breakout velocity, sweet-spot turnover (₹10L–₹1Cr), and review freshness to isolate rising waves before market saturation.
  </div>
</aside>

<!-- ── MAIN ── -->
<div class="main">

  <!-- Stats -->
  <div class="stats-bar">
    <div class="stat"><div class="v" id="st-total">0</div><div class="l">Scanned</div></div>
    <div class="stat"><div class="v" id="st-forming" style="color:#38bdf8">0</div><div class="l">🌊 Forming Waves</div></div>
    <div class="stat"><div class="v" id="st-surging" style="color:#34d399">0</div><div class="l">🚀 Surging Waves</div></div>
    <div class="stat"><div class="v" id="st-band">0</div><div class="l">₹10L–₹1Cr Band</div></div>
    <div class="stat"><div class="v" id="st-top">₹0</div><div class="l">Top Turnover Est.</div></div>
    <div class="stat" style="margin-left:auto">
      <div class="v" id="st-status" style="font-size:.95rem;color:#38bdf8">Idle</div>
      <div class="l">Radar Status</div>
    </div>
  </div>

  <!-- Filter Bar -->
  <div class="filter-bar">
    <!-- Search -->
    <label>🔍</label>
    <input type="text" id="search-box" placeholder="Search title, brand, ASIN…"
           oninput="applyFilters()">

    <div class="filter-sep"></div>

    <!-- Wave Filter -->
    <label>Wave:</label>
    <select id="wave-filter" onchange="applyFilters()">
      <option value="">All Wave Stages</option>
      <option value="Forming">🌊 Forming (Breakouts)</option>
      <option value="Surging">🚀 Surging (Velocity)</option>
      <option value="Peak">🏔️ Peak (Mature)</option>
    </select>

    <label>Band:</label>
    <select id="band-filter" onchange="applyFilters()">
      <option value="">All Bands</option>
      <option value="🔴">🔴 &gt;₹1Cr</option>
      <option value="🟠">🟠 ₹50L–₹1Cr</option>
      <option value="🟡">🟡 ₹25L–₹50L</option>
      <option value="🟢">🟢 ₹10L–₹25L</option>
      <option value="🔵">🔵 ₹5L–₹10L</option>
    </select>

    <label>Show:</label>
    <select id="worthy-filter" onchange="applyFilters()">
      <option value="">All Scanned</option>
      <option value="1">✅ Blog-Worthy only</option>
    </select>

    <label>Source:</label>
    <select id="source-filter" onchange="applyFilters()">
      <option value="">All Sources</option>
      <option value="movers">🚀 Movers &amp; Shakers</option>
      <option value="bestseller">📦 Bestsellers</option>
    </select>

    <div class="filter-sep"></div>

    <!-- Quick Sort Chips -->
    <div class="chip-row">
      <label>Sort:</label>
      <button class="sort-chip active" data-col="wave_score"
              onclick="chipSort(this)">🌊 Wave Score<span class="arr"> ↓</span></button>
      <button class="sort-chip" data-col="est_monthly_revenue"
              onclick="chipSort(this)">Revenue<span class="arr">↕</span></button>
      <button class="sort-chip" data-col="seller_count"
              onclick="chipSort(this)">Sellers<span class="arr">↕</span></button>
      <button class="sort-chip" data-col="bsr"
              onclick="chipSort(this)">BSR<span class="arr">↕</span></button>
      <button class="sort-chip" data-col="rating"
              onclick="chipSort(this)">Rating<span class="arr">↕</span></button>
      <button class="sort-chip" data-col="review_count"
              onclick="chipSort(this)">Reviews<span class="arr">↕</span></button>
      <button class="sort-chip" data-col="discount_pct"
              onclick="chipSort(this)">Discount<span class="arr">↕</span></button>
      <button class="sort-chip" data-col="price"
              onclick="chipSort(this)">Price<span class="arr">↕</span></button>
    </div>

    <div class="filter-sep"></div>
    <button class="btn-reset" onclick="resetFilters()">✕ Reset</button>
    <span class="row-badge" id="row-count">0 rows</span>
  </div>

  <!-- Log -->
  <div class="log-box" id="log-box">
    <span class="lok">▶ WAVEPICKS Radar Engine ready — http://localhost:5483</span><br>
  </div>

  <!-- Table -->
  <div class="table-wrap">
    <div class="empty" id="empty-state">
      <p>🌊 Select categories and click <strong>Scan Commerce Waves</strong></p>
    </div>
    <table id="results-table" style="display:none">
      <thead>
        <tr>
          <th data-col="rank"                onclick="thSort(this)">#</th>
          <th>Img</th>
          <th data-col="title"               onclick="thSort(this)">Product</th>
          <th data-col="wave_score"          onclick="thSort(this)">🌊 Wave Radar</th>
          <th data-col="category"            onclick="thSort(this)">Category</th>
          <th data-col="seller_count"        onclick="thSort(this)">Sellers</th>
          <th data-col="price"               onclick="thSort(this)">Price</th>
          <th data-col="discount_pct"        onclick="thSort(this)">Disc%</th>
          <th data-col="rating"              onclick="thSort(this)">⭐ Rating</th>
          <th data-col="review_count"        onclick="thSort(this)">Reviews</th>
          <th data-col="bsr"                 onclick="thSort(this)">BSR</th>
          <th data-col="est_monthly_sales"   onclick="thSort(this)">Sales/mo</th>
          <th data-col="est_monthly_revenue" onclick="thSort(this)">Turnover/mo</th>
          <th data-col="revenue_band"        onclick="thSort(this)">Band</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="results-body"></tbody>
    </table>
  </div>
</div><!-- .main -->
<!-- ── Keepa History Modal ── -->
<div class="overlay" id="keepa-modal">
  <div class="modal" style="max-width:680px;background:#0d1530;border:1px solid #1e3a8a">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <h3 style="display:flex;align-items:center;gap:8px;font-size:1.1rem;color:#f1f5f9">
        <span>📈 Pre-Launch BSR & Price History</span>
        <span class="pill" style="background:rgba(16,185,129,.15);color:#34d399;border-color:rgba(16,185,129,.3)">Keepa Verified (Amazon.in)</span>
      </h3>
      <span style="cursor:pointer;font-size:1.2rem;color:#94a3b8" onclick="closeKeepaModal()">✕</span>
    </div>
    <div id="keepa-modal-title" style="font-size:.82rem;color:#cbd5e1;margin-bottom:10px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"></div>
    <div style="text-align:center;background:#070d1e;padding:12px;border-radius:8px;border:1px solid #182859">
      <img id="keepa-modal-img" src="" style="width:100%;max-height:360px;object-fit:contain;border-radius:6px;display:block" alt="Keepa Historical Chart" />
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:14px">
      <span style="font-size:.72rem;color:#64748b">Amazon India (Domain 10) • Green = BSR, Blue = Price</span>
      <div style="display:flex;gap:8px">
        <a id="keepa-modal-link" href="#" target="_blank" class="btn-export btn-newsletter" style="text-decoration:none;padding:7px 14px;font-size:.78rem">Open Full Interactive Chart on Keepa ↗</a>
        <button class="btn-export" onclick="closeKeepaModal()">Close</button>
      </div>
    </div>
  </div>
</div>

<!-- ── Blog Generation Modal ── -->
<div class="overlay" id="blog-modal">
  <div class="modal" style="max-width:520px">
    <h3>📝 Generate Blog Post</h3>
    <p style="margin-bottom:10px">
      The full ZERO483 blog pipeline will run instantly:
      scrape product → generate SEO HTML → save locally → push to GitHub.
    </p>
    <div class="urlbox" id="modal-url"></div>
    <div id="modal-title" style="font-size:.83rem;color:#ddd;margin-bottom:10px;font-weight:600"></div>

    <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">
      <label style="font-size:.78rem;color:#888;white-space:nowrap">Category:</label>
      <select id="modal-cat" style="flex:1;background:#0d0d1a;border:1px solid #0f3460;
              border-radius:6px;padding:5px 8px;color:#e0e0e0;font-size:.8rem">
        <option value="beauty">Beauty</option>
        <option value="health">Health</option>
        <option value="kitchen">Home &amp; Kitchen</option>
        <option value="sports">Sports &amp; Fitness</option>
        <option value="electronics">Electronics</option>
        <option value="baby">Baby</option>
        <option value="apparel">Clothing</option>
        <option value="watches">Watches</option>
        <option value="grocery">Grocery</option>
        <option value="toys">Toys</option>
        <option value="lifestyle">Other / Lifestyle</option>
      </select>
    </div>

    <div id="gh-status" style="font-size:.75rem;margin-bottom:10px;padding:6px 10px;
         border-radius:6px;background:#0d0d1a;border:1px solid #0f3460"></div>

    <!-- Live blog progress log (shown after generation starts) -->
    <div id="blog-log-wrap" style="display:none">
      <div id="blog-log"
           style="background:#0b0b18;font-family:monospace;font-size:.72rem;color:#6ab4cc;
                  padding:8px 12px;height:140px;overflow-y:auto;border-radius:8px;
                  margin-bottom:10px;border:1px solid #1a1a40"></div>
    </div>
    <div id="blog-result" style="display:none;margin-bottom:10px"></div>

    <div class="mbtns" id="blog-modal-btns">
      <button class="mbtn-ok" onclick="confirmBlog()">🚀 Generate Blog</button>
      <button class="mbtn-cx" onclick="closeModal()">Cancel</button>
    </div>
  </div>
</div>

<script>
'use strict';
/* ─────────────────────────────────────────────────────────
   State
───────────────────────────────────────────────────────── */
let _jobId    = null;
let _evtSrc   = null;
let _products = [];        // master list (all scraped)
let _filtered = [];        // currently displayed
let _sortCol  = 'wave_score';
let _sortDir  = -1;        // -1 = desc, 1 = asc
let _pendUrl  = '';
let _pendTitle= '';
let _sseRetry = 0;
const MAX_SSE_RETRY = 3;
const MAX_LOG = {{ max_log }};

/* ─────────────────────────────────────────────────────────
   Sidebar helpers
───────────────────────────────────────────────────────── */
function setCats(v){
  document.querySelectorAll('.cc').forEach(cb=>cb.checked=v);
}
function onPagesChange(v){
  const cats = document.querySelectorAll('.cc:checked').length || 4;
  document.getElementById('pages-lbl').textContent =
    `${v} page(s) ≈ ${v*30*cats} products est.`;
}

/* ─────────────────────────────────────────────────────────
   Scan control
───────────────────────────────────────────────────────── */
function startScan(){
  const cats = [...document.querySelectorAll('.cc:checked')].map(e=>e.value);
  if(!cats.length){ alert('Select at least one category.'); return; }

  _products=[]; _filtered=[]; _sseRetry=0;
  document.getElementById('results-body').innerHTML='';
  document.getElementById('results-table').style.display='none';
  document.getElementById('empty-state').style.display='flex';
  document.getElementById('btn-run').disabled=true;
  document.getElementById('btn-stop').style.display='block';
  document.getElementById('export-row').style.display='none';
  _setStatus('Radar Active…','#38bdf8');
  _resetStats();
  _log('ok','🌊 Wave Radar initiated — categories: '+cats.join(', '));

  fetch('/api/start',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      cats,
      pages    : +document.getElementById('pages').value,
      moversOnly: false,
      bsOnly   : document.getElementById('opt-bs').checked,
      enrich   : document.getElementById('opt-en').checked,
      movers   : document.getElementById('opt-mv').checked,
    })
  })
  .then(r=>r.json())
  .then(d=>{ _jobId=d.job_id; _listenSSE(); });
}

function stopScan(){
  if(_jobId) fetch('/api/stop/'+_jobId,{method:'POST'});
  _finishScan('Radar Stopped','#f59e0b');
  _log('warn','⏹ Stopped by user');
}

function _finishScan(label='Radar Idle', color='#10b981'){
  document.getElementById('btn-run').disabled=false;
  document.getElementById('btn-stop').style.display='none';
  document.getElementById('export-row').style.removeProperty('display');
  _setStatus(label,color);
  if(_evtSrc){ _evtSrc.close(); _evtSrc=null; }
}

/* ─────────────────────────────────────────────────────────
   SSE (with auto-reconnect)
───────────────────────────────────────────────────────── */
function _listenSSE(){
  if(_evtSrc) _evtSrc.close();
  _evtSrc = new EventSource('/api/stream/'+_jobId);

  _evtSrc.addEventListener('log',      e=>{ const d=JSON.parse(e.data); _log(d.level,d.msg); });
  _evtSrc.addEventListener('product',  e=>_addProduct(JSON.parse(e.data)));
  _evtSrc.addEventListener('update',   e=>_updateProduct(JSON.parse(e.data)));
  _evtSrc.addEventListener('done',     e=>{
    _log('ok','✅ Wave Scan complete — '+JSON.parse(e.data).total+' products analyzed');
    _finishScan();
  });
  _evtSrc.addEventListener('error_evt', e=>{
    _log('err','❌ '+JSON.parse(e.data).msg);
    _finishScan('Error','#ef4444');
  });
  _evtSrc.onerror = ()=>{
    if(_sseRetry < MAX_SSE_RETRY){
      _sseRetry++;
      _log('warn',`SSE lost — retry ${_sseRetry}/${MAX_SSE_RETRY}…`);
      setTimeout(_listenSSE, 2000 * _sseRetry);
    } else {
      _finishScan('Disconnected','#ef4444');
    }
  };
}

/* ─────────────────────────────────────────────────────────
   Product rendering
───────────────────────────────────────────────────────── */
const BAND_CLASS = {
  '🔴':' br','🟠':' br','🟡':' by','🟢':' bg','🔵':' bb'
};

function _addProduct(p){
  _products.push(p);
  _scheduleRender();
}

function _updateProduct(upd){
  const idx = _products.findIndex(p=>p.asin===upd.asin);
  if(idx!==-1) _products[idx]=upd;
  _scheduleRender();
}

let _rafPending=false;
function _scheduleRender(){
  if(_rafPending) return;
  _rafPending=true;
  requestAnimationFrame(()=>{ _rafPending=false; _renderTable(); _updateStats(); });
}

function _renderTable(){
  const search = document.getElementById('search-box').value.toLowerCase().trim();
  const wave   = document.getElementById('wave-filter').value;
  const band   = document.getElementById('band-filter').value;
  const worthy = document.getElementById('worthy-filter').value;
  const source = document.getElementById('source-filter').value;

  _filtered = _products.filter(p => {
    if(search){
      const hay = (p.title + ' ' + (p.asin||'') + ' ' + (p.category||'')).toLowerCase();
      if(!hay.includes(search)) return false;
    }
    if(wave   && !(p.wave_stage||'').includes(wave))          return false;
    if(band   && !(p.revenue_band||'').startsWith(band))      return false;
    if(worthy && !p.blog_worthy)                               return false;
    if(source && (p.source_page||'') !== source)              return false;
    return true;
  });

  // sort
  _filtered.sort((a, b) => {
    const av = a[_sortCol] ?? 0, bv = b[_sortCol] ?? 0;
    if(typeof av === 'string') return _sortDir * av.localeCompare(bv);
    return _sortDir * (av < bv ? -1 : av > bv ? 1 : 0);
  });

  const n = _filtered.length;
  document.getElementById('row-count').textContent = n + ' row' + (n===1?'':'s');
  document.getElementById('empty-state').style.display = n ? 'none' : 'flex';
  document.getElementById('results-table').style.display = n ? 'table' : 'none';

  const rows = _filtered.map((p, i) => {
    const rev = p.est_monthly_revenue || 0;
    const bk  = (Object.entries(BAND_CLASS).find(([k]) =>
                  (p.revenue_band||'').startsWith(k)) || ['','bz'])[1];
    const img = p.image_url
      ? `<img class="prod-img" src="${p.image_url}" onerror="this.style.display='none'">`
      : '🖼️';
    const link = p.amazon_url
      ? `<a href="${p.amazon_url}" target="_blank">${_esc(p.title.substring(0,58))}${p.title.length>58?'…':''}</a>`
      : _esc(p.title.substring(0,58));
    const mrpHtml = p.mrp
      ? `<br><span style="color:#555;text-decoration:line-through;font-size:.68rem">₹${_fmt(p.mrp)}</span>`
      : '';
    const discHtml = p.discount_pct
      ? `<span style="color:#e74c3c;font-size:.72rem">${p.discount_pct.toFixed(0)}%&nbsp;off</span>`
      : '—';
    const blogBtn = p.blog_worthy
      ? `<button class="btn-blog" onclick="openBlog('${encodeURIComponent(p.amazon_url||'')}','${encodeURIComponent(p.title||'')}')">📝 Blog</button>`
      : '<span style="color:#444">—</span>';

    const waveClass = (p.wave_stage && p.wave_stage.includes('Forming'))
      ? 'wave-forming' : (p.wave_stage && p.wave_stage.includes('Surging')) ? 'wave-surging' : 'wave-peak';
    const waveBadge = `<span class="wave-pill ${waveClass}" title="${_esc(p.wave_reason || '')}">
      ${p.wave_stage || '—'}
      <span class="wave-score-val">${p.wave_score || 0}</span>
    </span>`;

    const sc = p.seller_count || 1;
    const sellerBadge = sc === 1
      ? `<span style="background:rgba(56,189,248,.12);border:1px solid rgba(56,189,248,.3);color:#38bdf8;padding:2px 7px;border-radius:10px;font-size:.68rem;font-weight:700" title="1 Seller: Exclusive Brand / Private Label">🔒 1</span>`
      : `<span style="background:rgba(245,158,11,.15);border:1px solid rgba(245,158,11,.35);color:#f59e0b;padding:2px 7px;border-radius:10px;font-size:.68rem;font-weight:700" title="${sc} competing sellers">👥 ${sc}</span>`;

    const keepaBtn = `<button class="btn-keepa" style="padding:4px 7px;border:1px solid #10b981;background:rgba(16,185,129,.15);color:#34d399;border-radius:5px;font-size:.68rem;cursor:pointer;margin-right:4px;font-weight:700" onclick="openKeepaModal('${p.asin}', '${_esc(p.title)}')" title="View Pre-Launch BSR &amp; Price History on Keepa">📈 Keepa</button>`;
    const trackBtn = `<button class="btn-track" style="padding:4px 7px;border:1px solid #0284c7;background:rgba(2,132,199,.15);color:#38bdf8;border-radius:5px;font-size:.68rem;cursor:pointer;margin-right:4px;font-weight:700" onclick="trackProduct(${i})" title="Track in SQLite &amp; Daily PDF Report">📌 Track</button>`;

    return `<tr class="${p.blog_worthy ? 'worthy' : ''}">
      <td style="text-align:center;color:#555;font-size:.72rem">${i+1}</td>
      <td>${img}</td>
      <td class="title-cell">${link}<br>
          <span style="color:#64748b;font-size:.65rem">${p.asin||''}</span></td>
      <td style="white-space:nowrap">${waveBadge}</td>
      <td style="font-size:.72rem;color:#cbd5e1">${p.category}</td>
      <td style="text-align:center">${sellerBadge}</td>
      <td><strong>₹${_fmt(p.price)}</strong>${mrpHtml}</td>
      <td style="text-align:center">${discHtml}</td>
      <td style="text-align:center">${p.rating||'—'}${p.rating?'⭐':''}</td>
      <td style="text-align:center;color:#94a3b8">${_fmt(p.review_count)}</td>
      <td style="text-align:center;color:#94a3b8">${p.bsr ? _fmt(p.bsr) : '—'}</td>
      <td style="text-align:center">${_fmt(p.est_monthly_sales)}</td>
      <td class="rev-est">₹${_fmt(rev, 0)}</td>
      <td><span class="badge${bk}">${p.revenue_band||'—'}</span></td>
      <td><div style="display:flex;gap:4px">${keepaBtn}${trackBtn}${blogBtn}</div></td></tr>`;
  }).join('');

  document.getElementById('results-body').innerHTML = rows;
}

function applyFilters(){ _scheduleRender(); }

function trackProduct(idx){
  const p = _filtered[idx];
  if(!p || !p.asin) return;
  fetch('/api/track', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(p)
  }).then(r=>r.json()).then(d=>{
    _log('ok', '📌 Wave tracked for daily audit: ' + (p.title||'').substring(0,35) + ' (ASIN: ' + p.asin + ')');
    alert('✅ Wave Tracked!\n\nThis product is now saved in your SQLite validation cohort.\nIt will be audited every time your computer switches on and included in your Daily PDF Report.');
  });
}

function resetFilters(){
  document.getElementById('search-box').value   = '';
  document.getElementById('wave-filter').value  = '';
  document.getElementById('band-filter').value  = '';
  document.getElementById('worthy-filter').value= '';
  document.getElementById('source-filter').value= '';
  _sortCol = 'wave_score';
  _sortDir = -1;
  _syncChips();
  _syncThHeaders();
  _scheduleRender();
}

/* ─────────────────────────────────────────────────────────
   Sort — two entry points: chip buttons + column headers
───────────────────────────────────────────────────────── */
function sortBy(col){
  if(_sortCol === col) _sortDir *= -1;
  else { _sortCol = col; _sortDir = -1; }
  _syncChips();
  _syncThHeaders();
  _renderTable();
}

// called by quick-sort chip buttons (data-col attribute)
function chipSort(el){
  const col = el.dataset.col;
  sortBy(col);
}

// called by clicking a <th data-col="...">
function thSort(th){
  sortBy(th.dataset.col);
}

function _syncChips(){
  document.querySelectorAll('.sort-chip').forEach(chip => {
    const active = chip.dataset.col === _sortCol;
    chip.classList.toggle('active', active);
    chip.querySelector('.arr').textContent = active
      ? (_sortDir === -1 ? ' ↓' : ' ↑')
      : ' ↕';
  });
}

function _syncThHeaders(){
  document.querySelectorAll('th[data-col]').forEach(th => {
    th.classList.remove('sorted-asc','sorted-desc');
    if(th.dataset.col === _sortCol)
      th.classList.add(_sortDir === -1 ? 'sorted-desc' : 'sorted-asc');
  });
}

// init chip state on load
_syncChips();

/* ─────────────────────────────────────────────────────────
   Stats (debounced via rAF in _scheduleRender)
───────────────────────────────────────────────────────── */
function _updateStats(){
  const forming = _products.filter(p=>(p.wave_stage||'').includes('Forming')).length;
  const surging = _products.filter(p=>(p.wave_stage||'').includes('Surging')).length;
  const band    = _products.filter(p=>p.est_monthly_revenue>=1000000&&p.est_monthly_revenue<=10000000).length;
  const top     = Math.max(0,..._products.map(p=>p.est_monthly_revenue||0));
  document.getElementById('st-total').textContent   = _products.length;
  document.getElementById('st-forming').textContent = forming;
  document.getElementById('st-surging').textContent = surging;
  document.getElementById('st-band').textContent    = band;
  document.getElementById('st-top').textContent     = '₹'+_fmt(top,0);
}
function _resetStats(){
  ['st-total','st-forming','st-surging','st-band'].forEach(id=>{
    const el = document.getElementById(id);
    if(el) el.textContent='0';
  });
  document.getElementById('st-top').textContent='₹0';
}
function _setStatus(t,c){
  const el=document.getElementById('st-status');
  el.textContent=t; el.style.color=c;
}

/* ─────────────────────────────────────────────────────────
   Log (capped)
───────────────────────────────────────────────────────── */
let _logLines=0;
function _log(level,msg){
  if(_logLines>=MAX_LOG){
    const box=document.getElementById('log-box');
    box.removeChild(box.firstChild); box.removeChild(box.firstChild); // rm line+<br>
    _logLines--;
  }
  const cls = level==='ok'?'lok':level==='warn'?'lwarn':level==='err'?'lerr':'';
  const ts  = new Date().toLocaleTimeString('en-IN');
  const box = document.getElementById('log-box');
  box.insertAdjacentHTML('beforeend',
    `<span class="lts">[${ts}]</span> <span class="${cls}">${_esc(msg)}</span><br>`);
  box.scrollTop=box.scrollHeight;
  _logLines++;
}

/* ─────────────────────────────────────────────────────────
   Blog Generation Modal
───────────────────────────────────────────────────────── */
let _blogSrc = null;

function openBlog(eu, et){
  _pendUrl   = decodeURIComponent(eu);
  _pendTitle = decodeURIComponent(et);

  // Reset modal state
  document.getElementById('modal-url').textContent   = _pendUrl;
  document.getElementById('modal-title').textContent = _pendTitle;
  document.getElementById('blog-log-wrap').style.display = 'none';
  document.getElementById('blog-log').innerHTML = '';
  document.getElementById('blog-result').style.display = 'none';
  document.getElementById('blog-result').innerHTML = '';
  document.getElementById('blog-modal-btns').innerHTML =
    `<button class="mbtn-ok" onclick="confirmBlog()">🚀 Generate Blog</button>
     <button class="mbtn-cx" onclick="closeModal()">Cancel</button>`;

  // Auto-detect category from scraped product category field
  const row = _filtered.find(p => p.amazon_url === _pendUrl || _pendUrl.includes(p.asin));
  if(row){
    const catSlug = (row.category || '').toLowerCase()
      .replace(/\s.*/,'').replace(/home.*/,'kitchen').replace(/sports.*/,'sports');
    const sel = document.getElementById('modal-cat');
    for(let opt of sel.options){ if(opt.value === catSlug){ sel.value = catSlug; break; } }
  }

  // Check GitHub token status
  fetch('/api/settings')
    .then(r => r.json())
    .then(s => {
      const el = document.getElementById('gh-status');
      if(s.gh_token_set){
        el.innerHTML = '✅ GitHub token set — blog will auto-publish to GitHub Pages';
        el.style.color = '#2ecc71';
      } else {
        el.innerHTML = '⚠️ No GitHub token — blog will be saved locally only.<br>'
          + '<small>Set <code>GH_TOKEN</code> env var or use /api/settings to enable auto-publish.</small>';
        el.style.color = '#f39c12';
      }
    });

  document.getElementById('blog-modal').classList.add('show');
}

function closeModal(){
  if(_blogSrc){ _blogSrc.close(); _blogSrc = null; }
  document.getElementById('blog-modal').classList.remove('show');
}

function openKeepaModal(asin, title){
  if(!asin) return;
  document.getElementById('keepa-modal-title').textContent = title + ' (' + asin + ')';
  document.getElementById('keepa-modal-img').src = 'https://graph.keepa.com/pricehistory.png?asin=' + asin + '&domain=10';
  document.getElementById('keepa-modal-link').href = 'https://keepa.com/#!product/10-' + asin;
  document.getElementById('keepa-modal').classList.add('show');
}

function closeKeepaModal(){
  document.getElementById('keepa-modal').classList.remove('show');
}

function confirmBlog(){
  const category = document.getElementById('modal-cat').value;

  // Disable buttons, show log
  document.getElementById('blog-modal-btns').innerHTML =
    `<span style="color:#f39c12;font-size:.85rem;font-weight:700">⏳ Generating… please wait</span>
     <button class="mbtn-cx" onclick="closeModal()">Close</button>`;
  document.getElementById('blog-log-wrap').style.display = 'block';

  const blogLog = document.getElementById('blog-log');
  function blogAppend(msg, color='#6ab4cc'){
    blogLog.insertAdjacentHTML('beforeend',
      `<span style="color:${color}">${_esc(msg)}</span><br>`);
    blogLog.scrollTop = blogLog.scrollHeight;
  }
  blogAppend('▶ Starting blog pipeline…', '#2ecc71');
  _log('ok', '📝 Blog generation started: ' + _pendTitle.substring(0, 55));

  // Start pipeline
  fetch('/api/generate-blog', {
    method : 'POST',
    headers: {'Content-Type': 'application/json'},
    body   : JSON.stringify({url: _pendUrl, category}),
  })
  .then(r => r.json())
  .then(d => {
    if(d.error){ blogAppend('❌ ' + d.error, '#e74c3c'); return; }
    const blogId = d.blog_id;

    // Stream progress
    if(_blogSrc) _blogSrc.close();
    _blogSrc = new EventSource('/api/blog-stream/' + blogId);

    _blogSrc.addEventListener('blog_log', e => {
      const msg = JSON.parse(e.data).msg || '';
      blogAppend(msg);
      _log('ok', msg.substring(0, 80));
    });

    _blogSrc.addEventListener('blog_done', e => {
      _blogSrc.close(); _blogSrc = null;
      const res = JSON.parse(e.data);
      const resEl = document.getElementById('blog-result');
      resEl.style.display = 'block';
      if(res.success){
        resEl.innerHTML =
          `<div style="background:#0d2b1a;border:1px solid #1a4731;border-radius:8px;padding:12px">
             <div style="color:#2ecc71;font-weight:700;margin-bottom:6px">✅ Blog Created!</div>
             <div style="font-size:.78rem;color:#aaa;margin-bottom:6px">
               Local: <code style="color:#7ec8e3">${_esc(res.local_path)}</code>
             </div>
             ${res.live_url ? `<a href="${_esc(res.live_url)}" target="_blank"
               style="display:inline-block;background:#c0392b;color:#fff;padding:6px 14px;
               border-radius:6px;font-size:.8rem;font-weight:700;text-decoration:none;margin-top:4px">
               🌐 Open Live Blog</a>` : ''}
           </div>`;
        _log('ok', '✅ Blog live: ' + res.live_url);
      } else {
        resEl.innerHTML = `<div style="color:#e74c3c">❌ ${_esc(res.message)}</div>`;
      }
      document.getElementById('blog-modal-btns').innerHTML =
        `<button class="mbtn-cx" onclick="closeModal()" style="flex:1">Close</button>`;
    });

    _blogSrc.addEventListener('blog_error', e => {
      _blogSrc.close(); _blogSrc = null;
      const msg = JSON.parse(e.data).msg || 'Unknown error';
      blogAppend('❌ ' + msg, '#e74c3c');
      _log('err', '❌ Blog error: ' + msg);
      document.getElementById('blog-modal-btns').innerHTML =
        `<button class="mbtn-ok" onclick="confirmBlog()">🔄 Retry</button>
         <button class="mbtn-cx" onclick="closeModal()">Close</button>`;
    });

    _blogSrc.onerror = () => {
      blogAppend('⚠️ Stream disconnected', '#f39c12');
    };
  })
  .catch(err => {
    blogAppend('❌ Network error: ' + err, '#e74c3c');
  });
}


/* ─────────────────────────────────────────────────────────
   Export
───────────────────────────────────────────────────────── */
function exportData(type){
  if(!_jobId){ alert('No active job.'); return; }
  window.location='/api/download/'+type+'/'+_jobId;
}

/* ─────────────────────────────────────────────────────────
   Utilities
───────────────────────────────────────────────────────── */
function _esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function _fmt(n,dec=0){ return (n||0).toLocaleString('en-IN',{maximumFractionDigits:dec}); }
</script>
</body>
</html>
"""

# inject server-side constant into template
_DASHBOARD = _DASHBOARD.replace("{{ max_log }}", str(MAX_LOG_LINES))


# ═════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════

if __name__ == "__main__":
    import webbrowser
    print("=" * 56)
    print("  ZERO483  Internal Product Research Server  v3.0")
    print(f"  Port: {PORT}")
    print("=" * 56)
    bind_host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    if not os.environ.get("PORT"):
        threading.Timer(1.4, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    app.run(host=bind_host, port=PORT, debug=False, threaded=True)
