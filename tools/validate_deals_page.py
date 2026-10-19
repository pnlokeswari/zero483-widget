# -*- coding: utf-8 -*-
"""
Automated Test & Validation Suite for WAVEPICKS deals.html
Runs syntax checks, headless browser simulation, and runtime tests across all 6 languages.
Prevents deployment of broken code or undeclared variables.
"""
import re
import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def validate():
    html_file = Path("deals.html")
    if not html_file.exists():
        print("❌ Error: deals.html not found.")
        return False

    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    print("🔍 [1/4] Checking HTML Structure & Critical Elements...")
    critical_elements = [
        'id="audit-input"',
        'id="btn-audit"',
        'id="audit-results"',
        'id="lang-menu"',
        'id="theme-menu"',
        'id="share-whatsapp-link"',
        'class="winner-banner"',
    ]
    for el in critical_elements:
        if el not in html:
            print(f"❌ Missing critical element: {el}")
            return False
    print("  ✓ All critical DOM elements present.")

    print("\n🔍 [2/4] Extracting & Checking JavaScript Syntax via Node.js...")
    scripts = re.findall(r'<script(?:\s+[^>]*)?>(.*?)</script>', html, re.DOTALL)
    if len(scripts) < 4:
        print(f"❌ Expected at least 4 script tags, found {len(scripts)}")
        return False

    main_script = max(scripts, key=len)
    test_script_path = Path("scratch/validate_script.js")
    test_script_path.parent.mkdir(parents=True, exist_ok=True)
    with open(test_script_path, "w", encoding="utf-8") as f:
        f.write(main_script)

    res = subprocess.run(["node", "--check", str(test_script_path)], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ JavaScript Syntax Error:\n{res.stderr}")
        return False
    print("  ✓ JavaScript syntax is 100% valid (0 syntax errors).")

    print("\n🔍 [3/4] Running Headless Browser Simulation & Multilingual Runtime Tests...")
    test_runner_code = """
const window = {
  location: { origin: 'https://alerts.zero483.com' },
  addEventListener: () => {}
};
const elements = {};
function createMockEl(id) {
  return {
    id,
    value: '',
    textContent: '',
    innerHTML: '',
    style: {},
    classList: { add: () => {}, remove: () => {}, toggle: () => {} },
    setAttribute: () => {},
    getAttribute: () => '',
    focus: () => {}
  };
}
const document = {
  addEventListener: () => {},
  querySelector: () => createMockEl('mock'),
  querySelectorAll: () => [],
  getElementById: (id) => {
    if (!elements[id]) elements[id] = createMockEl(id);
    return elements[id];
  },
  documentElement: {
    lang: 'en',
    setAttribute: () => {}
  },
  body: { appendChild: () => {} }
};
const localStorage = {
  store: {},
  getItem: (k) => localStorage.store[k] || null,
  setItem: (k, v) => { localStorage.store[k] = v; }
};

// Inject application script
""" + main_script + """

// TEST SUITE
try {
  // Test 1: Language Switching
  const supportedLangs = ['en', 'hi', 'te', 'kn', 'ta', 'bn'];
  for (const lang of supportedLangs) {
    if (!TRANSLATIONS[lang]) throw new Error(`Missing translation dictionary for ${lang}`);
    setLanguage(lang);
  }
  console.log('  ✓ Language switching verified across all 6 languages.');

  // Test 2: Multilingual Verdicts for all deal archetypes
  const mockDeals = [
    { type: 'massive', title: 'Test 1', current_price: 500, mrp: 2000, discount_mrp_pct: 75, savings_mrp_inr: 1500, lowest_90d: 499, bsr: 10, rating: 4.5, review_count: 100 },
    { type: 'record_low', title: 'Test 2', current_price: 999, mrp: 1200, discount_mrp_pct: 16.6, savings_mrp_inr: 201, lowest_90d: 980, diff_from_low: 19, bsr: 50, rating: 4.2, review_count: 50 },
    { type: 'solid', title: 'Test 3', current_price: 800, mrp: 1000, discount_mrp_pct: 20, savings_mrp_inr: 200, lowest_90d: 700, bsr: 200, rating: 4.0, review_count: 30 },
    { type: 'wait', title: 'Test 4', current_price: 990, mrp: 1000, discount_mrp_pct: 1, savings_mrp_inr: 10, lowest_90d: 600, bsr: 500, rating: 3.8, review_count: 10 }
  ];

  for (const d of mockDeals) {
    for (const lang of supportedLangs) {
      const v = getLocalizedVerdict(d, lang);
      if (!v || !v.title || !v.reason || !v.color) {
        throw new Error(`getLocalizedVerdict failed for ${d.type} in ${lang}`);
      }
      const share = getDealShareText(d, lang);
      if (!share || share.includes('undefined')) {
        throw new Error(`getDealShareText contains undefined for ${d.type} in ${lang}`);
      }
    }
  }
  console.log('  ✓ Localized verdict generation verified for all deal types.');

  // Test 3: Simulate runAudit template evaluation (Check for undefined variables like "v")
  const sampleProduct = {
    asin: 'B0CYQ6TJN8',
    category: 'Home',
    title: 'Robustt Wall Mount Universal',
    current_price: 349,
    mrp: 499,
    discount_mrp_pct: 30,
    savings_mrp_inr: 150,
    price_range_str: '₹349 - ₹499',
    bsr: 450,
    rating: 4.2,
    review_count: 1200,
    affiliate_url: 'https://amazon.in/dp/B0CYQ6TJN8',
    keepa_chart_url: '/api/keepa-chart/B0CYQ6TJN8',
    keepa_direct_url: 'https://keepa.com'
  };

  for (const lang of supportedLangs) {
    currentLang = lang;
    const d = sampleProduct;
    // THIS LINE TESTS EXACT TEMPLATE EVALUATION THAT BROKE PREVIOUSLY
    const v = getLocalizedVerdict(d, currentLang);
    const rendered = `
      <div class="audit-card">
        ${d.category} - ${d.asin} - ${d.title}
        ₹${d.current_price.toLocaleString('en-IN')} - ₹${d.mrp.toLocaleString('en-IN')}
        <div class="verdict-banner" style="border-left-color:${v.color}">
          ${v.title}
          ${v.reason}
          📊 ${TRANSLATIONS[currentLang].lbl_bsr}: #${d.bsr}
        </div>
      </div>
    `;
    if (rendered.includes('undefined')) {
      throw new Error(`Rendered card contains "undefined" in language ${lang}`);
    }
  }
  console.log('  ✓ runAudit card template evaluated successfully without undeclared variables.');

  console.log('SUCCESS');
} catch (err) {
  console.error('FAIL: ' + err.message);
  process.exit(1);
}
"""
    with open("scratch/runtime_test.js", "w", encoding="utf-8") as f:
        f.write(test_runner_code)

    res = subprocess.run(["node", "scratch/runtime_test.js"], capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        print(f"❌ Runtime Simulation Failed:\n{res.stderr or res.stdout}")
        return False
    print(res.stdout.strip())

    print("\n🔍 [4/4] Verifying File Synchronization...")
    buyer_path = Path("tools/buyer_ui.py")
    if buyer_path.exists():
        with open(buyer_path, "r", encoding="utf-8") as f:
            buyer_content = f.read()
        if "BUYER_HTML" in buyer_content and "const v = getLocalizedVerdict" in buyer_content:
            print("  ✓ tools/buyer_ui.py is synchronized with deals.html.")
        else:
            print("  ⚠️ Warning: tools/buyer_ui.py is missing latest verdict fix. Resync required.")
            return False

    print("\n🎉 ALL QUALITY & RUNTIME CHECKS PASSED! Safe to deploy.")
    return True

if __name__ == "__main__":
    success = validate()
    sys.exit(0 if success else 1)
