"""
YouTube Automation Bot - Main Orchestrator
Runs daily: finds trend → writes script → produces video → uploads to YouTube
"""

import os
import schedule
import time
import logging
from datetime import datetime
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
        # Step 1: Find trending topic
        log.info("📡 Step 1: Finding trending topic...")
        finder = TrendFinder()
        topic = finder.get_best_topic()
        log.info(f"✅ Topic selected: {topic['title']}")

        # Step 2: Generate script
        log.info("✍️  Step 2: Generating script...")
        generator = ScriptGenerator()
        script_data = generator.generate(topic)
        log.info(f"✅ Script ready ({len(script_data['script'])} chars)")

        # Step 3: Produce video
        log.info("🎬 Step 3: Producing video...")
        producer = VideoProducer()
        video_path, thumbnail_path = producer.produce(script_data)
        log.info(f"✅ Video ready: {video_path}")

        # Step 4: Upload to YouTube
        # Create a FRESH uploader instance per pipeline to avoid stale tokens
        log.info("📤 Step 4: Uploading to YouTube...")
        uploader = YouTubeUploader()
        video_id = uploader.upload(
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            metadata=script_data
        )
        log.info(f"✅ Uploaded! https://youtube.com/watch?v={video_id}")

        log.info("🎉 Pipeline complete!")

    except Exception as e:
        log.error(f"❌ Pipeline failed: {e}", exc_info=True)


def run_shorts_pipeline():
    """Shorter version for YouTube Shorts (vertical, < 60s)"""
    log.info("📱 Starting Shorts Pipeline...")
    try:
        finder = TrendFinder()
        topic = finder.get_best_topic(shorts=True)

        generator = ScriptGenerator()
        script_data = generator.generate(topic, shorts=True)

        producer = VideoProducer()
        video_path, thumbnail_path = producer.produce(script_data, shorts=True)

        # Create a FRESH uploader instance per pipeline to avoid stale tokens
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
    log.info("🤖 YouTube Bot starting up...")

    # Run Shorts first, wait between pipelines to avoid token conflicts
    run_shorts_pipeline()
    log.info("⏳ Waiting 30s between pipelines...")
    time.sleep(30)
    run_pipeline()

    # Schedule: Shorts every day at 9 AM EST, long video every 2 days at 3 PM EST
    schedule.every().day.at("14:00").do(run_shorts_pipeline)    # 9 AM EST = 14:00 UTC
    schedule.every(2).days.at("20:00").do(run_pipeline)         # 3 PM EST = 20:00 UTC

    log.info("⏰ Scheduler running. Waiting for next job...")
    while True:
        schedule.run_pending()
        time.sleep(60)
