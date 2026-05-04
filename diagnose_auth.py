"""
diagnose_auth.py - Run this to diagnose YouTube auth issues
Usage: python diagnose_auth.py
Add this file to Railway temporarily, run it once, check the logs.
"""

import os
import sys
import json
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

def check_env():
    print("\n" + "="*50)
    print("🔍 STEP 1: Checking environment variables")
    print("="*50)
    required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CHANNEL_ID"]
    ok = True
    for var in required:
        val = os.getenv(var, "")
        if val:
            print(f"  ✅ {var} = {val[:12]}...")
        else:
            print(f"  ❌ {var} = NOT SET")
            ok = False
    return ok

def check_token():
    print("\n" + "="*50)
    print("🔍 STEP 2: Testing token refresh")
    print("="*50)
    try:
        creds = Credentials(
            token=None,
            refresh_token=os.getenv("YOUTUBE_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=SCOPES
        )
        creds.refresh(Request())
        print(f"  ✅ Token refreshed successfully")
        print(f"  📅 Token expires at: {creds.expiry}")
        print(f"  🔑 Access token starts with: {creds.token[:20]}...")
        return creds
    except Exception as e:
        print(f"  ❌ Token refresh FAILED: {e}")
        print("\n  👉 CAUSE: Your YOUTUBE_REFRESH_TOKEN is expired or revoked.")
        print("  👉 FIX: Re-run auth_setup.py to get a new refresh token.")
        return None

def check_channel(creds):
    print("\n" + "="*50)
    print("🔍 STEP 3: Testing YouTube channel access")
    print("="*50)
    try:
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        resp = youtube.channels().list(part="snippet,status", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            print("  ❌ No YouTube channel found for this account!")
            print("  👉 FIX: Go to youtube.com and create a channel first.")
            return False
        for ch in items:
            ch_id = ch["id"]
            title = ch["snippet"]["title"]
            status = ch.get("status", {})
            print(f"  ✅ Channel found: '{title}' (ID: {ch_id})")
            print(f"  📊 Status: {status}")

            # Check if channel ID matches env var
            env_channel_id = os.getenv("YOUTUBE_CHANNEL_ID", "").strip()
            if env_channel_id and env_channel_id != ch_id:
                print(f"\n  ⚠️  WARNING: YOUTUBE_CHANNEL_ID in Railway ({env_channel_id})")
                print(f"  ⚠️  does NOT match authenticated channel ({ch_id})")
                print(f"  👉 FIX: Update YOUTUBE_CHANNEL_ID in Railway to: {ch_id}")
            elif not env_channel_id:
                print(f"\n  💡 TIP: Set YOUTUBE_CHANNEL_ID = {ch_id} in Railway variables")
        return True
    except HttpError as e:
        error_details = json.loads(e.content.decode())
        errors = error_details.get("error", {}).get("errors", [])
        for err in errors:
            reason = err.get("reason", "")
            domain = err.get("domain", "")
            print(f"  ❌ HttpError: reason={reason}, domain={domain}")
            if reason == "youtubeSignupRequired":
                print("\n  🔴 ROOT CAUSE: youtubeSignupRequired")
                print("  This means ONE of the following:")
                print("  1. The Google account has no YouTube channel created yet.")
                print("     → Go to youtube.com, sign in, and create a channel.")
                print("  2. Your OAuth app is in 'Testing' mode and the token expired (7-day limit).")
                print("     → Go to Google Cloud Console → OAuth consent screen → Publish the app")
                print("     → Then re-run auth_setup.py to get a fresh token.")
                print("  3. Wrong Google account was used during auth.")
                print("     → Re-run auth_setup.py and make sure to sign in with the RIGHT account.")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False

def check_upload_quota(creds):
    print("\n" + "="*50)
    print("🔍 STEP 4: Checking API quota")
    print("="*50)
    try:
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        # Small read-only call to test quota
        resp = youtube.videos().list(part="id", chart="mostPopular", maxResults=1).execute()
        print("  ✅ API quota OK — read call succeeded")
    except HttpError as e:
        if e.resp.status == 403:
            print("  ❌ Quota exceeded or API not enabled")
            print("  👉 FIX: Enable YouTube Data API v3 in Google Cloud Console")
        else:
            print(f"  ⚠️  HttpError {e.resp.status}: {e}")

if __name__ == "__main__":
    print("\n🤖 YouTube Auth Diagnostics")
    print("Run this file ONCE on Railway to find the exact issue.\n")

    if not check_env():
        print("\n❌ Fix missing environment variables first.")
        sys.exit(1)

    creds = check_token()
    if not creds:
        sys.exit(1)

    channel_ok = check_channel(creds)
    check_upload_quota(creds)

    print("\n" + "="*50)
    if channel_ok:
        print("✅ All checks passed! Auth should work.")
        print("If uploads still fail, the issue is in the video file itself.")
    else:
        print("❌ Auth issues found. Follow the FIX instructions above.")
    print("="*50 + "\n")
