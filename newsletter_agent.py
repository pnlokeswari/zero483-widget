import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SMTP_HOST = os.getenv("SMTP_HOST", "smtpout.secureserver.net")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

# Files
DB_FILE = "news_database.json"
SUBSCRIBERS_FILE = "subscribers.txt"
NEWSLETTERS_DIR = "newsletters"
ARCHIVE_PAGE = "newsletter_archive.html"
SITEMAP_FILE = "sitemap.xml"

# Check if Gemini key exists
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not set.")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro-latest')

def load_past_week_news():
    if not os.path.exists(DB_FILE):
        return []
    
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    past_week = []
    one_week_ago = datetime.now() - timedelta(days=7)
    
    for item in data.get("news", []):
        try:
            item_date = datetime.strptime(item.get("date_str", ""), "%Y-%m-%d")
            if item_date >= one_week_ago:
                past_week.append(item)
        except ValueError:
            continue
            
    return past_week

def generate_newsletter_html(news_items):
    if not news_items:
        return None
        
    print(f"Generating newsletter for {len(news_items)} items...")
    
    # Sort: put long form first
    news_items.sort(key=lambda x: x.get("is_long_form", False), reverse=True)
    
    # Take top 10 to not overwhelm Gemini
    top_items = news_items[:10]
    
    prompt = """You are an expert regulatory journalist writing a weekly newsletter for Zero483. 
The audience is Doctors, Nurses, and Pharma QA/R&D professionals.

Write a beautiful, professional HTML email newsletter summarizing the following regulatory alerts from the past week.
Focus heavily on the "is_long_form" items as the main feature stories.

Output ONLY valid HTML code. Do NOT wrap it in ```html markdown blocks.
Use inline CSS for styling (fonts like Inter/Arial, clean modern look, clear headings, dark text on white background).
Make sure to include a Header (Zero483 Weekly Regulatory Digest) and a Footer.

Here is the data:
"""
    for idx, item in enumerate(top_items):
        prompt += f"\n--- Item {idx+1} ---\n"
        prompt += f"Title: {item.get('title')}\n"
        prompt += f"Source: {item.get('source')}\n"
        prompt += f"Severity: {item.get('severity')}\n"
        prompt += f"Is Long Form (Deep Analysis): {item.get('is_long_form')}\n"
        prompt += f"Summary/Analysis: {item.get('analysis')}\n"
        
    response = model.generate_content(prompt)
    html_content = response.text.strip()
    
    # Strip markdown if Gemini included it despite instructions
    if html_content.startswith("```html"):
        html_content = html_content[7:]
    if html_content.endswith("```"):
        html_content = html_content[:-3]
        
    return html_content.strip()

def send_emails(html_content):
    if not SMTP_USER or not SMTP_PASS:
        print("Skipping email send: SMTP credentials not set in .env")
        return
        
    if not os.path.exists(SUBSCRIBERS_FILE):
        print(f"Skipping email send: {SUBSCRIBERS_FILE} not found.")
        return
        
    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
        subscribers = [line.strip() for line in f if line.strip() and "@" in line]
        
    if not subscribers:
        print("No subscribers found.")
        return
        
    print(f"Sending emails to {len(subscribers)} subscribers via {SMTP_HOST}...")
    
    try:
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
            
        server.login(SMTP_USER, SMTP_PASS)
        
        today_str = datetime.now().strftime("%B %d, %Y")
        subject = f"Zero483 Weekly Regulatory Digest - {today_str}"
        
        for email_addr in subscribers:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"Zero483 <{SMTP_USER}>"
            msg["To"] = email_addr
            
            part = MIMEText(html_content, "html")
            msg.attach(part)
            
            server.sendmail(SMTP_USER, email_addr, msg.as_string())
            print(f"  Sent to {email_addr}")
            
        server.quit()
        print("All emails sent successfully.")
    except Exception as e:
        print(f"Failed to send emails: {e}")

def update_seo_archive(html_content):
    if not os.path.exists(NEWSLETTERS_DIR):
        os.makedirs(NEWSLETTERS_DIR)
        
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"digest-{date_str}.html"
    filepath = os.path.join(NEWSLETTERS_DIR, filename)
    
    # Save the public webpage
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved public archive to {filepath}")
    
    # Update Archive Index
    link_html = f'<li><a href="newsletters/{filename}">Zero483 Weekly Digest - {date_str}</a></li>\n'
    
    if not os.path.exists(ARCHIVE_PAGE):
        # Create skeleton
        skeleton = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Zero483 Newsletter Archive</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
        h1 {{ color: #2c3e50; }}
        ul {{ list-style-type: none; padding: 0; }}
        li {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
        a {{ color: #3498db; text-decoration: none; font-size: 1.1em; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Zero483 Newsletter Archive</h1>
    <p>Read our past weekly regulatory digests.</p>
    <ul id="archive-list">
        {link_html}
    </ul>
</body>
</html>"""
        with open(ARCHIVE_PAGE, "w", encoding="utf-8") as f:
            f.write(skeleton)
    else:
        # Inject link
        with open(ARCHIVE_PAGE, "r", encoding="utf-8") as f:
            content = f.read()
        
        insert_marker = '<ul id="archive-list">'
        if insert_marker in content:
            content = content.replace(insert_marker, f"{insert_marker}\n        {link_html}")
            with open(ARCHIVE_PAGE, "w", encoding="utf-8") as f:
                f.write(content)
                
    # Update Sitemap (rudimentary addition)
    if os.path.exists(SITEMAP_FILE):
        with open(SITEMAP_FILE, "r", encoding="utf-8") as f:
            sitemap_data = f.read()
            
        url_entry = f"""
  <url>
    <loc>https://zero483.com/newsletters/{filename}</loc>
    <lastmod>{date_str}</lastmod>
    <changefreq>never</changefreq>
  </url>
</urlset>"""
        if "</urlset>" in sitemap_data and f"newsletters/{filename}" not in sitemap_data:
            sitemap_data = sitemap_data.replace("</urlset>", url_entry)
            with open(SITEMAP_FILE, "w", encoding="utf-8") as f:
                f.write(sitemap_data)

if __name__ == "__main__":
    print("Zero483 Newsletter Agent Starting...")
    news = load_past_week_news()
    
    if not news:
        print("No news from the past 7 days to report. Exiting.")
        exit(0)
        
    html = generate_newsletter_html(news)
    
    if html:
        update_seo_archive(html)
        send_emails(html)
    else:
        print("Failed to generate HTML.")
