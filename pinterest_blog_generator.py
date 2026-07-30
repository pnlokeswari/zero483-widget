"""
Pinterest Blog Generator (Hidden Affiliate Engine)
==================================================
Reads topics and affiliate links from amazon_links.txt.
Uses Gemini to generate SEO and Pinterest-friendly blog posts.
Saves HTML outputs into the /lifestyle/ directory using lifestyle_template.html.
"""

import os
import sys
import json
import time
import re
from datetime import datetime
from dotenv import load_dotenv

try:
    import google.genai as genai
    from google.genai import types
except ImportError:
    print("[ERROR] google-genai not installed. Run: pip install google-genai")
    sys.exit(1)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("[ERROR] GEMINI_API_KEY missing in .env file.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# Constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LINKS_FILE = os.path.join(BASE_DIR, "amazon_links.txt")
TEMPLATE_FILE = os.path.join(BASE_DIR, "lifestyle_template.html")
OUTPUT_DIR = os.path.join(BASE_DIR, "lifestyle")
BASE_URL = "https://alerts.zero483.com/lifestyle"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_blog_post(topic_or_link):
    """Uses Gemini to generate a JSON response with blog content."""
    prompt = f"""
    You are an expert Pinterest lifestyle blogger and Amazon affiliate marketer.
    I will provide you with a product link or a topic.
    Your job is to write a highly engaging, aesthetic, and SEO-optimized blog post for a Pinterest audience (mostly female, lifestyle-focused).
    
    Topic/Link provided: {topic_or_link}

    Output valid JSON strictly in this format:
    {{
        "title": "A catchy, click-worthy title (e.g. 10 Best Aesthetic Desk Accessories)",
        "description": "A 2-sentence Pinterest pin description with hashtags.",
        "category": "Lifestyle",
        "image_url": "https://images.unsplash.com/photo-1512418490979-9ce37274c6d3?q=80&w=800&auto=format&fit=crop", 
        "content_html": "<p>Engaging intro...</p> <h2>Why I love this</h2> <p>More details...</p> <a href='THE_AFFILIATE_LINK_PROVIDED' class='affiliate-btn'>Check Price on Amazon</a>"
    }}
    
    Rules:
    - Use a real Unsplash image URL that matches the topic if you don't have a specific product image.
    - If I provided an Amazon link, make sure to use that EXACT link in the 'affiliate-btn' a-tag.
    - If I only provided a topic, make up a generic placeholder link for the button (e.g. '#').
    - Write at least 400 words for the content_html. Format it beautifully with h2, h3, and paragraphs.
    - Ensure it is valid JSON.
    """
    
    print(f"Generating content for: {topic_or_link[:50]}...")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[ERROR] Failed to generate content: {e}")
        return None

def build_html(blog_data, filename):
    """Injects blog_data into lifestyle_template.html"""
    try:
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            template = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read template: {e}")
        return False
        
    date_str = datetime.now().strftime("%B %d, %Y")
    page_url = f"{BASE_URL}/{filename}"
    
    html = template.replace("{{TITLE}}", blog_data.get("title", "Lifestyle Finds"))
    html = html.replace("{{DESCRIPTION}}", blog_data.get("description", ""))
    html = html.replace("{{CATEGORY}}", blog_data.get("category", "Lifestyle"))
    html = html.replace("{{DATE}}", date_str)
    html = html.replace("{{IMAGE_URL}}", blog_data.get("image_url", ""))
    html = html.replace("{{PAGE_URL}}", page_url)
    html = html.replace("{{CONTENT}}", blog_data.get("content_html", ""))
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    print(f" -> Saved to {out_path}")
    return True

def main():
    if not os.path.exists(LINKS_FILE):
        print(f"[INFO] {LINKS_FILE} not found. Please create it and add topics.")
        return
        
    with open(LINKS_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines()]
        
    topics = [line for line in lines if line and not line.startswith("#")]
    
    if not topics:
        print("[INFO] No topics found in amazon_links.txt.")
        return
        
    print(f"[INFO] Found {len(topics)} topics to process.")
    
    for topic in topics:
        blog_data = generate_blog_post(topic)
        if blog_data:
            # Create a URL friendly filename
            safe_title = re.sub(r'[^a-z0-9]+', '-', blog_data.get("title", "post").lower()).strip('-')
            filename = f"{safe_title}.html"
            build_html(blog_data, filename)
            
        time.sleep(2) # Avoid rate limits
        
    print("[SUCCESS] All lifestyle blog posts generated.")

if __name__ == "__main__":
    main()
