"""
auth_refresh.py - Generate a new YouTube Refresh Token (one-time setup)
Run this LOCALLY on your PC, not on Railway.

Steps:
  1. pip install google-auth-oauthlib
  2. python auth_refresh.py
  3. Open the URL printed in the terminal
  4. Authorize with your YouTube account
  5. Paste the redirect URL back into terminal
  6. Copy the refresh_token printed at the end
  7. Update YOUTUBE_REFRESH_TOKEN in Railway variables
"""

import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")     or input("Enter GOOGLE_CLIENT_ID: ").strip()
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET") or input("Enter GOOGLE_CLIENT_SECRET: ").strip()

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ CLIENT_ID and CLIENT_SECRET are required.")
    sys.exit(1)

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
    }
}

print("\n🔐 Starting YouTube OAuth Flow...")
print("A browser window will open. Sign in with the Google account that has your YouTube channel.\n")

flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)

# run_local_server opens browser automatically if possible,
# fallback to copy-paste if no browser available
try:
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
except Exception:
    creds = flow.run_console()

refresh_token = creds.refresh_token

if not refresh_token:
    print("\n❌ No refresh token received.")
    print("Make sure your OAuth app is PUBLISHED (not in Testing mode).")
    print("Go to: Google Cloud Console → APIs & Services → OAuth consent screen → PUBLISH APP")
    sys.exit(1)

print("\n" + "="*60)
print("✅ SUCCESS! Your new refresh token:")
print("="*60)
print(f"\n{refresh_token}\n")
print("="*60)
print("\n📋 Next steps:")
print("1. Go to Railway → your project → Variables")
print("2. Update YOUTUBE_REFRESH_TOKEN with the token above")
print("3. Redeploy the bot")
print("\n⚠️  Keep this token secret — it gives full access to your YouTube channel.")
