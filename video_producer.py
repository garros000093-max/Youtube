"""
Video Producer - Assembles the final video
Stock footage from Pexels + voiceover + background music + thumbnail
"""

import os
import re
import logging
import requests
import random
import textwrap
from pathlib import Path
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip, TextClip
)
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np

# Fix Pillow ANTIALIAS deprecation (Pillow >= 10.0)
if not hasattr(__import__("PIL").Image, "ANTIALIAS"):
    __import__("PIL").Image.ANTIALIAS = __import__("PIL").Image.LANCZOS

log = logging.getLogger(__name__)

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Dark cinematic background music (royalty-free URLs - replace with your own)
BACKGROUND_MUSIC = [
    "https://www.soundjay.com/misc/sounds/dark-ambient-01.mp3",  # placeholder
]

# Thumbnail styles
THUMBNAIL_COLORS = [
    {"bg": "#0a0a0a", "accent": "#FF0000", "text": "#FFFFFF"},
    {"bg": "#1a0a2e", "accent": "#FF6B00", "text": "#FFFFFF"},
    {"bg": "#0d1b2a", "accent": "#00D4FF", "text": "#FFFFFF"},
]


class VideoProducer:
    def __init__(self):
        self.pexels_key = PEXELS_API_KEY
        self.output_dir = Path("/tmp/video_output")
        self.output_dir.mkdir(exist_ok=True)

    # ─── Stock Footage ───────────────────────────────────────────────────────

    def search_pexels_videos(self, query: str, count: int = 5) -> list:
        """Fetch stock video URLs from Pexels"""
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": self.pexels_key}
        params = {
            "query": query,
            "per_page": count,
            "orientation": "landscape",
            "size": "medium"
        }
        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
            r.raise_for_status()
            videos = r.json().get("videos", [])
            links = []
            for v in videos:
                for file in v.get("video_files", []):
                    if file.get("quality") == "hd" and file.get("width", 0) >= 1280:
                        links.append(file["link"])
                        break
            return links[:count]
        except Exception as e:
            log.warning(f"Pexels search failed for '{query}': {e}")
            return []

    def search_pexels_vertical(self, query: str, count: int = 5) -> list:
        """Fetch vertical stock videos for Shorts"""
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": self.pexels_key}
        params = {
            "query": query,
            "per_page": count,
            "orientation": "portrait"
        }
        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
            r.raise_for_status()
            videos = r.json().get("videos", [])
            links = []
            for v in videos:
                for file in v.get("video_files", []):
                    if file.get("width", 0) <= file.get("height", 1):
                        links.append(file["link"])
                        break
            return links[:count]
        except Exception as e:
            log.warning(f"Pexels vertical search failed: {e}")
            return []

    def download_video(self, url: str, path: str) -> str:
        """Download a video file"""
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return path

    # ─── Video Assembly ───────────────────────────────────────────────────────

    def build_video(self, audio_path: str, video_urls: list, output_path: str,
                    shorts: bool = False) -> str:
        """Assemble video from audio + stock clips"""
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration

        target_w, target_h = (1080, 1920) if shorts else (1920, 1080)
        clips = []

        for i, url in enumerate(video_urls):
            clip_path = f"/tmp/clip_{i}.mp4"
            try:
                self.download_video(url, clip_path)
                clip = VideoFileClip(clip_path)

                # Resize & crop to target aspect ratio
                clip = clip.resize(height=target_h) if shorts else clip.resize(width=target_w)
                clip = clip.crop(
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                    width=target_w,
                    height=target_h
                )

                # Loop clip if too short
                segment_duration = total_duration / len(video_urls)
                if clip.duration < segment_duration:
                    clip = clip.loop(duration=segment_duration)
                else:
                    clip = clip.subclip(0, segment_duration)

                # Slight brightness reduction for dark cinematic feel
                clip = clip.fl_image(lambda f: (f * 0.75).astype(np.uint8))
                clips.append(clip)

            except Exception as e:
                log.warning(f"Failed to process clip {i}: {e}")
                # Use black fallback clip
                clips.append(ColorClip(size=(target_w, target_h),
                                       color=(10, 10, 10),
                                       duration=total_duration / len(video_urls)))

        if not clips:
            clips = [ColorClip(size=(target_w, target_h),
                               color=(10, 10, 10),
                               duration=total_duration)]

        final_video = concatenate_videoclips(clips, method="compose")
        final_video = final_video.subclip(0, total_duration)
        final_video = final_video.set_audio(audio)

        final_video.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="fast",
            logger=None
        )

        log.info(f"✅ Video assembled: {output_path}")
        return output_path

    # ─── Thumbnail ────────────────────────────────────────────────────────────

    def create_thumbnail(self, title: str, output_path: str) -> str:
        """Create eye-catching thumbnail with PIL"""
        style = random.choice(THUMBNAIL_COLORS)
        img = Image.new("RGB", (1280, 720), color=style["bg"])
        draw = ImageDraw.Draw(img)

        # Gradient overlay
        for y in range(720):
            alpha = int(30 * (y / 720))
            draw.line([(0, y), (1280, y)], fill=(alpha, 0, 0))

        # Red accent bar on left
        draw.rectangle([0, 0, 8, 720], fill=style["accent"])

        # "TRUE STORY" badge
        draw.rectangle([60, 40, 280, 90], fill=style["accent"])
        try:
            badge_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        except Exception:
            badge_font = title_font = sub_font = ImageFont.load_default()

        draw.text((80, 48), "● TRUE STORY", fill="white", font=badge_font)

        # Main title (word wrap)
        words = title.upper()
        lines = textwrap.wrap(words, width=20)[:3]
        y_start = 150
        for line in lines:
            draw.text((60, y_start), line, fill=style["text"], font=title_font)
            # Shadow effect
            draw.text((63, y_start + 3), line, fill=(0, 0, 0, 100), font=title_font)
            y_start += 85

        # Bottom bar
        draw.rectangle([0, 650, 1280, 720], fill=style["accent"])
        draw.text((60, 658), "WATCH TILL THE END 👇", fill="white", font=sub_font)

        # Add noise for cinematic feel
        arr = np.array(img).astype(np.float32)
        noise = np.random.normal(0, 8, arr.shape)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

        img.save(output_path, "JPEG", quality=95)
        log.info(f"✅ Thumbnail created: {output_path}")
        return output_path

    # ─── Main Entry ──────────────────────────────────────────────────────────

    def produce(self, script_data: dict, shorts: bool = False) -> tuple:
        """Full video production pipeline"""
        topic = script_data["topic"]
        trend = topic["trend"]

        # Search for relevant stock footage
        search_queries = [trend, topic["category"], "dark mystery", "crime scene"]
        all_urls = []

        for query in search_queries[:3]:
            if shorts:
                urls = self.search_pexels_vertical(query, count=3)
            else:
                urls = self.search_pexels_videos(query, count=3)
            all_urls.extend(urls)
            if len(all_urls) >= 6:
                break

        if not all_urls:
            log.warning("No stock footage found, using color clips")

        suffix = "shorts" if shorts else "main"
        video_path = str(self.output_dir / f"video_{suffix}.mp4")
        thumb_path = str(self.output_dir / f"thumbnail_{suffix}.jpg")

        # Build video
        self.build_video(
            audio_path=script_data["audio_path"],
            video_urls=all_urls[:6],
            output_path=video_path,
            shorts=shorts
        )

        # Create thumbnail
        self.create_thumbnail(
            title=script_data["title"][:50],
            output_path=thumb_path
        )

        return video_path, thumb_path
