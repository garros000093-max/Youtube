"""
Trend Finder - Finds trending topics and builds story titles
"""

import os
import requests
import logging
import random
import xml.etree.ElementTree as ET
from datetime import datetime

log = logging.getLogger(__name__)

# Blacklist — skip these types of trends
BLACKLIST_KEYWORDS = [
    "official", "trailer", "teaser", "mv", "music video", "lyrics",
    "ft.", "feat.", "remix", "album", "ep ", "tour", "live",
    "season", "episode", "series", "netflix", "hbo", "disney",
    "marvel", "dc ", "anime", "manga", "game", "gaming",
    "vs ", "match", "score", "highlights", "nba", "nfl", "fifa",
    "world cup", "champion", "league", "transfer",
    "stock", "crypto", "bitcoin", "ethereum", "price",
    "weather", "forecast", "recipe", "tutorial", "how to",
    "tiktok", "instagram", "twitter", "facebook",
]

# High-value keywords that make great story topics
HIGH_VALUE = [
    "murder", "missing", "disappear", "secret", "expose", "reveal",
    "shock", "crime", "dark", "truth", "mystery", "untold", "hidden",
    "survivor", "escape", "trap", "fraud", "scam", "betray",
    "confession", "caught", "arrested", "sentenced", "victim",
    "haunted", "paranormal", "strange", "bizarre", "unexplained",
    "cover up", "conspiracy", "abuse", "corrupt", "scandal",
]

# Evergreen story topics — always work
EVERGREEN = [
    "The Woman Who Disappeared Without a Trace",
    "The Dark Secret That Shocked an Entire Town",
    "The True Crime Case Nobody Talks About",
    "The Survivor Who Escaped and Told Everything",
    "The Mystery That Investigators Never Solved",
    "The Whistleblower Who Exposed a Massive Fraud",
    "The Family That Vanished Overnight",
    "The Confession That Changed Everything",
    "The Cover-Up That Lasted 30 Years",
    "The Paranormal Experience That Defies Explanation",
    "The Serial Killer Nobody Suspected",
    "The Child Who Remembered a Past Life",
    "The Small Town With a Terrifying Secret",
    "The Experiment That Went Horribly Wrong",
    "The Escape That Shocked the World",
]

STORY_ANGLES = [
    "The Shocking True Story of {topic}",
    "The Dark Truth Behind {topic}",
    "What Really Happened with {topic}",
    "The Hidden Secret of {topic}",
    "The Mystery of {topic} Finally Solved",
    "The Untold Story of {topic}",
]


class TrendFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        })

    def _is_blacklisted(self, text: str) -> bool:
        t = text.lower()
        return any(kw in t for kw in BLACKLIST_KEYWORDS)

    def _score(self, text: str) -> int:
        t = text.lower()
        score = 0
        for kw in HIGH_VALUE:
            if kw in t:
                score += 15
        if len(text) < 60:
            score += 5
        # Penalize movie/music content
        if any(kw in t for kw in ["official", "trailer", "mv", "ft."]):
            score -= 50
        return score

    def get_google_trends(self) -> list:
        try:
            r = self.session.get(
                "https://trends.google.com/trending/rss?geo=US",
                timeout=15
            )
            r.raise_for_status()
            root = ET.fromstring(r.content)
            titles = []
            for item in root.iter("item"):
                el = item.find("title")
                if el is not None and el.text:
                    t = el.text.strip()
                    if not self._is_blacklisted(t):
                        titles.append(t)
            log.info(f"Google Trends RSS: {len(titles)} clean trends")
            return titles[:15]
        except Exception as e:
            log.warning(f"Google Trends RSS: {e}")
            return []

    def get_youtube_trending(self) -> list:
        api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        if not api_key:
            return []
        try:
            r = self.session.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "snippet", "chart": "mostPopular",
                        "regionCode": "US", "maxResults": 30, "key": api_key},
                timeout=15
            )
            r.raise_for_status()
            titles = []
            for it in r.json().get("items", []):
                t = it["snippet"]["title"]
                if not self._is_blacklisted(t):
                    titles.append(t)
            log.info(f"YouTube trending: {len(titles)} clean titles")
            return titles[:15]
        except Exception as e:
            log.warning(f"YouTube trending: {e}")
            return []

    def get_reddit_trending(self) -> list:
        """Get real crime/mystery stories from relevant subreddits"""
        topics = []
        subs = ["UnresolvedMysteries", "TrueCrime", "Missing411",
                "Paranormal", "news"]
        for sub in subs[:3]:
            try:
                r = self.session.get(
                    f"https://www.reddit.com/r/{sub}/hot.json?limit=8",
                    timeout=10
                )
                r.raise_for_status()
                for post in r.json().get("data", {}).get("children", []):
                    title = post.get("data", {}).get("title", "")
                    if title and len(title) > 15 and not self._is_blacklisted(title):
                        topics.append(title)
            except Exception as e:
                log.warning(f"Reddit {sub}: {e}")
        log.info(f"Reddit: {len(topics)} topics")
        return topics[:10]

    def build_story_topic(self, raw_trend: str, shorts: bool = False) -> dict:
        # Clean the trend string
        import re
        clean = re.sub(r'[^\x00-\x7F]+', '', raw_trend)
        clean = re.sub(r'\s+', ' ', clean).strip()
        clean = clean[:50]

        # Build a story-style title
        if self._score(raw_trend) > 10:
            # Already story-worthy — use directly
            title = clean
        else:
            # Wrap in story angle
            angle = random.choice(STORY_ANGLES)
            title = angle.format(topic=clean)

        category = random.choice([
            "true crime story", "mysterious disappearance",
            "dark secret revealed", "shocking true story",
            "unsolved mystery", "survival story"
        ])

        keywords = [w for w in clean.split() if len(w) > 4][:5]

        return {
            "title": title[:100],
            "trend": clean,
            "category": category,
            "tags": keywords + ["TrueCrime", "Mystery", "ShockingStory",
                                 "TrueStory", "Viral", "Scary"],
            "description": f"The shocking true story behind: {clean}. "
                           f"This {category} will leave you speechless.",
            "shorts_title": f"SHOCKING: {clean[:45]} 😱 #shorts"
        }

    def get_best_topic(self, shorts: bool = False) -> dict:
        log.info("Fetching US trends...")
        all_trends = []

        # Try all sources
        all_trends.extend(self.get_google_trends())
        all_trends.extend(self.get_youtube_trending())

        if len(all_trends) < 5:
            all_trends.extend(self.get_reddit_trending())

        if not all_trends:
            log.warning("All sources failed — using evergreen topic")
            topic_str = random.choice(EVERGREEN)
            return self.build_story_topic(topic_str, shorts)

        # Score and pick best
        scored = sorted(
            [(t, self._score(t)) for t in all_trends],
            key=lambda x: x[1],
            reverse=True
        )

        # Rotate through top 5 daily
        day = datetime.now().timetuple().tm_yday
        best = scored[day % min(5, len(scored))][0]

        log.info(f"Best trend: {best}")
        topic = self.build_story_topic(best, shorts)
        log.info(f"✅ Topic: {topic['title']}")
        return topic
