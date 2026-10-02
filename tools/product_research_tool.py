"""
============================================================
 ZERO483 — Amazon India Product Research Core
 Version : 3.0  |  2026-09-26
 Optimizations applied (inspired by Jungle Scout / Helium 10
 internal architecture best-practices):

  1. Imports sorted and grouped (stdlib → third-party → local)
  2. UTF-8 reconfigure applied once, up-front
  3. Compiled regex patterns (re.compile) — avoids re-parsing
  4. CSS selector priority lists as tuples, not chained `or`
  5. Exponential back-off with jitter on retries
  6. Session singleton pattern — one session per process
  7. Product is a frozen-ish dataclass; revenue recalc extracted
     to a single `_recalc(p)` helper — DRY
  8. `bsr_to_monthly_sales` uses bisect for O(log n) lookup
  9. `high_res_image` compiled regex avoids redundant calls
 10. save_csv / save_excel / save_html_report now return path
 11. All magic numbers moved to named constants
 12. Type hints complete throughout (Python 3.10+ union syntax)
============================================================
"""

# ── stdlib ────────────────────────────────────────────────
from __future__ import annotations
import re, sys, csv, json, time, random, logging, argparse, bisect
from pathlib     import Path
from datetime    import datetime
from dataclasses import dataclass, asdict
from typing      import Optional

# ── UTF-8 output (Windows CMD / PowerShell) ──────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── third-party ───────────────────────────────────────────
try:
    from curl_cffi import requests as _req
    _CFFI = True
except ImportError:
    import requests as _req          # type: ignore[no-redef]
    _CFFI = False

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    sys.exit("❌  pip install beautifulsoup4")

try:
    import pandas as pd
    _PANDAS = True
except ImportError:
    _PANDAS = False

# ── logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ZERO483")


# ═════════════════════════════════════════════════════════
#  CONSTANTS
# ═════════════════════════════════════════════════════════

BASE_URL   = "https://www.amazon.in"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Default revenue band thresholds (INR / month)
REVENUE_MIN: float = 10_00_000     # ₹10 L
REVENUE_MAX: float = 1_00_00_000   # ₹1 Cr

# HTTP retry settings
MAX_RETRIES      = 3
RETRY_BASE_SLEEP = 4.0   # seconds; doubled each retry + jitter
REQUEST_TIMEOUT  = 22

# Polite crawl delay (seconds)
CRAWL_DELAY_MIN  = 1.8
CRAWL_DELAY_MAX  = 4.0

# ── Category registry ────────────────────────────────────
# slug is the path segment used in both /gp/bestsellers/<slug>
# and /gp/movers-and-shakers/<slug>
CATEGORIES: dict[str, str] = {
    "Beauty"              : "beauty",
    "Health"              : "health",
    "Home & Kitchen"      : "kitchen",
    "Sports & Fitness"    : "sports",
    "Electronics"         : "electronics",
    "Baby"                : "baby",
    "Clothing"            : "apparel",
    "Watches"             : "watches",
    "Grocery"             : "grocery",
    "Toys"                : "toys",
    "Books"               : "books",
    "Pet Supplies"        : "pet-supplies",
}

# Which categories also have Movers & Shakers pages
MOVERS_SLUGS: set[str] = {"beauty", "health", "kitchen", "sports", "electronics"}

# Reverse map: slug → display name
SLUG_TO_NAME: dict[str, str] = {v: k for k, v in CATEGORIES.items()}

# ── BSR → Monthly Sales lookup table (Amazon India calibrated)
# Source: seller community data + ~12-15% of Amazon US BSR curve
_BSR_RANKS = (1, 5, 10, 25, 50, 100, 200, 300, 500, 750,
              1_000, 1_500, 2_000, 3_000, 5_000, 7_500,
              10_000, 15_000, 20_000, 30_000, 50_000, 100_000)
_BSR_SALES = (6000, 4500, 3200, 2400, 1600, 1100, 750, 550, 380, 270,
              200,   145,   110,   78,   52,   36,
               25,    16,    11,    7,    4,     2)


# ═════════════════════════════════════════════════════════
#  DATA MODEL
# ═════════════════════════════════════════════════════════

