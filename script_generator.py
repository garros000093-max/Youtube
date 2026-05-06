"""
Script Generator - Groq (free) for writing + OpenAI TTS for voice
Cost: ~$0 writing + ~$0.015/video voice = very cheap
"""

import os
import re
import json
import logging
import requests
import shutil
from openai import OpenAI

log = logging.getLogger(__name__)

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
GROQ_API_URL  = "https://api.groq.com/openai/v1/chat/completions"
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def groq_chat(messages: list, max_tokens: int = 2000) -> str:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in Railway variables")
    r = requests.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile",
              "messages": messages,
              "max_tokens": max_tokens,
              "temperature": 0.85},
        timeout=60
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


class ScriptGenerator:

    def write_script(self, topic: dict, shorts: bool = False) -> str:
        if shorts:
            prompt = f"""Write a 2-minute YouTube Shorts script about: "{topic['trend']}"

RULES:
- Hook in the FIRST 3 seconds — must stop the scroll
- Start with shocking statement
- Build tension every 15 seconds
- End with shocking twist or cliffhanger
- Short punchy sentences only
- American English, dramatic, fast-paced
- Length: EXACTLY 250-280 words
- Narration ONLY, no stage directions"""
        else:
            prompt = f"""Write a 10-12 minute YouTube video script about: "{topic['title']}"
Topic: {topic['trend']}
Category: {topic['category']}

RULES:
- Hook in first 15 seconds
- 6-8 dramatic segments building tension
- Transitions: "But here's where it gets DARK...", "Nobody expected this..."
- End with jaw-dropping revelation
- American English, conversational but dramatic
- Length: 1500-1800 words, narration only
- Start directly with the hook"""

        messages = [
            {"role": "system",
             "content": "You are a viral YouTube scriptwriter for true crime and mystery content. Your scripts get millions of views."},
            {"role": "user", "content": prompt}
        ]
        log.info("Writing script with Groq (free)...")
        return groq_chat(messages, max_tokens=2500)

    def generate_seo_metadata(self, topic: dict, script: str) -> dict:
        prompt = f"""Generate SEO metadata for YouTube video.
Topic: {topic['trend']}
Script: {script[:300]}...

Return ONLY valid JSON:
{{"title": "title max 70 chars", "description": "250 words", "tags": ["tag1","tag2"] 25 tags}}"""
        try:
            text = groq_chat([{"role": "user", "content": prompt}], max_tokens=800)
            text = re.sub(r"```json|```", "", text).strip()
            return json.loads(text)
        except Exception as e:
            log.warning(f"SEO failed: {e}")
            return {
                "title": topic["title"][:70],
                "description": f"The shocking true story of {topic['trend']}.",
                "tags": ["TrueCrime", "Mystery", "ShockingStory", "TrueStory", "Viral"],
            }

    def text_to_speech(self, text: str, output_path: str, shorts: bool = False) -> str:
        """OpenAI TTS - cheap and reliable"""
        voice = "nova" if shorts else "onyx"
        log.info(f"Generating voice with OpenAI TTS ({voice})...")

        chunks = []
        words = text.split()
        current, current_len = [], 0
        for word in words:
            current_len += len(word) + 1
            current.append(word)
            if current_len >= 4000:
                chunks.append(" ".join(current))
                current, current_len = [], 0
        if current:
            chunks.append(" ".join(current))

        audio_parts = []
        for i, chunk in enumerate(chunks):
            response = openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=chunk,
                speed=1.0
            )
            chunk_path = f"/tmp/tts_chunk_{i}.mp3"
            response.stream_to_file(chunk_path)
            audio_parts.append(chunk_path)
            log.info(f"  Chunk {i+1}/{len(chunks)} done")

        if len(audio_parts) == 1:
            shutil.copy(audio_parts[0], output_path)
        else:
            with open(output_path, "wb") as out:
                for part in audio_parts:
                    with open(part, "rb") as f:
                        out.write(f.read())

        log.info(f"✅ Voiceover saved: {output_path}")
        return output_path

    def generate(self, topic: dict, shorts: bool = False) -> dict:
        script = self.write_script(topic, shorts)
        log.info(f"✅ Script ready ({len(script)} chars)")

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
