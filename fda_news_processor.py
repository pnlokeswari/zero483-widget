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

# â”€â”€ Dependency check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
BASE_DIR       = Path(__file__).parent
DATABASE_FILE  = BASE_DIR / "news_database.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FDA_API_KEY    = os.getenv("FDA_API_KEY", "")
MAX_ITEMS_DB   = 50          # Max total items to keep in the database
FETCH_LIMIT    = 10          # Items to fetch per source per run
DAYS_LOOKBACK  = 2           # Only include items from past N days (48 hours)
MAX_NEW_ITEMS_PER_RUN = 3    # Limit newly published articles per run to avoid rate limits

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


# â”€â”€ Utility helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ Gemini AI analysis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


def ai_analyze(client, title: str, raw_text: str, length_mode: str = "long", retries: int = 3) -> dict:
    """
    Ask Gemini to produce an engaging, SEO-optimized blog post in JSON format:
      - seo_title
      - seo_description
      - summary (HTML formatted)
      - industry_context (HTML formatted)
      - compliance_impact (HTML formatted)
      - key_actions (HTML formatted)
    """
    if client is None:
        truncated = raw_text[:600].strip()
        return {
            "primary_company_name": None,
            "seo_title": title,
            "seo_description": "USFDA Pharma Update. Review the latest developments, market implications, and key takeaways.",
            "summary": f"<p>{truncated if truncated else title}</p>",
            "industry_context": "",
            "compliance_impact": "",
            "key_actions": "",
        }

    if length_mode == "long":
        word_count_guideline = """
Write a highly-detailed, comprehensive, SEO-optimized blog post (approx 800-1000 words total) deeply analysing this regulatory update.
Follow these specific section guidelines:
- "summary": A comprehensive 3-4 paragraph explanation of what happened, written in a clear, detailed, storytelling style. (Aim for 350-400 words)
- "industry_context": A detailed 2-3 paragraph section explaining the background, product history, therapeutic relevance, and wider implications. (Aim for 300 words)
- "compliance_impact": 4-5 detailed bullet points describing the key implications for stakeholders, patients, consumers, or the market. (Aim for 150-200 words)
- "key_actions": 3-5 detailed bullet points describing recommended next steps, advice, or takeaways for the readers. (Aim for 100-150 words)
"""
    else:
        word_count_guideline = """
Write a concise, high-impact, SEO-optimized article (approx 250-300 words total) summarizing this regulatory update.
Follow these specific section guidelines:
- "summary": A brief 1-2 paragraph explanation of what happened. (Aim for 100-120 words)
- "industry_context": A concise paragraph explaining the background and immediate context. (Aim for 80 words)
- "compliance_impact": 2-3 clear, short bullet points outlining the key implications. (Aim for 50-60 words)
- "key_actions": 2-3 short bullet points listing practical next steps. (Aim for 30-40 words)
"""

    prompt = f"""You are a professional medical journalist, regulatory affairs analyst, and expert SEO Content Writer.
Your task is to write an engaging, easy-to-understand blog post analysing this USFDA regulatory update.

CRITICAL INSTRUCTIONS:
- Knowledge Enrichment: Use your broad medical and regulatory knowledge base to explain the background of the medicine, the condition it treats, or the history of the issue. Even if the raw text is very brief, flesh out the article with deep context to make it an attractive, highly informative post.
- Tone and Style: Write in an accessible, informative, and engaging narrative style. Do NOT target "QA managers", "GMP auditors", or talk specifically about "Quality Assurance (QA) people". Avoid dry compliance checklists or audit jargon (like CAPA, OOS, inspection readiness, etc.). Write so that any reader (general public, patient, investor, or industry professional) can fully understand the situation and why it matters.
- Structure: Your response must be a single raw JSON object matching the schema below. Do NOT wrap it in markdown code block fences (like ```json), just return raw JSON text.

WORD COUNT & SECTION GUIDELINES:
{word_count_guideline}

JSON SCHEMA:
{{
  "primary_company_name": "The exact name of the company/manufacturer involved (e.g., 'Sun Pharmaceutical Industries Ltd.'). If this is a general guidance or the primary company is not explicitly the subject, output null. Do not guess.",
  "seo_title": "A highly engaging, keyword-rich headline (e.g., 'FDA Recall: [Product Name]')",
  "seo_description": "A 150-160 character meta description optimized for Google search results.",
  "summary": "The summary section formatted with HTML <p> tags according to the guidelines.",
  "industry_context": "The industry context section formatted with HTML <p> tags according to the guidelines.",
  "compliance_impact": "The implications section formatted as an HTML <ul> list with <li> elements.",
  "key_actions": "The recommended actions section formatted as an HTML <ul> list with <li> elements."
}}

TITLE: {title}
---
{raw_text[:1800]}
"""

    if getattr(client, "quota_exhausted", False):
        return {
            "primary_company_name": None,
            "seo_title": title,
            "seo_description": "USFDA Pharma Update. Review the latest developments, market implications, and key takeaways.",
            "summary": f"<p>{raw_text[:400].strip()}</p>",
            "industry_context": "",
            "compliance_impact": "",
            "key_actions": "",
        }

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            text = response.text.strip()
            # Strip any markdown code fences if model added them
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
            return json.loads(text)

        except Exception as exc:
            exc_str = str(exc)
            is_rate_limit = "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str
            is_unavailable = "503" in exc_str or "UNAVAILABLE" in exc_str or "high demand" in exc_str.lower()

            if is_rate_limit or is_unavailable:
                wait_secs = 60
                if is_rate_limit:
                    delay_match = re.search(r"retryDelay.*?(\d+)s", exc_str)
                    wait_secs = int(delay_match.group(1)) + 5 if delay_match else 65
                    err_type = "RATE LIMIT"
                else:
                    err_type = "TEMPORARY 503"

                if attempt < retries - 1:
                    print(f"  [{err_type}] Gemini issue. Waiting {wait_secs}s before retry {attempt+2}/{retries}...")
                    time.sleep(wait_secs)
                    continue
                else:
                    if is_rate_limit:
                        print(f"  [RATE LIMIT] Gemini quota exhausted for this item. Skipping AI for this specific item but keeping it active for others.")
                        # Removed client.quota_exhausted = True so it continues for next items
                    else:
                        print(f"  [TEMPORARY 503] Exhausted retries due to service unavailability.")
            else:
                print(f"  [AI ERROR] {exc_str[:200]}")

            # Fallback on final attempt or non-rate-limit error
            return {
                "summary": f"<p>{raw_text[:400].strip()}</p>",
                "compliance_impact": "<ul><li>Review the details of this regulatory action to assess potential public or market implications.</li></ul>",
                "key_actions": "<ul><li>Discuss this update with relevant team members or advisors to evaluate next steps.</li></ul>",
            }

    return {
        "summary": f"<p>{raw_text[:400].strip()}</p>",
        "compliance_impact": "<ul><li>Review the details of this regulatory action to assess potential public or market implications.</li></ul>",
        "key_actions": "<ul><li>Discuss this update with relevant team members or advisors to evaluate next steps.</li></ul>",
    }