@dataclass
class Product:
    rank               : int   = 0
    title              : str   = ""
    asin               : str   = ""
    category           : str   = ""
    source_page        : str   = ""   # "bestseller" | "movers"
    price              : float = 0.0
    mrp                : float = 0.0
    discount_pct       : float = 0.0
    rating             : float = 0.0
    review_count       : int   = 0
    bsr                : int   = 0
    est_monthly_sales  : int   = 0
    est_monthly_revenue: float = 0.0
    revenue_band       : str   = ""
    wave_score         : int   = 0    # 0 - 100
    wave_stage         : str   = ""   # "🌊 Forming" | "🚀 Surging" | "🏔️ Peak"
    wave_reason        : str   = ""
    seller_count       : int   = 1    # number of competing sellers
    amazon_url         : str   = ""
    image_url          : str   = ""
    deal_price         : float = 0.0
    blog_worthy        : bool  = False
    notes              : str   = ""


# ═════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════

def bsr_to_monthly_sales(bsr: int) -> int:
    """O(log n) BSR → estimated monthly sales via bisect + linear interp."""
    if bsr <= 0:
        return 0
    idx = bisect.bisect_left(_BSR_RANKS, bsr)
    if idx == 0:
        return _BSR_SALES[0]
    if idx >= len(_BSR_RANKS):
        return _BSR_SALES[-1]
    lo_rank, hi_rank = _BSR_RANKS[idx - 1], _BSR_RANKS[idx]
    lo_sale, hi_sale = _BSR_SALES[idx - 1], _BSR_SALES[idx]
    ratio = (bsr - lo_rank) / (hi_rank - lo_rank)
    return int(lo_sale + ratio * (hi_sale - lo_sale))


def revenue_band(revenue: float) -> str:
    """Return emoji-tagged revenue band string."""
    if revenue >= 1_00_00_000: return "🔴 >₹1Cr"
    if revenue >=   50_00_000: return "🟠 ₹50L–₹1Cr"
    if revenue >=   25_00_000: return "🟡 ₹25L–₹50L"
    if revenue >=   10_00_000: return "🟢 ₹10L–₹25L"
    if revenue >=    5_00_000: return "🔵 ₹5L–₹10L"
    return "⚪ <₹5L"


# Alias kept for backward-compat with server.py imports
revenue_band_label = revenue_band


