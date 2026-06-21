import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import uuid
import re

COMPANIES = [
    "sun pharmaceutical",
    "dr. reddy",
    "cipla",
    "lupin",
    "aurobindo",
    "zydus",
    "cadila",
    "torrent pharma",
    "alkem",
    "biocon",
    "glenmark",
    "divi's",
    "wockhardt",
    "intas"
]

def get_openfda_recalls(company, limit=15):
    query = urllib.parse.quote(f'recalling_firm:"{company}"')
    url = f"https://api.fda.gov/drug/enforcement.json?search=report_date:[20240101+TO+20261231]+AND+{query}&limit={limit}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read())
            return data.get('results', [])
    except Exception as e:
        print(f"  No records found for {company}")
        return []

def main():
    db_path = "news_database.json"
    with open(db_path, "r", encoding="utf-8") as f:
        db = json.load(f)
    
    existing_ids = {item["id"] for item in db.get("items", [])}
    added = 0
    
    print("Fetching Indian Pharma Historical Recalls from OpenFDA...")
    
    for comp in COMPANIES:
        results = get_openfda_recalls(comp, 15)
        if not results:
            continue
            
        print(f"  Found {len(results)} records for {comp}")
        for r in results:
            # Create a unique ID from the recall_number
            event_id = r.get("recall_number", str(uuid.uuid4()))
            item_id = "ind" + re.sub(r'[^a-z0-9]', '', event_id.lower())[:9]
            
            if item_id in existing_ids:
                continue
                
            # Parse dates
            date_str = r.get('recall_initiation_date', '')
            try:
                date_obj = datetime.strptime(date_str, '%Y%m%d')
                iso_date = date_obj.strftime('%Y-%m-%d')
            except:
                iso_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                
            prod_desc = r.get('product_description', '').split(',')[0].strip()
            firm = r.get('recalling_firm', '').title()
            reason = r.get('reason_for_recall', '')
            classification = r.get('classification', 'Class II')
            
            title = f"FDA {classification} Recall: {prod_desc} by {firm}"
            
            # Format exactly like ai_analyze output
            new_item = {
                "id": item_id,
                "title": title,
                "date": iso_date,
                "category": "Recall",
                "severity": "High" if classification == "Class I" else "Medium",
                "summary": f"<p>{reason}</p><p><strong>Product Details:</strong> {r.get('product_description', '')}</p><p><strong>Distribution:</strong> {r.get('distribution_pattern', '')}</p>",
                "source_url": "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "primary_company_name": firm,
                "seo_title": title,
                "seo_description": f"{classification} drug recall for {prod_desc} manufactured by {firm} due to {reason[:60]}...",
                "industry_context": f"<p>This {classification} recall by {firm} underscores the FDA's strict enforcement of CGMP standards.</p>",
                "compliance_impact": "<ul><li>Review QA procedures related to product release.</li><li>Verify stability testing protocols.</li></ul>",
                "key_actions": "<ul><li>Check internal inventory for affected lots.</li><li>Assess supplier quality agreements.</li></ul>"
            }
            
            db["items"].append(new_item)
            existing_ids.add(item_id)
            added += 1
            
    print(f"\nSuccessfully added {added} historical records from Indian Pharma.")
    
    # Sort by date descending
    db["items"].sort(key=lambda x: x.get("date", ""), reverse=True)
    
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
