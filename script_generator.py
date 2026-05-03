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

# ElevenLabs American voice IDs (free tier voices)
AMERICAN_VOICES = {
    "male_dramatic": "TxGEqnHWrfWFTfGW9XjX",    # Josh - deep dramatic
    "female_mystery": "EXAVITQu4vr4xnSDxMaL",    # Bella - storytelling
    "male_narrator": "VR6AewLTigWG4xSOukaG",     # Arnold - authoritative
}


class ScriptGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")

    def write_script(self, topic: dict, shorts: bool = False) -> str:
        """Use GPT-4o to write a viral story script"""
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
        """Generate SEO-optimized title, description, tags"""
        prompt = f"""Based on this YouTube script, generate SEO metadata optimized for American viewers.

Topic: {topic['trend']}
Script preview: {script[:300]}...

Return ONLY a JSON object with:
{{
  "title": "Clickbait but honest title (max 70 chars)",
  "description": "SEO description with keywords, 200-300 words, includes timestamps",
  "tags": ["tag1", "tag2", ...] (30 tags, mix of broad and specific),
  "category": "22"
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=800
        )

        text = response.choices[0].message.content
        # Clean JSON
        text = re.sub(r"```json|```", "", text).strip()
        try:
            return json.loads(text)
        except Exception:
            return {
                "title": topic["title"][:70],
                "description": f"The shocking true story of {topic['trend']}. Don't miss this!",
                "tags": topic["keywords"] + ["true story", "shocking", "mystery", "viral"],
                "category": "22"
            }

    def text_to_speech(self, text: str, output_path: str, shorts: bool = False) -> str:
        """Convert script to American voice using ElevenLabs"""
        voice_id = AMERICAN_VOICES["male_dramatic"] if not shorts else AMERICAN_VOICES["female_mystery"]

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.elevenlabs_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8,
                "style": 0.6,
                "use_speaker_boost": True
            }
        }

        log.info("Generating voiceover with ElevenLabs...")
        r = requests.post(url, json=payload, headers=headers, timeout=120)
        r.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(r.content)

        log.info(f"✅ Voiceover saved: {output_path}")
        return output_path

    def generate(self, topic: dict, shorts: bool = False) -> dict:
        """Full pipeline: write script → metadata → voiceover"""
        # Write script
        script = self.write_script(topic, shorts)
        log.info(f"Script written ({len(script)} chars)")

        # Generate metadata
        metadata = self.generate_seo_metadata(topic, script)

        # Generate voiceover
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
