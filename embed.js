// Zero483 FDA News Embed Widget v2.0
// Paste in Zoho Sites: <div id="z483-embed"></div><script src="https://alerts.zero483.com/embed.js"></script>
(function(){
var NEWS_URL='https://alerts.zero483.com/news_database.json?v='+Date.now();
var SUB_WH='https://hook.eu1.make.com/6gshw5et3mftrcl1kax5wxb250ysg4g9';
var root=document.getElementById('z483-embed');
if(!root){return;}

// Inject CSS
var css=document.createElement('style');
css.textContent='#z483-embed *{box-sizing:border-box;margin:0;padding:0;}'
+'#z483-wrap{font-family:Inter,Arial,sans-serif;background:#f8f9fa;padding:24px 20px;border-radius:10px;max-width:100%;color:#0f172a;}'
+'#z483-wrap a{text-decoration:none;}'
+'.z3-hdr{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;border-bottom:2px solid #0f172a;padding-bottom:16px;margin-bottom:18px;}'
+'.z3-hdr h2{font-size:1.5rem;font-weight:900;color:#0f172a;letter-spacing:-0.5px;}'
+'.z3-hdr p{font-size:0.85rem;color:#64748b;margin-top:3px;}'
+'.z3-hdr-right{display:flex;gap:10px;align-items:center;}'
+'.z3-subbtn{padding:8px 18px;background:#2563eb;color:#fff;border:none;border-radius:6px;font-weight:700;font-size:0.85rem;cursor:pointer;font-family:inherit;}'
+'.z3-subbtn:hover{background:#1d4ed8;}'
+'.z3-live{display:flex;align-items:center;gap:6px;font-size:0.7rem;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#dc2626;background:#fef2f2;border:1px solid #fecaca;border-radius:20px;padding:5px 10px;}'
+'.z3-dot{width:7px;height:7px;border-radius:50%;background:#dc2626;animation:z3pulse 2s infinite;}'
+'@keyframes z3pulse{0%,100%{box-shadow:0 0 0 0 rgba(220,38,38,0.4);}70%{box-shadow:0 0 0 5px rgba(220,38,38,0);}}'
+'.z3-ticker{display:none;background:#0f172a;border-radius:8px;overflow:hidden;margin-bottom:14px;padding:7px 0;align-items:center;}'
+'.z3-tlabel{font-size:0.68rem;font-weight:800;letter-spacing:1px;color:#fbbf24;white-space:nowrap;padding:0 14px;border-right:1px solid rgba(255,255,255,0.15);}'
+'.z3-ttrack{overflow:hidden;flex:1;}'
+'.z3-tcontent{display:inline-flex;gap:28px;animation:z3tick 40s linear infinite;white-space:nowrap;}'
+'.z3-tcontent:hover{animation-play-state:paused;}'
+'.z3-titem{font-size:0.77rem;color:rgba(255,255,255,0.82);}'
+'.z3-titem:hover{color:#fff;}'
+'@keyframes z3tick{from{transform:translateX(0);}to{transform:translateX(-50%);}}'
+'.z3-search{width:100%;padding:11px 14px 11px 40px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;font-size:0.92rem;font-family:inherit;outline:none;margin-bottom:14px;color:#0f172a;}'
+'.z3-search:focus{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,0.1);}'
+'.z3-swrap{position:relative;}'
+'.z3-sicon{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:#94a3b8;pointer-events:none;}'
+'.z3-chips{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:18px;}'
+'.z3-chip{padding:5px 13px;background:#fff;border:1.5px solid #e2e8f0;border-radius:20px;font-size:0.78rem;font-weight:600;color:#64748b;cursor:pointer;font-family:inherit;}'
+'.z3-chip:hover,.z3-chip.on{background:#2563eb;border-color:#2563eb;color:#fff;}'
+'.z3-feed{display:flex;flex-direction:column;gap:12px;}'
+'.z3-card{background:#fff;border:1px solid #e2e8f0;border-left:4px solid #2563eb;border-radius:10px;padding:16px 18px;cursor:pointer;transition:box-shadow 0.2s;}'
+'.z3-card:hover{box-shadow:0 6px 18px rgba(0,0,0,0.08);}'
+'.z3-ctop{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:8px;flex-wrap:wrap;}'
+'.z3-badges{display:flex;gap:5px;flex-wrap:wrap;}'
+'.z3-badge{font-size:0.66rem;font-weight:700;padding:3px 8px;border-radius:12px;text-transform:uppercase;letter-spacing:0.05em;}'
+'.z3-Recall,.z3-DrugRecall{background:#fef2f2;color:#dc2626;}'
+'.z3-DrugApproval{background:#f0fdf4;color:#16a34a;}'
+'.z3-DrugShortage{background:#fffbeb;color:#d97706;}'
+'.z3-WarningLetter{background:#fff7ed;color:#ea580c;}'
+'.z3-Form483{background:#faf5ff;color:#7c3aed;}'
+'.z3-Guidance{background:#eff6ff;color:#2563eb;}'
+'.z3-AdverseEvent{background:#fdf4ff;color:#a21caf;}'
+'.z3-High{background:#fef2f2;color:#dc2626;}'
+'.z3-Medium{background:#fffbeb;color:#d97706;}'
+'.z3-Low{background:#f0fdf4;color:#16a34a;}'
+'.z3-date{font-size:0.72rem;color:#94a3b8;white-space:nowrap;}'
+'.z3-card h3{font-size:0.93rem;font-weight:700;color:#0f172a;line-height:1.4;margin-bottom:7px;}'
+'.z3-sum{font-size:0.8rem;color:#64748b;line-height:1.6;margin-bottom:11px;}'
+'.z3-cfoot{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:7px;}'
+'.z3-co{font-size:0.73rem;color:#94a3b8;}'
+'.z3-rdlink{font-size:0.78rem;font-weight:600;color:#2563eb;}'
+'.z3-rdlink:hover{text-decoration:underline;}'
+'.z3-state{text-align:center;padding:40px 20px;color:#64748b;}'
+'.z3-spinner{width:34px;height:34px;border:3px solid #e2e8f0;border-top-color:#2563eb;border-radius:50%;animation:z3spin 0.75s linear infinite;margin:0 auto 12px;}'
+'@keyframes z3spin{to{transform:rotate(360deg);}}'
+'.z3-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:99999;align-items:center;justify-content:center;}'
+'.z3-overlay.open{display:flex;}'
+'.z3-modal{background:#fff;border-radius:14px;padding:28px 30px;max-width:400px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.25);position:relative;font-family:Inter,Arial,sans-serif;}'
+'.z3-modal h3{font-size:1.1rem;font-weight:800;margin-bottom:5px;color:#0f172a;}'
+'.z3-modal p{font-size:0.8rem;color:#64748b;margin-bottom:16px;}'
+'.z3-modal input{width:100%;padding:10px 13px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:0.85rem;font-family:inherit;outline:none;margin-bottom:9px;color:#0f172a;}'
+'.z3-modal input:focus{border-color:#2563eb;}'
+'.z3-subgo{width:100%;padding:10px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-weight:700;font-size:0.88rem;font-family:inherit;cursor:pointer;}'
+'.z3-subgo:hover{background:#1d4ed8;}'
+'.z3-mclose{position:absolute;top:11px;right:14px;background:none;border:none;font-size:1.2rem;cursor:pointer;color:#94a3b8;}'
+'.z3-ok{display:none;text-align:center;padding:8px 0;}'
+'.z3-ok.show{display:block;}';
document.head.appendChild(css);

// Inject HTML
root.innerHTML=
'<div id="z483-wrap">'
+'<div class="z3-hdr"><div><h2>USFDA Regulatory News</h2><p>Live recalls, approvals, shortages &amp; warning letters</p></div>'
+'<div class="z3-hdr-right"><button class="z3-subbtn" id="z3-opensub">Subscribe Free</button>'
+'<div class="z3-live"><span class="z3-dot"></span>Live Feed</div></div></div>'
+'<div class="z3-ticker" id="z3-ticker"><span class="z3-tlabel">LIVE</span><div class="z3-ttrack"><div class="z3-tcontent" id="z3-tc"></div></div></div>'
+'<div class="z3-swrap"><svg class="z3-sicon" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
+'<input class="z3-search" id="z3-search" type="text" placeholder="Search drugs, companies, recalls..."/></div>'
+'<div class="z3-chips" id="z3-chips">'
+'<button class="z3-chip on" data-f="All">All</button>'
+'<button class="z3-chip" data-f="Recall">Recalls</button>'
+'<button class="z3-chip" data-f="Drug Approval">Approvals</button>'
+'<button class="z3-chip" data-f="Drug Shortage">Shortages</button>'
+'<button class="z3-chip" data-f="Warning Letter">Warnings</button>'
+'<button class="z3-chip" data-f="Form 483">Form 483</button>'
+'<button class="z3-chip" data-f="Guidance">Guidance</button>'
+'</div>'
+'<div class="z3-feed" id="z3-feed"><div class="z3-state"><div class="z3-spinner"></div><p>Loading FDA alerts...</p></div></div>'
+'</div>'
+'<div class="z3-overlay" id="z3-overlay">'
+'<div class="z3-modal"><button class="z3-mclose" id="z3-mclose">✕</button>'
+'<h3>📬 Subscribe to FDA Alerts</h3>'
+'<p>Get drug recalls, approvals &amp; shortages delivered to your inbox — free.</p>'
+'<div id="z3-subform"><input type="text" id="z3-sname" placeholder="Your Name"/>'
+'<input type="email" id="z3-semail" placeholder="your@email.com"/>'
+'<button class="z3-subgo" id="z3-subgo">Subscribe Now →</button></div>'
+'<div class="z3-ok" id="z3-ok"><div style="font-size:2rem">✅</div><p style="font-weight:700;color:#16a34a;margin-top:8px">Subscribed!</p><p style="font-size:0.8rem;color:#64748b">You\'ll receive your first alert soon.</p></div>'
+'</div></div>';

// Helpers
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function stripHtml(s){return String(s||'').replace(/<[^>]*>?/gm,'');}
function trunc(s,n){var t=stripHtml(s);return t.length<=n?t:t.substring(0,n).trim()+'...';}
function fmtDate(d){try{return new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});}catch(e){return d||'';}}
function cc(c){return 'z3-'+(c||'').replace(/\s+/g,'');}

