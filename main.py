"""
YouTube Automation Bot - Main Orchestrator
"""

import os
import schedule
import time
import logging
from trend_finder import TrendFinder
from script_generator import ScriptGenerator
from video_producer import VideoProducer
from uploader import YouTubeUploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def run_pipeline():
    log.info("=" * 60)
    log.info("🚀 Starting YouTube Bot Pipeline")
    log.info("=" * 60)
    try:
        finder = TrendFinder()
        topic = finder.get_best_topic()
        log.info(f"✅ Topic selected: {topic['title']}")

        generator = ScriptGenerator()
        script_data = generator.generate(topic)
        log.info(f"✅ Script ready ({len(script_data['script'])} chars)")

        producer = VideoProducer()
        video_path, thumbnail_path = producer.produce(script_data)
        log.info(f"✅ Video ready: {video_path}")

        uploader = YouTubeUploader()
        video_id = uploader.upload(
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            metadata=script_data
        )
        log.info(f"✅ Uploaded! https://youtube.com/watch?v={video_id}")

    except Exception as e:
        log.error(f"❌ Pipeline failed: {e}", exc_info=True)


def run_shorts_pipeline():
    log.info("📱 Starting Shorts Pipeline...")
    try:
        finder = TrendFinder()
        topic = finder.get_best_topic(shorts=True)

        generator = ScriptGenerator()
        script_data = generator.generate(topic, shorts=True)

        producer = VideoProducer()
        video_path, thumbnail_path = producer.produce(script_data, shorts=True)

        uploader = YouTubeUploader()
        video_id = uploader.upload(
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            metadata=script_data,
            shorts=True
        )
        log.info(f"✅ Short uploaded! https://youtube.com/watch?v={video_id}")

    except Exception as e:
        log.error(f"❌ Shorts pipeline failed: {e}", exc_info=True)


if __name__ == "__main__":
    log.info("🤖 YouTube Bot starting up — scheduler only mode")
    log.info("📅 Shorts: daily at 15:00 Fez | Long video: every 2 days at 21:00 Fez")

    # Fez = UTC+1 → subtract 1 hour for UTC
    schedule.every().day.at("14:00").do(run_shorts_pipeline)   # 15:00 Fez
    schedule.every(2).days.at("20:00").do(run_pipeline)        # 21:00 Fez

    log.info("⏰ Waiting for scheduled jobs...")
    while True:
        schedule.run_pending()
        time.sleep(60)
