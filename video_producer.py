"""
Video Producer - Simple reliable ffmpeg pipeline
"""

import os
import subprocess
import logging
import requests
import random
import re
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

log = logging.getLogger(__name__)
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

THUMBNAIL_STYLES = [
    {"bg": (10, 10, 10),  "accent": (220, 0, 0),  "text": (255, 255, 255)},
    {"bg": (26, 10, 46),  "accent": (255, 107, 0), "text": (255, 255, 255)},
    {"bg": (13, 27, 42),  "accent": (0, 212, 255), "text": (255, 255, 255)},
]

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

def _find_font(size):
    for path in FONT_PATHS:
        if os.path.exists(path):
            try: return ImageFont.truetype(path, size)
            except: continue
    return ImageFont.load_default()


class VideoProducer:
    def __init__(self):
        self.output_dir = Path("/tmp/video_output")
        self.output_dir.mkdir(exist_ok=True)

    def _clean_query(self, text):
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
        text = re.sub(r"[\"'`|#@!$%^&*]", '', text)
        words = [w for w in text.split() if len(w) > 3]
        return ' '.join(words[:3]).strip() or "nature landscape"

    def search_pexels(self, query, count=5, portrait=False):
        if not PEXELS_API_KEY:
            return []
        try:
            r = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": query, "per_page": count,
                        "orientation": "portrait" if portrait else "landscape"},
                timeout=15
            )
            r.raise_for_status()
            links = []
            for v in r.json().get("videos", []):
                # Get SD file (easier to process) — around 1280x720
                files = v.get("video_files", [])
                # Sort by resolution — pick medium quality for reliability
                files_sorted = sorted(files, key=lambda f: abs(f.get("width",0) - 1280))
                if files_sorted:
                    links.append(files_sorted[0]["link"])
            return links[:count]
        except Exception as e:
            log.warning(f"Pexels: {e}")
            return []

    def download(self, url, path):
        try:
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(32768):
                    f.write(chunk)
            size = os.path.getsize(path)
            return size > 5000
        except Exception as e:
            log.warning(f"Download: {e}")
            return False

    def get_duration(self, path):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=15
            )
            return float(r.stdout.strip())
        except:
            return 60.0

    def build_video(self, audio_path, video_urls, output_path, shorts=False):
        duration = self.get_duration(audio_path)
        log.info(f"Audio: {duration:.1f}s")

        W, H = (1080, 1920) if shorts else (1920, 1080)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Try each clip with a simple, direct ffmpeg command
        for i, url in enumerate(video_urls[:8]):
            raw = f"/tmp/clip_{i}.mp4"
            if not self.download(url, raw):
                continue

            log.info(f"Trying clip {i+1}...")
            out = output_path
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", raw,
                "-i", audio_path,
                "-t", str(duration),
                "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart",
                "-map", "0:v:0", "-map", "1:a:0",
                out
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 50000:
                mb = os.path.getsize(out) / 1024 / 1024
                log.info(f"✅ Video built with clip {i+1} ({mb:.1f} MB)")
                return output_path
            else:
                log.warning(f"Clip {i+1} failed: {r.stderr[-200:]}")
                if os.path.exists(out):
                    os.remove(out)

        # All clips failed — solid color background
        log.warning("All clips failed — using color background")
        color = "0x1a1a2e" if not shorts else "0x0d0d1a"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color}:size={W}x{H}:rate=30:duration={duration}",
            "-i", audio_path,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            "-map", "0:v:0", "-map", "1:a:0",
            output_path
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            log.info("✅ Color background video built")
        else:
            log.error(f"❌ Final fallback failed: {r.stderr[-300:]}")

        return output_path

    def create_thumbnail(self, title, output_path):
        style = random.choice(THUMBNAIL_STYLES)
        W, H = 2560, 1440
        img = Image.new("RGB", (W, H), color=style["bg"])
        draw = ImageDraw.Draw(img)

        draw.rectangle([0, 0, 16, H], fill=style["accent"])
        draw.rectangle([60, 60, 520, 160], fill=style["accent"])
        draw.text((100, 84), "● TRUE STORY", fill="white", font=_find_font(52))

        lines = textwrap.wrap(title.upper(), width=20)[:3]
        y = 240
        f = _find_font(136)
        for line in lines:
            draw.text((104, y+6), line, fill=(0,0,0), font=f)
            draw.text((100, y), line, fill=style["text"], font=f)
            y += 164

        draw.rectangle([0, H-140, W, H], fill=style["accent"])
        draw.text((100, H-110), "WATCH TILL THE END  👇", fill="white", font=_find_font(68))

        try:
            arr = np.array(img).astype(np.float32)
            arr = np.clip(arr + np.random.normal(0, 4, arr.shape), 0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
        except: pass

        img = img.resize((1280, 720), Image.LANCZOS)
        img.save(output_path, "JPEG", quality=97, subsampling=0)
        log.info(f"✅ Thumbnail: {output_path}")
        return output_path

    def produce(self, script_data, shorts=False):
        topic    = script_data["topic"]
        category = topic.get("category", "mystery")
        trend    = self._clean_query(topic.get("trend", ""))

        cat_map = {
            "true crime story":         "crime investigation",
            "scary reddit story":       "dark forest night",
            "mysterious disappearance": "missing person",
            "unsolved mystery":         "detective mystery",
            "dark secret revealed":     "shadow secret",
            "survival story":           "wilderness survival",
            "paranormal experience":    "haunted ghost",
            "shocking true story":      "dramatic cinematic",
        }
        visual = cat_map.get(category, "mystery dramatic")

        urls = []
        for q in [visual, trend, "cinematic nature", "landscape aerial"]:
            urls += self.search_pexels(q, count=4, portrait=shorts)
            if len(urls) >= 8: break

        sfx = "shorts" if shorts else "main"
        vp  = str(self.output_dir / f"video_{sfx}.mp4")
        tp  = str(self.output_dir / f"thumb_{sfx}.jpg")

        self.build_video(script_data["audio_path"], urls, vp, shorts)
        self.create_thumbnail(script_data["title"][:50], tp)
        return vp, tp