# â”€â”€ Data sources â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def fetch_drug_recalls(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch recent drug enforcement/recall reports from openFDA."""
    print("\n[SOURCE] openFDA Drug Recalls / Enforcement...")
    # No date filter - openFDA has indexing lag of days/weeks so date filters cause 404.
    # Duplicate detection in merge_items() prevents re-adding already-seen items.
    url = (
        f"{OPENFDA_BASE}/drug/enforcement.json"
        f"?search=status:Ongoing"
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
    # No date filter - just fetch most recent current shortages.
    # Duplicate detection in merge_items() prevents re-adding already-seen items.
    url = (
        f"{OPENFDA_BASE}/drug/shortages.json"
        f"?search=status:Current"
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
            "_url": "https://www.accessdata.fda.gov/scripts/drugshortages/default.cfm",
        })
    print(f"  Fetched {len(items)} shortage items.")
    return items


def fetch_drug_approvals(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch recent NDA/ANDA approvals from openFDA drugsfda endpoint."""
    print("\n[SOURCE] openFDA Drug Approvals (drugsfda)...")
    # No date filter - openFDA indexing lag causes 404 on recent date ranges.
    # We filter in-memory for ORIG submissions and rely on duplicate detection.
    url = (
        f"{OPENFDA_BASE}/drug/drugsfda.json"
        f"?search=submissions.submission_status%3AAP"
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
        
        # Filter for ORIGINAL approved submissions only (no date filter - rely on duplicate detection)
        valid_orig_submissions = [
            s for s in submissions
            if s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP"
        ]
                    
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
    # No date filter - FAERS has multi-week indexing lag so date filters cause 404.
    # Fetch most recent serious adverse events; duplicate detection handles dedup.
    url = (
        f"{OPENFDA_BASE}/drug/event.json"
        f"?search=serious:1"
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
            "_url": "https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard",
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


def fetch_google_news_approvals(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch FDA/USFDA/CDSCO Drug Approvals from Google News RSS to bypass openFDA latency."""
    print("\n[SOURCE] Google News RSS (Drug Approvals)...")
    url = 'https://news.google.com/rss/search?q=(%22FDA+approval%22+OR+%22USFDA+approval%22+OR+%22CDSCO+approval%22+OR+%22drug+approval%22)+(drug+OR+pharma+OR+tablets+OR+injection)&hl=en-US&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
    except Exception as e:
        print(f"  Failed to fetch RSS: {e}")
        return []

    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.find('title').text or "Drug Approval News"
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
            "_category": "Drug Approval",
            "_severity": "Low",
            "_raw":      raw_text,
            "_url":      link,
        })
    print(f"  Fetched {len(items)} drug approval news items.")
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


def fetch_google_news_guidances(limit: int = 30) -> list[dict]:
    """Fetch FDA Draft Guidance and Guidelines news from Google News RSS."""
    print("\n[SOURCE] Google News RSS (FDA Guidelines)...")
    url = 'https://news.google.com/rss/search?q=(%22FDA%22+OR+%22ICH%22)+AND+(%22Guidance%22+OR+%22Guideline%22+OR+%22Guidelines%22)+AND+(drug+OR+pharma+OR+medicine+OR+biological)&hl=en-US&gl=US&ceid=US:en'
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


