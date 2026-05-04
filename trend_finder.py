"""
Trend Finder - Discovers what Americans are watching right now
Uses YouTube trending API + RSS feeds as primary sources (pytrends is blocked on Railway)
"""

import os
import requests
import logging
import random
import xml.etree.ElementTree as ET
from datetime import datetime

log = logging.getLogger(__name__)

STORY_CATEGORIES = [
    "true crime story",
    "scary reddit story",
    "mysterious disappearance",
    "unsolved mystery",
    "dark secret revealed",
    "survival story",
    "paranormal experience",
    "shocking true story"
]

# High-quality evergreen topics — used when all APIs fail
EVERGREEN_TOPICS = [
    "The Mysterious Disappearance That Shocked America",
    "The Dark Secret Nobody Talks About",
    "The True Crime Story That Broke The Internet",
    "The Survival Story That Left Everyone Speechless",
    "The Unsolved Mystery That Still Haunts Investigators",
    "The Paranormal Experience That Changed Everything",
    "The Shocking Confession That Went Viral",
    "The True Story Behind The Most Disturbing Case Ever",
    "The Whistleblower Who Exposed A Dark Secret",
    "The Disappearance That Was Never Solved",
]


class TrendFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36"
        })

    # ─── Source 1: YouTube Trending (most reliable) ─────────────────────────

    def get_youtube_trending(self) -> list:
        """Get trending YouTube videos via YouTube Data API v3"""
        api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        if not api_key:
            log.warning("YOUTUBE_API_KEY not set — skipping YouTube trending")
            return []
        try:
            r = self.session.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,statistics",
                    "chart": "mostPopular",
                    "regionCode": "US",
                    "maxResults": 25,
                    "key": api_key
                },
                timeout=15
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            titles = [it["snippet"]["title"] for it in items]
            log.info(f"YouTube trending: {len(titles)} titles fetched")
            return titles
        except Exception as e:
            log.warning(f"YouTube trending failed: {e}")
            return []

    # ─── Source 2: Google Trends RSS (no pytrends, no 404) ──────────────────

    def get_google_trends_rss(self) -> list:
        """Fetch Google Trends via public RSS feed — no pytrends needed"""
        url = "https://trends.google.com/trending/rss?geo=US"
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            ns = {"ht": "https://trends.google.com/trending/rss"}
            titles = []
            for item in root.iter("item"):
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    titles.append(title_el.text.strip())
            log.info(f"Google Trends RSS: {len(titles)} trends fetched")
            return titles[:20]
        except Exception as e:
            log.warning(f"Google Trends RSS failed: {e}")
            return []

    # ─── Source 3: Reddit Popular (backup) ──────────────────────────────────

    def get_reddit_popular(self) -> list:
        """Fetch popular posts from r/worldnews and r/todayilearned via JSON API"""
        topics = []
        subs = ["worldnews", "todayilearned", "news", "UpliftingNews"]
        for sub in subs[:2]:
            try:
                r = self.session.get(
                    f"https://www.reddit.com/r/{sub}/hot.json?limit=10",
                    timeout=10
                )
                r.raise_for_status()
                posts = r.json().get("data", {}).get("children", [])
                for post in posts:
                    title = post.get("data", {}).get("title", "")
                    if title and len(title) > 20:
                        topics.append(title)
            except Exception as e:
                log.warning(f"Reddit {sub} failed: {e}")
        log.info(f"Reddit popular: {len(topics)} topics fetched")
        return topics[:10]

    # ─── Scoring ─────────────────────────────────────────────────────────────

    def score_topic(self, topic: str) -> int:
        score = 0
        high_value = [
            "secret", "shocking", "murder", "missing", "mystery",
            "truth", "exposed", "real story", "untold", "dark",
            "terrifying", "unbelievable", "caught", "revealed",
            "horror", "disappear", "crime", "serial", "killer",
            "escape", "survivor", "haunted", "paranormal", "unsolved"
        ]
        topic_lower = topic.lower()
        for kw in high_value:
            if kw in topic_lower:
                score += 10
        # Prefer shorter, punchier topics
        if len(topic) < 60:
            score += 5
        return score

    def build_story_topic(self, trend: str) -> dict:
        category = random.choice(STORY_CATEGORIES)
        # Clean the trend string — remove special chars
        clean_trend = trend.replace("|", "").replace('"', "").strip()[:50]
        title = f"The {category.replace('story','Story').replace('experience','Experience').title()} That Shocked America | {clean_trend}"
        return {
            "title": title,
            "trend": clean_trend,
            "category": category,
            "keywords": [clean_trend, category, "true story", "shocking", "viral"],
            "shorts_title": f"SHOCKING: {clean_trend[:45]} 😱 #shorts #truestory"
        }

    # ─── Main ─────────────────────────────────────────────────────────────────

    def get_best_topic(self, shorts: bool = False) -> dict:
        """Returns the best topic to make a video about"""
        log.info("Fetching US trends...")
        all_trends = []

        # Try all sources in priority order
        yt = self.get_youtube_trending()
        all_trends.extend(yt)

        rss = self.get_google_trends_rss()
        all_trends.extend(rss)

        if len(all_trends) < 5:
            reddit = self.get_reddit_popular()
            all_trends.extend(reddit)

        if not all_trends:
            log.warning("All trend sources failed — using evergreen topic")
            fallback = random.choice(EVERGREEN_TOPICS)
            return self.build_story_topic(fallback)

        # Score and pick the best trend
        scored = sorted(all_trends, key=self.score_topic, reverse=True)
        # Rotate through top 5 to avoid repeating the same topic every day
        day_of_year = datetime.now().timetuple().tm_yday
        best_trend = scored[day_of_year % min(5, len(scored))]

        topic = self.build_story_topic(best_trend)
        log.info(f"✅ Topic selected: {topic['title']}")
        return topic
