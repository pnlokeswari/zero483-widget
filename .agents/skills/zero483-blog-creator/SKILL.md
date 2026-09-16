---
name: zero483-blog-creator
description: >-
  Comprehensive high-ranking publishing skill for ZERO483 blogs.
  Implements automated link scraping with curl_cffi, PNLOKESWARI verified author profile, quad-layer Schema (Article + Product + FAQPage + BreadcrumbList),
  Core Web Vitals LCP preloading, Interactive Table of Contents, Quick Verdict box, Testing Methodology, Top Affiliate Disclosure,
  and GitHub auto-publishing.
---

# ZERO483 Blog Creator & Publishing Skill (2026 Production Specification)

This skill provides an autonomous end-to-end pipeline to create, optimize, publish, and verify high-ranking affiliate product review blogs, lifestyle edits, and devotional guides on `https://alerts.zero483.com`.

---

## 1. Automated Link Resolution & Product Scraping

When given any marketplace link (e.g. `https://link.amazon/...`, `https://amzn.in/...`, Flipkart, Meesho):
1. Resolve HTTP 301/302 redirects to obtain canonical product URL and extract ASIN / Product ID.
2. Use `curl_cffi` impersonating `chrome120` to bypass marketplace anti-bot protections:
```python
from curl_cffi import requests
from bs4 import BeautifulSoup

session = requests.Session(impersonate="chrome120")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
resp = session.get(canonical_url, headers=headers)
soup = BeautifulSoup(resp.text, "html.parser")

# Extract Title, Deal Price, MRP, Rating, Feature bullets, and High-Res Images
# Primary image: look for data-old-hires or large JSON image block in #landingImage
```

---

## 2. Mandatory Google E-E-A-T & Author Profile Standards

Every blog MUST feature **PNLOKESWARI** as the verified expert author to meet Google's E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) and YMYL guidelines:

### A. Hero Meta Attribution Chips
Must be displayed in the hero section using distinct frosted-glass pills (`.hero-meta-chip`):
```html
<div class="hero-meta">
  <span class="hero-meta-chip">✍️ Reviewed by <a href="#author-bio" style="color: #ffd54f; font-weight: 700; text-decoration: underline;">PNLOKESWARI</a> (Lifestyle & Wellness Reviewer)</span>
  <span class="hero-meta-chip">⏱️ 4 Min Read</span>
  <span class="hero-meta-chip">🔬 Verified Swatch & Wear Test</span>
  <span class="hero-meta-chip">🎨 Shade / Model Info</span>
</div>
```

### B. Author Bio Card (`#author-bio`)
Positioned prominently near the bottom of the article before the footer:
```html
<section id="author-bio" class="author-bio-card">
  <div class="author-avatar-badge">PL</div>
  <div class="author-details">
    <div class="author-header">
      <h3 class="author-name">PNLOKESWARI</h3>
      <span class="author-role">Lifestyle & Wellness Reviewer at ZERO483</span>
    </div>
    <p class="author-description">
      PNLOKESWARI is an experienced lifestyle, beauty, and wellness reviewer specializing in Indian skincare, beauty formulations, and smart consumer essentials. Every product featured undergoes real-world testing for durability, skin safety, and real consumer value.
    </p>
    <div class="author-trust-pill">
      🛡️ 100% Unbiased & Hands-on Tested • Fact-Checked for 2026
    </div>
  </div>
</section>
```

### C. Person Entity Schema
In the JSON-LD `@graph`, author must be explicitly typed as a `Person`:
```json
"author": {
  "@type": "Person",
  "name": "PNLOKESWARI",
  "jobTitle": "Lifestyle & Wellness Reviewer",
  "url": "https://alerts.zero483.com/<category>/<slug>.html#author-bio"
}
```

---

## 3. Quad-Layer Structured Data & SEO Schema

Include all 4 schemas inside a single `<script type="application/ld+json">` in the `<head>` tag:
1. **`@type: Article`**: Contains `headline`, `image`, `datePublished`, `dateModified`, `author` (Person entity), and `publisher` (Organization).
2. **`@type: Product`**: Contains `name`, `image`, `description`, `brand`, `sku`/`asin`, `offers` (with `priceCurrency: "INR"`, `price`, `availability: "https://schema.org/InStock"`, `url`), and `aggregateRating`.
3. **`@type: FAQPage`**: Contains all article FAQs inside `mainEntity` with `Question` and `Answer` for rich Google search accordions.
4. **`@type: BreadcrumbList`**: Contains navigation hierarchy (`Home > Category > Product Name`) for enhanced Google SERP paths.

---

## 4. Technical SEO & Core Web Vitals

Ensure `<head>` always contains:
- **Canonical URL**: `<link rel="canonical" href="https://alerts.zero483.com/<category>/<slug>.html" />`
- **Core Web Vitals LCP Preload**: `<link rel="preload" as="image" href="<hero_product_image_url>" fetchpriority="high" />`
- **Open Graph**: `og:title`, `og:description`, `og:image` (high-res), `og:url`, `og:type` (`article`).
- **Twitter Card**: `twitter:card` (`summary_large_image`), `twitter:title`, `twitter:description`, `twitter:image`.
- **Viewport**: `<meta name="viewport" content="width=device-width, initial-scale=1.0" />`
- **Robots Directives**: `<meta name="robots" content="index, follow, max-image-preview:large" />`

