"""
Video Producer - Maximum quality output
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
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]


def _find_font(size: int):
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

    def _clean_pexels_query(self, text: str) -> str:
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
        text = re.sub(r"[\"'`|#@!$%^&*+=<>{}\\]", '', text)
        words = [w for w in text.split() if len(w) > 3]
        return ' '.join(words[:3]).strip() or "mystery suspense"

    def search_pexels(self, query: str, count: int = 4, portrait: bool = False) -> list:
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
                files = sorted(
                    v.get("video_files", []),
                    key=lambda f: f.get("width", 0) * f.get("height", 0),
                    reverse=True
                )
                for f in files:
                    w, h = f.get("width", 0), f.get("height", 0)
                    if portrait and w < h:
                        links.append(f["link"]); break
                    elif not portrait and w >= h:
                        links.append(f["link"]); break
            return links[:count]
        except Exception as e:
            log.warning(f"Pexels failed: {e}")
            return []

    def download_video(self, url: str, path: str) -> bool:
        try:
            r = requests.get(url, stream=True, timeout=120)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
            return os.path.getsize(path) > 10000
        except Exception as e:
            log.warning(f"Download failed: {e}")
            return False

    def reencode_clip(self, input_path: str, output_path: str,
                      w: int, h: int) -> bool:
        """Re-encode clip to standard format compatible with ffmpeg processing"""
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", (
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},setsar=1,fps=30"
            ),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-an",  # Remove audio from clip (we use voiceover)
            output_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0 and os.path.getsize(output_path) > 10000
        except Exception as e:
            log.warning(f"Re-encode failed: {e}")
            return False

    def get_audio_duration(self, audio_path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                 audio_path],
                capture_output=True, text=True, timeout=30
            )
            return float(result.stdout.strip())
        except Exception:
            return 60.0

    def build_video(self, audio_path: str, video_urls: list,
                    output_path: str, shorts: bool = False) -> str:

        duration = self.get_audio_duration(audio_path)
        log.info(f"Audio duration: {duration:.1f}s")

        target_w = 1080 if shorts else 1920
        target_h = 1920 if shorts else 1080

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Download and re-encode clip to standard format
        clean_clip = None
        for i, url in enumerate(video_urls[:8]):
            raw  = f"/tmp/raw_{i}.mp4"
            norm = f"/tmp/norm_{i}.mp4"
            if not self.download_video(url, raw):
                continue
            log.info(f"Re-encoding clip {i+1}...")
            if self.reencode_clip(raw, norm, target_w, target_h):
                clean_clip = norm
                log.info(f"✅ Clip {i+1} ready")
                break
            else:
                log.warning(f"Clip {i+1} re-encode failed, trying next...")

        if clean_clip:
            # Merge clean clip (looped) with audio
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", clean_clip,
                "-i", audio_path,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "16",
                "-profile:v", "high",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-movflags", "+faststart",
                output_path
            ]
        else:
            log.warning("No valid clips — black background")
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c=0x1a1a2e:size={target_w}x{target_h}:rate=30:duration={duration}",
                "-i", audio_path,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "16",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-movflags", "+faststart",
                output_path
            ]

        log.info("Building final video...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

        if result.returncode != 0:
            log.warning(f"ffmpeg error: {result.stderr[-500:]}")

        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            mb = os.path.getsize(output_path) / 1024 / 1024
            log.info(f"✅ Video ready: {output_path} ({mb:.1f} MB)")
        else:
            log.error("❌ Video build failed")

        return output_path

    def create_thumbnail(self, title: str, output_path: str) -> str:
        style = random.choice(THUMBNAIL_STYLES)
        W, H = 2560, 1440
        img = Image.new("RGB", (W, H), color=style["bg"])
        draw = ImageDraw.Draw(img)

        draw.rectangle([0, 0, 16, H], fill=style["accent"])
        draw.rectangle([60, 60, 520, 160], fill=style["accent"])

        font_badge = _find_font(52)
        font_title = _find_font(136)
        font_sub   = _find_font(68)

        draw.text((100, 84), "● TRUE STORY", fill="white", font=font_badge)

        lines = textwrap.wrap(title.upper(), width=20)[:3]
        y = 240
        for line in lines:
            draw.text((104, y + 6), line, fill=(0, 0, 0), font=font_title)
            draw.text((100, y), line, fill=style["text"], font=font_title)
            y += 164

        draw.rectangle([0, H - 140, W, H], fill=style["accent"])
        draw.text((100, H - 110), "WATCH TILL THE END  👇", fill="white", font=font_sub)

        try:
            arr = np.array(img).astype(np.float32)
            arr = np.clip(arr + np.random.normal(0, 4, arr.shape), 0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
        except Exception:
            pass

        img = img.resize((1280, 720), Image.LANCZOS)
        img.save(output_path, "JPEG", quality=97, subsampling=0)
        log.info(f"✅ Thumbnail: {output_path}")
        return output_path

    def produce(self, script_data: dict, shorts: bool = False) -> tuple:
        topic    = script_data["topic"]
        category = topic.get("category", "mystery")
        raw_trend = topic.get("trend", "")
        clean_trend = self._clean_pexels_query(raw_trend)

        category_visual_map = {
            "true crime story":         "crime investigation dark",
            "scary reddit story":       "dark forest night scary",
            "mysterious disappearance": "missing person search",
            "unsolved mystery":         "detective clue mystery",
            "dark secret revealed":     "secret shadow dark",
            "survival story":           "wilderness survival nature",
            "paranormal experience":    "haunted ghost dark",
            "shocking true story":      "dramatic cinematic dark",
        }
        visual_query = category_visual_map.get(category, "mystery suspense dramatic")

        urls = []
        for q in [visual_query, clean_trend, "cinematic dark", "suspense thriller"]:
            urls += self.search_pexels(q, count=4, portrait=shorts)
            if len(urls) >= 8:
                break

        suffix = "shorts" if shorts else "main"
        video_path = str(self.output_dir / f"video_{suffix}.mp4")
        thumb_path = str(self.output_dir / f"thumb_{suffix}.jpg")

        self.build_video(script_data["audio_path"], urls, video_path, shorts)
        self.create_thumbnail(script_data["title"][:50], thumb_path)

        return video_path, thumb_path
