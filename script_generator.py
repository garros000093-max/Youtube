"""
Script Generator - Viral story scripts + American voiceover
Optimized for maximum engagement
"""

import os
import re
import json
import logging
import requests
import shutil
from openai import OpenAI

log = logging.getLogger(__name__)


class ScriptGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def write_script(self, topic: dict, shorts: bool = False) -> str:
        if shorts:
            prompt = f"""Write a 2-minute YouTube Shorts script about: "{topic['trend']}"

RULES:
- Hook in the FIRST 3 seconds — must stop the scroll immediately
- Start with: "You won't believe what happened..." or "This will shock you..." or similar
- Build tension every 15 seconds
- End with a shocking twist or cliffhanger that makes them want more
- Short punchy sentences. No long paragraphs.
- American English, dramatic, fast-paced
- Length: EXACTLY 250-280 words (for ~2 minutes at normal pace)
- No stage directions, just narration text

Write ONLY the narration. Start immediately with the hook."""

        else:
            prompt = f"""Write a 10-12 minute YouTube video script about: "{topic['title']}"
Topic: {topic['trend']}
Category: {topic['category']}

RULES:
- Hook in first 15 seconds — make the viewer NEED to keep watching
- 6-8 dramatic segments, each building tension
- Use powerful transitions: "But here's where it gets DARK...", "What happened next shocked everyone...", "Nobody expected this..."
- End with a jaw-dropping revelation or twist
- American English, conversational but dramatic
- Include natural pauses with "..."
- Target: Americans 18-35 who love true crime
- Length: 1500-1800 words (narration only)

Start directly with the hook. No intro."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the world's best viral YouTube scriptwriter. "
                        "You specialize in true crime, mystery, and shocking stories "
                        "for American audiences. Your scripts get tens of millions of views. "
                        "You write in a style similar to the biggest true crime channels."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.85,
            max_tokens=2500
        )
        return response.choices[0].message.content

    def generate_seo_metadata(self, topic: dict, script: str) -> dict:
        prompt = f"""Generate viral SEO metadata for this YouTube {'Shorts' if len(script) < 500 else 'video'}.
Topic: {topic['trend']}
Script preview: {script[:400]}...

Return ONLY valid JSON:
{{
  "title": "Clickbait but honest title (max 70 chars, must create curiosity)",
  "description": "SEO description 250-350 words with keywords and timestamps",
  "tags": ["tag1", "tag2", ...] (exactly 30 tags)
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1000
        )
        text = re.sub(r"```json|```", "", response.choices[0].message.content).strip()
        try:
            return json.loads(text)
        except Exception:
            return {
                "title": topic["title"][:70],
                "description": f"The shocking true story of {topic['trend']}.",
                "tags": ["TrueCrime", "Mystery", "ShockingStory", "TrueStory",
                         "Viral", "Scary", "Horror", "Crime", "Unsolved", "Dark"],
            }

    def text_to_speech(self, text: str, output_path: str, shorts: bool = False) -> str:
        """Convert script to high-quality American voiceover"""

        # Best voices for true crime content
        # onyx = deep dramatic male (long videos)
        # nova = energetic female (shorts)
        # echo = smooth male (alternative)
        voice = "nova" if shorts else "onyx"

        # Use tts-1-hd for higher quality audio
        model = "tts-1-hd"

        # Split into chunks (max 4096 chars)
        chunks = []
        max_len = 4000
        words = text.split()
        current = []
        current_len = 0

        for word in words:
            current_len += len(word) + 1
            current.append(word)
            if current_len >= max_len:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
        if current:
            chunks.append(" ".join(current))

        log.info(f"Generating voiceover (voice: {voice}, model: {model}, chunks: {len(chunks)})...")

        audio_parts = []
        for i, chunk in enumerate(chunks):
            response = self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=chunk,
                speed=1.0  # Natural speed — more professional
            )
            chunk_path = f"/tmp/tts_chunk_{i}.mp3"
            response.stream_to_file(chunk_path)
            audio_parts.append(chunk_path)
            log.info(f"  Chunk {i+1}/{len(chunks)} done")

        if len(audio_parts) == 1:
            shutil.copy(audio_parts[0], output_path)
        else:
            with open(output_path, "wb") as out:
                for part_path in audio_parts:
                    with open(part_path, "rb") as f:
                        out.write(f.read())

        log.info(f"✅ Voiceover saved: {output_path}")
        return output_path

    def generate(self, topic: dict, shorts: bool = False) -> dict:
        script = self.write_script(topic, shorts)
        log.info(f"Script ready ({len(script)} chars)")

        metadata = self.generate_seo_metadata(topic, script)

        audio_path = f"/tmp/voiceover_{'shorts' if shorts else 'main'}.mp3"
        self.text_to_speech(script, audio_path, shorts)

        return {
            "script": script,
            "audio_path": audio_path,
            "title": metadata.get("title", topic["title"])[:100],
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
            "category": "22",
            "topic": topic,
            "is_shorts": shorts
        }
