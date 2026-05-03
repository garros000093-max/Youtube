"""
auth_setup.py - Run this ONCE to get your YouTube refresh token
Deploy on Railway → open the URL → authorize → copy the token → add to Railway variables

Usage: python auth_setup.py
"""

import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

# Get from Railway variables
CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
PORT          = int(os.getenv("PORT", 8080))

# Railway provides the public URL via RAILWAY_PUBLIC_DOMAIN
RAILWAY_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", f"localhost:{PORT}")
REDIRECT_URI   = f"https://{RAILWAY_DOMAIN}/callback"

flow = None
auth_code = None


def build_flow():
    client_config = {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )


class AuthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        global flow, auth_code
        parsed = urlparse(self.path)

        # Step 1: Show auth link
        if parsed.path == "/":
            flow = build_flow()
            auth_url, _ = flow.authorization_url(
                access_type="offline",
                prompt="consent"
            )
            html = f"""<!DOCTYPE html>
<html>
<head>
  <title>YouTube Bot Auth</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 100px auto; text-align: center; }}
    a.btn {{ background: #FF0000; color: white; padding: 15px 30px; text-decoration: none;
             border-radius: 8px; font-size: 18px; display: inline-block; margin-top: 20px; }}
    a.btn:hover {{ background: #cc0000; }}
  </style>
</head>
<body>
  <h1>🤖 YouTube Bot Setup</h1>
  <p>Click the button to connect your YouTube channel</p>
  <a class="btn" href="{auth_url}">🔗 Connect YouTube Channel</a>
</body>
</html>"""
            self._send(200, html)

        # Step 2: Handle callback → exchange code → show token
        elif parsed.path == "/callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            error = params.get("error", [None])[0]

            if error:
                self._send(400, f"<h1>❌ Error: {error}</h1>")
                return

            if not code or not flow:
                self._send(400, "<h1>❌ Missing code or flow expired. Go back to /</h1>")
                return

            try:
                flow.fetch_token(code=code)
                creds = flow.credentials
                refresh_token = creds.refresh_token

                html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Success!</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 60px auto; }}
    .token-box {{ background: #1a1a1a; color: #00ff00; padding: 20px; border-radius: 8px;
                  word-break: break-all; font-family: monospace; font-size: 14px; }}
    .step {{ background: #f0f8ff; padding: 15px; border-radius: 8px; margin: 15px 0;
             border-left: 4px solid #0066cc; }}
  </style>
</head>
<body>
  <h1>✅ Authorization Successful!</h1>

  <div class="step">
    <strong>Step 1:</strong> Copy this refresh token:
  </div>
  <div class="token-box">{refresh_token}</div>

  <div class="step">
    <strong>Step 2:</strong> Go to Railway → your project → Variables → Add:
    <br><br>
    <code>YOUTUBE_REFRESH_TOKEN = {refresh_token[:20]}...</code>
  </div>

  <div class="step">
    <strong>Step 3:</strong> Also add these variables if not already there:
    <br><br>
    <code>GOOGLE_CLIENT_ID = {CLIENT_ID}</code><br>
    <code>GOOGLE_CLIENT_SECRET = {CLIENT_SECRET}</code>
  </div>

  <div class="step">
    <strong>Step 4:</strong> Stop this auth service on Railway and deploy the main bot instead.
  </div>

  <p>🎉 Your YouTube channel is now connected!</p>
</body>
</html>"""
                self._send(200, html)

            except Exception as e:
                self._send(500, f"<h1>❌ Error: {e}</h1>")
        else:
            self._send(404, "<h1>404</h1>")

    def _send(self, code, html):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())


if __name__ == "__main__":
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in environment variables")
        exit(1)

    print(f"🚀 Auth server starting on port {PORT}")
    print(f"🌐 Open: https://{RAILWAY_DOMAIN}/")
    print("After authorizing, copy the refresh token to Railway variables")

    server = HTTPServer(("0.0.0.0", PORT), AuthHandler)
    server.serve_forever()
