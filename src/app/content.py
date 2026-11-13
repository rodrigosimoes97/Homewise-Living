from __future__ import annotations

import hashlib
import re
import urllib.parse
from typing import Any

from .gemini_client import GeminiClient
from .topics import Topic

ALLOWED_TAGS = {
    "home-organization",
    "kitchen",
    "decor",
    "garden",
    "home-office",
    "pets",
}

# ──────────────────────────────────────────────────────────────────────────────
# Prompt único: gera título + artigo completo em 1 chamada Gemini
# ──────────────────────────────────────────────────────────────────────────────
CONTENT_PROMPT = """\
Write a high-quality, inspiring, and deeply practical home and lifestyle article for a discerning US audience.
Return a strict JSON object only (no markdown, no code fences) with EXACTLY these keys:
title, slug, meta_description, html, image_query, pin_title, pin_description, pin_keywords, alt_text, tag, faq, pin_educational, pin_problem_solution, pin_seo_search

CRITICAL JSON RULES (read carefully before generating):
- NO literal newlines inside any JSON string value — use \\n instead.
- Escape all double-quote characters inside strings with \\".
- The entire response must be a single valid JSON object.
- Do NOT wrap in ```json or any markdown.

EDITORIAL & LIFESTYLE INTEGRITY RULES:
- Write in warm, authoritative, highly useful, and engaging US lifestyle and home journalism English.
- Target US homeowners, apartment dwellers, and organizers seeking realistic, sustainable, aesthetic, and functional home solutions.
- Emphasize the "Modern Organic Living" philosophy: clean aesthetics, functional storage, cozy textures, natural materials, and smart everyday habits.
- ACTIONABLE & HIGHLY USEFUL CONTENT:
  - Do NOT provide vague or generic platitudes like "keep things clean" or "organize your room".
  - Explain the spatial, functional, and organizational logic in clear, accessible terms.
  - Provide specific, daily or weekend actionable steps: dimensions, spatial zoning, decluttering workflows, lighting techniques, plant care tips, or material choices.
- DO NOT invent fictitious personal anecdotes, fake first-person stories, or unverified claims.
  Do NOT use fabricated "I," "me," "my personal struggle" personas. Write with an inspiring,
  objective, and empathetic voice focusing on the reader ("you").
- Minimum 500 words in the html body (excluding FAQ and metadata). Avoid superficial AI filler.

SEO & CONTENT STRUCTURE:
- Include {topic_name} naturally in: title, first paragraph, headings, and meta_description.
- Provide a clear, actionable angle: {angle}.

Input:
- topic_name: {topic_name}
- angle: {angle}
- title_hint: {title_hint}
- mode: {mode}
- offer_name: {offer_name}
- offer_link: {offer_link}

Allowed tag values (pick one, lowercase-hyphenated):
{allowed_tags}

Required HTML elements inside "html" field:
1. Dilemma & Solution Box: <div class='myth-fact'><div class='myth-header'>Common Dilemma</div><div class='myth-body'>...</div><div class='fact-header'>Practical Solution</div><div class='fact-body'>...</div></div>
2. Actionable Step / Quick Win: <div class='quick-win'><h3>Practical Daily Action</h3><p>...</p></div>
3. Expert Insight Quote: <blockquote>...</blockquote>
4. Exactly 5 internal link placeholders:
   href="#recent-1" (anchor: related home guide)
   href="#recent-2" (anchor: practical organizing strategy)
   href="#recent-3" (anchor: everyday design tip)
   href="#recent-4" (anchor: room styling breakdown)
   href="#recent-5" (anchor: explore more [tag] articles)
5. Mandatory Resources Section at the end of the body:
   <section class='scientific-sources'><h2>Helpful Resources & Guides</h2><ul><li><a href='https://www.thespruce.com/...' target='_blank' rel='noopener noreferrer'>Design & Living Guide — The Spruce</a></li><li><a href='https://www.architecturaldigest.com/...' target='_blank' rel='noopener noreferrer'>Interior Inspiration — Architectural Digest</a></li><li><a href='https://www.bhg.com/...' target='_blank' rel='noopener noreferrer'>Home & Garden Advice — Better Homes & Gardens</a></li></ul></section>
   (Include 2-4 references to reputable home, gardening, and living authorities such as The Spruce, Architectural Digest, Better Homes & Gardens, Bob Vila, HGTV, or Good Housekeeping, each with a clickable <a href='...'> link).
6. If mode=offer: ethical recommendation + exact sentence "Disclosure: This page may contain affiliate links."
7. If mode=info: do NOT include affiliate links.

For "faq": array of 3-5 objects [{{"question":"...","answer":"..."}}]. Helpful, concise answers.
For "title": clear, high-CTR, accurate SEO title (40–70 chars) based on title_hint. Avoid sensationalist clickbait.
For "slug": URL-friendly version of the title (lowercase, hyphens, max 80 chars, no extension).
For "meta_description": 140–160 chars, compelling, keyword-rich and actionable.
For "image_query": 3–5 word natural Pexels search query (e.g. "modern cozy kitchen storage", "minimalist living room interior").
For "pin_title": 40–70 chars, benefit-driven and clickable for US Pinterest audience.
For "pin_description": 150–250 chars. Engaging, natural US English highlighting aesthetic and practical benefits, weaving in 2-3 search phrases with a clear CTA (e.g. "Save this for your next home project!", "Pin this for easy home inspiration!").
For "pin_keywords": 4–6 authentic US search phrases (2–3 words each, comma-separated).
For "alt_text": accurate, descriptive image alt text (10–20 words).

Pinterest Angle Variations (Provide 3 distinct angles for Pinterest pins):
- "pin_educational": {{"pin_title": "40-70 chars focused on guide/how-to/step-by-step", "pin_description": "140-260 chars explaining practical benefits and clear action", "pin_keywords": "4-6 search phrases"}}
- "pin_problem_solution": {{"pin_title": "40-70 chars focused on clutter/layout fix/clever hack", "pin_description": "140-260 chars addressing pain point and practical fix", "pin_keywords": "4-6 search phrases"}}
- "pin_seo_search": {{"pin_title": "40-70 chars capturing high-volume Pinterest search intent/ideas/list", "pin_description": "140-260 chars rich in search queries with strong save CTA", "pin_keywords": "4-6 search phrases"}}
"""


