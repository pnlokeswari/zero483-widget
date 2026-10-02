"""
============================================================
 ZERO483 Deals & Auditor Cloud Entry Point
 Production WSGI / ASGI entry point for Render.com,
 Heroku, Railway, and Koyeb.
 Exposes 'app' for gunicorn app:app or python app.py
============================================================
"""
import sys, os
from pathlib import Path

# Ensure tools directory is in Python module search path
CURRENT_DIR = Path(__file__).resolve().parent
TOOLS_DIR = CURRENT_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Import the core Flask app object from server.py
from server import app

# Port assignment from cloud environment
PORT = int(os.environ.get("PORT", 5483))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