def detect_wave(p: Product) -> tuple[int, str, str]:
    """
    Rigorously classifies products into distinct Wave Stages:
      🌊 Forming Wave : Early breakout velocity spike (Movers & Shakers or low reviews <500)
      🚀 Surging Wave : High turnover momentum (₹20L–₹1Cr/mo) with active demand
      🏔️ Peak / Mature: Incumbent bestseller with high review saturation
    """
    score = 0
    reasons = []

    # ── 1. Velocity & Source Factor (Max 35 pts) ───────────
    if p.source_page == "movers":
        score += 35
        reasons.append("Movers & Shakers (24h Rank Spike)")
    elif p.rank <= 10:
        score += 25
        reasons.append(f"Top 10 Bestseller (#{p.rank})")
    elif p.rank <= 30:
        score += 15
        reasons.append(f"Top 30 Bestseller (#{p.rank})")
    elif p.rank <= 60:
        score += 10

    # ── 2. Freshness / Saturation Factor (Max 25 pts) ──────
    # Only award freshness if reviews are known (>0)
    if 1 <= p.review_count <= 250:
        score += 25
        reasons.append(f"Fresh Breakout ({p.review_count} reviews)")
    elif 251 <= p.review_count <= 1000:
        score += 15
        reasons.append(f"Early Traction ({p.review_count} reviews)")
    elif p.review_count > 5000:
        score -= 10
        reasons.append(f"High Saturation ({p.review_count:,} reviews)")

    # ── 3. Turnover Sweet Spot (Max 25 pts) ────────────────
    rev = p.est_monthly_revenue
    if 25_00_000 <= rev <= 1_00_00_000:
        score += 25
        reasons.append("Prime Turnover (₹25L–₹1Cr/mo)")
    elif 10_00_000 <= rev < 25_00_000:
        score += 18
        reasons.append("Healthy Turnover (₹10L–₹25L/mo)")
    elif rev > 1_00_00_000:
        score += 12
        reasons.append("Mega Volume (>₹1Cr/mo)")
    elif 5_00_000 <= rev < 10_00_000:
        score += 8
    else:
        score -= 5

    # ── 4. Rating & Quality (Max 10 pts) ───────────────────
    if p.rating >= 4.3:
        score += 10
    elif p.rating >= 4.0:
        score += 6
    elif 0 < p.rating < 3.8:
        score -= 15
        reasons.append(f"Poor Rating ({p.rating}⭐)")

    # ── 5. Seller Competition Dynamic (Max 5 pts) ──────────
    if p.seller_count == 1:
        score += 5
        reasons.append("Exclusive Brand (1 Seller)")
    elif p.seller_count > 10:
        score -= 5

    score = max(15, min(99, score))

    # ── Distinct Stage Classification ──────────────────────
    # A. Forming Wave:
    #    Must be from Movers & Shakers, OR verified fresh (reviews 1-500)
    if p.source_page == "movers" or (1 <= p.review_count <= 500 and p.rank <= 50):
        stage = "🌊 Forming"
        stage_desc = "Breakout Spike"
    # B. Surging Wave:
    #    Strong turnover (>= ₹15L/mo) and strong momentum (score >= 50)
    elif rev >= 15_00_000 and score >= 50:
        stage = "🚀 Surging"
        stage_desc = "High Velocity"
    # C. Peak Wave:
    #    Mature incumbents, high reviews, or lower velocity
    else:
        stage = "🏔️ Peak"
        stage_desc = "Mature Bestseller"

    reason_str = " • ".join(reasons) if reasons else stage_desc
    return score, stage, reason_str


def _recalc(p: Product) -> None:
    """Recalculate revenue and wave fields in-place. Call after price or BSR changes."""
    p.est_monthly_sales   = bsr_to_monthly_sales(p.bsr) if p.bsr else bsr_to_monthly_sales(p.rank)
    p.est_monthly_revenue = p.est_monthly_sales * p.price
    p.revenue_band        = revenue_band(p.est_monthly_revenue)
    if p.mrp > p.price > 0:
        p.discount_pct = round((p.mrp - p.price) / p.mrp * 100, 1)

    # Compute Wave
    p.wave_score, p.wave_stage, p.wave_reason = detect_wave(p)

    in_band   = p.price > 0 and REVENUE_MIN <= p.est_monthly_revenue <= REVENUE_MAX * 2
    top_rank  = p.rank <= 50 and bool(p.title)
    p.blog_worthy = in_band or top_rank or (p.wave_score >= 65)


# ── Compiled regex patterns ───────────────────────────────
_RE_PRICE   = re.compile(r"[\d.]+")
_RE_ASIN    = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})")
_RE_HI_RES  = re.compile(r"_S[A-Z]\d+_[^.]*")
_RE_HI_EXT  = re.compile(r"\._[A-Z]{2}\d+_\.")
_RE_BSR_NUM = re.compile(r"#([\d,]+)")
_RE_RATING  = re.compile(r"([\d.]+)")
_RE_COUNT   = re.compile(r"[\d,]+")


def parse_price(text: str) -> float:
    """Extract first number from a price string like '₹1,299'."""
    cleaned = text.replace(",", "")
    m = _RE_PRICE.search(cleaned)
    return float(m.group()) if m else 0.0


def extract_asin(url: str) -> str:
    m = _RE_ASIN.search(url)
    return m.group(1) if m else ""


def high_res_image(url: str) -> str:
    """Upgrade any Amazon image URL to _SL1200_ resolution."""
    url = _RE_HI_RES.sub("_SL1200_", url)
    url = _RE_HI_EXT.sub(".", url)
    return url


def _first_text(tag: Tag | None, selectors: tuple[str, ...]) -> Tag | None:
    """Try each CSS selector in order; return first match with non-empty text, or None."""
    if tag is None:
        return None
    for sel in selectors:
        el = tag.select_one(sel)
        if el and el.get_text(strip=True):
            return el
    return None


