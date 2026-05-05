"""
YouTube Automation Bot - Main Orchestrator
Produces videos and sends them to Telegram for manual upload
"""

import os
import schedule
import time
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from trend_finder import TrendFinder
from script_generator import ScriptGenerator
from video_producer import VideoProducer
from telegram_sender import send_video, send_document, send_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"YouTube Bot is running OK")
    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


def run_pipeline(shorts: bool = False):
    kind = "Shorts" if shorts else "Long Video"
    log.info(f"🚀 Starting {kind} Pipeline...")
    send_message(f"🤖 Starting {kind} pipeline...")

    try:
        # Step 1: Find trend
        finder = TrendFinder()
        topic = finder.get_best_topic(shorts=shorts)
        log.info(f"✅ Topic: {topic['title']}")

        # Step 2: Generate script
        generator = ScriptGenerator()
        script_data = generator.generate(topic, shorts=shorts)
        log.info(f"✅ Script ready ({len(script_data['script'])} chars)")

        # Step 3: Produce video
        producer = VideoProducer()
        video_path, thumbnail_path = producer.produce(script_data, shorts=shorts)
        log.info(f"✅ Video ready: {video_path}")

        # Step 4: Send to Telegram
        title = script_data.get("title", "New Video")
        tag = "#shorts" if shorts else ""

        caption = f"""🎬 *{'SHORTS' if shorts else 'LONG VIDEO'}* — Ready to upload!

📌 Title:
`{title[:200]}`

🏷️ Tags: #TrueCrime #Mystery #ShockingStory {tag}

⬆️ Upload to: https://studio.youtube.com
"""
        send_message(f"✅ Video produced! Sending file now...")

        # Try sending as video first, fallback to document
        success = send_video(video_path, caption=caption, thumbnail_path=thumbnail_path)
        if not success:
            log.info("Video send failed, trying as document...")
            send_document(video_path, caption=caption)

        # Send thumbnail separately
        if os.path.exists(thumbnail_path):
            import requests
            with open(thumbnail_path, "rb") as f:
                requests.post(
                    f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN', '8470062315:AAE1oSfBhIITjsJCZ6V2BSQo397yZYaIMpI')}/sendPhoto",
                    data={
                        "chat_id": os.getenv("TELEGRAM_CHAT_ID", "2064937908"),
                        "caption": f"🖼️ Thumbnail for: {title[:100]}"
                    },
                    files={"photo": f},
                    timeout=60
                )
            log.info("✅ Thumbnail sent!")

        log.info(f"✅ {kind} pipeline complete!")

    except Exception as e:
        log.error(f"❌ {kind} pipeline failed: {e}", exc_info=True)
        send_message(f"❌ {kind} pipeline failed: {str(e)[:200]}")


if __name__ == "__main__":
    log.info("🤖 YouTube Bot starting up — Telegram delivery mode")
    send_message("🚀 YouTube Bot started! Will send videos to this chat for manual upload.")

    # Start health server
    threading.Thread(target=start_health_server, daemon=True).start()

    # Run immediately on startup
    log.info("▶️ Running pipelines now...")
    run_pipeline(shorts=True)
    log.info("⏳ Waiting 60s before long video...")
    time.sleep(60)
    run_pipeline(shorts=False)

    # Schedule daily runs (Fez time = UTC+1)
    schedule.every().day.at("14:00").do(run_pipeline, shorts=True)   # 15:00 Fez
    schedule.every(2).days.at("20:00").do(run_pipeline, shorts=False) # 21:00 Fez

    log.info("⏰ Scheduler running...")
    while True:
        schedule.run_pending()
        time.sleep(60)
