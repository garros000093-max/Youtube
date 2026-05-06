"""
Video Producer - Assembles video using ffmpeg
Stock footage from Pexels + voiceover + thumbnail via Pillow
Maximum quality output
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
    {"bg": (10, 10, 10),    "accent": (220, 0, 0),   "text": (255, 255, 255)},
    {"bg": (26, 10, 46),    "accent": (255, 107, 0),  "text": (255, 255, 255)},
    {"bg": (13, 27, 42),    "accent": (0, 212, 255),  "text": (255, 255, 255)},
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
        return ' '.join(words[:3]).strip() or "mystery suspense dark"

    def search_pexels(self, query: str, count: int = 4, portrait: bool = False) -> list:
        if not PEXELS_API_KEY:
            return []
        try:
            r = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={
                    "query": query,
                    "per_page": count,
                    "orientation": "portrait" if portrait else "landscape"
                },
                timeout=15
            )
            r.raise_for_status()
            links = []
            for v in r.json().get("videos", []):
                # Pick highest resolution file
                files = sorted(
                    v.get("video_files", []),
                    key=lambda f: f.get("width", 0) * f.get("height", 0),
                    reverse=True
                )
                for f in files:
                    w, h = f.get("width", 0), f.get("height", 0)
                    if portrait and w < h and w >= 720:
                        links.append(f["link"]); break
                    elif not portrait and w >= 1920:
                        links.append(f["link"]); break
                else:
                    # Fallback: take highest res available
                    if files:
                        links.append(files[0]["link"])
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

    def run_ffmpeg(self, cmd: list, label: str = "") -> bool:
        full_cmd = ["ffmpeg", "-y"] + cmd
        log.info(f"ffmpeg{' (' + label + ')' if label else ''}...")
        try:
            result = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=900
            )
            if result.returncode != 0:
                log.warning(f"ffmpeg error: {result.stderr[-1000:]}")
            return result.returncode == 0
        except Exception as e:
            log.warning(f"ffmpeg exception: {e}")
            return False

    def build_video(self, audio_path: str, video_urls: list,
                    output_path: str, shorts: bool = False) -> str:

        duration = self.get_audio_duration(audio_path)
        log.info(f"Audio duration: {duration:.1f}s")

        # Target resolution
        if shorts:
            target_w, target_h = 1080, 1920   # Full HD vertical
        else:
            target_w, target_h = 1920, 1080   # Full HD horizontal

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Download best available clip
        video_input = None
        for i, url in enumerate(video_urls[:8]):
            raw = f"/tmp/raw_{i}.mp4"
            if not self.download_video(url, raw):
                continue
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-i", raw],
                capture_output=True, timeout=15
            )
            if probe.returncode == 0:
                video_input = raw
                log.info(f"Using clip {i+1}: {url[:60]}")
                break

        # Video filter: scale + crop + stabilize color
        vf = (
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h},"
            f"setsar=1,"
            f"eq=brightness=0.02:contrast=1.05:saturation=1.1"  # Slight enhancement
        )

        if video_input:
            success = self.run_ffmpeg([
                "-stream_loop", "-1",
                "-i", video_input,
                "-i", audio_path,
                "-vf", vf,
                "-t", str(duration),
                "-r", "30",
                # High quality H.264
                "-c:v", "libx264",
                "-preset", "slow",        # Better compression = better quality
                "-crf", "16",             # CRF 16 = very high quality (0=lossless, 51=worst)
                "-profile:v", "high",
                "-level", "4.2",
                "-pix_fmt", "yuv420p",
                # High quality audio
                "-c:a", "aac",
                "-b:a", "192k",           # 192k audio
                "-ar", "48000",           # 48kHz sample rate
                "-movflags", "+faststart",
                output_path
            ], "HQ with clip")
        else:
            log.warning("No valid clips — black background")
            success = self.run_ffmpeg([
                "-f", "lavfi",
                "-i", f"color=c=black:size={target_w}x{target_h}:rate=30:duration={duration}",
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
            ], "HQ black bg")

        # Verify output
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            log.info(f"✅ Video built: {output_path} ({size_mb:.1f} MB)")
        else:
            log.warning("HQ failed — trying fast fallback")
            self.run_ffmpeg([
                "-f", "lavfi",
                "-i", f"color=c=black:size=1920x1080:rate=30:duration={duration}",
                "-i", audio_path,
                "-t", str(duration),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ], "fallback")

        return output_path

    def create_thumbnail(self, title: str, output_path: str) -> str:
        """4K thumbnail (3840x2160 downscaled to 1280x720 for crisp result)"""
        style = random.choice(THUMBNAIL_STYLES)

        # Create at 2x resolution then downscale for sharpness
        W, H = 2560, 1440
        img = Image.new("RGB", (W, H), color=style["bg"])
        draw = ImageDraw.Draw(img)

        # Accent bar
        draw.rectangle([0, 0, 16, H], fill=style["accent"])

        # Badge
        draw.rectangle([60, 60, 520, 160], fill=style["accent"])

        font_badge = _find_font(52)
        font_title = _find_font(136)
        font_sub   = _find_font(68)

        draw.text((100, 84), "● TRUE STORY", fill="white", font=font_badge)

        # Title
        lines = textwrap.wrap(title.upper(), width=20)[:3]
        y = 240
        for line in lines:
            # Shadow
            draw.text((104, y + 6), line, fill=(0, 0, 0), font=font_title)
            draw.text((100, y), line, fill=style["text"], font=font_title)
            y += 164

        # Bottom bar
        draw.rectangle([0, H - 140, W, H], fill=style["accent"])
        draw.text((100, H - 110), "WATCH TILL THE END  👇", fill="white", font=font_sub)

        # Noise for realism
        try:
            arr = np.array(img).astype(np.float32)
            arr = np.clip(arr + np.random.normal(0, 4, arr.shape), 0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
        except Exception:
            pass

        # Downscale to 1280x720 with LANCZOS (highest quality)
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
            "mysterious disappearance": "missing person forest",
            "unsolved mystery":         "detective investigation clue",
            "dark secret revealed":     "secret shadow mystery",
            "survival story":           "wilderness survival nature",
            "paranormal experience":    "haunted dark ghost",
            "shocking true story":      "dramatic cinematic dark",
        }
        visual_query = category_visual_map.get(category, "mystery suspense dramatic")

        urls = []
        for q in [visual_query, clean_trend, "cinematic dark dramatic", "suspense thriller"]:
            urls += self.search_pexels(q, count=4, portrait=shorts)
            if len(urls) >= 8:
                break

        suffix = "shorts" if shorts else "main"
        video_path = str(self.output_dir / f"video_{suffix}.mp4")
        thumb_path = str(self.output_dir / f"thumb_{suffix}.jpg")

        self.build_video(script_data["audio_path"], urls, video_path, shorts)
        self.create_thumbnail(script_data["title"][:50], thumb_path)

        return video_path, thumb_path
