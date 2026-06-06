"""
USFDA Pharma News Processor for Zero483.com
============================================
Fetches the latest pharmaceutical regulatory news from:
  1. openFDA API (drug recalls, enforcement, approvals, shortages)
  2. FDA Warning Letters page (web scraping)

Uses Google Gemini API to analyze compliance impact and saves
structured results to news_database.json for the website widget.

Requirements:
  pip install google-genai requests python-dotenv

Usage:
  python fda_news_processor.py

Environment Variables (place in .env file in this folder):
  GEMINI_API_KEY=your_gemini_api_key_here
"""

import json
import os
import sys
import ssl
import re
import hashlib
import time
import base64
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
import difflib

# Force UTF-8 output on Windows (fixes cp1252 encoding errors)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env loading is optional

try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("[WARNING] google-genai not installed. AI summaries will be skipped.")
    print("          Install with: pip install google-genai")

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
DATABASE_FILE  = BASE_DIR / "news_database.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FDA_API_KEY    = os.getenv("FDA_API_KEY", "")
MAX_ITEMS_DB   = 50          # Max total items to keep in the database
FETCH_LIMIT    = 10          # Items to fetch per source per run
DAYS_LOOKBACK  = 7           # Only include items from past N days

# openFDA API base
OPENFDA_BASE = "https://api.fda.gov"

# SSL context (handles corporate proxies with self-signed certs)
SSL_CONTEXT = ssl._create_unverified_context()

# Categories shown in the widget filter bar
CATEGORY_MAP = {
    "enforcement": "Recall",
    "event":       "Adverse Event",
    "shortages":   "Drug Shortage",
    "drugsfda":    "Drug Approval",
    "label":       "Label Update",
    "warning":     "Warning Letter",
    "press":       "Press Release",
}

SEVERITY_KEYWORDS = {
    "High": [
        "class i", "death", "serious", "critical", "hospitalisation",
        "hospitalization", "life-threatening", "major violation",
        "seizure", "immediate recall", "public health emergency",
        "contamination", "microbial", "sterility failure",
    ],
    "Medium": [
        "class ii", "injury", "adverse event", "shortage", "warning letter",
        "deviations", "corrective action", "CAPA", "data integrity",
        "out-of-specification", "OOS",
    ],
    "Low": [
        "class iii", "voluntary recall", "label update", "guideline",
        "approval", "generic approval", "new drug application",
    ],
}


# ── Utility helpers ───────────────────────────────────────────────────────────

def http_get(url: str, timeout: int = 20) -> dict | None:
    """Perform a GET request and return parsed JSON, or None on failure."""
    # Append FDA API key if available (raises limit to 120,000 req/day)
    if FDA_API_KEY and "api.fda.gov" in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}api_key={FDA_API_KEY}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; Zero483Bot/1.0; "
            "+https://www.zero483.com)"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"  [HTTP ERROR] {url}\n  >> {exc}")
        return None


def make_id(text: str) -> str:
    """Generate a stable short ID from text."""
    return hashlib.md5(text.encode()).hexdigest()[:12]


