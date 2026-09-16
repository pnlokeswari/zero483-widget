# ZERO483 Blog Creation & Publishing Standards

Whenever the user requests to create, generate, or publish a blog post, ALWAYS automatically execute the following standards without requiring manual reminders:

## 1. Automated Link Resolution & Product Scraping
- Automatically resolve shortlinks (e.g. `https://link.amazon/...`, `https://amzn.in/...`, Flipkart, Meesho) following 302/301 redirects to extract the canonical product ASIN / ID.
- Use `curl_cffi` with `impersonate="chrome120"` to bypass Amazon / marketplace bot-checks and extract:
  - Exact product title, current deal price, MRP, and discount percentage.
  - High-res primary & secondary product images.
  - Key benefits, technical specs, and verified customer ratings.

## 2. Mandatory Author Profile & Google E-E-A-T Standards
Every blog post MUST feature a verified author section to satisfy Google's E-E-A-T and YMYL ranking guidelines:
- **Top Byline**:
  - Display author attribution in the hero meta bar:
    `✍️ Reviewed by <a href="#author-bio">PNLOKESWARI</a> (Lifestyle & Wellness Reviewer) • Fact-Checked & Updated for 2026`
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

## 3. Structured Data & SEO Schema (Mandatory)
Every blog post created MUST include rich JSON-LD Schema markup in the `<head>` tag:
- **For Product / Shopping Reviews**: Include a multi-entity `@graph` containing:
  - `@type: Article`: With headline, high-res lead image, author Person schema, publisher, and dates.
  - `@type: Product`: With name, brand, SKU/ASIN, price, currency (INR), in-stock status, and aggregateRating.
  - `@type: FAQPage`: Containing all article FAQs so Google renders expandable accordion dropdowns directly in search results.
- **For Recipes / Food Posts**: `@type: Recipe` schema with ingredients, prep time, cook time, and nutritional yield.
- **For Guides & Puja Vidhi**: `@type: Article` or `@type: HowTo`.

## 4. Technical SEO & Social Tags
Ensure `<head>` always contains:
- `<link rel="canonical" href="https://alerts.zero483.com/<path>" />` (Mandatory self-referential canonical).
- `og:title`, `og:description`, `og:image` (High resolution image), `og:url`, `og:type` (`article`).
- `twitter:card` (`summary_large_image`), `twitter:title`, `twitter:description`, `twitter:image`.
- Mobile viewport: `<meta name="viewport" content="width=device-width, initial-scale=1.0">`.
- Robots directive: `<meta name="robots" content="index, follow, max-image-preview:large">`.

## 5. UI, UX & Conversion Design
- Clean typography (`Plus Jakarta Sans`, `Outfit`, `Cinzel`) and responsive palette matching the niche:
  - Devotional: `#880e4f`, `#ffb300`, `#311b92`, `#fffdf9`.
  - Beauty & Wellness: `#be185d`, `#831843`, `#fffafb`, `#ffb300`.
  - Healthcare: `#00695c`, `#e0f2f1`, `#0284c7`, `#f8fbfb`.
- Sticky top navigation with quick-buy Amazon button and brand badge.
- Spotlight Product Card with deal badge, live price, MRP savings tag, and high-res image.
- Sticky bottom floating bar on mobile screens with price and 1-tap Amazon CTA.
- 1-tap WhatsApp Share button with pre-filled message text.
- Internal cross-linking box linking to 3 related articles on the site.

## 6. Local Persistence, Sitemap & GitHub Auto-Publishing
- Save the newly generated file into `c:\Users\Ram\OneDrive\Documents\ZERO483 automation\<category>\` (e.g. `lifestyle/` or `devotional/`).
- Automatically add the new URL with `<priority>0.9</priority>` to `sitemap.xml`.
- Automatically commit and push both the HTML file and `sitemap.xml` directly to the GitHub repository (`pnlokeswari/zero483-widget`) via the GitHub REST API:
  - Base64-encode content and call `PUT https://api.github.com/repos/pnlokeswari/zero483-widget/contents/<path>`.
- Verify that the live URL (e.g., `https://alerts.zero483.com/...`) returns `HTTP 200 OK`.
