# ZERO483 Blog Creation & Publishing Standards (2026 High-Ranking Specification)

Whenever the user requests to create, generate, or publish a blog post, ALWAYS automatically execute the following standards without requiring manual reminders:

## 1. Automated Link Resolution & Product Scraping
- Automatically resolve shortlinks (e.g. `https://link.amazon/...`, `https://amzn.in/...`, Flipkart, Meesho) following 302/301 redirects to extract the canonical product ASIN / ID.
- Use `curl_cffi` with `impersonate="chrome120"` to bypass marketplace bot-checks and extract:
  - Exact product title, current deal price, MRP, and discount percentage.
  - High-res primary & secondary product images.
  - Key benefits, technical specs, and verified customer ratings.

## 2. Mandatory Author Profile & Google E-E-A-T Standards
Every blog post MUST feature a verified author section to satisfy Google's E-E-A-T and YMYL ranking guidelines:
- **Top Byline**:
  - Display author attribution in the hero meta bar:
    `✍️ Reviewed by <a href="#author-bio" style="color: #ffd54f; font-weight: 700; text-decoration: underline;">PNLOKESWARI</a> (Lifestyle & Wellness Reviewer) • Fact-Checked & Updated for 2026`
  - The name MUST be an active anchor link jumping smoothly down to `#author-bio`.
- **Author Bio Card (`#author-bio`)**:
  - Placed before the footer/cross-links.
  - Includes:
    - Author Avatar badge (`PL`).
    - Name: **PNLOKESWARI**
    - Role: **Lifestyle & Wellness Reviewer at ZERO483**
    - Credibility bio emphasizing hands-on testing, formulation analysis, and transparent consumer advice.
    - Editorial Integrity seal (`🛡️ 100% Unbiased & Hands-on Tested`).
- **Structured Data Person Entity**:
  - In the JSON-LD `@graph`, the author MUST be typed as:
    ```json
    "author": {
      "@type": "Person",
      "name": "PNLOKESWARI",
      "jobTitle": "Lifestyle & Wellness Reviewer",
      "url": "https://alerts.zero483.com/<path>#author-bio"
    }
    ```

## 3. Quad-Layer Structured Data & SEO Schema (Mandatory)
Every blog post created MUST include rich JSON-LD Schema markup in the `<head>` tag:
- **`@type: Article`**: With headline, high-res lead image, author Person schema, publisher, and dates.
- **`@type: Product`**: With name, brand, SKU/ASIN, price, currency (INR), in-stock status, and aggregateRating.
- **`@type: FAQPage`**: Containing all article FAQs so Google renders expandable accordion dropdowns directly in search results.
- **`@type: BreadcrumbList`**: Clean navigation hierarchy (`Home > Category > Product Review`) for enhanced Google SERP paths.

## 4. Pinterest Rich Pin Standards (Mandatory for All Blogs)
Every blog post created MUST be pre-configured for 100% automatic Pinterest Rich Pin activation:
- **Head Meta Tags**:
  - `<meta name="pinterest-rich-pin" content="true" />`
  - `<meta name="p:domain_verify" content="cf07b06d0e5ffe4465aa2c5c2297a030" />`
- **Rich Open Graph Metadata**:
  - `og:site_name` ("ZERO483 Lifestyle & Devotional")
  - `og:type` ("article")
  - `article:published_time` & `article:modified_time` (ISO 8601 strings)
  - `article:author` ("PNLOKESWARI")
  - `article:section` & relevant `article:tag` entries.
- **Rich Pin Specific Schemas**:
  - **For Food / Recipe Posts**: MUST include full `@type: "Recipe"` schema with structured `recipeIngredient` (array of all items) and `recipeInstructions` (array of HowToStep objects), plus `cookTime`, `prepTime`, and `recipeYield`.
  - **For Product Reviews**: Complete `@type: "Product"` schema with brand, price, currency, availability, and rating.
  - **For Guides & Listicles**: Complete `@type: "Article"` schema with headline, author Person schema, and datePublished.
- **High-Resolution Pin Images (No Low-Res Thumbnails)**:
  - Any Amazon product images placed in the blog MUST use high-res links (`_SL1000_.jpg` or `_SL1200_.jpg`), NEVER compressed thumbnails like `_SY300_SX300_` to guarantee images exceed Pinterest's 600px width requirement.
- **Save to Pinterest Integration**:
  - Include Pinterest's official `pinit.js` (`<script async defer src="//assets.pinterest.com/js/pinit.js"></script>`) and a 1-tap "📌 Save to Pinterest" button.

## 5. Technical SEO, Speed & Core Web Vitals
Ensure `<head>` always contains:
- `<link rel="canonical" href="https://alerts.zero483.com/<path>" />` (Mandatory self-referential canonical).
- Core Web Vitals LCP Preload: `<link rel="preload" as="image" href="<hero_image_url>" fetchpriority="high">`.
- `og:title`, `og:description`, `og:image` (High resolution image), `og:url`, `og:type` (`article`).
- `twitter:card` (`summary_large_image`), `twitter:title`, `twitter:description`, `twitter:image`.
- Mobile viewport: `<meta name="viewport" content="width=device-width, initial-scale=1.0">`.
- Robots directive: `<meta name="robots" content="index, follow, max-image-preview:large">`.

## 6. UI, UX, Navigation & Conversion Design
- **Zero Negative Margin & Clean Section Flow**: The main `.container` MUST NEVER use negative margins (`margin: -24px`) which causes content overlap and hides hero metadata or disclosures on mobile/desktop. Always use positive spacing (`margin: 24px auto 50px;`).
- **Hero Meta Chips**: The hero byline (`.hero-meta`) must use distinct `.hero-meta-chip` glass pills (`background: rgba(0, 0, 0, 0.28); border-radius: 20px;`) for author, read time, testing badge, and shade to guarantee 100% visibility without awkward wrapping or line cutting.
- **Top Affiliate Disclosure Card (Google & ASCI Compliance)**: High-contrast white card (`.affiliate-disclosure-box`) with accent border (`border-left: 5px solid #be185d;`) positioned prominently at the top of the container before any buy links.
- **Reading Progress Bar**: 3px sticky accent progress bar at the top of the viewport tracking scroll depth.
- **Quick Verdict / At-a-Glance Box**: Executive summary highlighting "Who Should Buy", "Who Should Skip", and Rating.
- **Interactive Table of Contents (TOC)**: Sticky or collapsable anchor jump links generating Google Sitelinks.
- **"How We Tested" Methodology Box**: Documenting 3 specific real-world testing criteria to prove First-Hand Experience.
- **Spotlight Product Card**: With deal badge, live price, MRP savings tag, and high-res image.
- **Sticky Top Navigation & Floating Bottom Bar**: Persistent mobile buy CTA.
- **1-Tap WhatsApp Share Button**: With pre-filled message text.
- **Internal Cross-Linking Box**: Linking to 3 related articles on the site.

## 7. Local Persistence, Sitemap & GitHub Auto-Publishing
- Save the newly generated file into `c:\Users\Ram\OneDrive\Documents\ZERO483 automation\<category>\` (e.g. `lifestyle/` or `devotional/`).
- Automatically add the new URL with `<priority>0.9</priority>` to `sitemap.xml`.
- Automatically commit and push both the HTML file and `sitemap.xml` directly to the GitHub repository (`pnlokeswari/zero483-widget`) via the GitHub REST API.
- Verify that the live URL (e.g., `https://alerts.zero483.com/...`) returns `HTTP 200 OK`.
