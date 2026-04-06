#!/usr/bin/env python3
"""
Simple dev server for PR Review Bot web app.
Usage: python server.py [port]
"""
import http.server
import socketserver
import sys
import os
import webbrowser
import threading

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000

os.chdir(os.path.dirname(os.path.abspath(__file__)))

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {args[0]} {args[1]}")

def open_browser():
    import time; time.sleep(0.5)
    webbrowser.open(f"http://localhost:{PORT}")

print(f"\n  🔍 PR Review Bot")
print(f"  Serving at http://localhost:{PORT}")
print(f"  Press Ctrl+C to stop\n")
threading.Thread(target=open_browser, daemon=True).start()

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
