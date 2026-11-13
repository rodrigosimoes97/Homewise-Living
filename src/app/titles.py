from __future__ import annotations

import random

from .topics import Topic


# ──────────────────────────────────────────────────────────────────────────────
# Geração de título local (sem Gemini) — usado como hint para o artigo
# ──────────────────────────────────────────────────────────────────────────────

_TITLE_TEMPLATES = [
    "How to {verb} Your {topic} Without Breaking the Bank",
    "{count} Practical Ways to {verb} Your {topic} This Weekend",
    "Struggling with {topic}? Try This {adj} Reset",
    "Create a Calmer Space with This {adj} {topic} Guide",
    "The Honest Guide to {topic} for Busy Homes",
    "What Nobody Tells You About {topic}",
    "Stop Overcomplicating {topic} — Here's What Actually Works",
    "A Realistic {topic} Setup That Fits Your Daily Routine",
    "How to Organize {topic} and Keep It Clutter-Free",
    "{count} Inspiring {topic} Ideas Worth Trying",
]

_VERBS = ["transform", "organize", "upgrade", "refresh", "elevate", "simplify", "declutter", "style"]
_ADJS = ["Simple", "Cozy", "15-Minute", "Practical", "Modern", "Functional"]
_COUNTS = ["3", "5", "7", "4", "6"]


def _local_title_hint(topic: Topic) -> str:
    """
    Gera um hint de título localmente (sem Gemini).
    O modelo refinará isso no prompt unificado de artigo.
    """
    template = random.choice(_TITLE_TEMPLATES)
    title = template.format(
        topic=topic.name,
        verb=random.choice(_VERBS),
        adj=random.choice(_ADJS),
        count=random.choice(_COUNTS),
    )
    if len(title) > 80:
        title = title[:77].rsplit(" ", 1)[0] + "..."
    return title


# ──────────────────────────────────────────────────────────────────────────────
# Compatibilidade retroativa
# ──────────────────────────────────────────────────────────────────────────────

TITLE_PROMPT = """You are an expert SEO editor for Homewise Living, a premier US home and lifestyle publication.
Return JSON only with schema: {{"titles": ["...", "..."]}}.
Create exactly 10 unique, high-CTR titles in US English for topic '{topic_name}' and angle '{angle}'.

Rules for High-Quality Titles:
- Use warm, inspiring power words (e.g., Simple, Practical, Modern, Cozy, Functional, Beautiful, Effortless).
- Mix different formats:
  - The "How-To" (e.g., How to Actually Organize [Space] Without Overwhelm)
  - The "Listicle" (e.g., 5 Practical Ways to Elevate Your [Space] Today)
  - The "Question" (e.g., Struggling with [Topic]? Try This 15-Minute Reset)
  - The "Inspiration-First" (e.g., Transform Your [Space] with These Everyday Ideas)
- Target US search intent: practical solutions, small-space organizing, aesthetic upgrades, and cozy living.
- Avoid these phrases: Ultimate Guide, Best Ever, Secrets Revealed, You Won't Believe.
- Each title must be between 40 and 70 characters.
- No numbering, no bullets, plain title text only.
"""


def generate_titles(
    client: object,
    topic: Topic,
    excluded_titles: list[str] | None = None,
) -> list[str]:
    """
    Gera títulos via Gemini. Mantida para compatibilidade retroativa.
    """
    from .gemini_client import GeminiClient

    assert isinstance(client, GeminiClient)

    excluded_text = ""
    if excluded_titles:
        excluded_text = f"\nAvoid these exact titles: {', '.join(excluded_titles[:10])}"

    payload = client.generate_json(
        TITLE_PROMPT.format(topic_name=topic.name, angle=topic.angle) + excluded_text,
        max_output_tokens=500,
    )
    titles = payload.get("titles", [])
    clean = []
    for title in titles:
        if not isinstance(title, str):
            continue
        t = " ".join(title.strip().split())
        if t and "ultimate guide" not in t.lower() and "best ever" not in t.lower():
            if not excluded_titles or t not in excluded_titles:
                clean.append(t)
    return clean or [_local_title_hint(topic)]
