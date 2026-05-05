"""
auth_setup.py - Run ONCE to get YouTube refresh token
Deploy on Railway → open URL → authorize → copy token → add to Railway variables
"""

import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from google_auth_oauthlib.flow import Flow

# Must match EXACTLY what uploader.py uses
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
]

CLIENT_ID      = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET  = os.getenv("GOOGLE_CLIENT_SECRET")
PORT           = int(os.getenv("PORT", 8080))
RAILWAY_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", f"localhost:{PORT}")
REDIRECT_URI   = f"https://{RAILWAY_DOMAIN}/callback"

flow = None


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
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI)


class AuthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        global flow
        parsed = urlparse(self.path)

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
    body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 100px auto;
            text-align: center; background: #0f0f0f; color: white; }}
    a.btn {{ background: #FF0000; color: white; padding: 15px 30px;
             text-decoration: none; border-radius: 8px; font-size: 18px;
             display: inline-block; margin-top: 20px; }}
    p {{ color: #aaa; }}
  </style>
</head>
<body>
  <h1>🤖 YouTube Bot Setup</h1>
  <p>⚠️ Sign in with the <strong>Brand Account</strong> (your channel), not the personal Gmail</p>
  <a class="btn" href="{auth_url}">🔗 Connect YouTube Channel</a>
</body>
</html>"""
            self._send(200, html)

        elif parsed.path == "/callback":
            params = parse_qs(parsed.query)
            code   = params.get("code",  [None])[0]
            error  = params.get("error", [None])[0]

            if error:
                self._send(400, f"<h1>❌ Error: {error}</h1>")
                return
            if not code or not flow:
                self._send(400, "<h1>❌ Missing code</h1>")
                return

            try:
                flow.fetch_token(code=code)
                creds         = flow.credentials
                refresh_token = creds.refresh_token

                html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Done!</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 60px auto;
            background: #0f0f0f; color: white; }}
    .token {{ background: #1a1a1a; color: #00ff00; padding: 20px; border-radius: 8px;
              word-break: break-all; font-family: monospace; font-size: 13px; margin: 15px 0; }}
    .step {{ background: #1a1a2e; padding: 15px; border-radius: 8px; margin: 15px 0;
             border-left: 4px solid #FF0000; }}
  </style>
</head>
<body>
  <h1>✅ Done!</h1>
  <div class="step"><strong>Step 1 — Copy this token:</strong></div>
  <div class="token">{refresh_token}</div>
  <div class="step">
    <strong>Step 2 — Update Railway variable:</strong><br><br>
    YOUTUBE_REFRESH_TOKEN = {refresh_token[:30]}...
  </div>
  <div class="step">
    <strong>Step 3 — Change Start Command back to:</strong><br><br>
    python main.py
  </div>
  <p>🎉 Done! Redeploy and the bot will start uploading.</p>
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
        print("❌ Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")
        exit(1)

    print(f"🚀 Auth server on port {PORT}")
    print(f"🌐 Open: https://{RAILWAY_DOMAIN}/")
    HTTPServer(("0.0.0.0", PORT), AuthHandler).serve_forever()