var items=[],filter='All',q='';

function render(list){
  var feed=document.getElementById('z3-feed');
  if(!list.length){feed.innerHTML='<div class="z3-state"><p>No results found. Try a different filter.</p></div>';return;}
  feed.innerHTML=list.map(function(i){
    return '<div class="z3-card" onclick="window.open(\''+esc(i.source_url)+'\',\'_blank\')">'
      +'<div class="z3-ctop"><div class="z3-badges">'
      +'<span class="z3-badge '+cc(i.category)+'">'+esc(i.category)+'</span>'
      +(i.severity?'<span class="z3-badge '+cc(i.severity)+'">'+esc(i.severity)+'</span>':'')
      +'</div><span class="z3-date">'+fmtDate(i.date)+'</span></div>'
      +'<h3>'+esc(stripHtml(i.title))+'</h3>'
      +'<p class="z3-sum">'+esc(trunc(i.summary,200))+'</p>'
      +'<div class="z3-cfoot"><span class="z3-co">🏢 '+esc(i.primary_company_name||'')+'</span>'
      +'<a class="z3-rdlink" href="'+esc(i.source_url)+'" target="_blank" onclick="event.stopPropagation()">Read Full Article →</a>'
      +'</div></div>';
  }).join('');
}

function applyFilters(){
  var qq=q.toLowerCase().trim();
  render(items.filter(function(i){
    var mc=filter==='All'||i.category===filter;
    if(!mc)return false;
    if(!qq)return true;
    return (i.title||'').toLowerCase().includes(qq)||(i.summary||'').toLowerCase().includes(qq)||(i.primary_company_name||'').toLowerCase().includes(qq);
  }));
}