def date_str(yyyymmdd: str) -> str:
    """Convert openFDA YYYYMMDD date string to ISO 8601 format."""
    try:
        return datetime.strptime(yyyymmdd[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def assess_severity(text: str) -> str:
    """Heuristic severity rating based on keyword matching."""
    text_lower = text.lower()
    for level in ("High", "Medium", "Low"):
        if any(kw in text_lower for kw in SEVERITY_KEYWORDS[level]):
            return level
    return "Medium"


def today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def cutoff_date() -> str:
    """Return the cutoff date string (YYYYMMDD) for openFDA queries."""
    return (datetime.now(timezone.utc) - timedelta(days=DAYS_LOOKBACK)).strftime("%Y%m%d")


# ── Gemini AI analysis ────────────────────────────────────────────────────────

def build_gemini_client():
    """Initialize Gemini client if key is available."""
    if not GENAI_AVAILABLE:
        return None
    if not GEMINI_API_KEY:
        print("[WARNING] GEMINI_API_KEY not set. AI summaries will be skipped.")
        print("          Add GEMINI_API_KEY=<your_key> to a .env file in the workspace.")
        return None
    
    # We attach a custom flag to track if the quota is permanently exhausted
    client = genai.Client(api_key=GEMINI_API_KEY)
    client.quota_exhausted = False
    return client


def ai_analyze(client, title: str, raw_text: str, retries: int = 3) -> dict:
    """
    Ask Gemini to produce:
      - summary (2-3 sentences, plain language)
      - compliance_impact (2-3 bullet points for pharma QA professionals)
      - key_actions (1-2 immediate steps)
    Returns a dict; falls back to basic text if AI is unavailable.
    Automatically retries on 429 rate-limit errors with the suggested delay.
    """
    if client is None:
        truncated = raw_text[:600].strip()
        return {
            "summary": truncated if truncated else title,
            "compliance_impact": (
                "Review this update and assess its relevance to your quality systems. "
                "Consult with your regulatory affairs team for site-specific impact."
            ),
            "key_actions": "Review and escalate to QA leadership as appropriate.",
        }

    prompt = f"""You are a senior pharmaceutical GMP auditor and regulatory affairs expert \
with extensive knowledge of USFDA inspection readiness and Zero 483 culture.

Analyse this FDA regulatory update and provide a response in this exact JSON format \
(no markdown code fence, just raw JSON):

{{
  "summary": "2-3 plain-language sentences summarising what happened.",
  "compliance_impact": "2-3 concise bullet points (starting with *) describing the \
specific impact on pharmaceutical inspection readiness and quality systems.",
  "key_actions": "1-2 immediate action items a Quality Assurance Manager should take \
today."
}}

TITLE: {title}
---
{raw_text[:1500]}
"""

    if getattr(client, "quota_exhausted", False):
        return {
            "summary": raw_text[:400].strip(),
            "compliance_impact": "Review and assess the impact on your site's quality systems.",
            "key_actions": "Escalate to QA leadership for site-specific action plan.",
        }

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = response.text.strip()
            # Strip any markdown code fences if model added them
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
            return json.loads(text)

        except Exception as exc:
            exc_str = str(exc)

            # Handle 429 rate-limit: extract retry delay from error and wait
            if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
                # Try to parse the suggested retry delay from the error message
                delay_match = re.search(r"retryDelay.*?(\d+)s", exc_str)
                wait_secs = int(delay_match.group(1)) + 5 if delay_match else 15
                if attempt < retries - 1:
                    print(f"  [RATE LIMIT] Gemini quota hit. Waiting {wait_secs}s before retry {attempt+2}/{retries}...")
                    time.sleep(wait_secs)
                    continue
                else:
                    print(f"  [RATE LIMIT] Gemini quota exhausted. Disabling AI for remaining items to save time.")
                    client.quota_exhausted = True
            else:
                print(f"  [AI ERROR] {exc_str[:200]}")

            # Fallback on final attempt or non-rate-limit error
            return {
                "summary": raw_text[:400].strip(),
                "compliance_impact": "Review and assess the impact on your site's quality systems.",
                "key_actions": "Escalate to QA leadership for site-specific action plan.",
            }

    return {
        "summary": raw_text[:400].strip(),
        "compliance_impact": "Review and assess the impact on your site's quality systems.",
        "key_actions": "Escalate to QA leadership for site-specific action plan.",
    }



# ── Data sources ──────────────────────────────────────────────────────────────

def fetch_drug_recalls(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch recent drug enforcement/recall reports from openFDA."""
    print("\n[SOURCE] openFDA Drug Recalls / Enforcement...")
    # Use +TO+ syntax (confirmed working); bracket-encoded variants cause 404
    start = cutoff_date()
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y%m%d")
    url = (
        f"{OPENFDA_BASE}/drug/enforcement.json"
        f"?search=report_date:[{start}+TO+{end}]"
        f"&sort=report_date:desc&limit={limit}"
    )
    data = http_get(url)
    if not data or "results" not in data:
        print("  No recall data fetched.")
        return []

    items = []
    for r in data["results"]:
        title = (
            f"Drug Recall: {r.get('product_description', 'Unknown Product')[:80]}"
        )
        raw_text = (
            f"Recalling firm: {r.get('recalling_firm', 'N/A')}\n"
            f"Product: {r.get('product_description', 'N/A')}\n"
            f"Reason: {r.get('reason_for_recall', 'N/A')}\n"
            f"Classification: {r.get('classification', 'N/A')}\n"
            f"Status: {r.get('status', 'N/A')}\n"
            f"Distribution: {r.get('distribution_pattern', 'N/A')}\n"
            f"Quantity: {r.get('product_quantity', 'N/A')}"
        )
        items.append({
            "_id":      make_id(title + r.get("recall_initiation_date", "")),
            "_title":   title,
            "_date":    date_str(r.get("recall_initiation_date", "")),
            "_category":"Recall",
            "_severity": assess_severity(raw_text),
            "_raw":     raw_text,
            "_url":     (
                f"https://www.accessdata.fda.gov/scripts/ires/index.cfm?Event={r['event_id']}"
                if "event_id" in r
                else "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts"
            ),
        })
    print(f"  Fetched {len(items)} recall items.")
    return items


def fetch_drug_shortages(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch current drug shortage reports from openFDA."""
    print("\n[SOURCE] openFDA Drug Shortages...")
    # status:Current confirmed working (1,149 results); no date sort needed
    start = cutoff_date()
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y%m%d")
    url = (
        f"{OPENFDA_BASE}/drug/shortages.json"
        f"?search=status:Current+AND+update_date:[{start}+TO+{end}]"
        f"&sort=update_date:desc&limit={limit}"
    )
    data = http_get(url)
    if not data or "results" not in data:
        print("  No shortage data fetched.")
        return []

    items = []
    for r in data["results"]:
        title = (
            f"Drug Shortage: "
            f"{r.get('generic_name', r.get('proprietary_name', 'Unknown'))[:80]}"
        )
        raw_text = (
            f"Generic name: {r.get('generic_name', 'N/A')}\n"
            f"Brand name: {r.get('proprietary_name', 'N/A')}\n"
            f"Status: {r.get('status', 'N/A')}\n"
            f"Presentations: {json.dumps(r.get('presentations', []))[:300]}"
        )
        items.append({
            "_id":       make_id(title),
            "_title":    title,
            "_date":     date_str(r.get("update_date", today_iso().replace("-", ""))),
            "_category": "Drug Shortage",
            "_severity":  assess_severity(raw_text),
            "_raw":      raw_text,
            "_url":      (
                f"https://news.google.com/search?q="
                f"FDA+Shortage+{urllib.parse.quote_plus(r.get('generic_name', r.get('proprietary_name', '')))}"
            ),
        })
    print(f"  Fetched {len(items)} shortage items.")
    return items


def fetch_drug_approvals(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch recent NDA/ANDA approvals from openFDA drugsfda endpoint."""
    print("\n[SOURCE] openFDA Drug Approvals (drugsfda)...")
    start = cutoff_date()
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y%m%d")
    url = (
        f"{OPENFDA_BASE}/drug/drugsfda.json"
        f"?search=submissions.submission_status_date:[{start}+TO+{end}]"
        f"&sort=submissions.submission_status_date:desc&limit={limit}"
    )
    data = http_get(url)
    if not data or "results" not in data:
        print("  No approval data fetched.")
        return []

    items = []
    for r in data["results"]:
        sponsor = r.get("sponsor_name", "Unknown sponsor")
        products = r.get("products", [{}])
        brand = products[0].get("brand_name", "Unknown product") if products else "Unknown product"
        title = f"Drug Approval: {brand} - {sponsor}"

        submissions = r.get("submissions", [])
        
        # Filter strictly for ORIGINAL submissions in our date range
        valid_orig_submissions = []
        for s in submissions:
            if s.get("submission_type") == "ORIG":
                s_date = s.get("submission_status_date", "")
                if start <= s_date <= end:
                    valid_orig_submissions.append(s)
                    
        if not valid_orig_submissions:
            continue
            
        # Use the newest valid original submission
        valid_orig_submissions.sort(key=lambda s: s.get("submission_status_date", ""), reverse=True)
        latest = valid_orig_submissions[0]
        
        raw_text = (
            f"Application: {r.get('application_number', 'N/A')}\n"
            f"Sponsor: {sponsor}\n"
            f"Product: {brand}\n"
            f"Submission type: {latest.get('submission_type', 'N/A')}\n"
            f"Submission class: {latest.get('submission_class_code_description', 'N/A')}\n"
            f"Status: {latest.get('submission_status', 'N/A')}\n"
            f"Status date: {latest.get('submission_status_date', 'N/A')}"
        )
        # Normalize application number (e.g. ANDA220137 -> 220137, NDA220787 -> 220787) to form valid FDA Drugs@FDA link
        app_no_raw = r.get("application_number", "")
        # Remove any leading alpha prefix (like NDA, ANDA, BLA, etc.) keeping only digits
        app_no_clean = re.sub(r"^[a-zA-Z]+", "", app_no_raw)

        items.append({
            "_id":       make_id(app_no_raw if app_no_raw else title),
            "_title":    title[:120],
            "_date":     date_str(latest.get("submission_status_date", "")),
            "_category": "Drug Approval",
            "_severity":  "Low",
            "_raw":      raw_text,
            "_url":      (
                f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
                f"?event=overview.process&ApplNo="
                f"{app_no_clean}"
            ),
        })
    print(f"  Fetched {len(items)} approval items.")
    return items


def fetch_adverse_events_summary(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch recent serious adverse drug event reports."""
    print("\n[SOURCE] openFDA Serious Drug Adverse Events (FAERS)...")
    # +TO+ syntax confirmed working (881,427 results for Jan 2025 - Dec 2026)
    start = cutoff_date()
    end = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y%m%d")
    url = (
        f"{OPENFDA_BASE}/drug/event.json"
        f"?search=serious:1+AND+receivedate:[{start}+TO+{end}]"
        f"&sort=receivedate:desc&limit={limit}"
    )
    data = http_get(url)
    if not data or "results" not in data:
        print("  No adverse event data fetched.")
        return []

    items = []
    for r in data["results"]:
        drugs = r.get("patient", {}).get("drug", [])
        drug_names = ", ".join(
            d.get("medicinalproduct", "Unknown") for d in drugs[:3]
        )
        reactions = r.get("patient", {}).get("reaction", [])
        reaction_list = ", ".join(
            rx.get("reactionmeddrapt", "Unknown") for rx in reactions[:3]
        )
        title = f"Adverse Event Report: {drug_names[:80]}"
        raw_text = (
            f"Drugs involved: {drug_names}\n"
            f"Reactions: {reaction_list}\n"
            f"Serious: {'Yes' if r.get('serious') == '1' else 'No'}\n"
            f"Country: {r.get('occurcountry', 'N/A')}\n"
            f"Received date: {r.get('receivedate', 'N/A')}"
        )
        items.append({
            "_id":       make_id(title + r.get("safetyreportid", "")),
            "_title":    title,
            "_date":     date_str(r.get("receivedate", "")),
            "_category": "Adverse Event",
            "_severity":  "High",
            "_raw":      raw_text,
            "_url":      (
                f"https://news.google.com/search?q="
                f"FDA+Adverse+Event+{urllib.parse.quote_plus(drug_names[:30])}"
            ),
        })
    print(f"  Fetched {len(items)} adverse event items.")
    return items


def fetch_google_news_recalls(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch FDA Recalls from Google News RSS to bypass openFDA latency."""
    print("\n[SOURCE] Google News RSS (FDA Recalls)...")
    url = 'https://news.google.com/rss/search?q=%22FDA%22+%22Recall%22+(drug+OR+pharma)&hl=en-US&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
    except Exception as e:
        print(f"  Failed to fetch RSS: {e}")
        return []

    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.find('title').text or "FDA Recall News"
        link = item.find('link').text or ""
        pubDate = item.find('pubDate').text or ""
        
        try:
            dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
            if (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days > DAYS_LOOKBACK:
                continue
            date_s = dt.strftime("%Y-%m-%d")
        except:
            date_s = today_iso()

        raw_text = f"Title: {title}\nSource: Google News\nDate: {pubDate}"
        
        items.append({
            "_id":       make_id(title),
            "_title":    title[:120],
            "_date":     date_s,
            "_category": "Recall",
            "_severity": "High",
            "_raw":      raw_text,
            "_url":      link,
        })
    print(f"  Fetched {len(items)} recall news items.")
    return items


def fetch_google_news_shortages(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch FDA Drug Shortages from Google News RSS to bypass openFDA latency."""
    print("\n[SOURCE] Google News RSS (FDA Shortages)...")
    url = 'https://news.google.com/rss/search?q=FDA+drug+shortage&hl=en-US&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
    except Exception as e:
        print(f"  Failed to fetch RSS: {e}")
        return []

    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.find('title').text or "FDA Shortage News"
        link = item.find('link').text or ""
        pubDate = item.find('pubDate').text or ""
        
        try:
            dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
            if (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days > DAYS_LOOKBACK:
                continue
            date_s = dt.strftime("%Y-%m-%d")
        except:
            date_s = today_iso()

        raw_text = f"Title: {title}\nSource: Google News\nDate: {pubDate}"
        
        items.append({
            "_id":       make_id(title),
            "_title":    title[:120],
            "_date":     date_s,
            "_category": "Drug Shortage",
            "_severity": "Medium",
            "_raw":      raw_text,
            "_url":      link,
        })
    print(f"  Fetched {len(items)} shortage news items.")
    return items


def fetch_google_news_adverse_events(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch FDA Adverse Events / Safety Alerts from Google News RSS to bypass openFDA latency."""
    print("\n[SOURCE] Google News RSS (FDA Adverse Events)...")
    url = 'https://news.google.com/rss/search?q=(FDA+safety+alert+OR+FDA+adverse+event+OR+FDA+warning)+(drug+OR+pharma)&hl=en-US&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
    except Exception as e:
        print(f"  Failed to fetch RSS: {e}")
        return []

    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.find('title').text or "FDA Safety Alert News"
        link = item.find('link').text or ""
        pubDate = item.find('pubDate').text or ""
        
        try:
            dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
            if (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days > DAYS_LOOKBACK:
                continue
            date_s = dt.strftime("%Y-%m-%d")
        except:
            date_s = today_iso()

        raw_text = f"Title: {title}\nSource: Google News\nDate: {pubDate}"
        
        items.append({
            "_id":       make_id(title),
            "_title":    title[:120],
            "_date":     date_s,
            "_category": "Adverse Event",
            "_severity": "High",
            "_raw":      raw_text,
            "_url":      link,
        })
    print(f"  Fetched {len(items)} adverse event news items.")
    return items


def fetch_google_news_warning_letters(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch FDA Warning Letters and Form 483 news from Google News RSS."""
    print("\n[SOURCE] Google News RSS (Warning Letters / Form 483)...")
    url = 'https://news.google.com/rss/search?q=(%22FDA%22+%22Warning+Letter%22+OR+%22Form+483%22)+(drug+OR+pharma)&hl=en-US&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
    except Exception as e:
        print(f"  Failed to fetch RSS: {e}")
        return []

    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.find('title').text or "Warning Letter / 483 News"
        link = item.find('link').text or ""
        pubDate = item.find('pubDate').text or ""
        
        try:
            # e.g., Thu, 21 May 2026 07:00:00 GMT
            dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
            if (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days > DAYS_LOOKBACK:
                continue
            date_s = dt.strftime("%Y-%m-%d")
        except:
            date_s = today_iso()

        raw_text = f"Title: {title}\nSource: Google News\nDate: {pubDate}"
        cat = "Warning Letter" if "warning letter" in title.lower() else "Form 483"
        
        items.append({
            "_id":       make_id(title),
            "_title":    title[:120],
            "_date":     date_s,
            "_category": cat,
            "_severity": "High",
            "_raw":      raw_text,
            "_url":      link,
        })
    print(f"  Fetched {len(items)} regulatory news items.")
    return items


def fetch_google_news_guidances(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch FDA Draft Guidance and Guidelines news from Google News RSS."""
    print("\n[SOURCE] Google News RSS (FDA Guidelines)...")
    url = 'https://news.google.com/rss/search?q=(%22FDA%22+%22Guidance%22+OR+%22Guidelines%22)+(drug+OR+pharma)&hl=en-US&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
    except Exception as e:
        print(f"  Failed to fetch RSS: {e}")
        return []

    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.find('title').text or "FDA Guidance News"
        link = item.find('link').text or ""
        pubDate = item.find('pubDate').text or ""
        
        try:
            dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
            if (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days > DAYS_LOOKBACK:
                continue
            date_s = dt.strftime("%Y-%m-%d")
        except:
            date_s = today_iso()

        raw_text = f"Title: {title}\nSource: Google News\nDate: {pubDate}"
        
        items.append({
            "_id":       make_id(title),
            "_title":    title[:120],
            "_date":     date_s,
            "_category": "Guidance",
            "_severity": "Low",
            "_raw":      raw_text,
            "_url":      link,
        })
    print(f"  Fetched {len(items)} guidance news items.")
    return items


# ── Database I/O ──────────────────────────────────────────────────────────────

def load_database() -> dict:
    """Load existing database from JSON file, or return fresh structure."""
    if DATABASE_FILE.exists():
        with DATABASE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_updated": "", "total_items": 0, "items": []}


def save_database(db: dict) -> None:
    """Persist the database to disk."""
    db["last_updated"] = datetime.now(timezone.utc).isoformat()
    db["total_items"]  = len(db["items"])
    with DATABASE_FILE.open("w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] Database saved >> {DATABASE_FILE}")
    print(f"   Total items: {db['total_items']} | Last updated: {db['last_updated']}")


def is_duplicate_title(new_title: str, existing_titles: list, threshold: float = 0.65) -> bool:
    """Return True if new_title is too similar to any title in existing_titles."""
    new_title_lower = new_title.lower()
    for ext_title in existing_titles:
        if difflib.SequenceMatcher(None, new_title_lower, ext_title.lower()).ratio() > threshold:
            return True
    return False


def merge_items(db: dict, new_items: list[dict], client) -> int:
    """
    Add new items to the database, skipping duplicates.
    Runs AI analysis on each new item before inserting.
    Returns count of newly added items.
    """
    existing_ids = {item["id"] for item in db["items"]}
    existing_titles = [item["title"] for item in db["items"]]
    added = 0

    for raw in new_items:
        if raw["_id"] in existing_ids:
            continue

        if is_duplicate_title(raw["_title"], existing_titles):
            print(f"\n  [SKIP] Duplicate topic detected: {raw['_title'][:60]}...")
            continue

        print(f"\n  >> Analysing: {raw['_title'][:70]}...")
        analysis = ai_analyze(client, raw["_title"], raw["_raw"])
        # Stay within Gemini free tier: 15 req/min = 1 req per 4s minimum
        # Use 5s to have comfortable headroom
        time.sleep(5.0)

        record = {
            "id":               raw["_id"],
            "title":            raw["_title"],
            "date":             raw["_date"],
            "category":         raw["_category"],
            "severity":         raw["_severity"],
            "summary":          analysis.get("summary", ""),
            "compliance_impact":analysis.get("compliance_impact", ""),
            "key_actions":      analysis.get("key_actions", ""),
            "source_url":       raw["_url"],
            "fetched_at":       datetime.now(timezone.utc).isoformat(),
        }
        db["items"].insert(0, record)
        existing_ids.add(raw["_id"])
        existing_titles.append(raw["_title"])
        added += 1

    # Trim to MAX_ITEMS_DB keeping newest first
    db["items"] = db["items"][:MAX_ITEMS_DB]
    return added


def generate_zoho_widget(db: dict) -> None:
    """Read widget.html, inject JSON data, and write to local files"""
    widget_path = BASE_DIR / "widget.html"
    
    if not widget_path.exists():
        return
        
    with widget_path.open("r", encoding="utf-8") as f:
        html = f.read()
        
    # Inject the JSON directly into the JS variable
    json_str = json.dumps(db)
    target = "const INJECTED_DATA = null; /* __WIDGET_DATA_INJECT__ */"
    replacement = f"const INJECTED_DATA = {json_str}; /* __WIDGET_DATA_INJECT__ */"
    final_html = html.replace(target, replacement)
    
    # Write to widget_ready_for_zoho.html
    out_path = BASE_DIR / "widget_ready_for_zoho.html"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"\n[ZOHO READY] Generated {out_path.name}")
    
    # Write directly to index.html so it gets committed to Git Pages
    index_path = BASE_DIR / "index.html"
    with index_path.open("w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"[ZOHO READY] Generated {index_path.name}")


def generate_citizen_widget(db: dict) -> None:
    """Read citizen_widget.html, inject JSON data, and write to local files"""
    widget_path = BASE_DIR / "citizen_widget.html"
    if not widget_path.exists():
        return
        
    with widget_path.open("r", encoding="utf-8") as f:
        html = f.read()
        
    json_str = json.dumps(db)
    target = "const INJECTED_DATA = null; /* __WIDGET_DATA_INJECT__ */"
    replacement = f"const INJECTED_DATA = {json_str}; /* __WIDGET_DATA_INJECT__ */"
    final_html = html.replace(target, replacement)
    
    # Write to citizen_ready.html
    out_path = BASE_DIR / "citizen_ready.html"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"\n[CITIZEN READY] Generated {out_path.name}")
    
    # Write directly to citizen.html so it gets committed to Git Pages
    citizen_path = BASE_DIR / "citizen.html"
    with citizen_path.open("w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"[CITIZEN READY] Generated {citizen_path.name}")


def generate_rss_feed(db: dict) -> str:
    """Generate an XML RSS 2.0 feed from the database items."""
    import html
    from email.utils import formatdate
    import urllib.parse
    
    items_xml = []
    for item in db.get("items", []):
        title_raw = item.get("title", "")
        title = html.escape(title_raw)
        summary = html.escape(item.get("summary", ""))
        category = html.escape(item.get("category", ""))
        date_str = item.get("date", "")
        # convert iso date to rfc822
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            pub_date = formatdate(dt.timestamp(), usegmt=True)
        except:
            pub_date = date_str
            
        encoded_q = urllib.parse.quote(title_raw)
        link = f"https://www.zero483.com/USFDA-news?q={encoded_q}"
        
        item_xml = f"""
    <item>
      <title>{title}</title>
      <description>{summary}</description>
      <link>{link}</link>
      <guid>{link}</guid>
      <category>{category}</category>
      <pubDate>{pub_date}</pubDate>
    </item>"""
        items_xml.append(item_xml)
        
    rss = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>Zero483 FDA Pharma Alerts</title>
    <description>Live tracker for FDA drug recalls, warning letters, and guidance.</description>
    <link>https://www.zero483.com/USFDA-news</link>
    <lastBuildDate>{formatdate(datetime.utcnow().timestamp(), usegmt=True)}</lastBuildDate>
{''.join(items_xml)}
  </channel>
</rss>
"""
    # Write to local file as well
    out_path = BASE_DIR / "feed.xml"
    with out_path.open("w", encoding="utf-8") as f:
        f.write(rss)
    print(f"\n[RSS READY] Generated {out_path.name}")
    return rss


def upload_file_to_github(content: str, filename: str):
    """Uploads a file directly to GitHub Pages."""
    owner = "pnlokeswari"
    repo = "zero483-widget"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filename}"
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print(f"  [WARNING] GITHUB_TOKEN not found in environment. Skipping upload of {filename}.")
        print("  -> Create a .env file with GITHUB_TOKEN=your_token to enable automatic GitHub deployments.")
        return
        
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Zero483-Automation"
    }
    
    # 1. Get current file SHA if it exists
    sha = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            sha = data.get('sha')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            pass # File doesn't exist yet, which is fine
        else:
            print(f"  [ERROR] Failed to fetch current GitHub file state for {filename}: {e}")
            return
    except Exception as e:
        print(f"  [ERROR] Unexpected error: {e}")
        return

    # 2. Upload new content
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    payload = {
        "message": f"Automated {filename} update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha
        
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="PUT")
        with urllib.request.urlopen(req) as response:
            if response.status in (200, 201):
                print(f"  [OK] Successfully pushed {filename} live to: https://{owner}.github.io/{repo}/{filename}")
            else:
                print(f"  [ERROR] Unexpected status code: {response.status}")
    except Exception as e:
        print(f"  [ERROR] Failed to push {filename} to GitHub: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Zero483 | USFDA Pharma News Processor")
    print("=" * 60)

    client = build_gemini_client()
    db     = load_database()

    sources = [
        fetch_drug_recalls,
        fetch_google_news_recalls,
        fetch_drug_shortages,
        fetch_google_news_shortages,
        fetch_drug_approvals,
        fetch_adverse_events_summary,
        fetch_google_news_adverse_events,
        fetch_google_news_warning_letters,
        fetch_google_news_guidances,
    ]

    total_new = 0
    for fetch_fn in sources:
        try:
            raw_items = fetch_fn()
            if raw_items:
                added = merge_items(db, raw_items, client)
                total_new += added
                print(f"  [OK] Added {added} new items from {fetch_fn.__name__}.")
        except Exception as exc:
            print(f"  [ERROR] {fetch_fn.__name__} failed: {exc}")

    save_database(db)
    generate_zoho_widget(db)
    generate_citizen_widget(db)
    rss_content = generate_rss_feed(db)
    print("   -> Attempting automatic upload to GitHub Pages for RSS feed...")
    upload_file_to_github(rss_content, "feed.xml")
    
    print(f"\n[DONE] {total_new} new items added.")


if __name__ == "__main__":
    main()
