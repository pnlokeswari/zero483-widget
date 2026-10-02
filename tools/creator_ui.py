"""
============================================================
 WAVEPICKS — Creator Studio UI Template
 Dedicated workspace for Affiliate Bloggers & Content Creators
============================================================
"""

CREATOR_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>✍️ WAVEPICKS Creator Studio — Affiliate & Trend Intelligence</title>
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
.container{max-width:1400px;width:100%;margin:0 auto;padding:24px 20px;flex:1;display:flex;flex-direction:column;gap:20px}

/* Hero Stats Bar */
.hero-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.stat-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 20px;position:relative;overflow:hidden}
.stat-card::after{content:'';position:absolute;top:0;left:0;width:4px;height:100%;background:var(--brand-glow)}
.stat-card.accent-green::after{background:var(--green)}
.stat-card.accent-yellow::after{background:var(--yellow)}
.stat-card.accent-purple::after{background:#a855f7}
.stat-val{font-size:1.6rem;font-weight:800;color:#fff;margin-bottom:4px}
.stat-lbl{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-weight:600}

/* Filter & Action Toolbar */
.toolbar{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 18px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.search-box{flex:1;min-width:260px;background:#080e22;border:1px solid var(--border);border-radius:8px;padding:9px 14px;color:#fff;font-size:.85rem;outline:none}
.search-box:focus{border-color:var(--brand-glow)}
.filter-select{background:#080e22;border:1px solid var(--border);border-radius:8px;padding:9px 12px;color:#fff;font-size:.82rem;outline:none;cursor:pointer}

/* Creator Grid / Table */
.creator-table-wrapper{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.4)}
table{width:100%;border-collapse:collapse;text-align:left;font-size:.85rem}
th{background:#09122c;color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:1px;padding:14px 16px;border-bottom:1px solid var(--border);font-weight:700}
td{padding:14px 16px;border-bottom:1px solid rgba(24,40,89,.6);vertical-align:middle}
tr:hover td{background:rgba(56,189,248,.04)}

/* Table Badges & Cells */
.prod-cell{display:flex;flex-direction:column;gap:4px;max-width:320px}
.prod-title{font-weight:700;color:#fff;line-height:1.3;text-decoration:none}
.prod-title:hover{color:var(--brand-glow)}
.prod-cat{font-size:.72rem;color:var(--muted);display:flex;align-items:center;gap:6px}
.badge-trajectory{display:inline-flex;align-items:center;gap:4px;padding:4px 9px;border-radius:6px;font-size:.72rem;font-weight:700}
.traj-surging{background:rgba(16,185,129,.15);color:#34d399;border:1px solid rgba(16,185,129,.3)}
.traj-holding{background:rgba(56,189,248,.15);color:#38bdf8;border:1px solid rgba(56,189,248,.3)}
.traj-fluke{background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.3)}

.score-badge{font-size:.9rem;font-weight:800;color:#fff;background:linear-gradient(135deg,#0284c7,#0369a1);padding:4px 10px;border-radius:8px;display:inline-block}
.yield-box{display:flex;flex-direction:column;gap:2px}
.yield-inr{font-weight:800;color:#34d399;font-size:.95rem}
.yield-100{font-size:.72rem;color:var(--muted)}

.btn-action{padding:7px 12px;border-radius:7px;border:none;cursor:pointer;font-size:.75rem;font-weight:700;display:inline-flex;align-items:center;gap:6px;transition:.2s}
.btn-brief{background:rgba(56,189,248,.15);color:#38bdf8;border:1px solid rgba(56,189,248,.3)}
.btn-brief:hover{background:var(--brand);color:#fff}
.btn-draft{background:linear-gradient(135deg,#0284c7,#0369a1);color:#fff;box-shadow:0 2px 8px rgba(2,132,199,.3)}
.btn-draft:hover{background:#0369a1}
.btn-keepa{background:rgba(245,158,11,.15);color:#fbbf24;border:1px solid rgba(245,158,11,.3)}
.btn-keepa:hover{background:var(--yellow);color:#000}

/* Modals */
.modal-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.75);display:none;align-items:center;justify-content:center;z-index:999;backdrop-filter:blur(3px)}
.modal-overlay.show{display:flex}
.modal-content{background:#0b132e;border:1px solid #1e3a8a;border-radius:14px;max-width:750px;width:92%;max-height:85vh;overflow-y:auto;padding:24px;box-shadow:0 20px 60px rgba(0,0,0,.8);position:relative}
.modal-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;border-bottom:1px solid var(--border);padding-bottom:12px}
.modal-title{font-size:1.15rem;font-weight:800;color:#fff}
.modal-close{background:none;border:none;color:var(--muted);font-size:1.4rem;cursor:pointer;line-height:1}
.modal-close:hover{color:#fff}

.brief-sec{margin-bottom:18px}
.brief-lbl{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px}
.brief-content{background:#070d22;border:1px solid var(--border);border-radius:8px;padding:12px 14px;font-size:.85rem;line-height:1.6}
.tag-pill{display:inline-block;background:rgba(56,189,248,.12);border:1px solid rgba(56,189,248,.25);color:#7dd3fc;padding:3px 8px;border-radius:6px;font-size:.75rem;margin:2px 4px 2px 0}
.copy-btn{padding:8px 16px;background:var(--brand);color:#fff;border:none;border-radius:7px;font-weight:700;cursor:pointer;margin-top:10px}
</style>
</head>
<body>

<header>
  <div class="brand-title">
    <span>✍️ WAVEPICKS</span>
    <span class="pill">Creator Studio</span>
  </div>

  <nav class="app-switcher">
    <a href="/deals" class="switch-link">
      🛍️ <span>Buyer Deals</span>
      <span class="sub-badge">Shoppers</span>
    </a>
    <a href="/creator" class="switch-link active">
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
  <!-- Hero KPIs -->
  <div class="hero-stats">
    <div class="stat-card">
      <div class="stat-val" id="stat-total">8</div>
      <div class="stat-lbl">Tracked Breakout Products</div>
    </div>
    <div class="stat-card accent-green">
      <div class="stat-val" id="stat-surging">4</div>
      <div class="stat-lbl">🚀 Active Organic Surges</div>
    </div>
    <div class="stat-card accent-yellow">
      <div class="stat-val" id="stat-avg-comm">8.0%</div>
      <div class="stat-lbl">Avg Amazon Commission Rate</div>
    </div>
    <div class="stat-card accent-purple">
      <div class="stat-val" id="stat-top-yield">₹26.80</div>
      <div class="stat-lbl">Top Commission / Sale</div>
    </div>
  </div>

  <!-- Filter Toolbar -->
  <div class="toolbar">
    <input type="text" class="search-box" id="search-input" placeholder="🔍 Search product title, brand, or ASIN..." oninput="renderTable()">
    
    <select class="filter-select" id="cat-filter" onchange="renderTable()">
      <option value="">All Categories</option>
      <option value="Beauty">Beauty & Skincare</option>
      <option value="Haircare">Haircare</option>
      <option value="Personal Care">Personal Care</option>
    </select>

    <select class="filter-select" id="traj-filter" onchange="renderTable()">
      <option value="">All Trajectories</option>
      <option value="Surging">🚀 Surging Only</option>
      <option value="Holding">⏳ Stable Staples Only</option>
      <option value="Fluke">❌ Promo Flukes (Avoid)</option>
    </select>

    <select class="filter-select" id="sort-select" onchange="renderTable()">
      <option value="score">Sort by: Creator Opportunity Score</option>
      <option value="yield">Sort by: Commission Yield (₹/sale)</option>
      <option value="savings">Sort by: Keepa Discount Depth (%)</option>
    </select>
  </div>

  <!-- Creator Table -->
  <div class="creator-table-wrapper">
    <table>
      <thead>
        <tr>
          <th>Product & Category</th>
          <th>14-Day Trajectory</th>
          <th>Price & Keepa Peak</th>
          <th>Commission Rate</th>
          <th>Affiliate Yield (₹)</th>
          <th>Creator Score</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody id="creator-table-body">
        <tr><td colspan="7" style="text-align:center;padding:40px;color:var(--muted)">Loading creator intelligence data...</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Modal: SEO Brief -->
<div class="modal-overlay" id="brief-modal">
  <div class="modal-content">
    <div class="modal-header">
      <div class="modal-title" id="bm-title">SEO Content Brief & Writing Blueprint</div>
      <button class="modal-close" onclick="closeModal('brief-modal')">&times;</button>
    </div>
    <div class="brief-sec">
      <div class="brief-lbl">Strategic Content Angle</div>
      <div class="brief-content" id="bm-angle"></div>
    </div>
    <div class="brief-sec">
      <div class="brief-lbl">Recommended High-CTR Article Titles</div>
      <div class="brief-content" id="bm-titles"></div>
    </div>
    <div class="brief-sec">
      <div class="brief-lbl">High-Intent SEO Target Keywords</div>
      <div id="bm-keywords"></div>
    </div>
    <div class="brief-sec">
      <div class="brief-lbl">Suggested 5-Section Article Structure (H2)</div>
      <div class="brief-content" id="bm-outline"></div>
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end">
      <button class="copy-btn" onclick="copyBriefText()">📋 Copy Brief to Clipboard</button>
    </div>
  </div>
</div>

<!-- Modal: Draft Article Preview -->
<div class="modal-overlay" id="draft-modal">
  <div class="modal-content" style="max-width:850px">
    <div class="modal-header">
      <div class="modal-title" id="dm-title">Auto-Generated Affiliate Review Article</div>
      <button class="modal-close" onclick="closeModal('draft-modal')">&times;</button>
    </div>
    <div class="brief-sec">
      <div class="brief-lbl">Ready-to-Publish Markdown / HTML Review</div>
      <textarea id="dm-body" style="width:100%;height:350px;background:#070d22;border:1px solid var(--border);border-radius:8px;color:#cbd5e1;padding:12px;font-family:monospace;font-size:.8rem;line-height:1.5" readonly></textarea>
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end">
      <button class="copy-btn" onclick="copyDraftText()">📋 Copy Markdown Article</button>
      <button class="copy-btn" style="background:#10b981" onclick="openPublishModal()">🚀 Publish via ZERO483 Engine</button>
    </div>
  </div>
</div>

<!-- Modal: Keepa Pre-Launch Chart -->
<div class="modal-overlay" id="keepa-modal">
  <div class="modal-content" style="max-width:720px">
    <div class="modal-header">
      <div class="modal-title" id="km-title">Keepa 90-Day Price & BSR History</div>
      <button class="modal-close" onclick="closeModal('keepa-modal')">&times;</button>
    </div>
    <div style="margin:16px 0;background:#060a17;border-radius:8px;padding:12px;border:1px solid var(--border);text-align:center;min-height:220px;display:flex;align-items:center;justify-content:center;position:relative">
      <div id="km-loading" style="color:var(--muted);font-size:.85rem">⏳ Loading 90-Day Price & BSR Curve...</div>
      <img id="km-img" referrerpolicy="no-referrer" src="" alt="Keepa Price History" style="max-width:100%;max-height:360px;height:auto;border-radius:6px;display:none" onload="document.getElementById('km-loading').style.display='none';this.style.display='block';" onerror="document.getElementById('km-loading').textContent='⚠️ Chart preview temporarily restricted. Click the link below to view live on Keepa.';">
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;flex-wrap:wrap">
      <p style="font-size:.78rem;color:var(--muted);line-height:1.5;margin:0">
        🟢 Green = Sales Rank (BSR) • 🔵 Blue = Amazon Deal Price
      </p>
      <a id="km-link" href="#" target="_blank" class="copy-btn" style="text-decoration:none;margin-top:0;display:inline-block">
        Open Interactive Chart on Keepa ↗
      </a>
    </div>
  </div>
</div>

<script>
let productsData = [];
let currentBrief = null;
let currentDraft = null;

async function loadCreatorData() {
  try {
    const res = await fetch('/api/creator/products');
    productsData = await res.json();
    updateKPIs();
    renderTable();
  } catch (err) {
    document.getElementById('creator-table-body').innerHTML = 
      `<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--red)">Failed to load creator data: ${err.message}</td></tr>`;
  }
}

function updateKPIs() {
  document.getElementById('stat-total').textContent = productsData.length;
  const surgingCount = productsData.filter(p => p.trajectory.includes('Surging')).length;
  document.getElementById('stat-surging').textContent = surgingCount;
  
  if (productsData.length > 0) {
    const maxY = Math.max(...productsData.map(p => p.commission_per_sale || 0));
    document.getElementById('stat-top-yield').textContent = `₹${maxY.toFixed(2)}`;
  }
}

function renderTable() {
  const tbody = document.getElementById('creator-table-body');
  const search = document.getElementById('search-input').value.toLowerCase();
  const cat = document.getElementById('cat-filter').value.toLowerCase();
  const traj = document.getElementById('traj-filter').value.toLowerCase();
  const sort = document.getElementById('sort-select').value;

  let filtered = productsData.filter(p => {
    const matchesSearch = !search || p.title.toLowerCase().includes(search) || p.asin.toLowerCase().includes(search);
    const matchesCat = !cat || p.category.toLowerCase().includes(cat);
    const matchesTraj = !traj || p.trajectory.toLowerCase().includes(traj);
    return matchesSearch && matchesCat && matchesTraj;
  });

  filtered.sort((a, b) => {
    if (sort === 'yield') return (b.commission_per_sale || 0) - (a.commission_per_sale || 0);
    if (sort === 'savings') return (b.savings_pct || 0) - (a.savings_pct || 0);
    return (b.creator_score || 0) - (a.creator_score || 0);
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--muted)">No products match your filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(p => {
    let trajClass = 'traj-holding';
    if (p.trajectory.includes('Surging')) trajClass = 'traj-surging';
    if (p.trajectory.includes('Fluke')) trajClass = 'traj-fluke';

    return `
      <tr>
        <td>
          <div class="prod-cell">
            <a href="${p.amazon_url}" target="_blank" class="prod-title" title="${p.title}">
              ${p.title.length > 60 ? p.title.substring(0, 60) + '...' : p.title}
            </a>
            <div class="prod-cat">
              <span>🏷️ ${p.category}</span>
              <span>•</span>
              <span style="font-family:monospace;color:var(--brand-glow)">${p.asin}</span>
            </div>
          </div>
        </td>
        <td>
          <span class="badge-trajectory ${trajClass}">${p.trajectory}</span>
        </td>
        <td>
          <div style="font-weight:700;color:#fff">₹${p.current_price}</div>
          <div style="font-size:.72rem;color:var(--muted)">
            Peak: ₹${p.max_price} ${p.savings_pct > 0 ? `<span style="color:#34d399">(-${p.savings_pct}%)</span>` : ''}
          </div>
        </td>
        <td>
          <span style="font-weight:800;color:#38bdf8">${p.commission_pct_str}</span>
        </td>
        <td>
          <div class="yield-box">
            <span class="yield-inr">₹${p.commission_per_sale}</span>
            <span class="yield-100">~₹${p.commission_per_100.toLocaleString('en-IN')} / 100 sales</span>
          </div>
        </td>
        <td>
          <span class="score-badge">${p.creator_score}</span>
        </td>
        <td>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <button class="btn-action btn-brief" onclick="openBriefModal('${p.asin}')">⚡ Brief</button>
            <button class="btn-action btn-draft" onclick="openDraftModal('${p.asin}')">✍️ Draft</button>
            <button class="btn-action btn-keepa" onclick="openKeepaModal('${p.asin}', '${p.title.replace(/'/g, "\\'")}')">📈 Keepa</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

async function openBriefModal(asin) {
  try {
    const res = await fetch(`/api/creator/brief/${asin}`);
    const b = await res.json();
    currentBrief = b;

    document.getElementById('bm-title').textContent = `SEO Brief: ${b.title.substring(0, 45)}...`;
    document.getElementById('bm-angle').textContent = b.content_angle;
    
    document.getElementById('bm-titles').innerHTML = b.suggested_titles.map((t, idx) => 
      `<div style="margin:4px 0"><strong>${idx + 1}.</strong> ${t}</div>`
    ).join('');

    document.getElementById('bm-keywords').innerHTML = b.seo_keywords.map(kw => 
      `<span class="tag-pill">🔍 ${kw}</span>`
    ).join('');

    document.getElementById('bm-outline').innerHTML = b.outline_h2.map(h => 
      `<div style="margin:4px 0">${h}</div>`
    ).join('');

    document.getElementById('brief-modal').classList.add('show');
  } catch (err) {
    alert("Could not load SEO brief: " + err.message);
  }
}

function openDraftModal(asin) {
  const p = productsData.find(x => x.asin === asin);
  if (!p) return;

  const articleText = `# ${p.suggested_titles ? p.suggested_titles[0] : p.title}

*Published on: 2026-10-02 | Category: ${p.category} | Tested & Reviewed*

> **Affiliate Disclosure:** When you buy through links in this review, Wavepicks earns an affiliate commission from Amazon India at no additional cost to you.

---

## 1. Quick Verdict: Who Should Buy and Who Should Skip?
- **Current Amazon Deal Price:** ₹${p.current_price} (Historical Keepa Peak: ₹${p.max_price})
- **BSR Momentum:** ${p.trajectory} on Amazon India
- **Our Verdict:** ${p.content_angle}

---

## 2. Why This Product is Surging on Amazon India
Our empirical 14-day BSR tracker flagged this product due to sustained buyer demand. Unlike short-lived promotional flukes, this product maintains high reorder rates and genuine customer satisfaction.

---

## 3. Price History Breakdown (Keepa Audit)
- **Current Price:** ₹${p.current_price}
- **Maximum Observed Price:** ₹${p.max_price}
- **Savings Depth:** ${p.savings_pct}% below peak pricing
- **Value Verdict:** Highly competitive in the ${p.category} segment.

---

## 4. Pros & Key Cons
### What We Loved:
- Verified high customer satisfaction in the sub-₹${Math.round(p.current_price * 1.5)} segment.
- Strong formula performance with zero reported adverse breakouts.

### What Could Be Improved:
- High demand often causes stock fluctuations on Amazon India.

---

## 5. Where to Buy at Lowest Price
[👉 Check Lowest Price & Stock on Amazon India](${p.amazon_url})
`;

  currentDraft = articleText;
  document.getElementById('dm-title').textContent = `Draft: ${p.title.substring(0, 40)}...`;
  document.getElementById('dm-body').value = articleText;
  document.getElementById('draft-modal').classList.add('show');
}

function openKeepaModal(asin, title) {
  document.getElementById('km-title').textContent = `Keepa 90-Day Price & BSR History: ${title}`;
  document.getElementById('km-link').href = `https://keepa.com/#!product/10-${asin}`;
  const img = document.getElementById('km-img');
  const loading = document.getElementById('km-loading');
  if (loading) {
    loading.style.display = 'block';
    loading.textContent = '⏳ Loading 90-Day Price & BSR Curve...';
  }
  img.style.display = 'none';
  img.src = `/api/keepa-chart/${asin}`;
  document.getElementById('keepa-modal').classList.add('show');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('show');
}

function copyBriefText() {
  if (!currentBrief) return;
  const text = `SEO BRIEF: ${currentBrief.title}\n\nCONTENT ANGLE:\n${currentBrief.content_angle}\n\nSUGGESTED TITLES:\n${currentBrief.suggested_titles.join('\n')}\n\nKEYWORDS:\n${currentBrief.seo_keywords.join(', ')}\n\nOUTLINE:\n${currentBrief.outline_h2.join('\n')}`;
  navigator.clipboard.writeText(text);
  alert("✅ SEO Content Brief copied to clipboard!");
}

function copyDraftText() {
  if (!currentDraft) return;
  navigator.clipboard.writeText(currentDraft);
  alert("✅ Markdown Article copied to clipboard!");
}

function openPublishModal() {
  alert("🚀 Ready! You can copy this draft directly into your CMS or launch the ZERO483 automated blog publisher from the Brand Intelligence panel.");
}

// Close modals when clicking overlay
window.onclick = function(e) {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('show');
  }
}

// Initial Load
document.addEventListener('DOMContentLoaded', loadCreatorData);
</script>
</body>
</html>
"""
