"""
Zero483 Pinterest Blog Studio - Local Admin Server
==================================================
Runs locally at http://localhost:5000
Provides a web interface to generate AI drafts, preview/edit, and 1-click publish to GitHub.
"""

import os
import sys
import json
import re
import shutil
import subprocess
import webbrowser
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv(override=True)

# Initialize Flask
app = Flask(__name__, template_folder="templates")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DRAFTS_DIR = os.path.join(BASE_DIR, "drafts")
LIFESTYLE_DIR = os.path.join(BASE_DIR, "lifestyle")
TEMPLATE_FILE = os.path.join(BASE_DIR, "lifestyle_template.html")

os.makedirs(DRAFTS_DIR, exist_ok=True)
os.makedirs(LIFESTYLE_DIR, exist_ok=True)

# Initialize Gemini Client
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = None
if GEMINI_API_KEY:
    try:
        import google.genai as genai
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[WARNING] Could not initialize Gemini: {e}")

@app.route("/")
def index():
    return render_template("studio.html")

@app.route("/api/drafts", methods=["GET"])
def list_drafts():
    files = []
    if os.path.exists(DRAFTS_DIR):
        for f in os.listdir(DRAFTS_DIR):
            if f.endswith(".html"):
                filepath = os.path.join(DRAFTS_DIR, f)
                mtime = os.path.getmtime(filepath)
                date_str = datetime.fromtimestamp(mtime).strftime("%b %d, %I:%M %p")
                files.append({"filename": f, "date": date_str})
    files.sort(key=lambda x: x["filename"])
    return jsonify(files)

@app.route("/drafts/<path:filename>")
def serve_draft(filename):
    return send_from_directory(DRAFTS_DIR, filename)

@app.route("/api/generate-draft", methods=["POST"])
def generate_draft():
    data = request.json or {}
    amazon_url = data.get("amazon_url", "").strip()
    product_title = data.get("product_title", "").strip()
    custom_image = data.get("image_url", "").strip()

    if not amazon_url:
        return jsonify({"success": False, "error": "Amazon URL is required"}), 400

    if not client:
        return jsonify({"success": False, "error": "GEMINI_API_KEY missing or client not initialized"}), 500

    topic_input = f"Product Title: {product_title}\nAmazon Link: {amazon_url}" if product_title else amazon_url
    image_instruction = f"- Use this exact image URL for the image_url field: {custom_image}" if custom_image else "- Use a high-quality Unsplash image URL matching the topic if custom image is empty."

    prompt = f"""
    You are an expert Pinterest lifestyle blogger and Amazon affiliate marketer.
    Your job is to write a highly engaging, aesthetic, and SEO-optimized blog post for a Pinterest audience (lifestyle, fashion, home decor, beauty).
    
    Topic/Link provided: {topic_input}

    Output valid JSON strictly in this format:
    {{
        "title": "A catchy, click-worthy title (e.g. 10 Best Aesthetic Desk Accessories)",
        "description": "A 2-sentence Pinterest pin description with hashtags.",
        "category": "Lifestyle",
        "image_url": "https://images.unsplash.com/photo-1512418490979-9ce37274c6d3?q=80&w=800&auto=format&fit=crop", 
        "content_html": "<p>Engaging intro...</p> <h2>Why I love this</h2> <p>More details...</p> <a href='{amazon_url}' class='affiliate-btn'>Check Price on Amazon</a>"
    }}
    
    Rules:
    {image_instruction}
    - Make sure to use '{amazon_url}' in the 'affiliate-btn' a-tag.
    - Write at least 400 words for the content_html. Format it beautifully with h2, h3, and paragraphs.
    - Ensure it is valid JSON.
    """

    try:
        from google.genai import types
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        blog_data = json.loads(response.text)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    # Build HTML from template
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template = f.read()

    date_str = datetime.now().strftime("%B %d, %Y")
    safe_title = re.sub(r'[^a-z0-9]+', '-', blog_data.get("title", "post").lower()).strip('-')
    filename = f"{safe_title}.html"
    page_url = f"https://alerts.zero483.com/lifestyle/{filename}"

    html = template.replace("{{TITLE}}", blog_data.get("title", "Lifestyle Finds"))
    html = html.replace("{{DESCRIPTION}}", blog_data.get("description", ""))
    html = html.replace("{{CATEGORY}}", blog_data.get("category", "Lifestyle"))
    html = html.replace("{{DATE}}", date_str)
    html = html.replace("{{IMAGE_URL}}", blog_data.get("image_url", ""))
    html = html.replace("{{PAGE_URL}}", page_url)
    html = html.replace("{{CONTENT}}", blog_data.get("content_html", ""))

    draft_path = os.path.join(DRAFTS_DIR, filename)
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(html)

    return jsonify({"success": True, "filename": filename})

@app.route("/api/publish", methods=["POST"])
def publish():
    data = request.json or {}
    filename = data.get("filename", "").strip()

    if not filename:
        return jsonify({"success": False, "error": "Filename is required"}), 400

    draft_path = os.path.join(DRAFTS_DIR, filename)
    lifestyle_path = os.path.join(LIFESTYLE_DIR, filename)

    if not os.path.exists(draft_path):
        return jsonify({"success": False, "error": "Draft file not found"}), 404

    # Copy from drafts to lifestyle folder
    shutil.copyfile(draft_path, lifestyle_path)

    # Push to GitHub using existing upload script
    try:
        import upload_code_to_github as u
        github_path = f"lifestyle/{filename}"
        u.upload_file_to_github(lifestyle_path, github_path)
        live_url = f"https://alerts.zero483.com/{github_path}"
        return jsonify({"success": True, "live_url": live_url})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    print("\n========================================================")
    print(" 🚀 Zero483 Pinterest Blog Studio is running!")
    print(" 🌐 Open in browser: http://localhost:5000")
    print("========================================================\n")
    # Automatically open browser
    webbrowser.open("http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
