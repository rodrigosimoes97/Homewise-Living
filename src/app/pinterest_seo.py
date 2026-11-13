from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from .pinterest_performance import PinterestPerformanceTracker
from .topics import Topic

LOG = logging.getLogger(__name__)

SEARCH_INTENTS = [
    "how_to",
    "list",
    "checklist",
    "tips",
    "mistakes",
    "guide",
    "routine",
]

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "for", "with", "this",
    "that", "your", "from", "how", "to", "of", "in", "on", "at",
    "is", "it", "my", "me", "i", "you", "we", "be", "do", "get",
    "can", "more", "less", "what", "why", "when", "which", "make",
    "feel", "start", "try", "stop", "build", "help", "keep", "give",
    "about", "into", "their", "will", "our", "all", "so", "up", "may",
    "could", "should", "has", "have", "had", "was", "were", "are",
    "been", "being", "does", "did", "new", "find", "finds", "by",
}

_GENERIC_TITLE_PREFIXES = [
    "build a better week with",
    "feel better faster:",
    "a simpler way to",
    "what to do this week:",
    "small changes, real results:",
    "your practical plan for",
    "the busy person's guide to",
    "how to actually master",
    "stop struggling with",
    "ready for a change?",
    "your 5-minute reset for",
    "better ",
]

_GENERIC_DESC_PREFIXES = [
    "most people make these",
    "your no-nonsense guide to",
    "not sure what works for",
    "build a consistent",
    "use this simple",
    "get science-backed",
    "struggling to get results with",
    "feeling overwhelmed lately",
    "having trouble making",
    "if you cannot seem to keep up with",
    "tired of generic advice about",
    "stop overcomplicating",
]

US_PINTEREST_BOARDS: dict[str, str] = {
    "home-organization": "Home Organization & Storage Solutions",
    "kitchen": "Kitchen Essentials & Organization",
    "decor": "Home Decor & Interior Styling",
    "garden": "Gardening & Outdoor Living",
    "home-office": "Home Office & Smart Living",
    "pets": "Pet-Friendly Home Ideas",
}


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _trim_at_word_boundary(text: str, max_chars: int) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized
    trimmed = normalized[: max_chars + 1].rsplit(" ", 1)[0]
    return trimmed if trimmed else normalized[:max_chars].strip()


