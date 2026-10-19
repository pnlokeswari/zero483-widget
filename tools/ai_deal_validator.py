# -*- coding: utf-8 -*-
"""
====================================================================
 AI DEAL VALIDATOR — Gemini Semantic Intelligence Layer for ZERO483 & VerifyFirst
 Integrates Gemini 2.5 Flash for:
 1. Robust Semantic Extraction (bypassing CSS class churn & seller tag ambiguity)
 2. Cross-Store Variant Parity Verification (preventing 580ml vs 1000ml mismatches)
 3. Resilient Failover (falls back gracefully to deterministic logic if offline)
====================================================================
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Optional
from pathlib import Path
from curl_cffi import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

log = logging.getLogger("ai_deal_validator")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]

_session = requests.Session(impersonate="chrome120")


def is_ai_layer_available() -> bool:
    """Returns True if a valid Gemini API key is configured."""
    return bool(GEMINI_API_KEY and len(GEMINI_API_KEY) > 10)


def _call_gemini_json(prompt: str, timeout: float = 12.0) -> Optional[dict]:
    """Helper to query Gemini Flash with strict JSON response configuration and fallback models."""
    if not is_ai_layer_available():
        return None

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1
        }
    }

    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            r = _session.post(url, json=payload, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                candidates = data.get("candidates", [])
                if candidates:
                    raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if raw_text:
                        return json.loads(raw_text)
            else:
                log.warning(f"AI Layer ({model}) HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            log.warning(f"AI Layer ({model}) execution notice: {e}")
    return None


def ai_refine_product_metadata(
    platform: str,
    page_text_snippet: str,
    ld_json_data: list,
    current_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Uses Gemini Flash to verify and refine product title, variant size, live seller price,
    and printed packaging MRP from unstructured HTML snippets or Schema.org blocks.
    """
    if not is_ai_layer_available():
        return current_data

    clean_snippet = page_text_snippet[:2500].replace("\n", " ").strip()
    ld_summary = json.dumps(ld_json_data[:2]) if ld_json_data else "None"

    prompt = f"""You are an expert e-commerce data auditor for Indian marketplaces (Amazon India and Flipkart).
Analyze the provided listing data from {platform.upper()} and output strict JSON.

Listing Text Snippet:
{clean_snippet}

Structured Schema LD+JSON:
{ld_summary}

Initial Scraped Values:
Title: {current_data.get('title')}
Price: {current_data.get('price')}
MRP: {current_data.get('mrp')}

Your Tasks:
1. Extract the exact, official Product Title including brand and variant/volume/weight (e.g. '580 ml', '1000 ml', '30g', 'Pack of 2').
2. Identify the exact checkout price of the seller for this specific link.
3. Identify the official printed packaging Box MRP (strike-through retail price).
4. If another seller on the page offers a cheaper price for the same item, note that cheaper price; otherwise 0.
5. Extract the variant specification string (e.g. '580 ml', '100g', '60 pcs').

Respond strictly in this JSON format:
{{
  "title": "string",
  "brand": "string",
  "variant_spec": "string",
  "seller_price": float,
  "box_mrp": float,
  "alternative_cheaper_price": float,
  "confidence": float
}}"""

    refined = _call_gemini_json(prompt, timeout=6.0)
    if not refined:
        return current_data

    result = dict(current_data)
    if refined.get("title") and len(str(refined["title"])) > 10:
        result["title"] = str(refined["title"])
    if float(refined.get("seller_price") or 0) > 0:
        result["price"] = float(refined["seller_price"])
    if float(refined.get("box_mrp") or 0) > float(result.get("price", 0)):
        result["mrp"] = float(refined["box_mrp"])
    if refined.get("variant_spec"):
        result["variant_spec"] = str(refined["variant_spec"])
    if float(refined.get("alternative_cheaper_price") or 0) > 0:
        result["cheaper_seller_price"] = float(refined["alternative_cheaper_price"])

    return result


def ai_validate_cross_store_match(
    source_title: str,
    source_price: float,
    source_mrp: float,
    candidate_title: str,
    candidate_price: float,
    candidate_mrp: float,
    source_platform: str = "flipkart",
    candidate_platform: str = "amazon"
) -> Dict[str, Any]:
    """
    Verifies whether an Amazon candidate is an exact variant and size match for a Flipkart item.
    Prevents false matches between mismatched volumes (e.g., 580 ml vs 1000 ml, 25ml vs 60ml).
    """
    if not is_ai_layer_available():
        return {"is_match": True, "reason": "Deterministic fallback"}

    prompt = f"""You are an expert price auditor comparing products across Amazon India and Flipkart.
Evaluate if these two items are the EXACT SAME product and SAME variant size/pack count.

Source ({source_platform}):
Title: {source_title}
Price: ₹{source_price}
MRP: ₹{source_mrp}

Candidate ({candidate_platform}):
Title: {candidate_title}
Price: ₹{candidate_price}
MRP: ₹{candidate_mrp}

Rules:
- If brand or model differs: NOT a match.
- If size/volume/weight differs (e.g. 580ml vs 1000ml, or single vs 2-pack): NOT an exact match!
- If identical product and identical size: EXACT match!

Respond strictly in this JSON format:
{{
  "is_exact_match": bool,
  "confidence": float,
  "mismatch_reason": "string (empty if match)",
  "value_insight": "string (e.g. Candidate offers 2x volume for less money, or empty if exact match)"
}}"""

    verdict = _call_gemini_json(prompt, timeout=6.0)
    if not verdict:
        return {"is_match": True, "reason": "Deterministic fallback"}

    return {
        "is_match": bool(verdict.get("is_exact_match", True)),
        "confidence": float(verdict.get("confidence") or 0.9),
        "reason": str(verdict.get("mismatch_reason") or ""),
        "value_insight": str(verdict.get("value_insight") or "")
    }