---

## 5. UI, UX, Navigation & Layout Architecture

### A. Zero Negative Margins (Clean Section Separation)
- The main `.container` MUST NEVER use negative margins (`margin: -24px`) which causes content overlap and hides hero metadata or disclosures on mobile/desktop. Always use positive spacing (`margin: 24px auto 50px;`).

### B. Sticky Reading Progress Bar
```html
<div id="progress-container"><div id="progress-bar"></div></div>
```
With CSS:
```css
#progress-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 4px;
  background: transparent;
  z-index: 9999;
}
#progress-bar {
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, #be185d, #ffb300);
  transition: width 0.1s ease-out;
}
```
And scroll listener:
```javascript
window.addEventListener('scroll', function() {
  var winScroll = document.body.scrollTop || document.documentElement.scrollTop;
  var height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
  var scrolled = (winScroll / height) * 100;
  var bar = document.getElementById("progress-bar");
  if (bar) bar.style.width = scrolled + "%";
});
```

### C. Top Affiliate Transparency Disclosure Card
Placed at the very top of `.container` before any product details or affiliate links:
```html
<div class="affiliate-disclosure-box">
  <span class="disclosure-icon">ℹ️</span>
  <div class="disclosure-body">
    <strong class="title">Editorial Disclosure:</strong> When you buy through our links, we may earn an affiliate commission at no extra cost to you. All products undergo rigorous, independent testing by <strong>PNLOKESWARI</strong>.
  </div>
</div>
```
With CSS:
```css
.affiliate-disclosure-box {
  background: #ffffff;
  border: 1px solid #fce7f3;
  border-left: 5px solid #be185d;
  border-radius: 12px;
  padding: 14px 20px;
  margin-bottom: 26px;
  font-size: 0.88rem;
  line-height: 1.55;
  color: #334155;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  box-shadow: 0 2px 10px rgba(190, 24, 93, 0.05);
}
```

### D. "Quick Verdict / At-a-Glance" Box
Optimized for Google AI Overviews and Featured Snippets (#0):
```html
<div class="quick-verdict-box">
  <div class="verdict-header">
    <h3 class="verdict-title">⚡ Quick Verdict: Is It Worth It?</h3>
    <span class="verdict-score">Overall Score: 8.8 / 10</span>
  </div>
  <p class="verdict-bottomline">
    <strong>The Bottom Line:</strong> [Clear 2-sentence executive summary explaining who should buy and what problem it solves].
  </p>
  <div class="verdict-grid">
    <div class="verdict-good"><strong>👍 Perfect For:</strong> [Target audience, daily use cases]</div>
    <div class="verdict-skip"><strong>⚠️ Skip If:</strong> [Specific users who should choose an alternative]</div>
  </div>
</div>
```

### E. Interactive Table of Contents (TOC)
Generates Google Sitelinks below the main search result:
```html
<nav class="toc-container">
  <h4>📑 Table of Contents (Jump to Section)</h4>
  <div class="toc-grid">
    <a href="#section-features">• Key Features & Benefits</a>
    <a href="#section-weartest">• Wear & Performance Test</a>
    <a href="#section-comparison">• Competitor Comparison</a>
    <a href="#section-pros-cons">• Pros, Cons & Verdict</a>
    <a href="#section-faqs">• Frequently Asked Questions</a>
    <a href="#author-bio">• Verified Author Bio</a>
  </div>
</nav>
```

### F. "How We Tested" (E-E-A-T) Callout Box
Documents 3 specific testing criteria proving hands-on experience:
```html
<div class="how-we-tested-box">
  <h4>🧪 How PNLOKESWARI Tested This Product (First-Hand Experience)</h4>
  <ul>
    <li><strong>Durability & Long-Wear:</strong> Monitored continuously over real-world daily routines.</li>
    <li><strong>Environmental Performance:</strong> Tested under heat, humidity, and varying light conditions.</li>
    <li><strong>Skin Health & Comfort:</strong> Verified for comfort, irritation-free wear, and ease of cleanup.</li>
  </ul>
</div>
```

### G. Spotlight Product Card & Conversion Elements
- Product card with Deal Badge, Live Price, MRP Savings Tag, and High-Res Primary Image.
- Dual CTAs: **View on Amazon** (with live deal price) and **1-Tap WhatsApp Share**.
- Head-to-Head Comparison Table comparing against 2 leading alternatives.
- Internal Cross-Linking Box recommending 3 related articles.
- Persistent Sticky Bottom Mobile Bar for 1-tap conversion.

---

## 6. Local Persistence, Sitemap & GitHub Auto-Publishing

1. Save the generated HTML file locally into `<category>/<slug>.html` (e.g. `lifestyle/` or `devotional/`).
2. Add the URL entry into `sitemap.xml`:
```xml
<url>
  <loc>https://alerts.zero483.com/<category>/<slug>.html</loc>
  <lastmod>YYYY-MM-DD</lastmod>
  <priority>0.9</priority>
</url>
```
3. Commit and push both files to GitHub repo `pnlokeswari/zero483-widget` via GitHub REST API (`PUT /repos/{owner}/{repo}/contents/{path}`).
4. Verify HTTP 200 response on `https://alerts.zero483.com/<category>/<slug>.html`.