def _stable_hash_index(seed: str, size: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    hashed = int(digest[:8], 16)
    spread = sum(ord(ch) for ch in seed)
    return (hashed + spread) % max(size, 1)


def _is_generic_fallback_title(title: str) -> bool:
    low = title.lower().strip()
    return any(low.startswith(p) for p in _GENERIC_TITLE_PREFIXES)


def _is_generic_fallback_description(desc: str) -> bool:
    low = desc.lower().strip()
    return any(low.startswith(p) for p in _GENERIC_DESC_PREFIXES)


def extract_core_topic_phrase(topic_name: str, title: str = "") -> str:
    _BAD_ENDINGS = {
        "and", "or", "the", "a", "an", "for", "with", "to", "in", "of", "on", "at", "by", "that", "this", "my", "your",
    }
    raw_topic = _normalize_whitespace(topic_name).lower()
    topic_words = [w for w in re.findall(r"\b[a-z]{3,}\b", raw_topic) if w not in STOPWORDS]

    if 2 <= len(topic_words) <= 4:
        phrase = " ".join(topic_words)
        if not any(phrase.endswith(f" {end}") for end in _BAD_ENDINGS):
            return phrase

    if 1 <= len(topic_words) <= 2:
        return raw_topic

    if title:
        raw_title = _normalize_whitespace(title).lower()
        title_words = [w for w in re.findall(r"\b[a-z]{3,}\b", raw_title) if w not in STOPWORDS]
        for n in (3, 2):
            for i in range(len(title_words) - n + 1):
                candidate_words = title_words[i: i + n]
                if candidate_words[-1] not in _BAD_ENDINGS:
                    return " ".join(candidate_words)

    return _trim_at_word_boundary(topic_name.lower(), 30)


def detect_search_intent(
    title: str,
    topic_name: str = "",
    tag: str = "",
    html: str = "",
    performance_tracker: PinterestPerformanceTracker | None = None,
) -> str:
    text_to_check = f"{title} {topic_name}".lower()

    mistake_exact = [
        "mistake", "mistakes", "wrong", "avoid", "ruin", "ruining",
        "worst", "problem", "problems", "cluttered", "clutter",
        "overwhelmed", "warning",
    ]
    mistake_compound = ["what not to do", "stop doing", "common mistakes"]
    if any(phrase in text_to_check for phrase in mistake_compound):
        return "mistakes"
    if any(re.search(rf"\b{re.escape(w)}\b", text_to_check) for w in mistake_exact):
        return "mistakes"

    if re.search(r"\b(how to|how i|how you|ways? to|step by step|step-by-step)\b", text_to_check):
        return "how_to"

    checklist_patterns = ["checklist", "tracker", "action plan", "step-by-step", "system", "declutter plan"]
    if any(phrase in text_to_check for phrase in checklist_patterns):
        return "checklist"

    routine_phrases = ["routine", "schedule", "daily habit", "cleaning schedule", "weekend project"]
    if any(phrase in text_to_check for phrase in routine_phrases):
        return "routine"

    tip_patterns = ["tips", "tip", "hacks", "tricks", "secrets", "ideas", "quick wins"]
    if any(re.search(rf"\b{re.escape(w)}\b", text_to_check) for w in tip_patterns):
        return "tips"

    if re.search(r"\b\d+\b", text_to_check) or re.search(r"\b(items|products|swaps|ideas|types|ways|pieces)\b", text_to_check):
        return "list"

    guide_patterns = ["guide", "blueprint", "ultimate", "master", "deep dive", "overview", "makeover"]
    if any(re.search(rf"\b{re.escape(w)}\b", text_to_check) for w in guide_patterns):
        return "guide"

    if performance_tracker:
        historical_intent = performance_tracker.get_best_intent_for_tag(tag)
        if historical_intent and historical_intent in SEARCH_INTENTS:
            return historical_intent

    tag_defaults: dict[str, str] = {
        "home-organization": "checklist",
        "kitchen": "tips",
        "decor": "list",
        "garden": "guide",
        "home-office": "how_to",
        "pets": "tips",
    }
    return tag_defaults.get(tag, "guide")


AUTHENTIC_US_PINTEREST_KEYWORDS: dict[str, list[str]] = {
    "home-organization": [
        "home organization ideas",
        "decluttering tips",
        "closet organization",
        "pantry organization hacks",
        "storage solutions for small spaces",
        "cleaning and organizing",
    ],
    "kitchen": [
        "kitchen organization",
        "kitchen essentials",
        "small kitchen storage",
        "kitchen gadgets",
        "meal prep tools",
        "pantry organization",
    ],
    "decor": [
        "home decor ideas",
        "interior styling tips",
        "living room ideas",
        "bedroom makeover",
        "aesthetic room decor",
        "cozy home vibes",
    ],
    "garden": [
        "beginner gardening tips",
        "indoor plants care",
        "patio decor ideas",
        "container gardening",
        "herb garden indoors",
        "backyard landscape ideas",
    ],
    "home-office": [
        "home office setup",
        "desk organization ideas",
        "ergonomic home office",
        "productivity space",
        "smart home devices",
        "cable management ideas",
    ],
    "pets": [
        "pet friendly home ideas",
        "dog room ideas",
        "cat safe house plants",
        "pet organization storage",
        "pet friendly furniture",
        "living with pets tips",
    ],
}


def generate_search_keywords(
    topic_name: str,
    title: str,
    tag: str,
    intent: str,
    primary_keyword: str = "",
    article_keywords: str = "",
) -> list[str]:
    tag_clean = tag.replace("-", " ").strip().lower()
    core = (primary_keyword or "").strip().lower()
    if not core:
        core = extract_core_topic_phrase(topic_name, title)

    candidates: list[str] = []

    def _add_candidate(cand: str) -> None:
        c = re.sub(r"[^\w\s-]", "", cand).strip().lower()
        c = _normalize_whitespace(c)
        words = c.split()
        if 2 <= len(words) <= 5 and c not in candidates:
            candidates.append(c)

    if article_keywords:
        for kw in article_keywords.split(","):
            _add_candidate(kw)

    if core and 2 <= len(core.split()) <= 4:
        _add_candidate(core)

    pool = AUTHENTIC_US_PINTEREST_KEYWORDS.get(tag, AUTHENTIC_US_PINTEREST_KEYWORDS["home-organization"])
    for kw in pool:
        _add_candidate(kw)

    intent_modifiers = {
        "how_to": [f"how to organize {tag_clean}", f"diy {tag_clean} ideas"],
        "list": [f"best {tag_clean} ideas", f"{tag_clean} essentials list"],
        "checklist": [f"{tag_clean} checklist", f"step by step {tag_clean}"],
        "tips": [f"{tag_clean} tips and tricks", f"smart {tag_clean} hacks"],
        "mistakes": [f"{tag_clean} mistakes to avoid", f"{tag_clean} organizing mistakes"],
        "guide": [f"{tag_clean} beginner guide", f"complete {tag_clean} makeover"],
        "routine": [f"daily {tag_clean} routine", f"weekend {tag_clean} project"],
    }
    for mod in intent_modifiers.get(intent, []):
        _add_candidate(mod)

    return candidates[:8]


def build_pinterest_title(
    title: str,
    topic_name: str,
    tag: str,
    intent: str,
    primary_keyword: str = "",
) -> str:
    clean_title = _normalize_whitespace(title)

    if 40 <= len(clean_title) <= 70 and not _is_generic_fallback_title(clean_title):
        return clean_title

    if len(clean_title) > 70:
        trimmed = _trim_at_word_boundary(clean_title, 70)
        if 40 <= len(trimmed) <= 70 and not _is_generic_fallback_title(trimmed):
            return trimmed

    tag_clean = tag.replace("-", " ").title()
    core = _trim_at_word_boundary(
        primary_keyword.title() if primary_keyword else topic_name.title(), 35
    )
    seed = f"{title}-{topic_name}-{intent}"

    intent_title_templates: dict[str, list[str]] = {
        "how_to": [
            "How to Elevate Your {tag} Step-by-Step",
            "A Realistic Way to Organize Your {tag}",
            "How to Master {tag} Without Clutter",
        ],
        "list": [
            "The Best {tag} Ideas for a Better Home",
            "Top Inspiring {tag} Ideas to Try Today",
            "Key {tag} Swaps That Transform Your Space",
        ],
        "checklist": [
            "The Ultimate Weekend {tag} Checklist",
            "A Simple {tag} Action Plan for Any Home",
            "Your Complete {tag} Organizing Checklist",
        ],
        "tips": [
            "Practical {tag} Tips That Actually Work",
            "Smart Home & {tag} Hacks for Busy Days",
            "Simple {tag} Habits for a Clutter-Free Home",
        ],
        "mistakes": [
            "Common {tag} Mistakes and How to Fix Them",
            "Stop Making These Everyday {tag} Mistakes",
            "Hidden {tag} Organizing Mistakes to Avoid",
        ],
        "guide": [
            "The Complete Beginner's Guide to {tag}",
            "Everything You Need to Know About {tag}",
            "Your Practical Blueprint for Better {tag}",
        ],
        "routine": [
            "A Simple {tag} Routine That Keeps Order",
            "Realistic {tag} Habits for Modern Homes",
            "The 15-Minute Home Reset for {tag}",
        ],
    }

    templates = intent_title_templates.get(intent, intent_title_templates["guide"])
    idx = _stable_hash_index(seed, len(templates))
    template = templates[idx]

    candidate = template.format(core=core, tag=tag_clean)
    candidate = _trim_at_word_boundary(candidate, 70)

    if len(candidate) < 40:
        candidate = f"{candidate} ({tag_clean} Ideas)"
        candidate = _trim_at_word_boundary(candidate, 70)

    return candidate


def build_pinterest_description(
    title: str,
    meta_description: str,
    tag: str,
    intent: str,
    primary_keyword: str,
    html: str = "",
) -> str:
    tag_clean = tag.replace("-", " ").strip()
    clean_meta = _normalize_whitespace(meta_description)

    intent_ctas: dict[str, str] = {
        "how_to": "Save this pin to follow these simple home steps!",
        "list": "Save this pin to keep these inspiring home ideas handy!",
        "checklist": "Save this checklist and start your weekend home reset!",
        "tips": "Save this pin for daily home and organizing inspiration!",
        "mistakes": "Save this pin and avoid these common decorating mistakes!",
        "guide": "Save this pin and read the complete home styling guide!",
        "routine": "Save this routine and keep your space clutter-free!",
    }
    cta = intent_ctas.get(intent, "Save this pin for smart ideas for a better home!")

    if 80 <= len(clean_meta) <= 190:
        base = clean_meta.rstrip(".!?")
        combined = f"{base}. {cta}"
        if 140 <= len(combined) <= 260:
            return combined

    intent_descriptions: dict[str, str] = {
        "how_to": f"Looking for simple, realistic ways to upgrade your {tag_clean}? Discover practical steps designed for everyday living and beautiful homes. {cta}",
        "list": f"Explore the best aesthetic and practical {tag_clean} ideas to transform your space. Smart tips with zero fluff. {cta}",
        "checklist": f"Use this practical {tag_clean} checklist to organize your space without the overwhelm. Perfect for busy households. {cta}",
        "tips": f"Get functional {tag_clean} tips that actually fit your home and routine. Realistic ideas that make a noticeable difference. {cta}",
        "mistakes": f"Are you making common {tag_clean} mistakes without realizing it? Discover what to avoid and what actually works for lasting order. {cta}",
        "guide": f"Your practical, inspiring guide to {tag_clean}. Real solutions and styling ideas designed for everyday living. {cta}",
        "routine": f"Build a consistent {tag_clean} system that keeps your home organized effortlessly. Start small and enjoy a calmer space. {cta}",
    }

    desc = intent_descriptions.get(
        intent,
        f"Discover practical, inspiring {tag_clean} ideas designed for modern living. Simple solutions for a home you love. {cta}",
    )
    desc = _normalize_whitespace(desc)
    if len(desc) > 260:
        desc = _trim_at_word_boundary(desc, 260)
        if not desc.endswith((".", "!", "?")):
            desc = desc.rstrip() + "."

    if len(desc) < 140:
        desc = _trim_at_word_boundary(f"{desc} Smart ideas for a better home and everyday comfort.", 260)

    return desc


def generate_pinterest_seo(
    topic: "Topic | str",
    article_data: dict[str, Any],
    performance_tracker: PinterestPerformanceTracker | None = None,
) -> dict[str, Any]:
    from .topics import Topic as _Topic
    topic_name = topic.name if isinstance(topic, _Topic) else str(topic)
    topic_tag = topic.tag if isinstance(topic, _Topic) else ""
    tag = article_data.get("tag") or topic_tag or "home-organization"
    title = article_data.get("title", "")
    html = article_data.get("html", "")
    meta_desc = article_data.get("meta_description", "")

    intent = detect_search_intent(
        title=title,
        topic_name=topic_name,
        tag=tag,
        html=html,
        performance_tracker=performance_tracker,
    )

    primary_kw = extract_core_topic_phrase(topic_name, title)

    keywords_list = generate_search_keywords(
        topic_name=topic_name,
        title=title,
        tag=tag,
        intent=intent,
        primary_keyword=primary_kw,
        article_keywords=article_data.get("pin_keywords", ""),
    )
    keywords_csv = ", ".join(keywords_list)
    secondary_kws = [kw for kw in keywords_list if kw != primary_kw][:4]

    gemini_pin_title = _normalize_whitespace(article_data.get("pin_title", ""))
    if 40 <= len(gemini_pin_title) <= 70 and not _is_generic_fallback_title(gemini_pin_title):
        pin_title = gemini_pin_title
    else:
        pin_title = build_pinterest_title(
            title=gemini_pin_title or title,
            topic_name=topic_name,
            tag=tag,
            intent=intent,
            primary_keyword=primary_kw,
        )

    gemini_pin_desc = _normalize_whitespace(article_data.get("pin_description", ""))
    if 140 <= len(gemini_pin_desc) <= 260 and not _is_generic_fallback_description(gemini_pin_desc):
        pin_description = gemini_pin_desc
    else:
        pin_description = build_pinterest_description(
            title=title,
            meta_description=meta_desc,
            tag=tag,
            intent=intent,
            primary_keyword=primary_kw,
            html=html,
        )

    board = US_PINTEREST_BOARDS.get(tag, "Home Organization & Storage Solutions")

    seo_result = {
        "intent": intent,
        "primary_keyword": primary_kw,
        "secondary_keywords": secondary_kws,
        "pin_title": pin_title,
        "pin_description": pin_description,
        "keywords": keywords_csv,
        "keywords_list": keywords_list,
        "board": board,
    }

    return seo_result


def generate_triple_pins(
    topic: "Topic | str",
    article_data: dict[str, Any],
    performance_tracker: PinterestPerformanceTracker | None = None,
) -> list[dict[str, Any]]:
    from .topics import Topic as _Topic
    topic_name = topic.name if isinstance(topic, _Topic) else str(topic)
    topic_tag = topic.tag if isinstance(topic, _Topic) else ""
    tag = article_data.get("tag") or topic_tag or "home-organization"
    title = article_data.get("title", "")
    html = article_data.get("html", "")
    meta_desc = article_data.get("meta_description", "")
    primary_kw = extract_core_topic_phrase(topic_name, title)
    board = US_PINTEREST_BOARDS.get(tag, "Home Organization & Storage Solutions")

    gemini_edu = article_data.get("pin_educational") if isinstance(article_data.get("pin_educational"), dict) else {}
    gemini_prob = article_data.get("pin_problem_solution") if isinstance(article_data.get("pin_problem_solution"), dict) else {}
    gemini_seo = article_data.get("pin_seo_search") if isinstance(article_data.get("pin_seo_search"), dict) else {}

    # 1. Educational / Guide
    edu_intent = "guide"
    edu_keywords_list = generate_search_keywords(
        topic_name=topic_name,
        title=title,
        tag=tag,
        intent=edu_intent,
        primary_keyword=primary_kw,
        article_keywords=gemini_edu.get("pin_keywords", article_data.get("pin_keywords", "")),
    )
    raw_edu_title = _normalize_whitespace(gemini_edu.get("pin_title", ""))
    if 40 <= len(raw_edu_title) <= 70 and not _is_generic_fallback_title(raw_edu_title):
        edu_title = raw_edu_title
    else:
        edu_title = build_pinterest_title(
            title=f"The Practical Guide to {primary_kw.title()}" if primary_kw else title,
            topic_name=topic_name,
            tag=tag,
            intent=edu_intent,
            primary_keyword=primary_kw,
        )

    raw_edu_desc = _normalize_whitespace(gemini_edu.get("pin_description", ""))
    if 140 <= len(raw_edu_desc) <= 260 and not _is_generic_fallback_description(raw_edu_desc):
        edu_desc = raw_edu_desc
    else:
        edu_desc = build_pinterest_description(
            title=title,
            meta_description=meta_desc,
            tag=tag,
            intent=edu_intent,
            primary_keyword=primary_kw,
            html=html,
        )

    pin_1 = {
        "pin_type": "educational",
        "intent": edu_intent,
        "primary_keyword": primary_kw,
        "pin_title": edu_title,
        "pin_description": edu_desc,
        "keywords": ", ".join(edu_keywords_list),
        "keywords_list": edu_keywords_list,
        "board": board,
        "slot_index": 0,
        "utm_content": "pin_educational",
    }

    # 2. Problem / Solution
    prob_intent = "mistakes"
    prob_keywords_list = generate_search_keywords(
        topic_name=topic_name,
        title=title,
        tag=tag,
        intent=prob_intent,
        primary_keyword=primary_kw,
        article_keywords=gemini_prob.get("pin_keywords", article_data.get("pin_keywords", "")),
    )
    raw_prob_title = _normalize_whitespace(gemini_prob.get("pin_title", ""))
    if 40 <= len(raw_prob_title) <= 70 and not _is_generic_fallback_title(raw_prob_title):
        prob_title = raw_prob_title
    else:
        prob_title = build_pinterest_title(
            title=f"Common {tag.replace('-', ' ').title()} Mistakes and How to Avoid Them",
            topic_name=topic_name,
            tag=tag,
            intent=prob_intent,
            primary_keyword=primary_kw,
        )

    raw_prob_desc = _normalize_whitespace(gemini_prob.get("pin_description", ""))
    if 140 <= len(raw_prob_desc) <= 260 and not _is_generic_fallback_description(raw_prob_desc):
        prob_desc = raw_prob_desc
    else:
        prob_desc = build_pinterest_description(
            title=title,
            meta_description=f"Avoid frustrating home mistakes with {primary_kw}. Learn what commonly goes wrong and simple proven solutions.",
            tag=tag,
            intent=prob_intent,
            primary_keyword=primary_kw,
            html=html,
        )

    pin_2 = {
        "pin_type": "problem_solution",
        "intent": prob_intent,
        "primary_keyword": primary_kw,
        "pin_title": prob_title,
        "pin_description": prob_desc,
        "keywords": ", ".join(prob_keywords_list),
        "keywords_list": prob_keywords_list,
        "board": board,
        "slot_index": 2,
        "utm_content": "pin_problem_solution",
    }

    # 3. SEO / Search
    seo_intent = "list"
    seo_keywords_list = generate_search_keywords(
        topic_name=topic_name,
        title=title,
        tag=tag,
        intent=seo_intent,
        primary_keyword=primary_kw,
        article_keywords=gemini_seo.get("pin_keywords", article_data.get("pin_keywords", "")),
    )
    raw_seo_title = _normalize_whitespace(gemini_seo.get("pin_title", ""))
    if 40 <= len(raw_seo_title) <= 70 and not _is_generic_fallback_title(raw_seo_title):
        seo_title = raw_seo_title
    else:
        seo_title = build_pinterest_title(
            title=f"Top {tag.replace('-', ' ').title()} Ideas for Everyday Living",
            topic_name=topic_name,
            tag=tag,
            intent=seo_intent,
            primary_keyword=primary_kw,
        )

    raw_seo_desc = _normalize_whitespace(gemini_seo.get("pin_description", ""))
    if 140 <= len(raw_seo_desc) <= 260 and not _is_generic_fallback_description(raw_seo_desc):
        seo_desc = raw_seo_desc
    else:
        seo_desc = build_pinterest_description(
            title=title,
            meta_description=meta_desc,
            tag=tag,
            intent=seo_intent,
            primary_keyword=primary_kw,
            html=html,
        )

    pin_3 = {
        "pin_type": "seo_search",
        "intent": seo_intent,
        "primary_keyword": primary_kw,
        "pin_title": seo_title,
        "pin_description": seo_desc,
        "keywords": ", ".join(seo_keywords_list),
        "keywords_list": seo_keywords_list,
        "board": board,
        "slot_index": 4,
        "utm_content": "pin_seo_search",
    }

    return [pin_1, pin_2, pin_3]
