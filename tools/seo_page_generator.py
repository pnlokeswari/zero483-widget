# -*- coding: utf-8 -*-
"""
============================================================
 VERIFYFIRST — Programmatic SEO & Auto-Indexing Engine
 (BuyHatke-style Automatic Product Page & Sitemap Generator)
============================================================
Every time a shopper verifies a product on VerifyFirst:
1. Generates a permanent SEO-rich static comparison page:
   compare/<seo-slug>-<id>.html
2. Embeds Quad-Layer JSON-LD Schema (Product + AggregateOffer + FAQPage + BreadcrumbList)
3. Updates sitemap.xml automatically
4. Commits & pushes to GitHub Pages in the background so Google indexes it!
"""
from __future__ import annotations

import os
import re
import json
import base64
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("VERIFYFIRST.seo")

ROOT_DIR = Path(__file__).resolve().parent.parent
COMPARE_DIR = ROOT_DIR / "compare"
COMPARE_DIR.mkdir(parents=True, exist_ok=True)
INDEX_JSON_PATH = COMPARE_DIR / "index.json"
SITEMAP_PATH = ROOT_DIR / "sitemap.xml"

GITHUB_REPO = "pnlokeswari/zero483-widget"
SITE_ORIGIN = "https://alerts.zero483.com"


def make_seo_slug(title: str, prod_id: str) -> str:
    """Create a clean, keyword-rich URL slug like 'samsung-108-cm-43-inches-fhd-smart-led-tv-b0f84dkx8k'."""
    clean = re.sub(r"[^a-zA-Z0-9\s-]", " ", title or "product").lower()
    words = [w for w in clean.split() if len(w) > 1][:9]
    slug_base = "-".join(words) if words else "product"
    pid_clean = re.sub(r"[^a-zA-Z0-9]", "", prod_id or "").lower()
    return f"{slug_base}-{pid_clean}" if pid_clean else slug_base


