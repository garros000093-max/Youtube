"""
Video Producer - Assembles video using ffmpeg directly (no MoviePy)
Stock footage from Pexels + voiceover + thumbnail via Pillow
"""

import os
import subprocess
import logging
import requests
import random
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

log = logging.getLogger(__name__)

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

THUMBNAIL_STYLES = [
    {"bg": (10, 10, 10),    "accent": (220, 0, 0),   "text": (255, 255, 255)},
    {"bg": (26, 10, 46),    "accent": (255, 107, 0),  "text": (255, 255, 255)},
    {"bg": (13, 27, 42),    "accent": (0, 212, 255),  "text": (255, 255, 255)},
]

# Font search paths (in order of preference)
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]


def _find_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


class VideoProducer:
    def __init__(self):
        self.output_dir = Path("/tmp/video_output")
        self.output_dir.mkdir(exist_ok=True)

    # ─── Pexels ──────────────────────────────────────────────────────────────

    def search_pexels(self, query: str, count: int = 4, portrait: bool = False) -> list:
        if not PEXELS_API_KEY:
            log.warning("PEXELS_API_KEY not set — skipping stock footage")
            return []
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": query,
            "per_page": count,
            "orientation": "portrait" if portrait else "landscape"
        }
        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
            r.raise_for_status()
            links = []
            for v in r.json().get("videos", []):
                for f in v.get("video_files", []):
                    w, h = f.get("width", 0), f.get("height", 0)
                    if portrait and w < h and w >= 360:
                        links.append(f["link"]); break
                    elif not portrait and w >= 1280:
                        links.append(f["link"]); break
            return links[:count]
        except Exception as e:
            log.warning(f"Pexels failed for '{query}': {e}")
            return []

    def download_video(self, url: str, path: str) -> bool:
        try:
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        except Exception as e:
            log.warning(f"Download failed: {e}")
            return False

    # ─── ffmpeg helpers ───────────────────────────────────────────────────────

    def run_ffmpeg(self, cmd: list) -> bool:
        """Run ffmpeg with suppressed verbose output"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error"] + cmd,
                capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                log.warning(f"ffmpeg error: {result.stderr[-500:]}")
            return result.returncode == 0
        except Exception as e:
            log.warning(f"ffmpeg failed: {e}")
            return False

    def get_audio_duration(self, audio_path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, text=True, timeout=30
            )
            return float(result.stdout.strip())
        except Exception:
            return 60.0

    def build_video(self, audio_path: str, video_urls: list,
                    output_path: str, shorts: bool = False) -> str:
        """Assemble video using ffmpeg directly"""
        duration = self.get_audio_duration(audio_path)
        log.info(f"Audio duration: {duration:.1f}s")
        target_w, target_h = (1080, 1920) if shorts else (1920, 1080)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Try to download and use first working clip
        video_input = None
        for i, url in enumerate(video_urls[:6]):
            raw = f"/tmp/raw_{i}.mp4"
            if not self.download_video(url, raw):
                continue
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-i", raw],
                capture_output=True, timeout=15
            )
            if result.returncode == 0:
                video_input = raw
                log.info(f"Using clip {i+1}")
                break

        if video_input:
            vf = (
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h}"
            )
            self.run_ffmpeg([
                "-stream_loop", "-1", "-i", video_input,
                "-i", audio_path,
                "-vf", vf,
                "-t", str(duration),
                "-r", "30",
                # Use libx264 with explicit pixel format to suppress encoder warnings
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-shortest",
                output_path
            ])
        else:
            log.warning("No valid clips — using black video")
            self.run_ffmpeg([
                "-f", "lavfi",
                "-i", f"color=c=black:size={target_w}x{target_h}:rate=30",
                "-i", audio_path,
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-shortest",
                output_path
            ])

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            log.info(f"✅ Video built: {output_path}")
        else:
            log.error(f"❌ Video file missing or empty: {output_path}")
        return output_path

    # ─── Thumbnail ────────────────────────────────────────────────────────────

    def create_thumbnail(self, title: str, output_path: str) -> str:
        style = random.choice(THUMBNAIL_STYLES)
        img = Image.new("RGB", (1280, 720), color=style["bg"])
        draw = ImageDraw.Draw(img)

        # Left accent bar
        draw.rectangle([0, 0, 8, 720], fill=style["accent"])

        # Top badge
        draw.rectangle([30, 30, 260, 80], fill=style["accent"])

        font_sm = _find_font(26)
        font_lg = _find_font(68)
        font_md = _find_font(34)

        draw.text((50, 42), "● TRUE STORY", fill="white", font=font_sm)

        # Title lines
        lines = textwrap.wrap(title.upper(), width=22)[:3]
        y = 120
        for line in lines:
            draw.text((52, y + 3), line, fill=(0, 0, 0), font=font_lg)
            draw.text((50, y), line, fill=style["text"], font=font_lg)
            y += 82

        # Bottom bar
        draw.rectangle([0, 650, 1280, 720], fill=style["accent"])
        draw.text((50, 660), "WATCH TILL THE END  👇", fill="white", font=font_md)

        # Subtle noise
        arr = np.array(img).astype(np.float32)
        arr = np.clip(arr + np.random.normal(0, 6, arr.shape), 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

        img.save(output_path, "JPEG", quality=95)
        log.info(f"✅ Thumbnail: {output_path}")
        return output_path

    # ─── Main ─────────────────────────────────────────────────────────────────

    def _clean_pexels_query(self, text: str) -> str:
        """Extract simple English keywords for Pexels — strip special chars, Korean, etc."""
        import re
        # Remove non-ASCII characters (Korean, Chinese, etc.)
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        # Remove content inside brackets/parens
        text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
        # Remove quotes, special chars
        text = re.sub(r"[\"'`|#@!$%^&*+=<>{}\\]", '', text)
        # Remove short words and single chars
        words = [w for w in text.split() if len(w) > 3]
        # Take first 3 meaningful words max
        return ' '.join(words[:3]).strip() or "mystery suspense dark"

    def produce(self, script_data: dict, shorts: bool = False) -> tuple:
        topic = script_data["topic"]

        # Build clean, simple Pexels queries (2-3 English words max)
        category = topic.get("category", "mystery")
        raw_trend = topic.get("trend", "")
        clean_trend = self._clean_pexels_query(raw_trend)

        # Map category to visual search terms Pexels understands well
        category_visual_map = {
            "true crime story":         "crime investigation dark",
            "scary reddit story":        "dark forest night scary",
            "mysterious disappearance":  "missing person search",
            "unsolved mystery":          "detective investigation clue",
            "dark secret revealed":      "secret shadow mystery",
            "survival story":            "wilderness survival nature",
            "paranormal experience":     "haunted dark ghost",
            "shocking true story":       "dramatic dark cinematic",
        }
        visual_query = category_visual_map.get(category, "mystery suspense dramatic")

        queries = [visual_query, clean_trend if len(clean_trend) > 5 else "dark mystery", "cinematic dramatic"]

        urls = []
        for q in queries[:3]:
            urls += self.search_pexels(q, count=3, portrait=shorts)
            if len(urls) >= 6:
                break

        suffix = "shorts" if shorts else "main"
        video_path = str(self.output_dir / f"video_{suffix}.mp4")
        thumb_path = str(self.output_dir / f"thumb_{suffix}.jpg")

        self.build_video(script_data["audio_path"], urls, video_path, shorts)
        self.create_thumbnail(script_data["title"][:50], thumb_path)

        return video_path, thumb_path
