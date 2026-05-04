"""
YouTube Uploader - Uploads videos via YouTube Data API v3
Uses Refresh Token stored in Railway environment variables (no browser needed)
"""

import os
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import time

log = logging.getLogger(__name__)

# IMPORTANT: Only youtube.upload scope
# Adding youtube / youtube.force-ssl / youtubepartner causes youtubeSignupRequired
# unless Google has manually verified your app
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
]


class YouTubeUploader:
    def __init__(self):
        self.creds = None
        self.youtube = self._authenticate()

    def _authenticate(self):
        refresh_token  = os.getenv("YOUTUBE_REFRESH_TOKEN")
        client_id      = os.getenv("GOOGLE_CLIENT_ID")
        client_secret  = os.getenv("GOOGLE_CLIENT_SECRET")

        if not all([refresh_token, client_id, client_secret]):
            raise ValueError(
                "Missing YouTube credentials. Set YOUTUBE_REFRESH_TOKEN, "
                "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET in Railway variables."
            )

        self.creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )

        self._refresh_credentials()
        return build("youtube", "v3", credentials=self.creds, cache_discovery=False)

    def _refresh_credentials(self):
        for attempt in range(3):
            try:
                self.creds.refresh(Request())
                log.info("✅ YouTube authenticated via refresh token")
                return
            except Exception as e:
                log.warning(f"Token refresh attempt {attempt + 1}/3 failed: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise RuntimeError(
            "Failed to refresh YouTube token after 3 attempts. "
            "Re-run auth_setup.py to get a new refresh token."
        )

    def _rebuild_client(self):
        self._refresh_credentials()
        self.youtube = build("youtube", "v3", credentials=self.creds, cache_discovery=False)

    def upload(self, video_path: str, thumbnail_path: str,
               metadata: dict, shorts: bool = False) -> str:

        title = metadata.get("title", "Untitled")
        if shorts and "#shorts" not in title.lower():
            title = title[:60] + " #shorts"

        body = {
            "snippet": {
                "title": title[:100],
                "description": self._build_description(metadata, shorts),
                "tags": self._clean_tags(metadata.get("tags", [])),
                "categoryId": "22",
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
                "madeForKids": False
            }
        }

        log.info(f"Uploading video: {title}")

        for attempt in range(2):
            try:
                media = MediaFileUpload(
                    video_path,
                    chunksize=50 * 1024 * 1024,
                    resumable=True,
                    mimetype="video/mp4"
                )
                request = self.youtube.videos().insert(
                    part="snippet,status",
                    body=body,
                    media_body=media
                )
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        log.info(f"Upload progress: {int(status.progress() * 100)}%")
                break

            except HttpError as e:
                if e.resp.status == 401 and attempt == 0:
                    log.warning("Got 401 during upload, refreshing token and retrying...")
                    self._rebuild_client()
                    continue
                raise

        video_id = response["id"]
        log.info(f"✅ Video uploaded: https://youtube.com/watch?v={video_id}")

        try:
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            log.info("✅ Thumbnail set")
        except Exception as e:
            log.warning(f"Thumbnail skipped: {e}")

        return video_id

    def _clean_tags(self, tags: list) -> list:
        banned = {"youtube", "youtuber", "subscribe", "viral", "trending",
                  "youtube.video", "video", "shorts", "short"}
        cleaned = []
        for tag in tags:
            tag = tag.strip()
            if tag and len(tag) <= 30 and tag.lower() not in banned:
                cleaned.append(tag)
        return cleaned[:15]

    def _build_description(self, metadata: dict, shorts: bool) -> str:
        base = metadata.get("description", "")
        footer = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔔 SUBSCRIBE for daily shocking stories
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#TrueCrime #Mystery #ShockingStory #Viral #TrueStory
⚠️ For educational and entertainment purposes only.
"""
        return base + footer