def fetch_health_canada_alerts(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch Health Canada Recalls & Alerts."""
    print("\n[SOURCE] Health Canada RSS...")
    feeds = [
        "https://recalls-rappels.canada.ca/en/feed/health-products-alerts-recalls",
        "https://recalls-rappels.canada.ca/en/feed/medical-devices-alerts-recalls"
    ]
    items = []
    for url in feeds:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req, timeout=10).read()
            root = ET.fromstring(html)
        except Exception as e:
            print(f"  Failed to fetch {url}: {e}")
            continue

        for item in root.findall('.//item')[:limit]:
            title = item.find('title').text or "Health Canada Alert"
            link = item.find('link').text or ""
            pubDate = item.find('pubDate').text or ""
            
            try:
                # Remove timezone offset (like -0400 or EST) for simple parsing
                clean_pub_date = re.sub(r'\s[+-]\d{4}$', '', pubDate).strip()
                clean_pub_date = re.sub(r'\s[A-Z]{3,4}$', '', clean_pub_date).strip()
                dt = datetime.strptime(clean_pub_date, "%a, %d %b %Y %H:%M:%S")
                if (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days > DAYS_LOOKBACK:
                    continue
                date_s = dt.strftime("%Y-%m-%d")
            except Exception as pe:
                date_s = today_iso()

            raw_text = f"Title: {title}\nSource: Health Canada\nDate: {pubDate}"
            
            items.append({
                "_id":       make_id(title),
                "_title":    title[:120],
                "_date":     date_s,
                "_category": "Recall",
                "_severity": "High",
                "_raw":      raw_text,
                "_url":      link,
            })
    print(f"  Fetched {len(items)} Health Canada items.")
    return items


def fetch_ema_alerts(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch EMA Alerts via Google News RSS search."""
    print("\n[SOURCE] Google News RSS (EMA)...")
    url = 'https://news.google.com/rss/search?q=%22European+Medicines+Agency%22+OR+%22EMA%22+(drug+OR+pharma+OR+approval+OR+shortage)&hl=en-US&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
    except Exception as e:
        print(f"  Failed to fetch EMA RSS: {e}")
        return []

    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.find('title').text or "EMA Update"
        link = item.find('link').text or ""
        pubDate = item.find('pubDate').text or ""
        
        try:
            dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
            if (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days > DAYS_LOOKBACK:
                continue
            date_s = dt.strftime("%Y-%m-%d")
        except:
            date_s = today_iso()

        raw_text = f"Title: {title}\nSource: European Medicines Agency\nDate: {pubDate}"
        
        category = "Guidance"
        severity = "Low"
        title_lower = title.lower()
        if "shortage" in title_lower or "deficit" in title_lower:
            category = "Drug Shortage"
            severity = "Medium"
        elif "recall" in title_lower or "safety" in title_lower or "warning" in title_lower:
            category = "Recall"
            severity = "High"
        elif "approval" in title_lower or "approve" in title_lower or "authorise" in title_lower:
            category = "Drug Approval"
            severity = "Low"

        items.append({
            "_id":       make_id(title),
            "_title":    title[:120],
            "_date":     date_s,
            "_category": category,
            "_severity": severity,
            "_raw":      raw_text,
            "_url":      link,
        })
    print(f"  Fetched {len(items)} EMA items.")
    return items


def fetch_who_alerts(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch WHO Medical Product Alerts via Google News RSS search."""
    print("\n[SOURCE] Google News RSS (WHO Medical Alerts)...")
    url = 'https://news.google.com/rss/search?q=%22World+Health+Organization%22+OR+%22WHO%22+%22medical+product+alert%22&hl=en-US&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
    except Exception as e:
        print(f"  Failed to fetch WHO RSS: {e}")
        return []

    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.find('title').text or "WHO Medical Product Alert"
        link = item.find('link').text or ""
        pubDate = item.find('pubDate').text or ""
        
        try:
            dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
            if (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days > DAYS_LOOKBACK:
                continue
            date_s = dt.strftime("%Y-%m-%d")
        except:
            date_s = today_iso()

        raw_text = f"Title: {title}\nSource: World Health Organization\nDate: {pubDate}"
        
        items.append({
            "_id":       make_id(title),
            "_title":    title[:120],
            "_date":     date_s,
            "_category": "Warning Letter",
            "_severity": "High",
            "_raw":      raw_text,
            "_url":      link,
        })
    print(f"  Fetched {len(items)} WHO items.")
    return items


def fetch_cdsco_alerts(limit: int = FETCH_LIMIT) -> list[dict]:
    """Fetch CDSCO Alerts via Google News RSS search."""
    print("\n[SOURCE] Google News RSS (CDSCO)...")
    url = 'https://news.google.com/rss/search?q=%22CDSCO%22+OR+%22Central+Drugs+Standard+Control+Organisation%22+(alert+OR+recall+OR+drug+OR+pharma)&hl=en-US&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(html)
    except Exception as e:
        print(f"  Failed to fetch CDSCO RSS: {e}")
        return []

    items = []
    for item in root.findall('.//item')[:limit]:
        title = item.find('title').text or "CDSCO Alert"
        link = item.find('link').text or ""
        pubDate = item.find('pubDate').text or ""
        
        try:
            dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z")
            if (datetime.now(timezone.utc).replace(tzinfo=None) - dt).days > DAYS_LOOKBACK:
                continue
            date_s = dt.strftime("%Y-%m-%d")
        except:
            date_s = today_iso()

        raw_text = f"Title: {title}\nSource: CDSCO India\nDate: {pubDate}"
        
        category = "Warning Letter"
        severity = "High"
        title_lower = title.lower()
        if "recall" in title_lower or "spurious" in title_lower or "nsq" in title_lower or "substandard" in title_lower:
            category = "Recall"
            severity = "High"
        elif "approve" in title_lower or "clear" in title_lower or "authoris" in title_lower or "permission" in title_lower:
            category = "Drug Approval"
            severity = "Low"

        items.append({
            "_id":       make_id(title),
            "_title":    title[:120],
            "_date":     date_s,
            "_category": category,
            "_severity": severity,
            "_raw":      raw_text,
            "_url":      link,
        })
    print(f"  Fetched {len(items)} CDSCO items.")
    return items


# â”€â”€ Database I/O â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


def ai_verify_pharma_relevance(client, title: str, raw_text: str) -> bool:
    """Deprecated AI relevance check to save API quota."""
    return True

def is_pharma_relevant(title: str, raw_text: str, client=None) -> bool:
    """Filter out non-pharmaceutical/non-medical device news using fast keyword rules to save API quota."""
    text_lower = (title + " " + raw_text).lower()
    
    # Exclude obvious non-human-pharma items
    exclusion_keywords = [
        "pet food", "dog food", "cat food", "veterinary", "animal drug",
        "ice cream", "cheese", "salad", "vegetable", "fruit", "onion",
        "salmonella", "listeria monocytogenes", "e. coli"
    ]
    
    # Keep if it contains specific pharma/device words even if it hits exclusions
    inclusion_keywords = ["pharma", "drug", "device", "biologic", "vaccine", "therapy", "clinical"]
    
    if any(ex in text_lower for ex in exclusion_keywords):
        if not any(inc in text_lower for inc in inclusion_keywords):
            return False
            
    return True


def is_duplicate_title(new_title: str, existing_titles: list, threshold: float = 0.65) -> bool:
    """Return True if new_title is too similar to any title in existing_titles."""
    new_title_lower = new_title.lower()
    for ext_title in existing_titles:
        if difflib.SequenceMatcher(None, new_title_lower, ext_title.lower()).ratio() > threshold:
            return True
    return False


def count_long_forms_for_date(db: dict, date_str: str) -> int:
    """Count how many long-form articles exist in the database for the given date."""
    count = 0
    for item in db.get("items", []):
        if item.get("date") == date_str and item.get("is_long_form", False):
            count += 1
    return count


def merge_items(db: dict, new_items: list[dict], client) -> int:
    """
    Add new items to the database, skipping duplicates and non-pharma content.
    Runs AI analysis on each new item before inserting.
    Returns count of newly added items.
    """
    existing_ids = {item["id"] for item in db["items"]}
    existing_titles = [item["title"] for item in db["items"]]
    added = 0

    for raw in new_items:
        if added >= MAX_NEW_ITEMS_PER_RUN:
            print(f"\n  [LIMIT] Reached limit of {MAX_NEW_ITEMS_PER_RUN} new items per run. Skipping remaining items.")
            break

        if raw["_id"] in existing_ids:
            continue

        if not is_pharma_relevant(raw["_title"], raw["_raw"], client=client):
            print(f"  [SKIP] Not relevant to Pharma/Medical Devices: {raw['_title'][:60]}...")
            continue

        if is_duplicate_title(raw["_title"], existing_titles):
            print(f"\n  [SKIP] Duplicate topic detected: {raw['_title'][:60]}...")
            continue

        # Count how many long forms exist for this date in database (including this run)
        current_long_count = count_long_forms_for_date(db, raw["_date"])
        length_mode = "long" if current_long_count < 3 else "short"

        print(f"\n  >> Analysing: {raw['_title'][:70]} (Mode: {length_mode.upper()})...")
        analysis = ai_analyze(client, raw["_title"], raw["_raw"], length_mode=length_mode)
        # Stay within Gemini free tier: 15 req/min = 1 req per 4s minimum
        # Use 5s to have comfortable headroom
        time.sleep(5.0)

        # Detect if we successfully generated a long-form article
        # Truncated fallback has short summary and no is_long_form key
        summary_text = analysis.get("summary", "")
        clean_text = re.sub(r'<[^>]*>', '', summary_text)
        word_count = len(clean_text.split())
        
        is_long_form = False
        if length_mode == "long" and word_count > 150:
            is_long_form = True

        title_raw = raw["_title"]
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', title_raw.lower()).strip('-')

        record = {
            "id":                   raw["_id"],
            "title":                title_raw,
            "slug":                 slug,
            "date":                 raw["_date"],
            "category":             raw["_category"],
            "severity":             raw["_severity"],
            "summary":              analysis.get("summary", ""),
            "compliance_impact":    analysis.get("compliance_impact", ""),
            "key_actions":          analysis.get("key_actions", ""),
            "industry_context":     analysis.get("industry_context", ""),
            "seo_title":            analysis.get("seo_title", title_raw),
            "seo_description":      analysis.get("seo_description", ""),
            "primary_company_name":  analysis.get("primary_company_name", None),
            "source_url":           raw["_url"],
            "fetched_at":           datetime.now(timezone.utc).isoformat(),
            "is_long_form":         is_long_form,
        }
        db["items"].insert(0, record)
        existing_ids.add(raw["_id"])
        existing_titles.append(raw["_title"])
        added += 1

    # Sort all items by date descending to show today's/freshest news first
    db["items"].sort(key=lambda x: (x.get("date", ""), x.get("fetched_at", "")), reverse=True)
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
    
    # Also trigger standard Google Sitemap XML generation
    generate_sitemap(db)
    
    return rss


def generate_sitemap(db: dict) -> None:
    """Generate a valid Google Sitemap XML listing the main widget and all alert pages."""
    url_nodes = []
    
    # 1. Add Main Tracker page URL
    url_nodes.append(
        "  <url>\n"
        "    <loc>https://alerts.zero483.com/index.html</loc>\n"
        "    <changefreq>hourly</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>"
    )
    
    
    # 2. Add individual alert page URLs
    unique_companies = set()
    for item in db.get("items", []):
        comp = item.get("primary_company_name")
        if comp:
            unique_companies.add(comp.title())
            
        title_raw = item.get("title", "")
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', title_raw.lower()).strip('-')
        if not slug:
            continue
        url_nodes.append(
            f"  <url>\\n"
            f"    <loc>https://alerts.zero483.com/alerts/{slug}.html</loc>\\n"
            f"    <changefreq>monthly</changefreq>\\n"
            f"    <priority>0.8</priority>\\n"
            f"  </url>"
        )
        
    # 3. Add company pages
    if unique_companies:
        url_nodes.append(
            f"  <url>\\n"
            f"    <loc>https://alerts.zero483.com/companies.html</loc>\\n"
            f"    <changefreq>daily</changefreq>\\n"
            f"    <priority>0.9</priority>\\n"
            f"  </url>"
        )
        for comp in unique_companies:
            comp_slug = re.sub(r'[^a-zA-Z0-9]+', '-', comp.lower()).strip('-')
            url_nodes.append(
                f"  <url>\\n"
                f"    <loc>https://alerts.zero483.com/company/{comp_slug}.html</loc>\\n"
                f"    <changefreq>weekly</changefreq>\\n"
                f"    <priority>0.8</priority>\\n"
                f"  </url>"
            )

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{chr(10).join(url_nodes)}\n"
        '</urlset>\n'
    )
    
    sitemap_path = BASE_DIR / "sitemap.xml"
    with sitemap_path.open("w", encoding="utf-8") as f:
        f.write(sitemap)
    print(f"[SITEMAP READY] Generated {sitemap_path.name}")


def generate_seo_pages(db: dict) -> None:
    """Generate search-engine-friendly static HTML pages for each news item in the alerts folder."""
    import html
    alerts_dir = BASE_DIR / "alerts"
    alerts_dir.mkdir(exist_ok=True)
    
    # We clean old alerts that are no longer in the database to keep the repository clean
    existing_slugs = set()

    for item in db.get("items", []):
        title_raw = item.get("title", "")
        # Create a clean url slug (e.g., "Drug Recall: Gas-X Extra" -> "drug-recall-gas-x-extra")
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', title_raw.lower()).strip('-')
        if not slug:
            continue
            
        existing_slugs.add(slug + ".html")
        
        # Extract new SEO fields or fallback
        seo_title = html.escape(item.get("seo_title", title_raw))
        seo_desc = html.escape(item.get("seo_description", f"USFDA Pharma Alert - {title_raw}. Analysis and compliance impact."))
        
        # Safely extract AI fields (handling both strings and lists from older database schemas)
        summary_val = item.get("summary")
        if not summary_val:
            ai_summary = f"<p>{html.escape(title_raw)}</p>"
        else:
            if isinstance(summary_val, list):
                ai_summary = "".join(f"<p>{html.escape(x)}</p>" for x in summary_val)
            else:
                ai_summary = str(summary_val)

        context_val = item.get("industry_context")
        if not context_val:
            ai_context = ""
        else:
            if isinstance(context_val, list):
                ai_context = "".join(f"<p>{html.escape(x)}</p>" for x in context_val)
            else:
                ai_context = str(context_val)

        impact_val = item.get("compliance_impact")
        if not impact_val:
            ai_impact = ""
        else:
            if isinstance(impact_val, list):
                ai_impact = "<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in impact_val) + "</ul>"
            else:
                ai_impact = str(impact_val)

        actions_val = item.get("key_actions")
        if not actions_val:
            ai_actions = ""
        else:
            if isinstance(actions_val, list):
                ai_actions = "<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in actions_val) + "</ul>"
            else:
                ai_actions = str(actions_val)
        
        category = html.escape(item.get("category", ""))
        severity = html.escape(item.get("severity", ""))
        date_str = html.escape(item.get("date", ""))
        
        # Determine severity class color
        sev_color = "#dc2626" if severity == "High" else ("#d97706" if severity == "Medium" else "#16a34a")
        
        source_url = html.escape(item.get("source_url", ""))
        canonical_url = f"https://alerts.zero483.com/alerts/{slug}.html"
        
        # JSON-LD Schema
        schema_json = {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": seo_title,
            "description": seo_desc,
            "datePublished": date_str,
            "author": {
                "@type": "Organization",
                "name": "Zero483 Automated Monitoring"
            },
            "publisher": {
                "@type": "Organization",
                "name": "Zero483",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://alerts.zero483.com/logo.png"
                }
            },
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": canonical_url
            }
        }
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{seo_title} | USFDA Alert Zero483</title>
  <meta name="description" content="{seo_desc}" />
  <link rel="canonical" href="{canonical_url}" />
  <script type="application/ld+json">
{json.dumps(schema_json, indent=2)}
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Merriweather:wght@700;900&display=swap" rel="stylesheet" />
  <style>
    body {{
      font-family: 'Inter', sans-serif;
      line-height: 1.8;
      color: #1e293b;
      background: #f8fafc;
      padding: 40px 20px;
      margin: 0;
      font-size: 1.05rem;
    }}
    .container {{
      max-width: 760px;
      margin: 0 auto;
      background: #ffffff;
      padding: 50px 60px;
      border-radius: 12px;
      border: 1px solid #e2e8f0;
      box-shadow: 0 10px 25px rgba(0,0,0,0.03);
    }}
    a {{
      color: #2563eb;
      text-decoration: none;
      font-weight: 600;
      transition: color 0.2s ease;
    }}
    a:hover {{
      color: #1d4ed8;
      text-decoration: underline;
    }}
    .breadcrumb {{
      font-size: 0.85rem;
      color: #64748b;
      margin-bottom: 30px;
      letter-spacing: 0.5px;
    }}
    .breadcrumb a {{
      color: #64748b;
    }}
    .category-badge {{
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      padding: 6px 12px;
      border-radius: 20px;
      margin-bottom: 20px;
    }}
    .badge-Recall {{ background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }}
    .badge-DrugShortage {{ background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }}
    .badge-DrugApproval {{ background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }}
    .badge-AdverseEvent {{ background: #fdf4ff; color: #c026d3; border: 1px solid #f5d0fe; }}
    .badge-WarningLetter, .badge-Form483 {{ background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }}
    .badge-Guidance {{ background: #f0f9ff; color: #0284c7; border: 1px solid #bae6fd; }}
    
    h1 {{
      font-family: 'Merriweather', serif;
      font-size: 2.25rem;
      font-weight: 900;
      line-height: 1.3;
      margin-top: 0;
      margin-bottom: 24px;
      color: #0f172a;
    }}
    .metadata {{
      font-size: 0.9rem;
      color: #64748b;
      margin-bottom: 40px;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 16px;
      display: flex;
      gap: 16px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .section {{
      margin-bottom: 35px;
    }}
    h2 {{
      font-family: 'Merriweather', serif;
      font-size: 1.4rem;
      font-weight: 700;
      margin-top: 40px;
      margin-bottom: 16px;
      color: #0f172a;
      position: relative;
    }}
    h2::after {{
      content: '';
      display: block;
      width: 40px;
      height: 3px;
      background: #2563eb;
      margin-top: 8px;
      border-radius: 2px;
    }}
    p {{
      margin-bottom: 1.2em;
    }}
    .section:first-of-type p:first-of-type::first-letter {{
      float: left;
      font-size: 3.8rem;
      line-height: 0.8;
      font-family: 'Merriweather', serif;
      font-weight: 900;
      padding-right: 8px;
      padding-top: 4px;
      color: #2563eb;
    }}
    .action-box {{
      background: #f8fafc;
      border-left: 4px solid #3b82f6;
      padding: 24px;
      border-radius: 0 8px 8px 0;
      margin-top: 40px;
      box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
    }}
    .action-box strong {{
      font-family: 'Merriweather', serif;
      font-size: 1.1rem;
      color: #0f172a;
      display: block;
      margin-bottom: 12px;
    }}
    .share-container {
      display: flex;
      gap: 12px;
      margin: 30px 0;
      align-items: center;
      flex-wrap: wrap;
    }
    .share-btn {
      padding: 8px 16px;
      border-radius: 20px;
      font-size: 0.9rem;
      font-weight: 600;
      color: #fff;
      text-decoration: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .share-btn.linkedin { background: #0a66c2; }
    .share-btn.linkedin:hover { background: #004182; color: #fff; text-decoration: none; }
    .share-btn.twitter { background: #000000; }
    .share-btn.twitter:hover { background: #333333; color: #fff; text-decoration: none; }
    .share-btn.email { background: #64748b; }
    .share-btn.email:hover { background: #475569; color: #fff; text-decoration: none; }
    .subscribe-box {
      background: #f0f9ff;
      border: 1px solid #bae6fd;
      padding: 30px;
      border-radius: 12px;
      text-align: center;
      margin-top: 50px;
    }
    .subscribe-box h3 {
      font-family: 'Merriweather', serif;
      margin-top: 0;
      color: #0369a1;
      margin-bottom: 12px;
    }
    .subscribe-input {
      padding: 12px 16px;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      width: 100%;
      max-width: 300px;
      font-size: 1rem;
      margin-bottom: 10px;
    }
    .subscribe-btn {
      padding: 12px 24px;
      background: #0284c7;
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }
    .subscribe-btn:hover {
      background: #0369a1;
    }
    .footer {{
      margin-top: 50px;
      border-top: 1px solid #e2e8f0;
      padding-top: 24px;
      text-align: center;
      font-size: 0.9rem;
      color: #64748b;
    }}
    ul {{
      padding-left: 24px;
      margin-bottom: 1.5em;
    }}
    li {{
      margin-bottom: 10px;
      padding-left: 4px;
    }}
    li::marker {{
      color: #3b82f6;
    }}
    @media (max-width: 600px) {{
      .container {{ padding: 30px 20px; }}
      h1 {{ font-size: 1.75rem; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <nav class="breadcrumb">
      <a href="https://www.zero483.com/USFDA-news">Home</a> &gt; 
      <a href="https://alerts.zero483.com/index.html">Alerts</a> &gt; 
      <span>{seo_title}</span>
    </nav>
    <br/>
    <article>
      <header>
        <span class="category-badge badge-{category.replace(' ', '')}">{category}</span>
        <h1>{seo_title}</h1>
        
        <div class="metadata">
          <strong>Published:</strong> <time datetime="{date_str}">{date_str}</time> &nbsp;|&nbsp; 
          <strong>Severity:</strong> <span style="color: {sev_color}; font-weight: bold;">{severity}</span> &nbsp;|&nbsp;
          <strong>Source:</strong> <a href="{source_url}" target="_blank" rel="noopener noreferrer">Original Publication</a>
        </div>
      </header>
      
      <main>
        <div class="section">
          <h2>Article Analysis & Summary</h2>
          {ai_summary}
        </div>
        """
        if ai_context and ai_context.strip() != "":
            html_content += f"""
        <div class="section">
          <h2>Context & Background</h2>
          {ai_context}
        </div>
        """
        if ai_impact and ai_impact.strip() != "":
            html_content += f"""
        <div class="section">
          <h2>Key Implications & Public Impact</h2>
          {ai_impact}
        </div>
        """
        if ai_actions and ai_actions.strip() != "":
            html_content += f"""
        <div class="action-box">
          <strong>Key Takeaways & Recommended Actions:</strong>
          {ai_actions}
        </div>
        """
        html_content += f"""
      </main>
      
      <div class="share-container">
        <span style="font-weight:600; color:#64748b; font-size:0.95rem;">Share this alert:</span>
        <a class="share-btn linkedin" href="https://www.linkedin.com/sharing/share-offsite/?url={{canonical_url}}" target="_blank">LinkedIn</a>
        <a class="share-btn twitter" href="https://twitter.com/intent/tweet?url={{canonical_url}}&text={{seo_title}}" target="_blank">X (Twitter)</a>
        <a class="share-btn email" href="mailto:?subject={{seo_title}}&body=Read this FDA alert: {{canonical_url}}">Email</a>
      </div>

      <div class="subscribe-box">
        <h3>Stay Ahead of FDA Compliance</h3>
        <p style="color:#334155; font-size:0.95rem; margin-bottom:20px;">Get critical regulatory updates, warning letters, and drug shortages delivered straight to your inbox.</p>
        <div style="display:flex; justify-content:center; gap:10px; flex-wrap:wrap;">
          <input type="email" id="seo-sub-email" class="subscribe-input" placeholder="Enter your email address">
          <button onclick="seoSubscribe()" class="subscribe-btn">Subscribe Free</button>
        </div>
        <p id="seo-sub-msg" style="color:#16a34a; font-weight:600; display:none; margin-top:15px;">Subscribed successfully! Welcome aboard.</p>
      </div>

      <script>
      function seoSubscribe() {{
          var email = document.getElementById('seo-sub-email').value;
          if(!email) return;
          var payload = new URLSearchParams({{ subscriber_email: email, source: 'Zero483 SEO Article', timestamp: new Date().toLocaleString() }});
          fetch('https://hook.eu1.make.com/6gshw5et3mftrcl1kax5wxb250ysg4g9', {{ 
            method: 'POST', 
            headers: {{'Content-Type': 'application/x-www-form-urlencoded'}}, 
            body: payload.toString(), 
            mode: 'no-cors' 
          }}).then(() => {{
            document.getElementById('seo-sub-msg').style.display = 'block';
            document.getElementById('seo-sub-email').value = '';
          }});
      }}
      </script>

    </article>
    
    <footer class="footer">
      <p>Brought to you by <a href="https://www.zero483.com">Zero483.com</a>. Automated USFDA Compliance Monitoring.</p>
    </footer>
  </div>
</body>
</html>
"""
        
        file_path = alerts_dir / (slug + ".html")
        with file_path.open("w", encoding="utf-8") as f:
            f.write(html_content)
            
    # Remove old alerts not present in database
    for f in alerts_dir.glob("*.html"):
        if f.name not in existing_slugs:
            try:
                f.unlink()
            except OSError:
                pass
                
    print(f"\n[SEO READY] Generated {len(existing_slugs)} static alert pages inside /alerts folder.")



def generate_company_pages(db: dict) -> None:
    """Generate dynamic directory and profile pages for specific pharmaceutical companies."""
    import html
    from collections import defaultdict
    
    company_dir = BASE_DIR / "company"
    company_dir.mkdir(exist_ok=True)
    
    # Group items by company
    companies = defaultdict(list)
    for item in db.get("items", []):
        comp = item.get("primary_company_name")
        if comp:
            companies[comp.title()].append(item)
            
    if not companies:
        return
        
    css_style = """
    body { font-family: 'Inter', sans-serif; line-height: 1.6; color: #0f172a; background: #f8f9fa; padding: 40px 20px; margin: 0; }
    .container { max-width: 800px; margin: 0 auto; background: #ffffff; padding: 40px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    a { color: #2563eb; text-decoration: none; font-weight: 600; }
    a:hover { text-decoration: underline; }
    .breadcrumb { font-size: 0.85rem; color: #64748b; margin-bottom: 24px; }
    h1 { font-family: 'Merriweather', serif; font-size: 2.2rem; font-weight: 900; line-height: 1.3; margin-top: 0; margin-bottom: 10px; }
    .company-meta { font-size: 1rem; color: #475569; margin-bottom: 30px; border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; }
    .alert-card { background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #dc2626; padding: 20px; border-radius: 4px; margin-bottom: 20px; transition: box-shadow 0.2s; }
    .alert-card:hover { box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left-color: #b91c1c; }
    .alert-card.recall { border-left-color: #ea580c; }
    .alert-card.warning-letter { border-left-color: #dc2626; }
    .alert-date { font-size: 0.85rem; color: #64748b; font-weight: 600; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
    .alert-title { font-family: 'Merriweather', serif; font-size: 1.2rem; font-weight: 700; margin-top: 0; margin-bottom: 10px; }
    .alert-title a { color: #0f172a; }
    .alert-summary { font-size: 0.95rem; color: #475569; margin: 0; }
    .footer { margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 20px; text-align: center; font-size: 0.9rem; color: #64748b; }
    
    .directory-list { list-style: none; padding: 0; }
    .directory-list li { margin-bottom: 10px; padding: 15px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }
    .badge { background: #ef4444; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: bold; }
    """
    
    # Generate Main Directory Index
    sorted_comps = sorted(companies.items(), key=lambda x: x[0])
    dir_items = ""
    for comp, items in sorted_comps:
        comp_slug = re.sub(r'[^a-zA-Z0-9]+', '-', comp.lower()).strip('-')
        dir_items += f'<li><a href="company/{comp_slug}.html">{comp}</a> <span class="badge">{len(items)} Alerts</span></li>\n'
        
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pharmaceutical Compliance Directory | Zero483</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Merriweather:wght@700;900&display=swap" rel="stylesheet">
  <style>{css_style}</style>
</head>
<body>
  <div class="container">
    {f'<div class="z483-featured-badge" style="display: inline-flex; align-items: center; gap: 6px; background: linear-gradient(135deg, #FFD700 0%, #F59E0B 100%); color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.15); padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 0.8rem; letter-spacing: 0.5px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(245, 158, 11, 0.25); border: 1px solid rgba(255,255,255,0.4);"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg> Featured Deep Insight</div>' if item.get('is_long_form') else ''}
    <div class="breadcrumb"><a href="/index.html">Zero483 Home</a> &gt; Company Directory</div>
    <header>
      <h1>Pharma Compliance Directory</h1>
      <p class="company-meta">A complete database of historical FDA enforcement reports, warning letters, and drug recalls organized by manufacturer.</p>
    </header>
    <main>
      <ul class="directory-list">
        {dir_items}
      </ul>
    </main>
    <footer class="footer"><p>Automated FDA Compliance tracking by <a href="https://www.zero483.com">Zero483</a>.</p></footer>
  </div>
</body>
</html>"""
    (BASE_DIR / "companies.html").write_text(index_html, encoding="utf-8")
    
    # Generate Widget
    widget_html = f"""<!DOCTYPE html>
<html>
<head>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  body {{ font-family: 'Inter', sans-serif; background: transparent; margin: 0; padding: 10px; }}
  .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
  .title {{ font-size: 1.1rem; font-weight: 700; color: #0f172a; margin: 0; }}
  .updated {{ font-size: 0.8rem; color: #64748b; font-weight: 600; background: #f1f5f9; padding: 4px 8px; border-radius: 4px; }}
  .directory-list {{ list-style: none; padding: 0; margin: 0; }}
  .directory-list li {{ margin-bottom: 8px; padding: 12px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
  a {{ color: #2563eb; text-decoration: none; font-weight: 600; font-size: 0.95rem; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{ background: #fee2e2; color: #ef4444; padding: 3px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; border: 1px solid #fca5a5; }}
</style>
</head>
<body>
  <div class="header">
    <h3 class="title">Company Directory</h3>
    <span class="updated">Last Updated: {datetime.now(timezone.utc).strftime('%b %d, %Y')}</span>
  </div>
  <ul class="directory-list">
    {dir_items}
  </ul>
</body>
</html>"""
    (BASE_DIR / "company_widget.html").write_text(widget_html, encoding="utf-8")
    
    # Generate Individual Company Pages
    existing_slugs = set()
    for comp, items in companies.items():
        comp_slug = re.sub(r'[^a-zA-Z0-9]+', '-', comp.lower()).strip('-')
        existing_slugs.add(comp_slug + ".html")
        
        cards_html = ""
        # Sort items chronologically descending
        items_sorted = sorted(items, key=lambda x: x.get("date", ""), reverse=True)
        
        for item in items_sorted:
            date_str = item.get("date", "")
            title = item.get("seo_title", item.get("title", ""))
            summary = item.get("summary", "")
            
            # extract text from summary paragraphs
            clean_summary = re.sub(r'<[^>]+>', '', summary)[:200] + "..."
            
            cat = item.get("category", "").lower()
            css_class = "recall" if "recall" in cat else "warning-letter"
            
            alert_slug = re.sub(r'[^a-zA-Z0-9]+', '-', item.get("title", "").lower()).strip('-')
            link = f"../alerts/{alert_slug}.html"
            
            cards_html += f"""
      <div class="alert-card {css_class}">
        <div class="alert-date">{date_str} â€¢ {item.get('category', '').upper()}</div>
        <h3 class="alert-title"><a href="{link}" target="_parent">{title}</a></h3>
        <p class="alert-summary">{clean_summary}</p>
      </div>"""
      
        page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{comp} - FDA Compliance Profile | Zero483</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Merriweather:wght@700;900&display=swap" rel="stylesheet">
  <style>{css_style}</style>
</head>
<body>
  <div class="container">
    {f'<div class="z483-featured-badge" style="display: inline-flex; align-items: center; gap: 6px; background: linear-gradient(135deg, #FFD700 0%, #F59E0B 100%); color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.15); padding: 6px 14px; border-radius: 20px; font-weight: 800; font-size: 0.8rem; letter-spacing: 0.5px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(245, 158, 11, 0.25); border: 1px solid rgba(255,255,255,0.4);"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg> Featured Deep Insight</div>' if item.get('is_long_form') else ''}
    <div class="breadcrumb">
      <a href="/index.html">Zero483 Home</a> &gt; <a href="/companies.html">Company Directory</a> &gt; {comp}
    </div>
    <header>
      <h1>{comp}</h1>
      <div class="company-meta">
        <strong>History:</strong> {len(items)} FDA Enforcement Reports/Alerts on Record
      </div>
    </header>
    <main>
      <h2>Historical Compliance Alerts</h2>
      {cards_html}
    </main>
    <footer class="footer">
      <p>Automated FDA Compliance tracking by <a href="https://www.zero483.com">Zero483</a>.</p>
    </footer>
  </div>
</body>
</html>"""
        (company_dir / (comp_slug + ".html")).write_text(page_html, encoding="utf-8")
        
    print(f"\n[SEO READY] Generated Directory for {len(companies)} companies inside /company folder.")



def ping_indexnow(db: dict):
    """Pings the IndexNow API to instantly index new URLs."""
    import urllib.request
    import json
    
    # Get the 10 most recent items to ensure they are indexed
    items = sorted(db.get("items", []), key=lambda x: x.get("date", ""), reverse=True)[:10]
    if not items:
        return
        
    key = "5d3bbf14bf914b8eb7906b0e3b5a479a"
    host = "alerts.zero483.com"
    urlList = []
    
    for item in items:
        title_raw = item.get("title", "")
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', title_raw.lower()).strip('-')
        if slug:
            urlList.append(f"https://{host}/alerts/{slug}.html")
        comp = item.get("primary_company_name")
        if comp:
            comp_slug = re.sub(r'[^a-zA-Z0-9]+', '-', comp.lower()).strip('-')
            urlList.append(f"https://{host}/company/{comp_slug}.html")
    
    # Also ping the homepage
    urlList.append(f"https://{host}/index.html")
    
    payload = {
        "host": host,
        "key": key,
        "keyLocation": f"https://{host}/{key}.txt",
        "urlList": urlList
    }
    
    api_url = "https://api.indexnow.org/indexnow"
    try:
        req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), 
                                     headers={"Content-Type": "application/json", "charset": "utf-8"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=20) as response:
            if response.status in [200, 202]:
                print(f"  [OK] IndexNow Ping successful. Sent {len(urlList)} URLs to search engines in real-time.")
            else:
                print(f"  [WARNING] IndexNow returned status code: {response.status}")
    except Exception as e:
        print(f"  [ERROR] IndexNow Ping failed: {e}")





# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        fetch_google_news_approvals,
        fetch_adverse_events_summary,
        fetch_google_news_adverse_events,
        fetch_google_news_warning_letters,
        fetch_google_news_guidances,
        fetch_health_canada_alerts,
        fetch_ema_alerts,
        fetch_who_alerts,
        fetch_cdsco_alerts,
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
    generate_seo_pages(db)
    generate_company_pages(db)
    
    print("   -> Pinging Search Engines for Real-Time Indexing...")
    ping_indexnow(db)
    

    
    print(f"\n[DONE] {total_new} new items added.")


if __name__ == "__main__":
    main()

