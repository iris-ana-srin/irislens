#app.py
import os
import sys
from flask import Flask, send_from_directory, abort

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SURVEILLANCE_ROOT, HOST, PORT2
from surveillance.dvr import start as start_dvr

app = Flask(__name__)
ROOT = str(SURVEILLANCE_ROOT)                      
PAGE_ROOT = os.path.dirname(os.path.abspath(__file__))   
PAGES = {"img.html", "vid.html"}

start_dvr()

@app.route("/")
def index():
    try:
        entries = sorted(os.listdir(ROOT))
    except FileNotFoundError:
        entries = []

    links = "\n".join(f'<a href="{name}">{name}</a><br>' for name in entries if os.path.isfile(os.path.join(ROOT, name)))
    return f"<html><head><title>IrisLens-DVR</title></head><body>{links}</body></html>"

@app.route("/<path:filename>")
def serve(filename):
    if filename in PAGES:
        return send_from_directory(PAGE_ROOT, filename)
    if os.path.isfile(os.path.join(ROOT, filename)):
        return send_from_directory(ROOT, filename)
    abort(404)
    
if __name__ == "__main__":
    print(f"[SurveillanceWeb] Serving {ROOT}")
    print(f"[SurveillanceWeb] Starting on http://localhost:{PORT2}")
    app.run(host=HOST, port=PORT2, threaded=True)