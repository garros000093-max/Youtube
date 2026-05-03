"""
Trend Finder - Discovers what Americans are watching right now
Uses Google Trends + YouTube trending to find viral topics
"""

import os
import requests
import logging
from pytrends.request import TrendReq
from datetime import datetime, timedelta
import random

log = logging.getLogger(__name__)

# Story categories that work best for Faceless channels
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


class TrendFinder:
    def __init__(self):
        self.pytrends = TrendReq(hl="en-US", tz=360)  # US timezone

    def get_trending_us(self):
        """Get trending searches in the US right now"""
        try:
            trending = self.pytrends.trending_searches(pn="united_states")
            return trending[0].tolist()[:20]
        except Exception as e:
            log.warning(f"Google Trends failed: {e}")
            return []

    def get_youtube_trending(self):
        """Get trending YouTube videos via YouTube API"""
        api_key = os.getenv("YOUTUBE_API_KEY")
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": "US",
            "videoCategoryId": "22",  # People & Blogs
            "maxResults": 20,
            "key": api_key
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            items = r.json().get("items", [])
            return [item["snippet"]["title"] for item in items]
        except Exception as e:
            log.warning(f"YouTube trending failed: {e}")
            return []

    def score_topic(self, topic: str) -> int:
        """Score a topic based on viral potential"""
        score = 0
        high_value_keywords = [
            "secret", "shocking", "murder", "missing", "mystery",
            "truth", "exposed", "real story", "untold", "dark",
            "terrifying", "unbelievable", "caught", "revealed"
        ]
        for kw in high_value_keywords:
            if kw.lower() in topic.lower():
                score += 10
        return score

    def build_story_topic(self, trend: str) -> dict:
        """Combine a trend with a story angle"""
        category = random.choice(STORY_CATEGORIES)
        title = f"The {category.title()} That Shocked America | {trend[:40]}"
        return {
            "title": title,
            "trend": trend,
            "category": category,
            "keywords": [trend, category, "true story", "shocking", "viral"],
            "shorts_title": f"SHOCKING: {trend[:50]} 😱 #shorts #truestory"
        }

    def get_best_topic(self, shorts: bool = False) -> dict:
        """Main method: returns the best topic to make a video about"""
        log.info("Fetching US trends...")

        trending = self.get_trending_us()
        youtube_trending = self.get_youtube_trending()
        all_trends = trending + youtube_trending

        if not all_trends:
            # Fallback to evergreen topics
            log.warning("No trends found, using evergreen topic")
            fallback = random.choice([
                "mysterious disappearance that shocked the world",
                "the dark secret nobody talks about",
                "the true crime story that broke the internet"
            ])
            return self.build_story_topic(fallback)

        # Score all trends and pick the best
        scored = sorted(all_trends, key=self.score_topic, reverse=True)
        best_trend = scored[0]

        topic = self.build_story_topic(best_trend)
        log.info(f"Best topic: {topic['title']}")
        return topic