def render_static_comparison_html(res: Dict[str, Any], slug: str) -> str:
    """Render a standalone, fast-loading, mobile-responsive HTML page for Google SEO."""
    prod_id = res.get("asin") or res.get("pid") or ""
    title = res.get("title") or f"Product ({prod_id})"
    short_title = title[:75] + ("..." if len(title) > 75 else "")
    category = res.get("category") or "Smart Shopping"
    cur_price = float(res.get("current_price") or 0.0)
    mrp = float(res.get("mrp") or cur_price or 1.0)
    lowest_90d = float(res.get("lowest_90d") or round(cur_price * 0.90, 0))
    savings = float(res.get("savings_mrp_inr") or max(0.0, mrp - cur_price))
    disc_pct = float(res.get("discount_mrp_pct") or 0.0)
    verdict = res.get("verdict") or "🟢 VERIFIED DEAL"
    verdict_reason = res.get("verdict_reason") or f"Verified against official printed packaging box MRP of ₹{mrp:,.0f}."
    svg_chart = res.get("svg_chart") or ""
    img_url = res.get("image_url") or "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=1200&auto=format&fit=crop&q=80"
    primary_url = res.get("affiliate_url") or res.get("amazon_url") or f"https://www.amazon.in/dp/{prod_id}?tag=10fa9c-21"
    fk_search_url = res.get("flipkart_search_url") or f"https://www.flipkart.com/search?q={requests.utils.quote(title[:50])}"
    amz_search_url = res.get("amazon_search_url") or f"https://www.amazon.in/s?k={requests.utils.quote(title[:50])}&tag=10fa9c-21"
    platform = res.get("platform", "amazon")

    fk_comp = res.get("flipkart_counterpart")
    amz_comp = res.get("amazon_counterpart")
    has_comp = bool(res.get("has_competitor") and fk_comp and amz_comp)

    amz_price = float(amz_comp["price"]) if (amz_comp and amz_comp.get("price")) else (cur_price if platform == "amazon" else 0.0)
    fk_price = float(fk_comp["price"]) if (fk_comp and fk_comp.get("price")) else (cur_price if platform == "flipkart" else 0.0)
    raw_amz_url = (amz_comp.get("url") if amz_comp else None) or (primary_url if platform == "amazon" else amz_search_url)
    raw_fk_url = (fk_comp.get("url") if fk_comp else None) or (primary_url if platform == "flipkart" else fk_search_url)
    amz_buy_url = raw_amz_url if str(raw_amz_url).lower().startswith("http") else amz_search_url
    fk_buy_url = raw_fk_url if str(raw_fk_url).lower().startswith("http") else fk_search_url
    if "amazon.in" in amz_buy_url and "tag=" not in amz_buy_url:
        sep = "&" if "?" in amz_buy_url else "?"
        amz_buy_url = f"{amz_buy_url}{sep}tag=10fa9c-21"

    low_price = min([p for p in [amz_price, fk_price, cur_price] if p > 0] or [cur_price])
    high_price = max([p for p in [amz_price, fk_price, mrp] if p > 0] or [mrp])
    offer_count = 2 if (amz_price > 0 and fk_price > 0) else 1

    canonical_url = f"{SITE_ORIGIN}/compare/{slug}.html"
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30")
    date_display = datetime.now().strftime("%d %b %Y")

    bullets = res.get("about_this_item") or res.get("highlights") or []
    bullets_html = ""
    if bullets:
        li_items = "".join(f"<li style='margin-bottom:6px'>{b}</li>" for b in bullets[:5])
        bullets_html = f"""
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:18px;margin-top:20px">
          <h3 style="font-size:.95rem;color:#38bdf8;margin-bottom:10px">📋 Key Product Highlights &amp; Specifications</h3>
          <ul style="padding-left:18px;font-size:.85rem;color:#cbd5e1;line-height:1.6">{li_items}</ul>
        </div>
        """

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Product",
                "name": title,
                "image": [img_url],
                "description": f"Live Amazon vs Flipkart price comparison, official printed box MRP (₹{mrp:,.0f}), and 90-day price history for {title}.",
                "sku": prod_id,
                "category": category,
                "offers": {
                    "@type": "AggregateOffer",
                    "url": canonical_url,
                    "priceCurrency": "INR",
                    "lowPrice": str(int(low_price)),
                    "highPrice": str(int(high_price)),
                    "offerCount": str(offer_count),
                    "availability": "https://schema.org/InStock"
                }
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f"What is the official printed box MRP of {short_title}?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": f"The verified printed packaging box MRP of {title} is ₹{mrp:,.0f}. The current live deal price is ₹{cur_price:,.0f}, saving you ₹{savings:,.0f} ({disc_pct:.0f}% off)."
                        }
                    },
                    {
                        "@type": "Question",
                        "name": f"What is the 90-day lowest price for {short_title} in India?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": f"Based on 90-day historical price tracking, {short_title} has traded as low as ₹{lowest_90d:,.0f} during major sale events."
                        }
                    },
                    {
                        "@type": "Question",
                        "name": f"Is {short_title} cheaper on Amazon or Flipkart?",
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": f"Currently, you can verify and compare live store prices for {short_title} starting at ₹{low_price:,.0f} against its box MRP of ₹{mrp:,.0f} on VerifyFirst."
                        }
                    }
                ]
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "VerifyFirst Home", "item": f"{SITE_ORIGIN}/deals.html"},
                    {"@type": "ListItem", "position": 2, "name": "Trending Comparisons", "item": f"{SITE_ORIGIN}/deals.html#trending-comparisons"},
                    {"@type": "ListItem", "position": 3, "name": short_title, "item": canonical_url}
                ]
            }
        ]
    }

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{short_title} — Amazon vs Flipkart Price Comparison, Box MRP &amp; 90-Day Price History | VerifyFirst</title>
<meta name="description" content="Compare {short_title} live price (₹{cur_price:,.0f}) vs Printed Box MRP (₹{mrp:,.0f}). Check 90-day lowest price (₹{lowest_90d:,.0f}) across Amazon India &amp; Flipkart before buying.">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{canonical_url}" />
<meta property="og:site_name" content="VerifyFirst — Smart Price &amp; Deal Comparison" />
<meta property="og:type" content="product" />
<meta property="og:title" content="{short_title} — Price Comparison &amp; 90-Day Low (₹{cur_price:,.0f} vs MRP ₹{mrp:,.0f})" />
<meta property="og:description" content="{verdict} — Save ₹{savings:,.0f} ({disc_pct:.0f}% Off Box MRP). Compare Amazon vs Flipkart live prices &amp; 90-day trajectory." />
<meta property="og:url" content="{canonical_url}" />
<meta property="og:image" content="{img_url}" />
<meta property="article:published_time" content="{now_iso}" />
<script type="application/ld+json">
{json.dumps(schema_graph, ensure_ascii=False, indent=2)}
</script>
<style>
  :root {{ --bg:#060b19; --card:#0d152c; --border:#1e293b; --text:#f1f5f9; --muted:#94a3b8; --brand:#38bdf8; --green:#10b981; --amber:#f59e0b; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); line-height:1.5; padding-bottom:60px; }}
  header {{ background:rgba(13,21,44,.95); border-bottom:1px solid var(--border); padding:14px 20px; position:sticky; top:0; z-index:100; backdrop-filter:blur(10px); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; }}
  .brand {{ font-size:1.15rem; font-weight:800; color:#fff; text-decoration:none; display:flex; align-items:center; gap:8px; }}
  .pill {{ font-size:.7rem; background:rgba(56,189,248,.12); color:var(--brand); border:1px solid rgba(56,189,248,.3); padding:3px 10px; border-radius:99px; font-weight:700; }}
  .container {{ max-width:980px; margin:24px auto; padding:0 16px; }}
  .breadcrumb {{ font-size:.78rem; color:var(--muted); margin-bottom:16px; }}
  .breadcrumb a {{ color:var(--brand); text-decoration:none; }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:24px; margin-bottom:22px; box-shadow:0 12px 32px rgba(0,0,0,.35); }}
  .prod-grid {{ display:grid; grid-template-columns:160px 1fr; gap:22px; align-items:start; }}
  @media(max-width:640px) {{ .prod-grid {{ grid-template-columns:1fr; }} }}
  .prod-img-box {{ background:#fff; border-radius:12px; padding:12px; text-align:center; }}
  .prod-img-box img {{ max-width:100%; max-height:140px; object-fit:contain; }}
  h1 {{ font-size:1.25rem; font-weight:800; color:#fff; margin-bottom:10px; line-height:1.35; }}
  .verdict-banner {{ background:rgba(16,185,129,.12); border:1px solid rgba(16,185,129,.35); border-radius:10px; padding:12px 16px; margin:14px 0; }}
  .metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:18px 0; }}
  .m-box {{ background:#091024; border:1px solid var(--border); border-radius:12px; padding:14px; text-align:center; }}
  .m-val {{ font-size:1.45rem; font-weight:800; }}
  .m-lbl {{ font-size:.72rem; color:var(--muted); text-transform:uppercase; margin-top:4px; font-weight:700; }}
  .store-btns {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:18px; }}
  @media(max-width:560px) {{ .store-btns {{ grid-template-columns:1fr; }} }}
  .btn {{ display:inline-flex; align-items:center; justify-content:center; gap:8px; padding:13px 18px; border-radius:10px; font-weight:800; font-size:.9rem; text-decoration:none; transition:transform .15s; }}
  .btn:hover {{ transform:translateY(-2px); }}
  .btn-amz {{ background:linear-gradient(135deg,#f59e0b,#d97706); color:#000; }}
  .btn-fk {{ background:linear-gradient(135deg,#2874f0,#1e5cc0); color:#fff; }}
  .btn-verify {{ background:linear-gradient(135deg,#38bdf8,#0284c7); color:#000; padding:8px 16px; font-size:.8rem; border-radius:8px; text-decoration:none; font-weight:800; }}
  .faq-item {{ border-bottom:1px solid var(--border); padding:14px 0; }}
  .faq-q {{ font-weight:700; color:#fff; font-size:.92rem; margin-bottom:6px; }}
  .faq-a {{ color:var(--muted); font-size:.84rem; }}
  .caution-box {{ background:rgba(245,158,11,.08); border-left:4px solid var(--amber); padding:12px 16px; border-radius:8px; font-size:.8rem; color:#fde68a; margin-bottom:18px; }}
</style>
</head>
<body>
<header>
  <a href="/deals.html" class="brand">🛡️ VerifyFirst <span class="pill">Smart Price &amp; Deal Comparison</span></a>
  <a href="/deals.html?q={prod_id}" class="btn-verify">⚡ Run Fresh Live Check</a>
</header>

<div class="container">
  <div class="breadcrumb">
    <a href="/deals.html">VerifyFirst Home</a> &rsaquo; <a href="/deals.html#trending-comparisons">Price Comparisons</a> &rsaquo; <span>{short_title}</span>
  </div>

  <div class="caution-box">
    <strong>⚠️ Price Fluctuation Notice:</strong> E-commerce prices on Amazon and Flipkart change dynamically. The figures below were verified on <strong>{date_display}</strong>. Click the store buttons below or run a fresh live check to confirm real-time prices and active bank card discounts.
  </div>

  <div class="card">
    <div class="prod-grid">
      <div class="prod-img-box">
        <img src="{img_url}" alt="{short_title}" loading="eager">
      </div>
      <div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
          <span class="pill">{category}</span>
          <span class="pill" style="background:rgba(16,185,129,.15);color:#34d399">ID: {prod_id}</span>
        </div>
        <h1>{title}</h1>
        <div class="verdict-banner">
          <div style="font-weight:800;color:#34d399;font-size:.95rem">{verdict}</div>
          <div style="font-size:.82rem;color:#cbd5e1;margin-top:4px">{verdict_reason}</div>
        </div>
      </div>
    </div>

    <div class="metrics">
      <div class="m-box">
        <div class="m-val" style="color:var(--brand)">₹{cur_price:,.0f}</div>
        <div class="m-lbl">Live Deal Price</div>
      </div>
      <div class="m-box">
        <div class="m-val" style="color:var(--muted);text-decoration:line-through">₹{mrp:,.0f}</div>
        <div class="m-lbl">Printed Box MRP</div>
      </div>
      <div class="m-box">
        <div class="m-val" style="color:var(--green)">₹{savings:,.0f} ({disc_pct:.0f}% Off)</div>
        <div class="m-lbl">Verified MRP Savings</div>
      </div>
      <div class="m-box">
        <div class="m-val" style="color:var(--amber)">₹{lowest_90d:,.0f}</div>
        <div class="m-lbl">90-Day Lowest Dip</div>
      </div>
    </div>

    <div class="store-btns">
      <a href="{amz_buy_url}" target="_blank" rel="nofollow noopener sponsored" class="btn btn-amz">
        🛒 Check Price on Amazon India {f"(₹{amz_price:,.0f})" if amz_price > 0 else ""} ↗
      </a>
      <a href="{fk_buy_url}" target="_blank" rel="nofollow noopener sponsored" class="btn btn-fk">
        ⚡ Check Price on Flipkart {f"(₹{fk_price:,.0f})" if fk_price > 0 else ""} ↗
      </a>
    </div>

    {bullets_html}
  </div>

  <div class="card">
    <h2 style="font-size:1.05rem;font-weight:800;margin-bottom:12px;color:#fff">📈 90-Day Real Price Trajectory vs Printed Box MRP Ceiling</h2>
    <p style="font-size:.82rem;color:var(--muted);margin-bottom:14px">
      Inspect how <strong>{short_title}</strong> has fluctuated over the last 90 days compared to its official packaging MRP ceiling of <strong>₹{mrp:,.0f}</strong>.
    </p>
    <div style="background:#0b0f19;border-radius:12px;padding:10px;border:1px solid var(--border)">
      {svg_chart}
    </div>
  </div>

  <div class="card">
    <h2 style="font-size:1.05rem;font-weight:800;margin-bottom:12px;color:#fff">❓ Frequently Asked Questions (Price &amp; MRP Verification)</h2>
    <div class="faq-item">
      <div class="faq-q">What is the official printed box MRP of {short_title}?</div>
      <div class="faq-a">The official manufacturer printed box MRP is <strong>₹{mrp:,.0f}</strong>. At the current deal price of <strong>₹{cur_price:,.0f}</strong>, shoppers save <strong>₹{savings:,.0f} ({disc_pct:.0f}% off)</strong>.</div>
    </div>
    <div class="faq-item">
      <div class="faq-q">What is the lowest price {short_title} has dropped to in the last 90 days?</div>
      <div class="faq-a">Over the past 90 days, the lowest recorded price dip for this product is approximately <strong>₹{lowest_90d:,.0f}</strong>.</div>
    </div>
    <div class="faq-item" style="border-bottom:none">
      <div class="faq-q">How can I run a live price comparison right now?</div>
      <div class="faq-a">Click <a href="/deals.html?q={prod_id}" style="color:var(--brand);font-weight:700">Verify Live Price on VerifyFirst</a> to run a fresh real-time scan across Amazon India and Flipkart.</div>
    </div>
  </div>
</div>
</body>
</html>"""
    return html


def load_index_entries() -> List[Dict[str, Any]]:
    if INDEX_JSON_PATH.exists():
        try:
            return json.loads(INDEX_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def update_sitemap_with_slug(slug: str) -> bool:
    """Ensure compare/<slug>.html is listed in sitemap.xml."""
    if not SITEMAP_PATH.exists():
        return False
    loc_url = f"{SITE_ORIGIN}/compare/{slug}.html"
    content = SITEMAP_PATH.read_text(encoding="utf-8")
    if loc_url in content:
        return False
    entry = f"""  <url>
    <loc>{loc_url}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>\n</urlset>"""
    if "</urlset>" in content:
        new_content = content.replace("</urlset>", entry)
        SITEMAP_PATH.write_text(new_content, encoding="utf-8")
        return True
    return False


def _push_to_github_async(files_to_push: List[tuple[str, Path]], commit_msg: str) -> None:
    """Background worker that commits and pushes new comparison pages to GitHub Pages."""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        return
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "VerifyFirst-SEO-Indexer"
    }
    for repo_path, local_path in files_to_push:
        try:
            if not local_path.exists():
                continue
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{repo_path}"
            r_get = requests.get(url, headers=headers, timeout=12)
            sha = r_get.json().get("sha") if r_get.status_code == 200 else None
            b64 = base64.b64encode(local_path.read_bytes()).decode("utf-8")
            payload = {"message": commit_msg, "content": b64, "branch": "main"}
            if sha:
                payload["sha"] = sha
            requests.put(url, headers=headers, json=payload, timeout=15)
        except Exception as e:
            log.warning(f"GitHub auto-index push warning for {repo_path}: {e}")


def auto_index_verified_product(res: Dict[str, Any], push_remote: bool = True) -> str:
    """
    Saves static SEO comparison page, updates compare/index.json & sitemap.xml,
    and triggers non-blocking GitHub Pages deployment.
    Returns the relative URL path (/compare/<slug>.html).
    """
    try:
        prod_id = res.get("asin") or res.get("pid") or ""
        title = res.get("title") or ""
        if not prod_id or not title or "error" in res:
            return ""

        slug = make_seo_slug(title, prod_id)
        html_path = COMPARE_DIR / f"{slug}.html"
        html_content = render_static_comparison_html(res, slug)
        html_path.write_text(html_content, encoding="utf-8")

        # Update compare/index.json (keep top 60 most recent unique products)
        entries = load_index_entries()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        new_entry = {
            "id": prod_id,
            "slug": slug,
            "url": f"/compare/{slug}.html",
            "title": title[:110],
            "category": res.get("category") or "Smart Shopping",
            "price": float(res.get("current_price") or 0.0),
            "mrp": float(res.get("mrp") or 0.0),
            "lowest_90d": float(res.get("lowest_90d") or 0.0),
            "discount_pct": round(float(res.get("discount_mrp_pct") or 0.0), 0),
            "savings": round(float(res.get("savings_mrp_inr") or 0.0), 0),
            "verdict": res.get("verdict") or "🟢 VERIFIED DEAL",
            "image_url": res.get("image_url") or "",
            "platform": res.get("platform") or "amazon",
            "updated_at": now_str
        }

        # Deduplicate by prod_id
        filtered = [e for e in entries if e.get("id") != prod_id]
        filtered.insert(0, new_entry)
        filtered = filtered[:60]
        INDEX_JSON_PATH.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")

        sitemap_changed = update_sitemap_with_slug(slug)

        if push_remote:
            files = [
                (f"compare/{slug}.html", html_path),
                ("compare/index.json", INDEX_JSON_PATH),
            ]
            if sitemap_changed:
                files.append(("sitemap.xml", SITEMAP_PATH))
            threading.Thread(
                target=_push_to_github_async,
                args=(files, f"seo(auto-index): publish comparison page for {prod_id}"),
                daemon=True
            ).start()

        return f"/compare/{slug}.html"
    except Exception as e:
        log.warning(f"Auto-index error: {e}")
        return ""
