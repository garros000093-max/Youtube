"""
Video Producer - Fixed AAC encoder issue
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

def get_duration(path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=15
        )
        return float(r.stdout.strip())
    except:
        return 60.0

def ffmpeg_test_audio():
    """Test which audio encoder works on this system"""
    for enc in ["aac", "libfdk_aac", "ac3", "mp2"]:
        r = subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", "1", "-c:a", enc, "-f", "null", "-"],
            capture_output=True, timeout=10
        )
        if r.returncode == 0:
            log.info(f"Audio encoder: {enc}")
            return enc
    return "aac"


class VideoProducer:
    def __init__(self):
        self.output_dir = Path("/tmp/video_output")
        self.output_dir.mkdir(exist_ok=True)
        self.audio_enc = ffmpeg_test_audio()

    def _clean_query(self, text):
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
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
                files = sorted(v.get("video_files", []),
                               key=lambda f: f.get("width", 0))
                # Pick lowest resolution that's still usable (faster + more compatible)
                for f in files:
                    if f.get("width", 0) >= 640:
                        links.append(f["link"])
                        break
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
            return os.path.getsize(path) > 5000
        except Exception as e:
            log.warning(f"Download: {e}")
            return False

    def build_video(self, audio_path, video_urls, output_path, shorts=False):
        duration = get_duration(audio_path)
        log.info(f"Audio: {duration:.1f}s | Audio encoder: {self.audio_enc}")

        W, H = (1080, 1920) if shorts else (1920, 1080)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Convert audio to WAV first (most compatible)
        wav_path = "/tmp/voiceover.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", audio_path,
            "-ar", "44100", "-ac", "1", wav_path
        ], capture_output=True, timeout=60)

        audio_input = wav_path if os.path.exists(wav_path) else audio_path

        for i, url in enumerate(video_urls[:8]):
            raw = f"/tmp/clip_{i}.mp4"
            if not self.download(url, raw):
                continue

            log.info(f"Trying clip {i+1}...")
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", raw,
                "-i", audio_input,
                "-t", str(duration),
                "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                       f"crop={W}:{H},setsar=1,format=yuv420p",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "20",
                "-c:a", self.audio_enc,
                "-b:a", "128k",
                "-movflags", "+faststart",
                "-map", "0:v:0",
                "-map", "1:a:0",
                output_path
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if r.returncode == 0 and os.path.exists(output_path) \
               and os.path.getsize(output_path) > 50000:
                mb = os.path.getsize(output_path) / 1024 / 1024
                log.info(f"✅ Video built ({mb:.1f} MB)")
                return output_path
            else:
                log.warning(f"Clip {i+1} failed")
                if os.path.exists(output_path):
                    os.remove(output_path)

        # Fallback: color background
        log.warning("All clips failed — color background")
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x1a1a2e:size={W}x{H}:rate=30:duration={duration}",
            "-i", audio_input,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-vf", "format=yuv420p",
            "-c:a", self.audio_enc, "-b:a", "128k",
            "-movflags", "+faststart",
            "-map", "0:v:0", "-map", "1:a:0",
            output_path
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            log.info("✅ Color bg video built")
        else:
            log.error(f"❌ All failed: {r.stderr[-300:]}")

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
        y, f = 240, _find_font(136)
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
        log.info(f"✅ Thumbnail saved")
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
        visual = cat_map.get(category, "nature landscape")

        urls = []
        for q in [visual, trend, "landscape aerial", "nature timelapse"]:
            urls += self.search_pexels(q, count=4, portrait=shorts)
            if len(urls) >= 8: break

        sfx = "shorts" if shorts else "main"
        vp  = str(self.output_dir / f"video_{sfx}.mp4")
        tp  = str(self.output_dir / f"thumb_{sfx}.jpg")

        self.build_video(script_data["audio_path"], urls, vp, shorts)
        self.create_thumbnail(script_data["title"][:50], tp)
        return vp, tp
