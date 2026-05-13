"""
YouTube Bot - Shorts ONLY mode (max duration for maximum reach)
"""

import os
import requests
import schedule
import time
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from trend_finder import TrendFinder
from script_generator import ScriptGenerator
from video_producer import VideoProducer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8470062315:AAE1oSfBhIITjsJCZ6V2BSQo397yZYaIMpI")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "2064937908")
API       = f"https://api.telegram.org/bot{BOT_TOKEN}"

pipeline_running = False


def tg_message(text: str):
    try:
        requests.post(f"{API}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15)
    except Exception as e:
        log.warning(f"Telegram message failed: {e}")


def tg_file(path: str, kind: str, caption: str = ""):
    try:
        with open(path, "rb") as f:
            endpoint = "sendVideo" if kind == "video" else "sendPhoto"
            field    = "video" if kind == "video" else "photo"
            r = requests.post(f"{API}/{endpoint}",
                data={"chat_id": CHAT_ID, "caption": caption[:1024],
                      "supports_streaming": True},
                files={field: f},
                timeout=600)
        if r.status_code == 200:
            log.info(f"✅ Sent {kind} to Telegram")
            return True
        with open(path, "rb") as f:
            requests.post(f"{API}/sendDocument",
                data={"chat_id": CHAT_ID, "caption": caption[:1024]},
                files={"document": f},
                timeout=600)
        return True
    except Exception as e:
        log.warning(f"Telegram file failed: {e}")
        return False


def run_shorts():
    global pipeline_running
    if pipeline_running:
        log.warning("Pipeline already running — skipping")
        return

    pipeline_running = True
    log.info("📱 Starting Shorts Pipeline...")
    tg_message("⏳ 📱 Shorts pipeline starting...")

    try:
        finder    = TrendFinder()
        topic     = finder.get_best_topic(shorts=True)

        generator = ScriptGenerator()
        data      = generator.generate(topic, shorts=True)

        producer  = VideoProducer()
        video_path, thumb_path = producer.produce(data, shorts=True)

        title       = data.get("title", topic["title"])
        description = data.get("description", "")
        tags        = data.get("tags", [])
        tags_str    = ", ".join(tags[:20])

        yt_info = f"""━━━━━━━━━━━━━━━━━━━━━━━━━
📱 SHORTS — READY TO UPLOAD
━━━━━━━━━━━━━━━━━━━━━━━━━

📌 <b>TITLE:</b>
<code>{title[:100]} #shorts</code>

📝 <b>DESCRIPTION:</b>
<code>{description[:800]}

#shorts #TrueCrime #Mystery #Viral</code>

🏷️ <b>TAGS:</b>
<code>{tags_str}</code>

📂 Category: People & Blogs
🌍 Language: English
👶 Made for kids: NO

⬆️ https://studio.youtube.com
━━━━━━━━━━━━━━━━━━━━━━━━━"""

        tg_message(yt_info)

        if os.path.exists(thumb_path):
            tg_file(thumb_path, "photo", caption=f"🖼️ {title[:80]}")

        tg_message("📤 Sending video...")
        tg_file(video_path, "video", caption=f"📱 {title[:200]} #shorts")

        log.info("✅ Shorts complete!")
        tg_message("✅ Shorts done! Upload to YouTube Studio.")

    except Exception as e:
        log.error(f"❌ Shorts failed: {e}", exc_info=True)
        tg_message(f"❌ Shorts failed: {str(e)[:300]}")
    finally:
        pipeline_running = False


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot running OK")
    def log_message(self, *args): pass


if __name__ == "__main__":
    log.info("🤖 Bot starting — Shorts ONLY mode (3 per day)")

    threading.Thread(
        target=lambda: HTTPServer(
            ("0.0.0.0", int(os.getenv("PORT", 8080))), HealthHandler
        ).serve_forever(),
        daemon=True
    ).start()

    tg_message("🚀 Bot started!\n📱 Shorts only: 3x daily\n⏰ 09:00 | 15:00 | 21:00 Fez time")

    # Run immediately on startup
    threading.Thread(target=run_shorts, daemon=True).start()

    # Schedule 3 shorts per day (Fez = UTC+1)
    schedule.every().day.at("08:00").do(
        lambda: threading.Thread(target=run_shorts, daemon=True).start()
    )  # 09:00 Fez
    schedule.every().day.at("14:00").do(
        lambda: threading.Thread(target=run_shorts, daemon=True).start()
    )  # 15:00 Fez
    schedule.every().day.at("20:00").do(
        lambda: threading.Thread(target=run_shorts, daemon=True).start()
    )  # 21:00 Fez

    log.info("⏰ Schedule: 09:00 | 15:00 | 21:00 Fez time")

    while True:
        schedule.run_pending()
        time.sleep(60)