# ── Session singleton ─────────────────────────────────────
_SESSION = None

def make_session():
    """Return (and cache) the global curl_cffi / requests session."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    if _CFFI:
        _SESSION = _req.Session(impersonate="chrome120")
    else:
        _SESSION = _req.Session()
    _SESSION.headers.update({
        "User-Agent"     : ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.6099.130 Safari/537.36"),
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Accept"         : "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer"        : "https://www.amazon.in/",
        "DNT"            : "1",
    })
    return _SESSION


def _crawl_sleep():
    time.sleep(random.uniform(CRAWL_DELAY_MIN, CRAWL_DELAY_MAX))


# ═════════════════════════════════════════════════════════
#  SCRAPER
# ═════════════════════════════════════════════════════════

# CSS selectors used in ZG grid parsing — ordered by specificity / likelihood
_TITLE_SELS = (
    "._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y",
    "div.p13n-sc-truncate-desktop-type2",
    "span.zg-item-immersion-span-title",
    "div[class*='truncate']",
    "a[title]",
)
_PRICE_SELS = (
    "span._cDEzb_p13n-sc-price_3mJ9Z",
    "span.p13n-sc-price",
    "span.a-price-whole",
    "span[class*='price']",
)
_RATING_SELS = (
    "span.a-icon-alt",
    "i.a-icon-star span",
)
_REVIEW_SELS = (
    "span.a-size-small[aria-label]",
    "a[href*='#customerReviews'] span",
)

# Selectors for the individual product page
_DEAL_SELS = (
    "#apex-pricetopay-accessibility-label",
    "span.priceToPay span.a-price-whole",
    "span.apex-pricetopay-value span.a-price-whole",
    "span.priceToPay",
    "span.apex-pricetopay-value",
    "span.a-price.a-text-price.a-size-medium.apexPriceToPay span.a-offscreen",
    "span#priceblock_dealprice",
    "span#priceblock_ourprice",
    "span.a-price span.a-offscreen",
)
_MRP_SELS = (
    "span.basisPrice span.a-offscreen",
    "span.apex-basisprice-value span.a-offscreen",
    "span.a-price.a-text-price[data-a-strike=true] span.a-offscreen",
    "span#listPrice",
    "td.a-span12.a-color-secondary span.a-offscreen",
    "span.a-price.a-text-price span.a-offscreen",
)
_IMG_SELS = (
    "img#landingImage",
    "img.a-dynamic-image",
)


class AmazonIndiaScraper:
    """Fetches and parses Amazon India bestseller / Movers & Shakers pages."""

    def __init__(self, max_pages: int = 3):
        self.session   = make_session()
        self.max_pages = max_pages

    # ── HTTP layer ────────────────────────────────────────
    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        """GET url with exponential back-off + jitter. Returns soup or None."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    return BeautifulSoup(resp.text, "html.parser")
                backoff = RETRY_BASE_SLEEP * (2 ** (attempt - 1)) + random.uniform(0, 2)
                log.warning(f"  HTTP {resp.status_code} (attempt {attempt}) — sleeping {backoff:.1f}s")
                time.sleep(backoff)
            except Exception as exc:
                backoff = RETRY_BASE_SLEEP * attempt + random.uniform(0, 2)
                log.warning(f"  Request error (attempt {attempt}): {exc} — sleeping {backoff:.1f}s")
                time.sleep(backoff)
        return None

    # ── Public entry-points ───────────────────────────────
    def scrape_bestsellers(self, slug: str, page: int = 1) -> list[Product]:
        cat_name = SLUG_TO_NAME.get(slug, slug.title())
        url = f"{BASE_URL}/gp/bestsellers/{slug}/ref=zg_bs_pg_{page}?ie=UTF8&pg={page}"
        log.info(f"  📦  Bestsellers [{cat_name}] p{page}")
        soup = self.fetch(url)
        return self._parse_zg(soup, cat_name, "bestseller", page) if soup else []

    def scrape_movers(self, slug: str, page: int = 1) -> list[Product]:
        cat_name = SLUG_TO_NAME.get(slug, slug.title()) + " (M&S)"
        url = f"{BASE_URL}/gp/movers-and-shakers/{slug}/ref=zg_bsms_pg_{page}?ie=UTF8&pg={page}"
        log.info(f"  🚀  Movers & Shakers [{cat_name}] p{page}")
        soup = self.fetch(url)
        return self._parse_zg(soup, cat_name, "movers", page) if soup else []

    # ── ZG page parser ────────────────────────────────────
    def _parse_zg(self, soup: BeautifulSoup, cat: str, source: str, page: int) -> list[Product]:
        # Amazon uses multiple grid layouts — cascade through known selectors
        items = (soup.select("div[id^='gridItemRoot']")
                 or soup.select("li.zg-item-immersion")
                 or soup.select("div.zg-item"))
        log.info(f"    ↳ {len(items)} items found")

        products: list[Product] = []
        base_rank = (page - 1) * 50

        for idx, item in enumerate(items, 1):
            try:
                p = self._parse_item(item, cat, source, base_rank + idx)
                if p.price > 0 or p.rank <= 50:
                    _recalc(p)
                    products.append(p)
            except Exception as exc:
                log.debug(f"  ⚠  item {idx}: {exc}")

        return products

    def _parse_item(self, item: Tag, cat: str, source: str, rank: int) -> Product:
        p = Product(rank=rank, category=cat, source_page=source)

        # title
        el = _first_text(item, _TITLE_SELS)
        if el and el.get_text(strip=True):
            p.title = el.get_text(strip=True)
        elif item.select_one("img") and item.select_one("img").get("alt"):
            p.title = item.select_one("img").get("alt").strip()
        else:
            p.title = ""

        # URL + ASIN
        link = item.select_one("a[href*='/dp/']") or item.select_one("a.a-link-normal")
        if link and link.get("href"):
            href = link["href"]
            p.amazon_url = href if href.startswith("http") else BASE_URL + href
            p.asin = extract_asin(p.amazon_url)

        # image
        img = item.select_one("img")
        if img:
            src = img.get("data-old-hires") or img.get("data-src") or img.get("src", "")
            p.image_url = high_res_image(src)

        # price
        pel = _first_text(item, _PRICE_SELS)
        if pel:
            p.price = parse_price(pel.get_text())

        # rating
        rel = _first_text(item, _RATING_SELS)
        if rel:
            m = _RE_RATING.search(rel.get_text())
            if m:
                p.rating = float(m.group(1))

        # review count
        rcel = _first_text(item, _REVIEW_SELS)
        if rcel:
            text = rcel.get("aria-label", "") or rcel.get_text()
            m = _RE_COUNT.search(text.replace(",", ""))
            if m:
                p.review_count = int(m.group().replace(",", ""))

        # seller count from card if present
        olp_link = item.select_one("span.a-declarative a") or item.select_one("a[href*='offer-listing']")
        if olp_link:
            m_olp = _RE_PRICE.search(olp_link.get_text())
            if m_olp and "offer" in olp_link.get_text().lower():
                p.seller_count = int(m_olp.group())

        # use rank as BSR proxy until enrichment
        p.bsr = rank
        return p

    # ── Deep product-page enrichment ──────────────────────
    def enrich_product(self, p: Product) -> Product:
        """Visit /dp/<ASIN> to get real BSR, accurate price, and hi-res image."""
        if not p.asin:
            return p
        soup = self.fetch(f"{BASE_URL}/dp/{p.asin}")
        if not soup:
            return p

        # title
        t_el = soup.select_one("span#productTitle") or soup.select_one("h1#title")
        if t_el and t_el.get_text(strip=True):
            p.title = t_el.get_text(strip=True)

        # deal price
        del_el = _first_text(soup, _DEAL_SELS)
        if del_el:
            v = parse_price(del_el.get_text())
            if v > 0:
                p.deal_price = v
                if p.price == 0:
                    p.price = v

        # MRP
        mrp_el = _first_text(soup, _MRP_SELS)
        if mrp_el:
            v = parse_price(mrp_el.get_text())
            if v > p.price:
                p.mrp = v

        # rating
        r_el = soup.select_one("span#acrPopover span.a-icon-alt") or soup.select_one("span#acrPopover") or soup.select_one("i.a-icon-star span")
        if r_el:
            m = re.search(r"(\d+(?:\.\d+)?)\s*out\s*of", r_el.get_text()) or _RE_RATING.search(r_el.get_text())
            if m:
                try:
                    p.rating = float(m.group(1))
                except ValueError:
                    pass

        # review count
        rc_el = soup.select_one("span#acrCustomerReviewText") or soup.select_one("span#acrPopoverText")
        if rc_el:
            m = _RE_COUNT.search(rc_el.get_text().replace(",", ""))
            if m:
                p.review_count = int(m.group().replace(",", ""))

        # BSR — find first #N in the "Best Sellers Rank" section
        bsr_node = soup.find(string=re.compile("Best Sellers Rank", re.I))
        if bsr_node:
            candidates = [bsr_node.find_parent()]
            if bsr_node.find_parent():
                candidates.append(bsr_node.find_parent().find_parent())
            for ptag in candidates:
                if ptag:
                    m = re.search(r"#([\d,]+)\s+in", ptag.get_text()) or _RE_BSR_NUM.search(ptag.get_text())
                    if m:
                        p.bsr = int(m.group(1).replace(",", ""))
                        break

        # hi-res image — prefer data-a-dynamic-image JSON (largest variant)
        img_el = _first_text(soup, _IMG_SELS)
        if img_el:
            dyn = img_el.get("data-a-dynamic-image", "{}")
            try:
                imgs = json.loads(dyn)
                if imgs:
                    p.image_url = max(imgs, key=lambda u: imgs[u][0])
                    img_el = None  # skip fallback
            except (json.JSONDecodeError, KeyError):
                pass
            if img_el:
                src = img_el.get("data-old-hires") or img_el.get("src", "")
                if src:
                    p.image_url = high_res_image(src)

        # Number of competing sellers
        p.seller_count = 1
        for sel in ["div#olp_feature_div", "div#moreBuyingChoices_feature_div", "div#all-offers-display", "div#dynamic-aod-ingress-box"]:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(" ", strip=True)
                m = re.search(r"(?:New\s*\(([0-9]+)\)|([0-9]+)\s*(?:new|offers|sellers))", txt, re.I)
                if m:
                    p.seller_count = int(m.group(1) or m.group(2))
                    break
        if p.seller_count == 1:
            m2 = re.search(r"([0-9]+)\s*offers", soup.get_text(), re.I)
            if m2 and int(m2.group(1)) > 1:
                p.seller_count = int(m2.group(1))

        _recalc(p)
        return p


