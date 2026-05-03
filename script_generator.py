"""
Script Generator - Writes viral story scripts + generates American voiceover
Uses GPT-4o for writing and ElevenLabs for voice synthesis
"""

import os
import re
import json
import logging
import requests
from openai import OpenAI

log = logging.getLogger(__name__)

# ElevenLabs American voice IDs (free tier - premade voices)
AMERICAN_VOICES = {
    "male_dramatic": "pNInz6obpgDQGcFmaJgB",    # Adam - deep American
    "female_mystery": "21m00Tcm4TlvDq8ikWAM",   # Rachel - American female
    "male_narrator": "ErXwobaYiN019PkySvjV",     # Antoni - American male
}


class ScriptGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")

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
- Hook in first 15 seconds
- 5-7 dramatic segments building tension
- Use "But here's where it gets DARK..." type transitions
- End with a shocking revelation
- American English, conversational but dramatic
- Length: 1200-1500 words (narration only)
Start directly with the hook."""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a viral YouTube scriptwriter for American audiences."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=2000
        )
        return response.choices[0].message.content

    def generate_seo_metadata(self, topic: dict, script: str) -> dict:
        prompt = f"""Based on this YouTube script, generate SEO metadata for American viewers.
Topic: {topic['trend']}
Script preview: {script[:300]}...
Return ONLY a JSON object:
{{
  "title": "Clickbait but honest title (max 70 chars)",
  "description": "SEO description 200-300 words with timestamps",
  "tags": ["tag1", "tag2"] (30 tags),
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
        voice_id = AMERICAN_VOICES["male_dramatic"] if not shorts else AMERICAN_VOICES["female_mystery"]
        text = text[:2500]  # Free tier limit

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.elevenlabs_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        log.info(f"Generating voiceover (voice_id: {voice_id})...")
        r = requests.post(url, json=payload, headers=headers, timeout=120)

        if r.status_code != 200:
            log.error(f"ElevenLabs {r.status_code}: {r.text[:300]}")
            r.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(r.content)

        log.info(f"✅ Voiceover saved: {output_path}")
        return output_path

    def generate(self, topic: dict, shorts: bool = False) -> dict:
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
