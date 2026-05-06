"""
Script Generator - Uses Groq (free) for writing + ElevenLabs for voice
Much cheaper than OpenAI: ~$0 for writing, minimal for voice
"""

import os
import re
import json
import logging
import requests
import shutil

log = logging.getLogger(__name__)

GROQ_API_KEY      = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
GROQ_API_URL      = "https://api.groq.com/openai/v1/chat/completions"

# ElevenLabs voice IDs — dramatic American voices
# Rachel: calm, professional female
# Antoni: deep dramatic male
# Adam: clear male narrator
ELEVENLABS_VOICES = {
    "shorts": "EXAVITQu4vr4xnSDxMaL",  # Sarah - mature female
    "main":   "IKne3meqSaSn9XLyUdCD",  # Charlie - deep male — deep dramatic male
}


def groq_chat(messages: list, max_tokens: int = 2000) -> str:
    """Call Groq API — free tier, very fast"""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in Railway variables")

    r = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.85,
        },
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
- Start with: "You won't believe what happened..." or similar
- Build tension every 15 seconds
- End with shocking twist or cliffhanger
- Short punchy sentences only
- American English, dramatic, fast-paced
- Length: EXACTLY 250-280 words
- Narration ONLY, no stage directions

Start immediately with the hook."""

        else:
            prompt = f"""Write a 10-12 minute YouTube video script about: "{topic['title']}"
Topic: {topic['trend']}
Category: {topic['category']}

RULES:
- Hook in first 15 seconds — viewer MUST keep watching
- 6-8 dramatic segments building tension
- Powerful transitions: "But here's where it gets DARK...", "Nobody expected this..."
- End with jaw-dropping revelation
- American English, conversational but dramatic
- Natural pauses with "..."
- Target: Americans 18-35 who love true crime
- Length: 1500-1800 words, narration only

Start directly with the hook."""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a viral YouTube scriptwriter specializing in true crime "
                    "and mystery content for American audiences. "
                    "Your scripts get tens of millions of views."
                )
            },
            {"role": "user", "content": prompt}
        ]

        log.info("Writing script with Groq (Llama 3.3 70B)...")
        return groq_chat(messages, max_tokens=2500)

    def generate_seo_metadata(self, topic: dict, script: str) -> dict:
        prompt = f"""Generate viral SEO metadata for this YouTube video.
Topic: {topic['trend']}
Script preview: {script[:400]}...

Return ONLY valid JSON, no markdown:
{{
  "title": "Clickbait but honest title (max 70 chars)",
  "description": "SEO description 250-350 words with keywords",
  "tags": ["tag1", "tag2"] (exactly 25 tags)
}}"""

        try:
            text = groq_chat([{"role": "user", "content": prompt}], max_tokens=800)
            text = re.sub(r"```json|```", "", text).strip()
            return json.loads(text)
        except Exception as e:
            log.warning(f"SEO metadata failed: {e}")
            return {
                "title": topic["title"][:70],
                "description": f"The shocking true story of {topic['trend']}.",
                "tags": ["TrueCrime", "Mystery", "ShockingStory", "TrueStory",
                         "Viral", "Scary", "Crime", "Unsolved", "Dark", "Horror"],
            }

    def text_to_speech_elevenlabs(self, text: str, output_path: str,
                                   shorts: bool = False) -> str:
        """High quality voice using ElevenLabs"""
        if not ELEVENLABS_API_KEY:
            raise ValueError("ELEVENLABS_API_KEY not set in Railway variables")

        voice_id = ELEVENLABS_VOICES["shorts" if shorts else "main"]

        # ElevenLabs max ~5000 chars per request — split if needed
        max_len = 4500
        chunks = []
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

        log.info(f"Generating voice with ElevenLabs ({len(chunks)} chunks)...")

        audio_parts = []
        for i, chunk in enumerate(chunks):
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "text": chunk,
                    "model_id": "eleven_turbo_v2_5",  # Fast + cheap
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.8,
                        "style": 0.3,
                        "use_speaker_boost": True
                    }
                },
                timeout=120
            )
            r.raise_for_status()

            chunk_path = f"/tmp/el_chunk_{i}.mp3"
            with open(chunk_path, "wb") as f:
                f.write(r.content)
            audio_parts.append(chunk_path)
            log.info(f"  Chunk {i+1}/{len(chunks)} done")

        # Combine chunks
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
        # Write script
        script = self.write_script(topic, shorts)
        log.info(f"✅ Script ready ({len(script)} chars)")

        # SEO metadata
        metadata = self.generate_seo_metadata(topic, script)

        # Voice
        audio_path = f"/tmp/voiceover_{'shorts' if shorts else 'main'}.mp3"
        self.text_to_speech_elevenlabs(script, audio_path, shorts)

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