// Fetch news
fetch(NEWS_URL)
  .then(function(r){return r.json();})
  .then(function(d){
    items=d.items||[];
    applyFilters();
    var tc=document.getElementById('z3-tc');
    var tw=document.getElementById('z3-ticker');
    if(items.length>0){
      var top=items.slice(0,8);
      var h=top.map(function(i){return'<a class="z3-titem" href="'+esc(i.source_url)+'" target="_blank">'+esc(stripHtml(i.title))+'</a>';}).join(' &bull; ');
      tc.innerHTML=h+' &bull; '+h;
      tw.style.display='flex';
    }
  })
  .catch(function(){
    document.getElementById('z3-feed').innerHTML='<div class="z3-state"><p>⚠ Could not load news. Please refresh the page.</p></div>';
  });

// Events
document.getElementById('z3-search').addEventListener('input',function(){q=this.value;applyFilters();});
document.getElementById('z3-chips').addEventListener('click',function(e){
  var b=e.target.closest('.z3-chip');if(!b)return;
  document.querySelectorAll('#z483-embed .z3-chip').forEach(function(x){x.classList.remove('on');});
  b.classList.add('on');filter=b.dataset.f;applyFilters();
});
document.getElementById('z3-opensub').addEventListener('click',function(){document.getElementById('z3-overlay').classList.add('open');});
document.getElementById('z3-mclose').addEventListener('click',function(){document.getElementById('z3-overlay').classList.remove('open');});
document.getElementById('z3-overlay').addEventListener('click',function(e){if(e.target===this)this.classList.remove('open');});
document.getElementById('z3-subgo').addEventListener('click',function(){
  var name=document.getElementById('z3-sname').value.trim();
  var email=document.getElementById('z3-semail').value.trim();
  if(!email||!email.includes('@')){alert('Please enter a valid email address.');return;}
  fetch(SUB_WH,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({subscriber_name:name,subscriber_email:email,source:'Zero483 Zoho Widget',timestamp:new Date().toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})}).toString(),mode:'no-cors'}).catch(function(){});
  document.getElementById('z3-subform').style.display='none';
  document.getElementById('z3-ok').classList.add('show');
  setTimeout(function(){document.getElementById('z3-overlay').classList.remove('open');},2500);
});
})();
