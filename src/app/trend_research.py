from __future__ import annotations

import logging
import re
from typing import Any

import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq

LOG = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://www.apartmenttherapy.com/main.rss",
    "https://www.thespruce.com/feed",
    "https://www.architecturaldigest.com/feed/rss",
    "https://www.bhg.com/feed",
    "https://www.bobvila.com/feed",
]

REDDIT_URLS = [
    "https://www.reddit.com/r/HomeImprovement/top/.json?t=day&limit=15",
    "https://www.reddit.com/r/organization/top/.json?t=day&limit=15",
    "https://www.reddit.com/r/InteriorDesign/top/.json?t=day&limit=15",
    "https://www.reddit.com/r/cozyplaces/top/.json?t=day&limit=15",
    "https://www.reddit.com/r/gardening/top/.json?t=day&limit=15",
    "https://www.reddit.com/r/CleaningTips/top/.json?t=day&limit=15",
]


def get_trending_topics() -> list[str]:
    """Fetches trending home and lifestyle topics from Google Trends, RSS, and Reddit."""
    topics = []

    # 1. Google Trends
    try:
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
        try:
            trending_searches = pytrends.trending_searches(pn='united_states')
            for search in trending_searches[0][:20]:
                if _is_relevant(search):
                    topics.append(search)
        except Exception as te:
            LOG.debug("Trending searches fallback: %s", te)
    except Exception as e:
        LOG.warning("Failed to fetch Google Trends: %s. Moving to fallbacks.", e)

    # 2. RSS
    for url in RSS_FEEDS:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "xml")
                items = soup.find_all("item")
                for item in items[:8]:
                    title = item.title.text if item.title else ""
                    description = item.description.text if item.description else ""
                    if title and (_is_relevant(title) or _is_relevant(description)):
                        topics.append(title)
        except Exception as e:
            LOG.debug("Failed to fetch RSS %s: %s", url, e)

    # 3. Reddit
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for url in REDDIT_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for child in children:
                    t_data = child.get("data", {})
                    title = t_data.get("title", "")
                    selftext = t_data.get("selftext", "")
                    if title and (_is_relevant(title) or _is_relevant(selftext)):
                        topics.append(title)
        except Exception as e:
            LOG.debug("Failed to fetch Reddit %s: %s", url, e)

    # Clean and filter
    cleaned_topics = []
    for t in topics:
        t = re.sub(r"\[.*?\]", "", t)
        t = re.sub(r"\(.*?\)", "", t)
        t = t.replace('"', "").replace("'", "").strip()
        if len(t) > 15 and _is_relevant(t):
            cleaned_topics.append(t)

    seen = set()
    unique_topics = []
    for t in cleaned_topics:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique_topics.append(t)

    LOG.info("Gathered %d unique trending topics.", len(unique_topics))
    return unique_topics[:15]


def _is_relevant(text: str) -> bool:
    """Filters for home, decor, kitchen, garden, organization, and living."""
    if not text:
        return False

    keywords = [
        "home", "house", "room", "decor", "interior", "living room", "kitchen",
        "bedroom", "bathroom", "closet", "pantry", "organize", "organization",
        "storage", "declutter", "garden", "gardening", "plants", "patio",
        "furniture", "design", "aesthetic", "cozy", "desk", "office", "smart home",
        "cleaning", "diy", "makeover", "renovation", "lighting", "shelf",
        "shelves", "containers", "countertop", "cooking", "meal prep", "appliances",
        "tools", "backyard", "outdoor", "balcony", "indoor plants", "pets",
        "pet friendly", "dog", "cat", "dog bed", "cat tree", "rug", "curtains",
        "paint", "woodwork", "minimalist", "scandinavian", "modern organic",
    ]

    exclude = [
        "crypto", "bitcoin", "stocks", "market", "politics", "war", "trump", "biden",
        "movie", "trailer", "gaming", "ps5", "xbox", "celebrity", "gossip", "actor",
        "shooting", "crime", "police", "court", "lawsuit", "football", "nba", "nfl",
    ]

    text_lower = text.lower()
    if any(ex in text_lower for ex in exclude):
        return False

    return any(kw in text_lower for kw in keywords)
