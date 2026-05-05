"""
Telegram Sender - Sends video files to Telegram chat
"""

import os
import requests
import logging

log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8470062315:AAE1oSfBhIITjsJCZ6V2BSQo397yZYaIMpI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "2064937908")

def send_message(text: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10
        )
    except Exception as e:
        log.warning(f"Telegram message failed: {e}")

def send_video(video_path: str, caption: str = "", thumbnail_path: str = None):
    """Send video file to Telegram"""
    log.info(f"📤 Sending video to Telegram: {video_path}")
    try:
        with open(video_path, "rb") as video_file:
            files = {"video": video_file}
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption[:1024] if caption else "",
                "supports_streaming": True
            }
            if thumbnail_path and os.path.exists(thumbnail_path):
                with open(thumbnail_path, "rb") as thumb:
                    files["thumbnail"] = thumb
                    r = requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                        data=data,
                        files=files,
                        timeout=300
                    )
            else:
                r = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                    data=data,
                    files=files,
                    timeout=300
                )
        if r.status_code == 200:
            log.info("✅ Video sent to Telegram!")
            return True
        else:
            log.warning(f"Telegram video failed: {r.text[:200]}")
            return False
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")
        return False

def send_document(file_path: str, caption: str = ""):
    """Send as document (no size limit compression)"""
    log.info(f"📤 Sending as document to Telegram: {file_path}")
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1024]},
                files={"document": f},
                timeout=300
            )
        if r.status_code == 200:
            log.info("✅ Document sent to Telegram!")
            return True
        else:
            log.warning(f"Telegram document failed: {r.text[:200]}")
            return False
    except Exception as e:
        log.warning(f"Telegram document send failed: {e}")
        return False
