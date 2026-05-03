"""
Script Generator - Writes viral story scripts + generates American voiceover
Uses GPT-4o for writing and OpenAI TTS for voice (no proxy issues)
"""

import os
import re
import json
import logging
import requests
from openai import OpenAI

log = logging.getLogger(__name__)


class ScriptGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def write_script(self, topic: dict, shorts: bool = False) -> str:
        if shorts:
            prompt = f"""Write a 45-second YouTube Shorts script about: "{topic['trend']}"
Style: Shocking, fast-paced, hook in first 3 seconds
Format: Just the narration text, no stage directions
Hook: Start with "Wait until you hear this..." or similar
End with: A cliffhanger or shocking revelation
Length: Exactly 100-120 words
Voice: American, conversational, dramatic"""
        else:
            prompt = f"""Write a 8-10 minute YouTube video script about: "{topic['title']}"
Topic: {topic['trend']}
Category: {topic['category']}
Requirements:
- Hook in first 15 seconds (make viewer NEED to keep watching)
- 5-7 dramatic segments, each building tension
- Use "But here's where it gets DARK..." type transitions
- End with a shocking revelation or twist
- American English, conversational but dramatic
- Include natural pauses with "..."
- Target audience: Americans 18-35
- Length: 1200-1500 words (narration only, no stage directions)
Start directly with the hook, no introduction."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a viral YouTube scriptwriter specializing in true crime and mystery content for American audiences. Your scripts get millions of views."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=2000
        )
        return response.choices[0].message.content

    def generate_seo_metadata(self, topic: dict, script: str) -> dict:
        prompt = f"""Based on this YouTube script, generate SEO metadata optimized for American viewers.
Topic: {topic['trend']}
Script preview: {script[:300]}...
Return ONLY a JSON object with:
{{
  "title": "Clickbait but honest title (max 70 chars)",
  "description": "SEO description with keywords, 200-300 words, includes timestamps",
  "tags": ["tag1", "tag2"] (30 tags, mix of broad and specific),
  "category": "22"
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=800
        )
        text = re.sub(r"```json|```", "", response.choices[0].message.content).strip()
        try:
            return json.loads(text)
        except Exception:
            return {
                "title": topic["title"][:70],
                "description": f"The shocking true story of {topic['trend']}.",
                "tags": topic["keywords"] + ["true story", "shocking", "mystery", "viral"],
                "category": "22"
            }

    def text_to_speech(self, text: str, output_path: str, shorts: bool = False) -> str:
        """Convert script to American voice using OpenAI TTS"""

        # OpenAI TTS voices - all American English
        voice = "onyx" if not shorts else "nova"
        # onyx = deep dramatic male, nova = energetic female

        # OpenAI TTS max 4096 chars per request — split if needed
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

        log.info(f"Generating voiceover with OpenAI TTS (voice: {voice}, chunks: {len(chunks)})...")

        # Generate each chunk and combine
        audio_parts = []
        for i, chunk in enumerate(chunks):
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=chunk,
                speed=1.05  # Slightly faster = more engaging
            )
            chunk_path = f"/tmp/tts_chunk_{i}.mp3"
            response.stream_to_file(chunk_path)
            audio_parts.append(chunk_path)
            log.info(f"  Chunk {i+1}/{len(chunks)} done")

        # Combine chunks if multiple
        if len(audio_parts) == 1:
            import shutil
            shutil.copy(audio_parts[0], output_path)
        else:
            # Concatenate mp3 files
            with open(output_path, "wb") as out:
                for part_path in audio_parts:
                    with open(part_path, "rb") as f:
                        out.write(f.read())

        log.info(f"✅ Voiceover saved: {output_path}")
        return output_path

    def generate(self, topic: dict, shorts: bool = False) -> dict:
        """Full pipeline: write script → metadata → voiceover"""
        script = self.write_script(topic, shorts)
        log.info(f"Script written ({len(script)} chars)")

        metadata = self.generate_seo_metadata(topic, script)

        audio_path = f"/tmp/voiceover_{'shorts' if shorts else 'main'}.mp3"
        self.text_to_speech(script, audio_path, shorts)

        return {
            "script": script,
            "audio_path": audio_path,
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "category": metadata["category"],
            "topic": topic,
            "is_shorts": shorts
        }
