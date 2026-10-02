"""
============================================================
 WAVEPICKS — Buyer Deals & Price Fluctuation Auditor UI
 Dedicated consumer portal for Amazon India Shoppers
 Pure, clean, focused deal auditing experience
============================================================
"""

BUYER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🛍️ WAVEPICKS Deals — Amazon India Price Fluctuation &amp; Deal Auditor</title>
<meta name="description" content="Paste any Amazon India product link to verify true printed box MRP, authentic deal discount %, and inspect 90-day price history curves before buying.">

<!-- Pinterest Rich Pin Standards & Domain Verification -->
<meta name="pinterest-rich-pin" content="true" />
<meta name="p:domain_verify" content="cf07b06d0e5ffe4465aa2c5c2297a030" />

<!-- Open Graph (Rich Pins / Social Sharing) -->
<meta property="og:site_name" content="ZERO483 Deals &amp; Price Auditor" />
<meta property="og:type" content="article" />
<meta property="og:title" content="Amazon India Deal &amp; Price Fluctuation Auditor — 100% Real Box MRP" />
<meta property="og:description" content="Audit real packaging box MRPs and inspect 90-day price drops before buying on Amazon India. Stop falling for fake discounts." />
<meta property="og:url" content="https://alerts.zero483.com/deals.html" />
<meta property="og:image" content="https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=1200&amp;auto=format&amp;fit=crop&amp;q=80" />
<meta property="article:author" content="PNLOKESWARI" />
<meta property="article:section" content="Shopping &amp; Consumer Protection" />

<!-- Twitter Cards -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Amazon India Deal &amp; Price Fluctuation Auditor — 100% Real Box MRP" />
<meta name="twitter:description" content="Audit real packaging box MRPs and inspect 90-day price drops before buying on Amazon India." />
<meta name="twitter:image" content="https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=1200&amp;auto=format&amp;fit=crop&amp;q=80" />

<!-- Canonical -->
<link rel="canonical" href="https://alerts.zero483.com/deals.html" />

<!-- Structured Data Schema (JSON-LD) for Google &amp; Pinterest Rich Pins -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebApplication",
      "name": "WAVEPICKS Amazon India Deal Auditor",
      "url": "https://alerts.zero483.com/deals.html",
      "applicationCategory": "ShoppingApplication",
      "operatingSystem": "All",
      "description": "Verifies authentic Amazon India printed box MRPs and renders 90-day Keepa price fluctuation curves."
    },
    {
      "@type": "Article",
      "headline": "Amazon India Deal & Price Fluctuation Auditor — 100% Real Box MRP",
      "description": "Verify authentic packaging box MRPs and inspect 90-day price drops before buying on Amazon India.",
      "image": "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=1200&auto=format&fit=crop&q=80",
      "author": {
        "@type": "Person",
        "name": "PNLOKESWARI",
        "jobTitle": "Lifestyle & Wellness Reviewer",
        "url": "https://alerts.zero483.com/#author-bio"
      },
      "publisher": {
        "@type": "Organization",
        "name": "ZERO483",
        "logo": {
          "@type": "ImageObject",
          "url": "https://alerts.zero483.com/favicon.ico"
        }
      }
    }
  ]
}
</script>

