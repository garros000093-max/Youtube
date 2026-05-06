"""
YouTube Automation Bot - Telegram Delivery Mode
Runs ONCE on startup, then waits for scheduled times only
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

# Flag to prevent concurrent pipeline runs
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
            field    = "video"    if kind == "video" else "photo"
            r = requests.post(f"{API}/{endpoint}",
                data={"chat_id": CHAT_ID, "caption": caption[:1024],
                      "supports_streaming": True},
                files={field: f},
                timeout=600)
        if r.status_code == 200:
            log.info(f"✅ Sent {kind} to Telegram")
            return True
        # Fallback: document
        with open(path, "rb") as f:
            requests.post(f"{API}/sendDocument",
                data={"chat_id": CHAT_ID, "caption": caption[:1024]},
                files={"document": f},
                timeout=600)
        return True
    except Exception as e:
        log.warning(f"Telegram file failed: {e}")
        return False


def run_pipeline(shorts: bool = False):
    global pipeline_running

    if pipeline_running:
        log.warning("Pipeline already running — skipping")
        return

    pipeline_running = True
    kind = "📱 SHORTS" if shorts else "🎬 LONG VIDEO"
    log.info(f"Starting {kind} Pipeline...")
    tg_message(f"⏳ {kind} pipeline starting...")

    try:
        finder    = TrendFinder()
        topic     = finder.get_best_topic(shorts=shorts)

        generator = ScriptGenerator()
        data      = generator.generate(topic, shorts=shorts)

        producer  = VideoProducer()
        video_path, thumb_path = producer.produce(data, shorts=shorts)

        title       = data.get("title", topic["title"])
        description = data.get("description", "")
        tags        = data.get("tags", [])
        tags_str    = ", ".join(tags[:20])

        yt_info = f"""━━━━━━━━━━━━━━━━━━━━━━━━━
{kind} — READY TO UPLOAD
━━━━━━━━━━━━━━━━━━━━━━━━━

📌 <b>TITLE:</b>
<code>{title[:100]}</code>

📝 <b>DESCRIPTION:</b>
<code>{description[:800]}</code>

🏷️ <b>TAGS:</b>
<code>{tags_str}</code>

📂 Category: People & Blogs
🌍 Language: English
👶 Made for kids: NO
{'🔖 Add #shorts to title' if shorts else ''}

⬆️ https://studio.youtube.com
━━━━━━━━━━━━━━━━━━━━━━━━━"""

        tg_message(yt_info)

        if os.path.exists(thumb_path):
            tg_file(thumb_path, "photo", caption=f"🖼️ {title[:80]}")

        tg_message("📤 Sending video... (may take a few minutes)")
        tg_file(video_path, "video", caption=f"{'📱' if shorts else '🎬'} {title[:200]}")

        log.info(f"✅ {kind} complete!")
        tg_message(f"✅ {kind} done!")

    except Exception as e:
        log.error(f"❌ Pipeline failed: {e}", exc_info=True)
        tg_message(f"❌ Pipeline failed: {str(e)[:300]}")
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
    log.info("🤖 Bot starting — Telegram delivery mode")

    # Health server
    threading.Thread(
        target=lambda: HTTPServer(
            ("0.0.0.0", int(os.getenv("PORT", 8080))), HealthHandler
        ).serve_forever(),
        daemon=True
    ).start()

    tg_message("🚀 Bot started!\n📅 Shorts: daily 15:00 Fez\n🎬 Long video: every 2 days 21:00 Fez")

    # Run ONCE on startup in background thread
    threading.Thread(target=lambda: run_pipeline(shorts=True), daemon=True).start()
    time.sleep(120)  # Wait 2 min before long video
    threading.Thread(target=lambda: run_pipeline(shorts=False), daemon=True).start()

    # Schedule (UTC = Fez - 1h)
    schedule.every().day.at("14:00").do(
        lambda: threading.Thread(target=lambda: run_pipeline(shorts=True), daemon=True).start()
    )
    schedule.every(2).days.at("20:00").do(
        lambda: threading.Thread(target=lambda: run_pipeline(shorts=False), daemon=True).start()
    )

    log.info("⏰ Scheduler running... Next: 15:00 Fez (shorts) | 21:00 Fez (long)")

    while True:
        schedule.run_pending()
        time.sleep(60)