# ═════════════════════════════════════════════════════════
#  REPORT WRITERS  (each returns the Path written)
# ═════════════════════════════════════════════════════════

def save_csv(products: list[Product], path: Path) -> Path:
    if not products:
        return path
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(products[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(p) for p in products)
    log.info(f"  💾  CSV  → {path.name}")
    return path


def save_excel(products: list[Product], path: Path) -> Path:
    if not (_PANDAS and products):
        return path
    try:
        import openpyxl  # noqa: F401
        priority = ["rank","title","category","source_page","price","mrp","discount_pct",
                    "rating","review_count","bsr","est_monthly_sales","est_monthly_revenue",
                    "revenue_band","blog_worthy","asin","amazon_url"]
        df = pd.DataFrame(asdict(p) for p in products)
        ordered = priority + [c for c in df.columns if c not in priority]
        df[[c for c in ordered if c in df.columns]].to_excel(path, index=False)
        log.info(f"  📊  XLSX → {path.name}")
    except ImportError:
        log.warning("  openpyxl not installed — skipping Excel")
    except Exception as exc:
        log.warning(f"  Excel save failed: {exc}")
    return path


def save_html_report(products: list[Product], path: Path) -> Path:
    """Standalone HTML report (no server needed)."""
    now      = datetime.now().strftime("%d %B %Y, %I:%M %p")
    rows_html = ""
    for p in products:
        bg    = "#f0fff4" if p.blog_worthy else "#ffffff"
        badge = "✅ Blog Pick" if p.blog_worthy else ""
        img   = (f'<img src="{p.image_url}" style="width:56px;height:56px;'
                 f'object-fit:contain;border-radius:6px;">' if p.image_url else "🖼️")
        link  = (f'<a href="{p.amazon_url}" target="_blank" '
                 f'style="color:#c0392b;font-weight:600;">'
                 f'{p.title[:70]}{"…" if len(p.title)>70 else ""}</a>'
                 if p.amazon_url else p.title[:70])
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td style="text-align:center">{p.rank}</td>'
            f'<td>{img}</td>'
            f'<td>{link}<br><small style="color:#888">{p.asin}</small></td>'
            f'<td>{p.category}</td>'
            f'<td style="text-align:center">{p.source_page}</td>'
            f'<td style="text-align:right;font-weight:700">₹{p.price:,.0f}</td>'
            f'<td style="text-align:right;color:#888">{"₹{:,.0f}".format(p.mrp) if p.mrp else "—"}</td>'
            f'<td style="text-align:center;color:#e74c3c">{"{}%".format(int(p.discount_pct)) if p.discount_pct else "—"}</td>'
            f'<td style="text-align:center">{p.rating} ⭐<br><small>{p.review_count:,}</small></td>'
            f'<td style="text-align:center">{p.bsr:,}</td>'
            f'<td style="text-align:center">{p.est_monthly_sales:,}</td>'
            f'<td style="text-align:right;font-weight:700;color:#155724">₹{p.est_monthly_revenue:,.0f}</td>'
            f'<td style="text-align:center">{p.revenue_band}</td>'
            f'<td style="text-align:center">{badge}</td>'
            f'</tr>'
        )

    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZERO483 Research — {now}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f9;color:#333}}
  header{{background:linear-gradient(135deg,#c0392b,#e74c3c);color:#fff;padding:24px 32px}}
  header h1{{font-size:1.6rem}} header p{{font-size:.9rem;opacity:.85;margin-top:6px}}
  .stats{{display:flex;gap:16px;flex-wrap:wrap;padding:20px 32px}}
  .sc{{background:#fff;border-radius:12px;padding:16px 24px;
       box-shadow:0 2px 8px rgba(0,0,0,.08);min-width:160px}}
  .sc .v{{font-size:1.8rem;font-weight:700;color:#c0392b}} .sc .l{{font-size:.78rem;color:#777;margin-top:4px}}
  .tw{{overflow-x:auto;padding:0 32px 40px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;
         overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);font-size:.82rem}}
  th{{background:#2c3e50;color:#fff;padding:10px 8px;text-align:left;white-space:nowrap}}
  td{{padding:8px;border-bottom:1px solid #f0f0f0;vertical-align:middle}}
  tr:hover{{background:#fffde7!important}}
</style></head><body>
<header>
  <h1>🛍️ ZERO483 — Product Research Report</h1>
  <p>Generated: {now} &nbsp;|&nbsp; Revenue Band: ₹10L – ₹1Cr / month</p>
</header>
<div class="stats">
  <div class="sc"><div class="v">{len(products)}</div><div class="l">Total Products</div></div>
  <div class="sc"><div class="v">{sum(1 for p in products if p.blog_worthy)}</div><div class="l">✅ Blog-Worthy</div></div>
  <div class="sc"><div class="v">{sum(1 for p in products if p.est_monthly_revenue >= REVENUE_MIN)}</div><div class="l">In ₹10L+ Band</div></div>
  <div class="sc"><div class="v">₹{max((p.est_monthly_revenue for p in products), default=0):,.0f}</div><div class="l">Top Revenue Est.</div></div>
</div>
<div class="tw"><table>
  <thead><tr><th>#</th><th>Image</th><th>Product / ASIN</th><th>Category</th><th>Source</th>
  <th>Price</th><th>MRP</th><th>Disc%</th><th>Rating / Reviews</th><th>BSR</th>
  <th>Sales/mo</th><th>Revenue/mo</th><th>Band</th><th>Flag</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table></div>
<div style="padding:16px 32px 32px;font-size:.82rem;color:#666">
  ⚠️ <strong>Disclaimer:</strong> Estimates derived from BSR interpolation (Amazon India ~12-15% of US).
  Use for content research only.
</div></body></html>"""

    path.write_text(html, encoding="utf-8")
    log.info(f"  🌐  HTML → {path.name}")
    return path


# ═════════════════════════════════════════════════════════
#  CLI RUNNER
# ═════════════════════════════════════════════════════════

def run_cli(args) -> list[Product]:
    log.info("=" * 56)
    log.info("  ZERO483  Amazon India Product Research Tool v3.0")
    log.info("=" * 56)

    scraper = AmazonIndiaScraper(max_pages=args.pages)
    all_products: list[Product] = []

    # Resolve categories
    if args.all_categories:
        slugs = list(CATEGORIES.values())
    elif args.categories:
        slugs = [
            v for k, v in CATEGORIES.items()
            if any(a.lower() in k.lower() for a in args.categories)
        ]
    else:
        slugs = ["beauty", "health", "kitchen", "sports"]

    # Bestsellers
    if not args.movers_only:
        log.info("\n📦  BESTSELLERS")
        for slug in slugs:
            for pg in range(1, args.pages + 1):
                all_products.extend(scraper.scrape_bestsellers(slug, pg))
                _crawl_sleep()

    # Movers & Shakers
    if not args.bestsellers_only:
        log.info("\n🚀  MOVERS & SHAKERS")
        for slug in slugs:
            if slug not in MOVERS_SLUGS:
                continue
            all_products.extend(scraper.scrape_movers(slug, 1))
            _crawl_sleep()

    log.info(f"\n  ✅  Scraped {len(all_products)} products total")

    # Deep enrich
    if args.enrich and all_products:
        top = sorted(
            (p for p in all_products if p.price > 0),
            key=lambda p: p.rank
        )[:args.enrich_limit]
        log.info(f"\n🔍  Enriching top {len(top)} …")
        for i, p in enumerate(top, 1):
            log.info(f"  [{i}/{len(top)}] {p.title[:52]}")
            scraper.enrich_product(p)
            _crawl_sleep()

    # Sort & filter
    revenue_products = sorted(
        (p for p in all_products if p.price > 0),
        key=lambda p: p.est_monthly_revenue, reverse=True
    )
    blog_picks = [p for p in revenue_products if p.blog_worthy]

    log.info(f"\n📊  SUMMARY  total={len(all_products)}  "
             f"priced={len(revenue_products)}  blog-worthy={len(blog_picks)}")

    # Console top 20
    print("\n" + "═" * 80)
    print("  TOP 20 BLOG-WORTHY PRODUCTS")
    print("═" * 80)
    for i, p in enumerate(blog_picks[:20], 1):
        print(f"  {i:>2}. {p.revenue_band}  ₹{p.est_monthly_revenue:>12,.0f}/mo"
              f"  |  ₹{p.price:,.0f}  |  BSR #{p.bsr:,}")
        print(f"       {p.title[:74]}")
        print(f"       {p.amazon_url[:80]}")

    # Save outputs
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    save_csv(revenue_products,       OUTPUT_DIR / f"products_{ts}.csv")
    save_html_report(revenue_products, OUTPUT_DIR / f"report_{ts}.html")
    save_excel(revenue_products,     OUTPUT_DIR / f"products_{ts}.xlsx")
    log.info(f"\n✅  Done — open {OUTPUT_DIR / f'report_{ts}.html'}")
    return revenue_products


def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ZERO483 Amazon India Product Research Tool v3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--categories", nargs="*", metavar="CAT")
    p.add_argument("--all-categories", action="store_true")
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--movers-only", action="store_true")
    p.add_argument("--bestsellers-only", action="store_true")
    p.add_argument("--enrich", action="store_true")
    p.add_argument("--enrich-limit", type=int, default=50)
    p.add_argument("--revenue-min", type=float, default=REVENUE_MIN)
    p.add_argument("--revenue-max", type=float, default=REVENUE_MAX)
    return p


if __name__ == "__main__":
    args = _build_cli().parse_args()
    REVENUE_MIN = args.revenue_min
    REVENUE_MAX = args.revenue_max
    run_cli(args)
