"""
Trend Finder - Focuses on true crime and mystery stories only
"""

import requests
import logging
import random
from datetime import datetime

log = logging.getLogger(__name__)

# High-quality evergreen story topics
EVERGREEN = [
    "The Woman Who Vanished Without a Trace for 20 Years",
    "The Dark Secret That Destroyed an Entire Family",
    "The Serial Killer Nobody Suspected Was Their Neighbor",
    "The Child Who Survived the Unsurvivable",
    "The Cover-Up That Lasted 30 Years",
    "The Whistleblower Who Exposed a Billion Dollar Fraud",
    "The Family That Disappeared Overnight and Was Never Found",
    "The Confession That Shocked an Entire Nation",
    "The Experiment That Went Horribly Wrong",
    "The Small Town With a Terrifying Dark Secret",
    "The Innocent Man Who Spent 20 Years in Prison",
    "The Cult That Controlled an Entire Town",
    "The Detective Who Solved a 40-Year-Old Cold Case",
    "The Survivor Who Escaped and Told Everything",
    "The Missing Girl Who Came Back as Someone Else",
    "The Man Who Faked His Own Death for 10 Years",
    "The Doctor Who Killed His Patients for Years",
    "The Child Who Remembered Detailed Memories of a Past Life",
    "The Paranormal Activity That Science Cannot Explain",
    "The Haunted House Where Three Families Refused to Stay",
    "The Serial Arsonist Who Was Never Caught",
    "The Mysterious Death That Was Ruled a Suicide",
    "The FBI Agent Who Turned Out to Be a Criminal",
    "The Nurse Who Was Secretly Poisoning Patients",
    "The Town That Went Silent After a Terrible Secret Was Revealed",
]

STORY_ANGLES = [
    "The Shocking True Story of {topic}",
    "The Dark Truth Behind {topic} Nobody Talks About",
    "What Really Happened with {topic} — The Full Story",
    "The Hidden Secret of {topic} Finally Revealed",
    "The Untold Story of {topic} That Will Leave You Speechless",
]

CATEGORIES = [
    "true crime story",
    "mysterious disappearance",
    "dark secret revealed",
    "shocking true story",
    "unsolved mystery",
    "survival story",
    "paranormal experience",
    "scary reddit story",
]


class TrendFinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        })

    def get_reddit_stories(self) -> list:
        """Get real crime/mystery stories from relevant subreddits"""
        topics = []
        subs = [
            "UnresolvedMysteries",
            "TrueCrime",
            "Paranormal",
            "LetsNotMeet",
            "Missing411",
        ]
        for sub in subs:
            try:
                r = self.session.get(
                    f"https://www.reddit.com/r/{sub}/hot.json?limit=10",
                    timeout=10
                )
                r.raise_for_status()
                for post in r.json().get("data", {}).get("children", []):
                    title = post.get("data", {}).get("title", "").strip()
                    # Filter: must be substantial and not meta posts
                    if (len(title) > 20 and
                        not title.lower().startswith(("weekly", "monthly", "mod",
                                                       "rules", "announcement", "["))):
                        topics.append(title)
            except Exception as e:
                log.warning(f"Reddit r/{sub}: {e}")
        log.info(f"Reddit stories: {len(topics)} found")
        return topics[:15]

    def build_story_topic(self, raw: str, shorts: bool = False) -> dict:
        import re
        # Clean non-ASCII
        clean = re.sub(r'[^\x00-\x7F]+', '', raw)
        clean = re.sub(r'\s+', ' ', clean).strip()[:80]

        category = random.choice(CATEGORIES)
        tags = (
            ["TrueCrime", "Mystery", "ShockingStory", "TrueStory",
             "Viral", "Scary", "Horror", "Crime", "Unsolved", "Dark"]
            + [w for w in clean.split() if len(w) > 4][:5]
        )

        description = (
            f"{clean}\n\n"
            f"In this video, we dive deep into one of the most shocking {category} "
            f"stories you'll ever hear. The truth behind this story will leave you "
            f"speechless. Stay until the end for the full reveal.\n\n"
            f"🔔 Subscribe for daily shocking true stories.\n"
            f"#TrueCrime #Mystery #ShockingStory #TrueStory"
        )

        return {
            "title": clean[:100],
            "trend": clean,
            "category": category,
            "tags": tags,
            "description": description,
        }

    def get_best_topic(self, shorts: bool = False) -> dict:
        log.info("Finding best story topic...")

        # Try Reddit first
        reddit_topics = self.get_reddit_stories()

        if reddit_topics:
            # Pick based on day rotation for variety
            day = datetime.now().timetuple().tm_yday
            idx = day % len(reddit_topics)
            best = reddit_topics[idx]
            log.info(f"Using Reddit story: {best[:60]}")
        else:
            # Fallback to evergreen
            log.info("Reddit unavailable — using evergreen topic")
            best = random.choice(EVERGREEN)

        topic = self.build_story_topic(best, shorts)
        log.info(f"✅ Topic: {topic['title']}")
        return topic
