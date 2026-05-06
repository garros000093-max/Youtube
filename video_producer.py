"""
Video Producer - Uses static images with Ken Burns effect (no Pexels video issues)
"""

import os
import subprocess
import logging
import requests
import random
import re
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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


class VideoProducer:
    def __init__(self):
        self.output_dir = Path("/tmp/video_output")
        self.output_dir.mkdir(exist_ok=True)

    def _clean_query(self, text):
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        text = re.sub(r'\(.*?\)|\[.*?\]', '', text)
        words = [w for w in text.split() if len(w) > 3]
        return ' '.join(words[:3]).strip() or "nature landscape"

    def search_pexels_images(self, query, count=8, portrait=False):
        """Search Pexels PHOTOS (not videos) — much more reliable"""
        if not PEXELS_API_KEY:
            return []
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={
                    "query": query,
                    "per_page": count,
                    "orientation": "portrait" if portrait else "landscape"
                },
                timeout=15
            )
            r.raise_for_status()
            photos = r.json().get("photos", [])
            links = []
            for p in photos:
                src = p.get("src", {})
                # Use large2x for high quality
                url = src.get("large2x") or src.get("large") or src.get("medium")
                if url:
                    links.append(url)
            log.info(f"Pexels images for '{query}': {len(links)} found")
            return links
        except Exception as e:
            log.warning(f"Pexels images failed: {e}")
            return []

    def download_image(self, url, path):
        try:
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(32768):
                    f.write(chunk)
            return os.path.getsize(path) > 1000
        except Exception as e:
            log.warning(f"Image download failed: {e}")
            return False

    def prepare_image(self, img_path, out_path, W, H):
        """Resize and crop image to exact target dimensions"""
        try:
            img = Image.open(img_path).convert("RGB")
            # Scale to fill
            ratio = max(W / img.width, H / img.height)
            new_w = int(img.width * ratio) + 2
            new_h = int(img.height * ratio) + 2
            img = img.resize((new_w, new_h), Image.LANCZOS)
            # Center crop
            x = (new_w - W) // 2
            y = (new_h - H) // 2
            img = img.crop((x, y, x + W, y + H))
            img.save(out_path, "JPEG", quality=95)
            return True
        except Exception as e:
            log.warning(f"Image prepare failed: {e}")
            return False

    def build_video(self, audio_path, image_urls, output_path, shorts=False):
        duration = get_duration(audio_path)
        log.info(f"Audio: {duration:.1f}s")

        W, H = (1080, 1920) if shorts else (1920, 1080)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Download and prepare images
        prepared = []
        for i, url in enumerate(image_urls[:12]):
            raw = f"/tmp/img_{i}.jpg"
            prep = f"/tmp/prep_{i}.jpg"
            if self.download_image(url, raw) and self.prepare_image(raw, prep, W, H):
                prepared.append(prep)

        log.info(f"Prepared {len(prepared)} images")

        if not prepared:
            # Generate colored gradient images
            log.warning("No images — generating gradient backgrounds")
            colors = [
                (26, 10, 46), (10, 26, 46), (46, 10, 10),
                (10, 46, 26), (30, 20, 50), (50, 20, 30)
            ]
            for i, color in enumerate(colors):
                prep = f"/tmp/prep_{i}.jpg"
                img = Image.new("RGB", (W, H), color)
                draw = ImageDraw.Draw(img)
                # Add subtle gradient effect
                for y in range(0, H, 4):
                    alpha = int(30 * (1 - y/H))
                    draw.rectangle([0, y, W, y+4],
                        fill=tuple(min(255, c + alpha) for c in color))
                img.save(prep, "JPEG", quality=90)
                prepared.append(prep)

        # Each image shown for equal duration
        img_duration = duration / len(prepared)

        # Create concat input file
        concat_file = "/tmp/images.txt"
        with open(concat_file, "w") as f:
            for prep in prepared:
                f.write(f"file '{prep}'\n")
                f.write(f"duration {img_duration:.2f}\n")
            # Repeat last image
            f.write(f"file '{prepared[-1]}'\n")

        # Build video with Ken Burns zoom effect
        log.info("Building video with slideshow...")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-i", audio_path,
            "-t", str(duration),
            # Zoom effect
            "-vf", (
                f"scale={W*2}:{H*2},"
                f"zoompan=z='min(zoom+0.0008,1.3)':d={int(img_duration*25)}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={W}x{H}:fps=25,"
                f"format=yuv420p"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-map", "0:v:0", "-map", "1:a:0",
            output_path
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

        if r.returncode == 0 and os.path.exists(output_path) \
           and os.path.getsize(output_path) > 50000:
            mb = os.path.getsize(output_path) / 1024 / 1024
            log.info(f"✅ Video built ({mb:.1f} MB)")
            return output_path

        # Simpler fallback without zoom effect
        log.warning(f"Ken Burns failed — trying simple slideshow")
        cmd2 = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-i", audio_path,
            "-t", str(duration),
            "-vf", f"scale={W}:{H},format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-map", "0:v:0", "-map", "1:a:0",
            output_path
        ]
        r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=600)

        if r2.returncode == 0 and os.path.exists(output_path) \
           and os.path.getsize(output_path) > 50000:
            mb = os.path.getsize(output_path) / 1024 / 1024
            log.info(f"✅ Simple slideshow built ({mb:.1f} MB)")
        else:
            log.error(f"❌ All video methods failed: {r2.stderr[-300:]}")

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
        draw.text((100, H-110), "WATCH TILL THE END  👇",
                  fill="white", font=_find_font(68))
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
            "true crime story":         "crime investigation dark",
            "scary reddit story":       "dark forest night",
            "mysterious disappearance": "missing person forest",
            "unsolved mystery":         "detective mystery",
            "dark secret revealed":     "shadow secret dark",
            "survival story":           "wilderness nature",
            "paranormal experience":    "haunted dark",
            "shocking true story":      "dramatic cinematic",
        }
        visual = cat_map.get(category, "mystery dramatic dark")

        urls = []
        for q in [visual, trend, "cinematic landscape", "dramatic sky"]:
            urls += self.search_pexels_images(q, count=4, portrait=shorts)
            if len(urls) >= 10: break

        sfx = "shorts" if shorts else "main"
        vp  = str(self.output_dir / f"video_{sfx}.mp4")
        tp  = str(self.output_dir / f"thumb_{sfx}.jpg")

        self.build_video(script_data["audio_path"], urls, vp, shorts)
        self.create_thumbnail(script_data["title"][:50], tp)
        return vp, tp