def normalize_tag(raw: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (raw or ""))
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    return cleaned if cleaned in ALLOWED_TAGS else ""


def generate_article(
    client: GeminiClient,
    topic: Topic,
    title_hint: str,
    mode: str,
    offer: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Gera artigo completo (incluindo título final) em uma única chamada Gemini.
    """
    payload = client.generate_json(
        CONTENT_PROMPT.format(
            topic_name=topic.name,
            angle=topic.angle,
            title_hint=title_hint,
            mode=mode,
            offer_name=(offer or {}).get("name", ""),
            offer_link=(offer or {}).get("link", ""),
            allowed_tags=", ".join(sorted(ALLOWED_TAGS)),
        ),
        max_output_tokens=4096,
    )

    required = [
        "title",
        "slug",
        "meta_description",
        "html",
        "image_query",
        "pin_title",
        "pin_description",
        "alt_text",
    ]
    for key in required:
        if key not in payload or not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError(f"Campo obrigatório ausente ou inválido: {key}")

    cleaned_slug = _clean_slug(payload["slug"])
    final_tag = normalize_tag(str(payload.get("tag", ""))) or normalize_tag(topic.tag) or "home-organization"
    payload["slug"] = cleaned_slug
    payload["tag"] = final_tag

    # pin_title e pin_description
    pin_title = str(payload.get("pin_title", "")).strip()
    if not (40 <= len(pin_title) <= 70):
        pin_title = _build_pin_title(payload["title"], cleaned_slug, payload.get("meta_description", ""), final_tag)
    payload["pin_title"] = pin_title

    pin_desc = str(payload.get("pin_description", "")).strip()
    if not (140 <= len(pin_desc) <= 260):
        pin_desc = _build_pin_description(
            payload["title"],
            cleaned_slug,
            final_tag,
            payload.get("meta_description", ""),
            payload.get("html", ""),
        )
    payload["pin_description"] = pin_desc

    pin_kws = str(payload.get("pin_keywords", "")).strip()
    payload["pin_keywords"] = pin_kws

    def _normalize_sub_pin(raw: Any, default_title: str, default_desc: str, default_kws: str) -> dict[str, str]:
        if not isinstance(raw, dict):
            return {"pin_title": default_title, "pin_description": default_desc, "pin_keywords": default_kws}
        t = str(raw.get("pin_title", "")).strip() or default_title
        d = str(raw.get("pin_description", "")).strip() or default_desc
        k = str(raw.get("pin_keywords", "")).strip() or default_kws
        return {"pin_title": t, "pin_description": d, "pin_keywords": k}

    payload["pin_educational"] = _normalize_sub_pin(
        payload.get("pin_educational"), payload["pin_title"], payload["pin_description"], payload["pin_keywords"]
    )
    payload["pin_problem_solution"] = _normalize_sub_pin(
        payload.get("pin_problem_solution"), payload["pin_title"], payload["pin_description"], payload["pin_keywords"]
    )
    payload["pin_seo_search"] = _normalize_sub_pin(
        payload.get("pin_seo_search"), payload["pin_title"], payload["pin_description"], payload["pin_keywords"]
    )

    if mode == "info":
        payload["html"] = payload["html"].replace("Disclosure: This page may contain affiliate links.", "")

    payload["faq"] = _normalize_faq(payload.get("faq"))
    payload["recipe"] = None

    payload["html"] = ensure_scientific_links(payload["html"], topic.name, final_tag)

    is_valid, reason = validate_article_quality(payload, topic.name)
    if not is_valid:
        raise ValueError(f"Artigo gerado rejeitado no controle editorial: {reason}")

    return payload


# ──────────────────────────────────────────────────────────────────────────────
# Validação Editorial de Qualidade
# ──────────────────────────────────────────────────────────────────────────────

FICTITIOUS_FIRST_PERSON_PATTERNS = [
    r"\bwhen I was diagnosed\b",
    r"\bin my personal experience\b",
    r"\bmy personal struggle\b",
    r"\bI personally struggled\b",
    r"\bI personally tried\b",
    r"\bas a former patient\b",
    r"\bmy personal journey with\b",
    r"\bI used to suffer from\b",
    r"\bmy doctor warned me personally\b",
]

FORBIDDEN_CURE_PATTERNS = [
    r"\bmiracle cure\b",
    r"\bguaranteed cure\b",
    r"\bcures (cancer|diabetes|alzheimer|dementia|hypertension|arthritis)\b",
    r"\bsecret cure\b",
    r"\binstant cure\b",
    r"\b100% cure\b",
    r"\bcure all diseases\b",
]

HOME_INDICATOR_KEYWORDS = [
    "home", "room", "space", "design", "decor", "organize", "storage",
    "tips", "practical", "kitchen", "living", "setup", "ideas", "guide",
    "simple", "clean", "furniture", "comfort", "daily", "style", "plants",
    "garden", "office", "bedroom", "closet", "pantry", "routine", "solutions",
]

ACTIONABLE_INDICATOR_KEYWORDS = [
    "practical", "daily", "routine", "step", "setup", "action",
    "habit", "habits", "guide", "how to", "timing", "schedule",
    "tips", "actionable", "strategy", "strategies", "organize", "ideas",
]

AUTHORITY_RESOURCE_PATTERN = re.compile(
    r'href=[\'"]https?://(?:www\.)?(?:thespruce\.com|architecturaldigest\.com|bhg\.com|bobvila\.com|hgtv\.com|goodhousekeeping\.com|apartmenttherapy\.com|realsimple\.com|dwell\.com|elledecor\.com|housebeautiful\.com)[^\'"]*[\'"]',
    re.IGNORECASE,
)
SCIENTIFIC_URL_PATTERN = AUTHORITY_RESOURCE_PATTERN  # Alias para compatibilidade


def ensure_scientific_links(html: str, topic_name: str, tag: str) -> str:
    """
    Garante que o artigo contenha links clicáveis diretos (<a href="...">)
    para fontes de autoridade em Home, Design e Lifestyle:
    - The Spruce
    - Architectural Digest
    - Better Homes & Gardens
    - Bob Vila
    """
    if not html:
        return html

    existing_links = AUTHORITY_RESOURCE_PATTERN.findall(html)
    if len(existing_links) >= 2:
        return html

    clean_tag = (tag or "home-organization").replace("-", " ")
    topic_clean = re.sub(r"[^\w\s]", "", topic_name).strip()
    encoded_topic = urllib.parse.quote_plus(topic_clean or clean_tag)

    default_links = [
        f'<a href="https://www.thespruce.com/search?q={encoded_topic}" target="_blank" rel="noopener noreferrer">The Spruce — Practical Living & Home Guide for {topic_name}</a>',
        f'<a href="https://www.architecturaldigest.com/search?q={encoded_topic}" target="_blank" rel="noopener noreferrer">Architectural Digest — Design & Spatial Inspiration</a>',
        f'<a href="https://www.bhg.com/search?q={encoded_topic}" target="_blank" rel="noopener noreferrer">Better Homes & Gardens — Everyday Living & Organization</a>',
    ]

    sources_match = re.search(r"<section class=['\"]scientific-sources['\"]>(.*?)</section>", html, flags=re.DOTALL | re.IGNORECASE)
    if sources_match:
        section_content = sources_match.group(1)
        li_matches = list(re.finditer(r"<li>(.*?)</li>", section_content, flags=re.DOTALL | re.IGNORECASE))
        if li_matches:
            new_lis = []
            trusted_providers = [
                ("The Spruce", "https://www.thespruce.com/search?q="),
                ("Architectural Digest", "https://www.architecturaldigest.com/search?q="),
                ("Better Homes & Gardens", "https://www.bhg.com/search?q="),
            ]
            for idx, m in enumerate(li_matches):
                inner = m.group(1).strip()
                if AUTHORITY_RESOURCE_PATTERN.search(inner) or "<a " in inner:
                    new_lis.append(f"<li>{inner}</li>")
                else:
                    provider_name, provider_url = trusted_providers[idx % len(trusted_providers)]
                    li_plain = re.sub(r"<[^>]+>", "", inner).strip()
                    query = urllib.parse.quote_plus(re.sub(r"[^\w\s]", " ", li_plain)[:60].strip())
                    new_lis.append(
                        f'<li><a href="{provider_url}{query}" target="_blank" rel="noopener noreferrer">{li_plain} — {provider_name}</a></li>'
                    )
            if len(new_lis) < 2:
                for link in default_links[:2]:
                    new_lis.append(f"<li>{link}</li>")
            new_section = f"<section class='scientific-sources'><h2>Helpful Resources & Guides</h2><ul>{''.join(new_lis)}</ul></section>"
            return html[:sources_match.start()] + new_section + html[sources_match.end():]

    new_section = (
        f"<section class='scientific-sources'><h2>Helpful Resources & Guides</h2>"
        f"<ul>{''.join(f'<li>{link}</li>' for link in default_links)}</ul></section>"
    )
    return f"{html}\n{new_section}"


def validate_article_quality(post: dict[str, Any], topic_name: str) -> tuple[bool, str]:
    """
    Validação editorial sênior para Homewise Living:
    - Mínimo de 450 palavras de texto limpo
    - Presença do tópico no título ou corpo
    - Ausência de anedotas pessoais autobiográficas fictícias em 1ª pessoa
    - Ausência de promessas de cura perigosas
    - Variedade lexical (TTR >= 0.35)
    - Pelo menos 2 perguntas no FAQ
    - Presença de links para fontes e guias confiáveis
    - Presença de conteúdo prático e acionável com utilidade para o lar
    """
    if not isinstance(post, dict):
        return False, "Payload não é um dicionário válido"

    html = str(post.get("html", "")).strip()
    title = str(post.get("title", "")).strip()

    if not title:
        return False, "Título do artigo ausente"

    # 1. Contagem de palavras do corpo
    clean_text = re.sub(r"<[^>]+>", " ", html)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{2,}\b", clean_text)]
    word_count = len(words)

    if word_count < 450:
        return False, f"Artigo muito superficial: {word_count} palavras (mínimo exigido: 450)"

    # 2. Presença do tópico no título ou corpo
    t_tokens = [t.lower() for t in re.findall(r"\b[a-zA-Z]{3,}\b", topic_name)]
    lower_title = title.lower()
    lower_body = clean_text.lower()
    found_topic = any(tok in lower_title or tok in lower_body for tok in t_tokens)

    if not found_topic and topic_name.lower() not in lower_title and topic_name.lower() not in lower_body:
        return False, f"Tópico focal '{topic_name}' ausente no título e corpo"

    # 3. Ausência de relatos pessoais autobiográficos fictícios
    for pattern in FICTITIOUS_FIRST_PERSON_PATTERNS:
        if re.search(pattern, clean_text, flags=re.IGNORECASE):
            return False, f"Artigo contém relato pessoal fictício em 1ª pessoa proibido: '{pattern}'"

    # 4. Ausência de promessas de cura proibidas
    for pattern in FORBIDDEN_CURE_PATTERNS:
        if re.search(pattern, clean_text, flags=re.IGNORECASE):
            return False, f"Artigo contém alegação de cura perigosa proibida: '{pattern}'"

    # 5. Marcadores temáticos de home & living
    found_home_markers = sum(1 for kw in HOME_INDICATOR_KEYWORDS if kw in words)
    if found_home_markers < 3:
        return False, f"Artigo sem vocabulário temático suficiente sobre casa/estilo de vida (apenas {found_home_markers} termos encontrados)"

    # 6. Variedade lexical
    meaningful_words = [w for w in words if len(w) >= 4]
    if meaningful_words:
        unique_ratio = len(set(meaningful_words)) / len(meaningful_words)
        if unique_ratio < 0.35:
            return False, f"Artigo superficial com vocabulário repetitivo (variedade lexical: {unique_ratio:.2f} < 0.35)"

    # 7. FAQs
    faq = post.get("faq")
    if not isinstance(faq, list) or len(faq) < 2:
        return False, "Artigo deve conter FAQ estruturada com pelo menos 2 perguntas"

    # 8. Links para fontes e guias confiáveis
    if not AUTHORITY_RESOURCE_PATTERN.search(html):
        return False, "Artigo deve conter pelo menos um link direto e clicável para fontes ou guias confiáveis (The Spruce, Architectural Digest, Better Homes & Gardens, Bob Vila)"

    # 9. Verificação de conteúdo prático e acionável
    found_action_markers = sum(1 for kw in ACTIONABLE_INDICATOR_KEYWORDS if kw in words)
    if found_action_markers < 3 and "<div class='quick-win'>" not in html and "<div class=\"quick-win\">" not in html:
        return False, "Artigo sem conteúdo acionável ou orientações práticas suficientes para o leitor"

    return True, ""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_faq(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, str]] = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if question and answer:
            items.append({"question": question, "answer": answer})
    return items


def _clean_slug(raw: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")[:80]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _trim_at_word_boundary(text: str, max_chars: int) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized
    trimmed = normalized[: max_chars + 1].rsplit(" ", 1)[0]
    return trimmed if trimmed else normalized[:max_chars].strip()


def _stable_template_index(seed: str, size: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    hashed = int(digest[:8], 16)
    spread = sum(ord(ch) for ch in seed)
    return (hashed + spread) % size


def _build_pin_title(title: str, slug: str, meta_description: str, tag: str) -> str:
    normalized_title = _normalize_whitespace(title)
    if 40 <= len(normalized_title) <= 70:
        return normalized_title

    keyword = _trim_at_word_boundary(normalized_title, 38)
    benefit_hint = _trim_at_word_boundary(meta_description or f"smart {tag.replace('-', ' ')} ideas", 32)
    templates = [
        "Smart Home Ideas: {keyword}",
        "A Simpler Way to {keyword}",
        "Transform Your Home With {keyword}",
        "Easy Home Projects: {keyword}",
        "Small Space Solutions: {keyword}",
        "Your Weekend Guide to {keyword}",
        "The Complete Guide to {keyword}",
        "How to Actually Master {keyword}",
        "Declutter & Organize: {keyword}",
        "Better {tag} Starts Here: {keyword}",
        "Design Inspiration: {keyword}",
        "Your 10-Minute Reset for {keyword}",
    ]
    idx = _stable_template_index(slug or normalized_title, len(templates))
    candidate = templates[idx].format(keyword=keyword.lower(), tag=tag.replace("-", " "))
    if len(candidate) < 40:
        candidate = _normalize_whitespace(f"{candidate}: {benefit_hint}")
    return _trim_at_word_boundary(candidate, 70)


_DUP_WORD_RE = re.compile(r"\b(\w+)(\s+\1\b)+", re.IGNORECASE)
_LEADING_LABEL_RE = re.compile(r"^\s*(question|tip|guide)\s*:\s*", re.IGNORECASE)


def _cleanup_pin_description(text: str, cta: str) -> str:
    text = _normalize_whitespace(text)
    text = _LEADING_LABEL_RE.sub("", text).strip()

    lower = text.lower()
    pos = lower.find(" based on ")
    if pos != -1:
        text = text[:pos].rstrip()
        if not text.endswith((".", "?", "!")):
            text += "."

    while True:
        new = _DUP_WORD_RE.sub(r"\1", text)
        if new == text:
            break
        text = new

    text = text.replace("?.", "?").replace(".?", "?")
    text = re.sub(r"\.\.+", ".", text)
    text = re.sub(r"\?\?+", "?", text)
    text = re.sub(r"!!+", "!", text)

    cta_clean = cta.strip().rstrip(".!?")
    for variant in ["Save this", "Try this today", "Read the full guide"]:
        variant_clean = variant.strip().rstrip(".!?")
        text = re.sub(rf"\s*{re.escape(variant_clean)}[.!?]\s*$", "", text, flags=re.IGNORECASE).rstrip()

    if not text.endswith((".", "?", "!")):
        text += "."
    text = text.rstrip() + f" {cta_clean}."

    return _normalize_whitespace(text)


def _build_pin_description(title: str, slug: str, tag: str, meta_description: str, html: str) -> str:
    del title
    tag_phrase = tag.replace("-", " ")
    base_topic = _trim_at_word_boundary(_normalize_whitespace(meta_description).lower(), 54)
    if not base_topic:
        base_topic = _trim_at_word_boundary(f"your {tag_phrase} space", 54)

    specificity = ["this weekend", "in 15 minutes", "on a budget", "step-by-step", "in small spaces", "for everyday living", "with smart storage", "starting today"]
    ctas = ["Save this home idea", "Pin this for later", "Read the full guide", "Check the home checklist", "Get the full setup"]

    seed = slug or meta_description or tag

    templates = [
        "Looking to refresh your space? This {specific} guide helps you elevate {topic} with practical solutions.",
        "Need inspiration for {tag}? Try this {specific} approach to create a clean, functional home you love.",
        "Struggling to make {topic} work in real life? Use this {specific} layout to keep things organized and stylish.",
        "If you want to upgrade your {tag}, this breakdown focuses on practical, beautiful ideas for busy households {specific}.",
        "When home organization feels overwhelming, {topic} needs a simpler plan. Start with this {specific} method.",
        "Looking for a practical home reset? This {specific} strategy helps you improve {tag} with minimal effort.",
        "Stop overcomplicating {tag}. This {specific} guide shows you exactly what works best for {topic}.",
        "Want a more inviting home with less clutter? This {specific} idea for {tag} is designed for everyday comfort.",
        "Practical and timeless tips for {tag}: this {specific} breakdown of {topic} gives you tools you can use immediately.",
    ]

    idx = _stable_template_index(seed, len(templates))
    specific = specificity[_stable_template_index(f"{seed}-specific", len(specificity))]
    cta = ctas[_stable_template_index(f"{seed}-cta", len(ctas))]

    template_text = templates[idx].format(topic=base_topic, tag=tag_phrase, specific=specific, cta=cta)
    description = _cleanup_pin_description(template_text, cta)
    description = _trim_at_word_boundary(description, 260)

    if len(description) < 140:
        extra = "Simple, beautiful ideas crafted for everyday living."
        cta_sentence = f" {cta.strip().rstrip('.!?')}."
        if description.endswith(cta_sentence):
            base = description[: -len(cta_sentence)].rstrip()
            if not base.endswith((".", "?", "!")):
                base += "."
            description = _trim_at_word_boundary(f"{base} {extra} {cta.strip().rstrip('.!?')}.", 260)
        else:
            description = _trim_at_word_boundary(f"{description} {extra}", 260)

        description = _cleanup_pin_description(description, cta)
        description = _trim_at_word_boundary(description, 260)

    return description