<!-- Official Pinterest Script -->
<script async defer src="//assets.pinterest.com/js/pinit.js"></script>
<style>
:root {
  --brand:#0284c7; --brand-glow:#38bdf8; --dark:#070d1e; --card:#0e1738; --card-hover:#13204d;
  --border:#182859; --green:#10b981; --yellow:#f59e0b; --red:#ef4444; --text:#f1f5f9; --muted:#94a3b8;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,Arial,sans-serif;background:var(--dark);color:var(--text);min-height:100vh;display:flex;flex-direction:column}

/* Header */
header{background:linear-gradient(135deg,#0369a1,#0b132b);padding:14px 24px;display:flex;align-items:center;gap:16px;border-bottom:1px solid #1e3a8a;box-shadow:0 4px 20px rgba(0,0,0,.6);flex-wrap:wrap}
.brand-title{font-size:1.25rem;font-weight:800;letter-spacing:.5px;display:flex;align-items:center;gap:8px}
.pill{background:rgba(56,189,248,.15);border:1px solid rgba(56,189,248,.3);border-radius:20px;padding:3px 10px;font-size:.72rem;color:#7dd3fc;font-weight:700}

/* Switcher Nav */
.app-switcher{display:flex;align-items:center;gap:6px;background:rgba(15,23,42,.7);padding:4px;border-radius:10px;border:1px solid rgba(56,189,248,.2);margin-left:auto}
.switch-link{text-decoration:none;color:#94a3b8;font-size:.76rem;font-weight:700;padding:6px 14px;border-radius:7px;transition:all .2s;display:flex;align-items:center;gap:6px}
.switch-link:hover{color:#f1f5f9;background:rgba(255,255,255,.05)}
.switch-link.active{color:#fff;background:linear-gradient(135deg,#0284c7,#0369a1);box-shadow:0 2px 8px rgba(2,132,199,.4)}
.sub-badge{font-size:.65rem;opacity:.8;background:rgba(0,0,0,.25);padding:1px 5px;border-radius:4px}

/* Container */
.container{max-width:1100px;width:100%;margin:0 auto;padding:32px 20px;flex:1;display:flex;flex-direction:column;gap:24px}

/* Trust Banner */
.trust-banner{background:linear-gradient(135deg,rgba(2,132,199,.18),rgba(14,23,56,.85));border:1px solid rgba(56,189,248,.3);border-radius:14px;padding:18px 24px;display:flex;align-items:center;gap:18px}
.trust-icon{font-size:2.2rem}
.trust-text h2{font-size:1.1rem;font-weight:800;color:#fff;margin-bottom:4px}
.trust-text p{font-size:.85rem;color:var(--muted);line-height:1.5}

/* Auditor Box */
.auditor-box{background:linear-gradient(135deg,#0d183f,#070d22);border:1px solid #1e3a8a;border-radius:16px;padding:28px 28px;box-shadow:0 10px 35px rgba(0,0,0,.5)}
.auditor-header h3{font-size:1.25rem;font-weight:800;display:flex;align-items:center;gap:10px}
.auditor-header p{font-size:.88rem;color:var(--muted);margin-top:6px;line-height:1.5}

.auditor-input-wrap{display:flex;gap:12px;margin-top:18px;flex-wrap:wrap}
.auditor-input{flex:1;min-width:300px;background:#050918;border:1px solid var(--border);border-radius:10px;padding:14px 18px;color:#fff;font-size:.95rem;outline:none;transition:border-color .2s}
.auditor-input:focus{border-color:var(--brand-glow)}
.btn-audit{background:linear-gradient(135deg,#0284c7,#0369a1);color:#fff;border:none;border-radius:10px;padding:14px 28px;font-weight:700;font-size:.95rem;cursor:pointer;box-shadow:0 2px 12px rgba(2,132,199,.35);transition:all .2s;white-space:nowrap}
.btn-audit:hover{background:#0369a1;transform:translateY(-1px)}
.btn-audit:disabled{opacity:.6;cursor:not-allowed}

.sample-row{display:flex;align-items:center;gap:8px;margin-top:12px;flex-wrap:wrap;font-size:.78rem;color:var(--muted)}
.sample-chip{background:rgba(15,23,42,.7);border:1px solid var(--border);border-radius:20px;padding:4px 12px;color:#7dd3fc;cursor:pointer;transition:all .2s}
.sample-chip:hover{background:rgba(2,132,199,.25);border-color:var(--brand-glow);color:#fff}

/* Audit Result Dossier Card */
.audit-card{background:#09122c;border:1px solid rgba(56,189,248,.35);border-radius:16px;padding:24px;margin-top:24px;box-shadow:0 14px 40px rgba(0,0,0,.6);animation:fadeIn .3s ease-in-out}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.audit-grid{display:grid;grid-template-columns:1.1fr 1fr;gap:26px}
@media(max-width:960px){.audit-grid{grid-template-columns:1fr}}

.metric-triplet{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:14px 0}
.metric-box{background:#060a17;border:1px solid var(--border);border-radius:10px;padding:12px 14px;text-align:center}
.metric-box.highlight{border-color:rgba(56,189,248,.4);background:rgba(2,132,199,.1)}
.m-val{font-size:1.4rem;font-weight:800;line-height:1.2}
.m-lbl{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-top:4px;font-weight:600}

.graph-invite-banner{background:linear-gradient(135deg,rgba(2,132,199,.22),rgba(6,10,23,.95));border:1px solid rgba(56,189,248,.4);border-radius:10px;padding:12px 16px;margin:12px 0;display:flex;align-items:center;gap:14px}
.graph-invite-banner .gib-icon{font-size:1.8rem;flex-shrink:0}
.graph-invite-banner .gib-text strong{color:#38bdf8;font-size:.88rem;display:block;margin-bottom:3px}
.graph-invite-banner .gib-text p{font-size:.78rem;color:#cbd5e1;line-height:1.45;margin:0}

.chart-guide-box{background:#070d22;border:1px solid var(--border);border-radius:8px;padding:10px 14px;margin-top:10px;font-size:.76rem}

.verdict-banner{background:#070d22;border-radius:10px;padding:14px 16px;margin:14px 0;border-left:4px solid #10b981}
.fluctuation-note{background:rgba(15,23,42,.6);border-radius:8px;padding:12px 14px;border:1px solid var(--border);margin-top:12px}

.btn-track-action{background:rgba(245,158,11,.15);color:#fbbf24;border:1px solid rgba(245,158,11,.3);padding:10px 16px;border-radius:8px;font-size:.82rem;font-weight:700;cursor:pointer;transition:all .2s}
.btn-track-action:hover{background:var(--yellow);color:#000}

.btn-buy{flex:1;text-align:center;text-decoration:none;background:linear-gradient(135deg,#0284c7,#0369a1);color:#fff;font-weight:700;font-size:.88rem;padding:12px 24px;border-radius:8px;box-shadow:0 2px 10px rgba(2,132,199,.3);transition:all .2s;display:inline-block}
.btn-buy:hover{background:#0369a1;transform:translateY(-1px)}

.chart-container{background:#050814;border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center;min-height:240px;display:flex;align-items:center;justify-content:center;position:relative;cursor:pointer;transition:border-color .2s}
.chart-container:hover{border-color:rgba(56,189,248,.6)}
.chart-container img{max-width:100%;max-height:280px;height:auto;border-radius:6px;display:none}

/* Footer Disclosure */
footer{background:#060a18;border-top:1px solid var(--border);padding:28px 20px;text-align:center;font-size:.8rem;color:var(--muted);line-height:1.6;margin-top:auto}

/* Keepa Modal */
.modal-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.75);display:none;align-items:center;justify-content:center;z-index:999;backdrop-filter:blur(3px)}
.modal-overlay.show{display:flex}
.modal-content{background:#0b132e;border:1px solid #1e3a8a;border-radius:14px;max-width:720px;width:92%;padding:24px;box-shadow:0 20px 60px rgba(0,0,0,.8);position:relative}
.modal-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.modal-title{font-size:1.1rem;font-weight:800;color:#fff}
.modal-close{background:none;border:none;color:var(--muted);font-size:1.4rem;cursor:pointer}
</style>
</head>
<body>

<header>
  <div class="brand-title">
    <span>🛍️ WAVEPICKS</span>
    <span class="pill">Deal Auditor</span>
  </div>

  <nav class="app-switcher">
    <a href="/deals" class="switch-link active">
      🛍️ <span>Deal Auditor</span>
      <span class="sub-badge">Shoppers</span>
    </a>
    <a href="/creator" class="switch-link">
      ✍️ <span>Creator Studio</span>
      <span class="sub-badge">Bloggers</span>
    </a>
    <a href="/" class="switch-link">
      📊 <span>Brand Intelligence</span>
      <span class="sub-badge">Sellers & D2C</span>
    </a>
  </nav>
</header>

<div class="container">
  <!-- Trust Banner -->
  <div class="trust-banner">
    <div class="trust-icon">🛡️</div>
    <div class="trust-text">
      <h2>100% Algorithmic Verification (Zero Manipulated Discounts)</h2>
      <p>Wavepicks audits real Amazon India packaging MRPs under Legal Metrology Rules and renders 90-day price history curves. We verify whether a deal is a genuine bargain or an everyday promo fluke.</p>
    </div>
  </div>

  <!-- Live Deal Auditor Box -->
  <div class="auditor-box">
    <div class="auditor-header">
      <h3>
        <span>🔍 Live Deal &amp; Price Fluctuation Auditor</span>
        <span class="pill" style="background:rgba(16,185,129,.15);color:#34d399;border-color:rgba(16,185,129,.3)">Audit Any Product</span>
      </h3>
      <p>
        Paste any Amazon India product link, shortlink (amzn.in/d/...), or ASIN. We'll verify the authentic discount against official printed box MRP, and render the interactive 90-day price curve to inspect actual market fluctuations.
      </p>
    </div>
    
    <div class="auditor-input-wrap">
      <input type="text" id="audit-input" class="auditor-input" placeholder="e.g. https://www.amazon.in/dp/B0BDVG99J5 or paste shortlink / ASIN" onkeydown="if(event.key==='Enter') runAudit()">
      <button class="btn-audit" id="btn-audit" onclick="runAudit()">Audit Deal ⚡</button>
    </div>

    <!-- Quick Sample Chips -->
    <div class="sample-row">
      <span>💡 Try these sample products:</span>
      <span class="sample-chip" onclick="quickAudit('B0BDVG99J5')">Dot &amp; Key Moisturizer</span>
      <span class="sample-chip" onclick="quickAudit('B01CCGW4OE')">Cetaphil Cleanser</span>
      <span class="sample-chip" onclick="quickAudit('B0HDYLT6XY')">Alps Goodness Rosemary</span>
      <span class="sample-chip" onclick="quickAudit('B0HCZCP1BR')">Foxtale Moisturiser</span>
      <span class="sample-chip" onclick="quickAudit('B0HBW2CJ62')">Ghar Soaps Kojic</span>
    </div>

    <!-- Live Audit Results Card (Initially Hidden) -->
    <div id="audit-results" style="display:none"></div>
  </div>
</div>

<!-- Modal: Keepa Price Chart -->
<div class="modal-overlay" id="keepa-modal">
  <div class="modal-content" style="max-width:720px">
    <div class="modal-header">
      <div class="modal-title" id="km-title">Verified 90-Day Price History</div>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div style="margin:16px 0;background:#060a17;border-radius:8px;padding:12px;border:1px solid var(--border);text-align:center;min-height:220px;display:flex;align-items:center;justify-content:center;position:relative">
      <div id="km-loading" style="color:var(--muted);font-size:.85rem">⏳ Loading 90-Day Price & BSR Curve...</div>
      <img id="km-img" referrerpolicy="no-referrer" src="" alt="Price History" style="max-width:100%;max-height:360px;height:auto;border-radius:6px;display:none" onload="document.getElementById('km-loading').style.display='none';this.style.display='block';" onerror="document.getElementById('km-loading').textContent='⚠️ Chart preview temporarily restricted. Click the button below to view live on Keepa.';">
    </div>

    <!-- Educational Guide on Price Fluctuations -->
    <div style="background:#070d22;border:1px solid var(--border);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:.76rem">
      <div style="font-weight:700;color:#38bdf8;margin-bottom:4px">📊 How to Interpret Price Fluctuations:</div>
      <div style="color:#cbd5e1;line-height:1.45">
        • <strong style="color:#60a5fa">🔵 Blue Price Curve:</strong> Shows exact day-by-day selling price on Amazon. Check if today is sitting at the bottom of a drop.<br>
        • <strong style="color:#34d399">🟢 Green Rank Line:</strong> Amazon BSR velocity. When green plunges downward towards #1, buyer orders are surging.<br>
        • <strong style="color:#e2e8f0">Official Box MRP:</strong> Indian law caps retail at printed MRP. Real discounts are measured by how far below MRP the blue line drops.
      </div>
    </div>

    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;flex-wrap:wrap">
      <p style="font-size:.78rem;color:var(--muted);line-height:1.5;margin:0">
        💡 <em>Look for deep blue valleys to time your purchase at peak savings.</em>
      </p>
      <a id="km-link" href="#" target="_blank" class="btn-buy" style="padding:8px 16px;font-size:.8rem;text-decoration:none;flex:none">
        Open Interactive Chart on Keepa ↗
      </a>
    </div>
  </div>
</div>

<footer>
  <p><strong>Amazon Associates Disclosure:</strong> As an Amazon Associate, Wavepicks earns from qualifying purchases made through links on this page. Product prices and availability are verified daily through automated audits and may change over time.</p>
</footer>

<script>
let lastAuditedItem = null;

function quickAudit(asin) {
  document.getElementById('audit-input').value = asin;
  runAudit();
}

async function runAudit() {
  const inputEl = document.getElementById('audit-input');
  const btnEl = document.getElementById('btn-audit');
  const resEl = document.getElementById('audit-results');
  const val = inputEl.value.trim();

  if (!val) {
    alert("Please paste an Amazon product link, shortlink, or ASIN.");
    inputEl.focus();
    return;
  }

  btnEl.disabled = true;
  btnEl.innerHTML = "Auditing Deal ⏳...";
  resEl.style.display = "block";
  resEl.innerHTML = `
    <div style="background:#070d22;border:1px solid var(--border);border-radius:12px;padding:26px;text-align:center;color:#38bdf8;font-size:.9rem">
      <div style="font-size:1.8rem;margin-bottom:8px">⚙️</div>
      <strong>Auditing Amazon India Pricing &amp; BSR Velocity...</strong>
      <div style="font-size:.78rem;color:var(--muted);margin-top:4px">Resolving ASIN, comparing box MRP, and querying Keepa 90-day price curve...</div>
    </div>
  `;

  try {
    const resp = await fetch('/api/buyer/audit-deal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: val })
    });
    const d = await resp.json();

    if (d.error) {
      resEl.innerHTML = `
        <div style="background:#220909;border:1px solid var(--red);border-radius:10px;padding:16px;color:#fca5a5;font-size:.85rem">
          <strong>⚠️ Audit Error:</strong> ${d.error}
        </div>
      `;
      btnEl.disabled = false;
      btnEl.innerHTML = "Audit Deal ⚡";
      return;
    }

    lastAuditedItem = d;

    resEl.innerHTML = `
      <div class="audit-card">
        <div class="audit-grid">
          <!-- Left Column -->
          <div class="audit-left">
            <div style="font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-weight:700">
              🏷️ ${d.category} • <span style="color:var(--brand-glow)">ASIN: ${d.asin}</span>
            </div>
            
            <h3 style="font-size:1.15rem;font-weight:800;color:#fff;margin:8px 0 14px;line-height:1.4">
              ${d.title}
            </h3>

            <!-- Metric Triplet: 100% Authentic Packaging MRP & Real Savings -->
            <div class="metric-triplet">
              <div class="metric-box">
                <div class="m-val" style="color:#fff">₹${d.current_price.toLocaleString('en-IN')}</div>
                <div class="m-lbl">Current Deal Price</div>
              </div>
              <div class="metric-box">
                <div class="m-val" style="color:#94a3b8">₹${d.mrp.toLocaleString('en-IN')}</div>
                <div class="m-lbl">Printed Box MRP</div>
              </div>
              <div class="metric-box highlight">
                <div class="m-val" style="color:#34d399">-${d.discount_mrp_pct}%</div>
                <div class="m-lbl">Save ₹${d.savings_mrp_inr.toLocaleString('en-IN')} off MRP</div>
              </div>
            </div>

            <!-- Graph Invitation Callout -->
            <div class="graph-invite-banner">
              <div class="gib-icon">📊</div>
              <div class="gib-text">
                <strong>Examine the 90-Day Price Curve on the Right ➔</strong>
                <p>In India, retail price cannot legally exceed printed box MRP (₹${d.mrp.toLocaleString('en-IN')}). To verify if today's ₹${d.current_price.toLocaleString('en-IN')} deal is an authentic festival-grade bargain or standard pricing, <strong>inspect the 90-day curve</strong> to see historical price drops and seller changes.</p>
              </div>
            </div>

            <!-- Fluctuation Range Bar -->
            <div style="background:#070d22;border:1px solid var(--border);border-radius:8px;padding:8px 14px;display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;font-size:.78rem">
              <span style="color:var(--muted)">📉 <strong>Historical Fluctuation Spread:</strong></span>
              <span style="color:#38bdf8;font-weight:700">${d.price_range_str}</span>
            </div>

            <!-- Verdict Banner -->
            <div class="verdict-banner" style="border-left-color:${d.verdict_color}">
              <div style="font-weight:800;font-size:1.02rem;color:${d.verdict_color};margin-bottom:4px">
                ${d.verdict}
              </div>
              <div style="font-size:.82rem;color:#cbd5e1;line-height:1.5">
                ${d.verdict_reason}
              </div>
            </div>

            <!-- Price Fluctuation & Volatility Note -->
            <div class="fluctuation-note">
              <div style="font-weight:700;font-size:.82rem;color:#7dd3fc;margin-bottom:3px">
                ${d.volatility_level}
              </div>
              <div style="font-size:.8rem;color:#cbd5e1;line-height:1.4">
                ${d.volatility_desc}
              </div>
              <div style="font-size:.76rem;color:var(--muted);margin-top:6px">
                📊 Amazon India BSR: #${d.bsr ? d.bsr.toLocaleString('en-IN') : 'N/A'} • ⭐ ${d.rating} / 5 (${d.review_count ? d.review_count.toLocaleString('en-IN') : 0} reviews)
              </div>
            </div>

            <!-- Actions -->
            <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap">
              <a href="${d.affiliate_url || d.amazon_url}" target="_blank" rel="nofollow noopener sponsored" class="btn-buy">
                Check Deal &amp; Buy on Amazon at ₹${d.current_price} ↗
              </a>
              <button class="btn-track-action" onclick="trackAuditedProduct('${d.asin}')">
                📌 Monitor in 14-Day Radar
              </button>
            </div>

            <!-- Ethical Referral Notice -->
            <div style="margin-top:10px;padding:8px 12px;background:rgba(2,132,199,.12);border:1px solid rgba(56,189,248,.25);border-radius:8px;font-size:.74rem;color:#cbd5e1;display:flex;align-items:center;gap:8px">
              <span style="font-size:1.1rem">🛍️</span>
              <span><strong>Support Wavepicks:</strong> Buying through our verified link credits a small referral fee to our research team at zero extra cost to you. Keeps our deal auditor 100% free!</span>
            </div>
          </div>

          <!-- Right Column: Keepa Curve -->
          <div class="audit-right">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
              <span style="font-size:.78rem;font-weight:800;color:#38bdf8;text-transform:uppercase;letter-spacing:1px;display:flex;align-items:center;gap:6px">
                📈 90-Day Price &amp; Demand Fluctuations
              </span>
              <span class="pill" style="font-size:.65rem;background:rgba(56,189,248,.15);color:#7dd3fc">Verified Keepa Curve</span>
            </div>
            
            <div class="chart-container" onclick="openKeepa('${d.asin}')" title="Click to view full-screen interactive chart">
              <div id="res-chart-loading" style="color:var(--muted);font-size:.85rem">⏳ Loading 90-day price curve...</div>
              <img id="res-chart-img" referrerpolicy="no-referrer" src="${d.keepa_chart_url}" alt="Keepa Price History" onload="document.getElementById('res-chart-loading').style.display='none';this.style.display='block';" onerror="document.getElementById('res-chart-loading').textContent='⚠️ Chart preview temporarily restricted. Click below to view on Keepa.';">
            </div>

            <div style="display:flex;align-items:center;justify-content:space-between;margin-top:8px;flex-wrap:wrap;gap:8px">
              <span style="font-size:.72rem;color:#94a3b8">
                🔍 <em>Click chart to enlarge • Box MRP is the legal ceiling</em>
              </span>
              <a href="${d.keepa_direct_url}" target="_blank" style="font-size:.75rem;color:var(--brand-glow);text-decoration:none;font-weight:700">
                Open Full Interactive Chart on Keepa ↗
              </a>
            </div>

            <!-- Guide to Reading Fluctuations -->
            <div class="chart-guide-box">
              <div style="font-weight:700;color:#f1f5f9;margin-bottom:5px;display:flex;align-items:center;gap:6px">
                <span>💡 How to Read Price Fluctuations on this Graph:</span>
              </div>
              <div style="color:#cbd5e1;line-height:1.45">
                • <strong style="color:#60a5fa">🔵 Blue Price Curve:</strong> Shows exact day-by-day selling price on Amazon. Check if today is sitting at the bottom of a drop.<br>
                • <strong style="color:#34d399">🟢 Green Demand Line:</strong> Amazon BSR velocity. When green plunges downward towards #1, buyer orders are surging.<br>
                • <strong style="color:#e2e8f0">Official Box MRP (₹${d.mrp.toLocaleString('en-IN')}):</strong> Constant legal ceiling under Indian law. Real discounts are measured by how far below MRP the blue line drops.
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    resEl.innerHTML = `
      <div style="background:#220909;border:1px solid var(--red);border-radius:10px;padding:16px;color:#fca5a5;font-size:.85rem">
        <strong>⚠️ Network Error:</strong> ${err.message}
      </div>
    `;
  } finally {
    btnEl.disabled = false;
    btnEl.innerHTML = "Audit Deal ⚡";
  }
}

async function trackAuditedProduct(asin) {
  if (!lastAuditedItem) return;
  try {
    const res = await fetch('/api/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        asin: lastAuditedItem.asin,
        title: lastAuditedItem.title,
        category: lastAuditedItem.category,
        amazon_url: lastAuditedItem.amazon_url,
        initial_price: lastAuditedItem.current_price,
        initial_rank: lastAuditedItem.bsr || 100,
        initial_reviews: lastAuditedItem.review_count || 0,
        initial_wave_score: 75,
        rationale: `Added via Live Deal Auditor (Deal: ₹${lastAuditedItem.current_price}, MRP: ₹${lastAuditedItem.mrp})`,
        cohort: 'Buyer Audited'
      })
    });
    const d = await res.json();
    if (d.ok) {
      alert(`✅ ASIN ${lastAuditedItem.asin} added to 14-Day Wave Tracking Radar! It will be audited every morning in your validation PDF.`);
    }
  } catch (err) {
    alert("Could not track product: " + err.message);
  }
}

function openKeepa(asin) {
  if (!asin) return;
  document.getElementById('km-title').textContent = `Verified 90-Day Price Curve (${asin})`;
  document.getElementById('km-loading').style.display = 'block';
  document.getElementById('km-loading').textContent = '⏳ Loading 90-Day Price & BSR Curve...';
  const img = document.getElementById('km-img');
  img.style.display = 'none';
  img.src = `/api/keepa-chart/${asin}`;
  document.getElementById('km-link').href = `https://keepa.com/#!product/10-${asin}`;
  document.getElementById('keepa-modal').classList.add('show');
}

function closeModal() {
  document.getElementById('keepa-modal').classList.remove('show');
}

window.onclick = function(e) {
  if (e.target.classList.contains('modal-overlay')) {
    closeModal();
  }
}
</script>
</body>
</html>
"""
