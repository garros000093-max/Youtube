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

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


class YouTubeUploader:
    def __init__(self):
        self.youtube = self._authenticate()

    def _authenticate(self):
        """Authenticate using refresh token stored in Railway variables"""
        refresh_token  = os.getenv("YOUTUBE_REFRESH_TOKEN")
        client_id      = os.getenv("GOOGLE_CLIENT_ID")
        client_secret  = os.getenv("GOOGLE_CLIENT_SECRET")

        if not all([refresh_token, client_id, client_secret]):
            raise ValueError(
                "Missing YouTube credentials. Set YOUTUBE_REFRESH_TOKEN, "
                "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET in Railway variables."
            )

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )

        # Auto-refresh the access token
        creds.refresh(Request())
        log.info("✅ YouTube authenticated via refresh token")

        return build("youtube", "v3", credentials=creds)

    def upload(self, video_path: str, thumbnail_path: str,
               metadata: dict, shorts: bool = False) -> str:
        """Upload video to YouTube and set thumbnail"""

        title = metadata["title"]
        if shorts and "#shorts" not in title.lower():
            title = title[:60] + " #shorts"

        body = {
            "snippet": {
                "title": title[:100],
                "description": self._build_description(metadata, shorts),
                "tags": metadata.get("tags", [])[:30],
                "categoryId": metadata.get("category", "22"),
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
        media = MediaFileUpload(
            video_path,
            chunksize=50 * 1024 * 1024,  # 50MB chunks
            resumable=True,
            mimetype="video/mp4"
        )

        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        # Resumable upload with progress
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                log.info(f"Upload progress: {pct}%")

        video_id = response["id"]
        log.info(f"✅ Video uploaded: {video_id}")

        # Set thumbnail
        try:
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            log.info("✅ Thumbnail set")
        except Exception as e:
            log.warning(f"Thumbnail upload failed (needs verified account): {e}")

        return video_id

    def _build_description(self, metadata: dict, shorts: bool) -> str:
        """Build SEO-optimized description with affiliate links"""
        base_desc = metadata.get("description", "")

        affiliate_section = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔔 SUBSCRIBE for daily shocking stories
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 Recommended Books on True Crime:
👉 https://amzn.to/YOUR_AFFILIATE_LINK_HERE

🎧 Listen on Spotify: [Your Podcast Link]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#TrueCrime #Mystery #ShockingStory #Viral #TrueStory
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ This video is for educational and entertainment purposes only.
"""
        return base_desc + affiliate_section

    def update_underperforming(self, video_id: str, new_title: str, new_thumbnail: str = None):
        """Update title/thumbnail for videos with low CTR"""
        log.info(f"Updating video {video_id} with new title: {new_title}")

        self.youtube.videos().update(
            part="snippet",
            body={
                "id": video_id,
                "snippet": {
                    "title": new_title[:100],
                    "categoryId": "22"
                }
            }
        ).execute()

        if new_thumbnail:
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(new_thumbnail)
            ).execute()

        log.info(f"✅ Video {video_id} updated")

    def get_analytics(self, video_id: str) -> dict:
        """Get basic video stats"""
        response = self.youtube.videos().list(
            part="statistics",
            id=video_id
        ).execute()

        if response["items"]:
            stats = response["items"][0]["statistics"]
            return {
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0))
            }
        return {}
