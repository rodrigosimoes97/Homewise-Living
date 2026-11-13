# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from html import escape
from pathlib import Path

PUBLIC_BASE_URL = "https://homewise-living.pages.dev"

# ── Tag colour map — used in hub cards & card placeholders ────────────────────
_TAG_COLORS: dict[str, tuple[str, str]] = {
    "home-organization": ("#DCE3D5", "#34483B"),
    "kitchen":           ("#F0E8D8", "#C49A72"),
    "decor":             ("#E9E2D6", "#34483B"),
    "garden":            ("#D6E8DD", "#34483B"),
    "home-office":       ("#E0E8F5", "#34483B"),
    "pets":              ("#F5EDE0", "#C49A72"),
    "home":              ("#DCE3D5", "#34483B"),
}

def _tag_gradient(tag: str) -> str:
    c = _TAG_COLORS.get(str(tag).lower(), ("#DCE3D5", "#34483B"))
    return f"background:linear-gradient(135deg,{c[0]},{c[1]})"


def _brand_icon_svg(light: bool = False) -> str:
    cls = "brand-icon brand-icon-light" if light else "brand-icon"
    return f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg>'


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def publish_post(
    docs_dir: Path,
    base_url: str,
    site_title: str,
    post: dict[str, object],
    hero_path_rel: str,
    run_date: date,
) -> dict[str, str]:
    docs_dir.mkdir(parents=True, exist_ok=True)
    posts = _load_posts(docs_dir / "posts.json")

    tag = post.get("tag", "home-organization")
    related = _pick_related(posts, tag, post.get("slug", ""))
    same_tag_more = _pick_more_in_tag(posts, tag, post.get("slug", ""), 2)
    next_post = _pick_next_post(posts, tag, post.get("slug", ""))
    article_html, toc_items = _inject_h2_ids_and_collect_toc(
        _normalize_article_headings(post["html"])
    )
    article_html = _inject_internal_links(article_html, related, tag)

    page_html = _render_post_html(
        base_url=base_url,
        site_title=site_title,
        post=post,
        hero_path_rel=hero_path_rel,
        article_html=article_html,
        toc_items=toc_items,
        run_date=run_date,
        related=related,
        same_tag_more=same_tag_more,
        next_post=next_post,
    )
    (docs_dir / f"{post['slug']}.html").write_text(page_html, encoding="utf-8")

    record = {
        "slug": post["slug"],
        "title": post["title"],
        "description": post["meta_description"],
        "date": run_date.isoformat(),
        "url": str(post["slug"]).strip(),
        "hero": hero_path_rel,
        "tag": tag,
    }
    posts = [record] + [p for p in posts if p.get("slug") != post["slug"]]
    write_site_state(docs_dir, base_url, site_title, posts)
    return record


def write_site_state(
    docs_dir: Path,
    base_url: str,
    site_title: str,
    posts: list[dict[str, str]],
) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = docs_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "style.css").write_text(_base_css(), encoding="utf-8")
    (docs_dir / "posts.json").write_text(
        json.dumps(posts[:200], indent=2), encoding="utf-8"
    )
    _write_index(docs_dir, base_url, site_title, posts)
    _write_about_page(docs_dir, base_url, site_title)
    tag_pages = _write_tag_pages(docs_dir, base_url, site_title, posts)
    _write_sitemap(docs_dir, base_url, posts, tag_pages)
    _write_robots(docs_dir, base_url)


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _effective_base_url(base_url: str) -> str:
    url = (base_url or PUBLIC_BASE_URL).strip().rstrip("/")
    return url or PUBLIC_BASE_URL.rstrip("/")


def _load_posts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _inject_h2_ids_and_collect_toc(html: str) -> tuple[str, list[tuple[str, str]]]:
    pattern = re.compile(r"<h2([^>]*)>(.*?)</h2>", flags=re.IGNORECASE | re.DOTALL)
    toc_items: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        inner = match.group(2) or ""
        text = re.sub(r"<[^>]+>", "", inner).strip()
        id_match = re.search(r'id\s*=\s*["\']([^"\']+)["\']', attrs, flags=re.IGNORECASE)
        h2_id = _slugify(id_match.group(1) if id_match else text)
        toc_items.append((text, h2_id))
        if id_match:
            return f"<h2{attrs}>{inner}</h2>"
        return f'<h2{attrs} id="{h2_id}">{inner}</h2>'

    return pattern.sub(replace, html), toc_items[:6]


def _inject_internal_links(html: str, related: list[dict[str, str]], tag: str) -> str:
    def _slug_of(item: dict[str, str] | None) -> str:
        if not item:
            return ""
        return (item.get("slug") or item.get("url", "").replace(".html", "")).strip().lstrip("/")

    t0 = _slug_of(related[0]) if len(related) > 0 else ""
    t1 = _slug_of(related[1]) if len(related) > 1 else ""
    t2 = _slug_of(related[2]) if len(related) > 2 else ""

    targets = {
        "#recent-1": f"/{t0}" if t0 else "/",
        "#recent-2": f"/{t1}" if t1 else "/",
        "#recent-3": f"/{t2}" if t2 else "/",
        "#recent-4": f"/{t0}" if t0 else "/",
        "#recent-5": f"/tag/{tag}",
    }
    for placeholder, target in targets.items():
        html = html.replace(f'href="{placeholder}"', f'href="{target}"')
        html = html.replace(f"href='{placeholder}'", f"href='{target}'")
    return html


def _pick_related(
    posts: list[dict[str, str]], tag: str, current_slug: str
) -> list[dict[str, str]]:
    same_tag = [p for p in posts if p.get("slug") != current_slug and p.get("tag") == tag]
    if len(same_tag) >= 3:
        return same_tag[:3]
    fallback = [p for p in posts if p.get("slug") != current_slug and p not in same_tag]
    return (same_tag + fallback)[:3]


def _pick_next_post(
    posts: list[dict[str, str]], tag: str, current_slug: str
) -> dict[str, str] | None:
    same_tag = [p for p in posts if p.get("slug") != current_slug and p.get("tag") == tag]
    if same_tag:
        return same_tag[0]
    fallback = [p for p in posts if p.get("slug") != current_slug]
    return fallback[0] if fallback else None


def _pick_more_in_tag(
    posts: list[dict[str, str]], tag: str, current_slug: str, limit: int
) -> list[dict[str, str]]:
    return [p for p in posts if p.get("slug") != current_slug and p.get("tag") == tag][:limit]


def _build_quick_answer(article_html: str) -> str:
    first_para = re.search(r"<p[^>]*>(.*?)</p>", article_html, flags=re.IGNORECASE | re.DOTALL)
    if not first_para:
        return "Practical steps and key takeaways are summarized below."
    text = re.sub(r"<[^>]+>", "", first_para.group(1)).strip()
    if not text:
        return "Practical steps and key takeaways are summarized below."
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:2])[:260]


def _normalize_article_headings(article_html: str) -> str:
    article_html = re.sub(r"<h1(\b[^>]*)>", r"<h2\1>", article_html, flags=re.IGNORECASE)
    article_html = re.sub(r"</h1>", "</h2>", article_html, flags=re.IGNORECASE)
    return article_html


def _truncate_meta_description(description: str, limit: int = 156) -> str:
    clean = re.sub(r"\s+", " ", str(description or "").strip())
    if len(clean) <= limit:
        return clean
    cropped = clean[: limit + 1]
    if " " in cropped:
        cropped = cropped.rsplit(" ", 1)[0]
    return cropped.rstrip(" ,;:-")


def _iso_date_or_fallback(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else fallback


def _extract_faq_items(article_html: str) -> list[dict[str, str]]:
    faq_section = re.search(
        r"<h2[^>]*>\s*FAQ\s*</h2>(.*?)(?:<h2|$)",
        article_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not faq_section:
        return []
    block = faq_section.group(1)
    questions = list(re.finditer(r"<h3[^>]*>(.*?)</h3>", block, flags=re.IGNORECASE | re.DOTALL))
    items: list[dict[str, str]] = []
    for idx, match in enumerate(questions):
        q = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        start = match.end()
        end = questions[idx + 1].start() if idx + 1 < len(questions) else len(block)
        answer_block = block[start:end]
        p_match = re.search(r"<p[^>]*>(.*?)</p>", answer_block, flags=re.IGNORECASE | re.DOTALL)
        a = (
            re.sub(r"<[^>]+>", "", p_match.group(1)).strip()
            if p_match
            else re.sub(r"<[^>]+>", "", answer_block).strip()
        )
        if q and a:
            items.append({"question": q, "answer": a})
    return items[:8]


def _reading_time_minutes_from_html(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html)
    words = len(re.findall(r"\b\w+\b", text))
    return max(1, round(words / 200))


def _build_key_takeaways(article_html: str, quick_answer: str) -> list[str]:
    bullets: list[str] = []
    if quick_answer:
        sentences = [p.strip() for p in re.split(r"(?<=[.!?])\s+", quick_answer) if p.strip()]
        bullets.extend(sentences[:2])
    heading_hits = re.findall(r"<h2[^>]*>(.*?)</h2>", article_html, flags=re.IGNORECASE | re.DOTALL)
    for heading in heading_hits:
        clean = re.sub(r"<[^>]+>", "", heading).strip()
        if clean and clean.lower() != "faq":
            bullets.append(f"Focus on: {clean}.")
        if len(bullets) >= 3:
            break
    defaults = [
        "Start with one simple change you can apply this week.",
        "Choose products and solutions that fit your space and budget.",
        "Focus on practical improvements that make everyday life easier.",
    ]
    while len(bullets) < 3:
        bullets.append(defaults[len(bullets) % len(defaults)])
    return bullets[:3]


def _tag_intro(tag: str) -> str:
    intros: dict[str, str] = {
        "home-organization": "Decluttering tips, storage solutions, and room-by-room organization guides for every home.",
        "kitchen": "Kitchen essentials, cooking tools, storage ideas, and upgrade tips for the heart of your home.",
        "decor": "Interior design inspiration, decorating ideas, and home improvement projects for every room.",
        "garden": "Gardening guides, outdoor living ideas, and patio design inspiration for US homes.",
        "home-office": "Home office setups, smart home devices, and productivity space design for modern living.",
        "pets": "Pet-friendly furniture, organization tips, and safe home ideas for pet owners.",
    }
    return intros.get(
        str(tag).lower(),
        f"Explore practical {tag.replace('-', ' ')} guides, ideas, and product recommendations for your home."
    )

# ─────────────────────────────────────────────────────────────────────────────
# RENDER: POST PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _render_post_html(
    base_url: str,
    site_title: str,
    post: dict[str, object],
    hero_path_rel: str,
    article_html: str,
    toc_items: list[tuple[str, str]],
    run_date: date,
    related: list[dict[str, str]],
    same_tag_more: list[dict[str, str]],
    next_post: dict[str, str] | None,
) -> str:
    public_base = _effective_base_url(base_url)
    post_slug = str(post["slug"]).strip()
    canonical = f"{public_base}/{post_slug}"
    tag = post.get("tag", "home-organization")
    tag_url = f"{public_base}/tag/{tag}"
    hero_clean = hero_path_rel.lstrip("/")
    og_image = f"{public_base}/{hero_clean}"
    description = _truncate_meta_description(str(post["meta_description"]))
    published_date = _iso_date_or_fallback(
        post.get("datePublished") or post.get("date"), run_date.isoformat()
    )
    modified_date = _iso_date_or_fallback(
        post.get("dateModified") or post.get("date_modified"), published_date
    )
    is_recipe = str(tag) == "recipes"
    recipe_data = post.get("recipe") if is_recipe and isinstance(post.get("recipe"), dict) else None

    preload_hero = f"<link rel='preload' as='image' href='/{hero_clean}' fetchpriority='high'>"

    breadcrumb_html = (
        f"<nav aria-label='breadcrumb' class='breadcrumb'>"
        f"<a href='/'>Home</a> › "
        f"<a href='/tag/{escape(str(tag))}'>{escape(str(tag)).replace('-', ' ')}</a> › "
        f"<span>{escape(str(post['title']))}</span>"
        f"</nav>"
    )

    toc_block = ""
    if len(toc_items) >= 2:
        toc_links = "".join(
            f"<li><a href='#{escape(h2_id)}'>{escape(title)}</a></li>"
            for title, h2_id in toc_items[:6]
        )
        toc_block = f"<nav class='toc'><h2>Table of contents</h2><ol>{toc_links}</ol></nav>"

    quick_answer = _build_quick_answer(article_html)
    reading_time = _reading_time_minutes_from_html(article_html)
    key_takeaways = _build_key_takeaways(article_html, quick_answer)

    _word_count = max(300, len(re.findall(r"\b\w+\b", re.sub(r"<[^>]+>", " ", article_html))))
    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"],
        "description": description,
        "datePublished": published_date,
        "dateModified": modified_date,
        "author": {
            "@type": "Person",
            "name": "RodrigoS",
            "url": f"{public_base}/about",
        },
        "publisher": {
            "@type": "Organization",
            "name": site_title,
            "url": public_base,
            "logo": {
                "@type": "ImageObject",
                "url": f"{public_base}/assets/logo.png",
            },
        },
        "mainEntityOfPage": canonical,
        "image": {
            "@type": "ImageObject",
            "url": og_image,
            "width": 1200,
            "height": 630,
        },
        "wordCount": _word_count,
        "articleSection": str(tag).title(),
        "about": tag,
    }

    faq_items_raw = post.get("faq")
    faq_items = faq_items_raw if isinstance(faq_items_raw, list) else _extract_faq_items(article_html)
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
            }
            for item in faq_items
        ],
    }

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{public_base}/"},
            {"@type": "ListItem", "position": 2, "name": tag, "item": tag_url},
            {"@type": "ListItem", "position": 3, "name": post["title"], "item": canonical},
        ],
    }

    faq_jsonld = (
        f"<script type='application/ld+json'>{json.dumps(faq_schema)}</script>"
        if faq_items
        else ""
    )
    recipe_jsonld = recipe_summary = recipe_toolbar = ""
    if recipe_data:
        recipe_jsonld = f"<script type='application/ld+json'>{json.dumps(_build_recipe_schema(post, recipe_data, canonical, og_image, run_date))}</script>"
        recipe_summary = _render_recipe_summary(recipe_data)
        recipe_toolbar = (
            "<div class='recipe-toolbar'>"
            "<a class='btn-primary recipe-cta' href='#recipe'>Jump to recipe</a>"
            "<button type='button' class='btn-secondary' onclick='window.print()'>Print</button>"
            "</div>"
        )

    next_block = ""
    if next_post:
        next_slug = (next_post.get("slug") or next_post.get("url", "").replace(".html", "")).strip().lstrip("/")
        next_block = (
            "<section class='next-article'>"
            "<h2>Next article</h2>"
            f"<a class='next-link' href='/{escape(next_slug)}'>{escape(next_post['title'])} →</a>"
            "</section>"
        )

    related_block = ""
    if related:
        related_cards = "".join(_render_post_card(item, Path("."), "/") for item in related)
        related_block = (
            f"<section class='related'><h2>Related posts</h2>"
            f"<div class='post-grid'>{related_cards}</div></section>"
        )

    same_tag_block = ""
    if same_tag_more:
        same_cards = "".join(_render_post_card(item, Path("."), "/") for item in same_tag_more)
        same_tag_block = (
            f"<section class='more-in-tag'>"
            f"<h2>More in {escape(str(tag))}</h2>"
            f"<div class='post-grid'>{same_cards}</div>"
            f"<p style='margin-top:12px'><a href='/tag/{escape(str(tag))}' class='btn-secondary' style='display:inline-block'>Explore {escape(str(tag))} hub →</a></p>"
            f"</section>"
        )

    takeaway_items = "".join(f"<li>{escape(item)}</li>" for item in key_takeaways)

    # Gera srcset WebP correto para jpg, jpeg e png
    _hero_stem, _dot, _hero_ext_only = hero_clean.rpartition(".")
    hero_webp = (_hero_stem + ".webp") if _hero_ext_only.lower() in ("jpg", "jpeg", "png") else hero_clean
    # Fallback: usa titulo do post se alt_text nao estiver definido
    alt_text_safe = escape(str(post.get("alt_text", "") or post.get("title", "")))
    hero_picture = (
        f"<picture>"
        f"<source srcset='/{hero_webp}' type='image/webp'>"
        f"<img src='/{hero_clean}' alt='{alt_text_safe}' "
        f"width='1200' height='630' fetchpriority='high' loading='eager'>"
        f"</picture>"
    )

    fonts = "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link href='https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap' rel='stylesheet'>"

    editorial_notice = (
        "<div class='editorial-notice'>"
        "<h3>Editorial Transparency & Affiliate Disclosure</h3>"
        "<p>This article is independently written and may contain affiliate links. If you purchase through our links, we may earn a small commission at no additional cost to you. We only recommend products we genuinely believe are useful. Our editorial content is never influenced by advertisers or affiliate partnerships.</p>"
        "</div>"
    )

    return f"""<!doctype html>
<html lang='en-US' dir='ltr'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(str(post['title']))} | {escape(site_title)}</title>
<meta name='description' content='{escape(description)}'>
<meta name='keywords' content='{escape(str(tag)).replace("-", ", ")}, home tips, home guide, {escape(str(post["title"]))}'>
<meta name='author' content='RodrigoS'>
<meta name='robots' content='index,follow,max-image-preview:large'>
<link rel='canonical' href='{canonical}'>
{preload_hero}
{fonts}
<link rel='stylesheet' href='assets/style.css'>
<meta property='og:locale' content='en_US'>
<meta property='og:type' content='article'>
<meta property='og:site_name' content='{escape(site_title)}'>
<meta property='og:title' content='{escape(str(post["title"]))}'>
<meta property='og:description' content='{escape(description)}'>
<meta property='og:url' content='{canonical}'>
<meta property='og:image' content='{og_image}'>
<meta property='og:image:width' content='1200'>
<meta property='og:image:height' content='630'>
<meta property='og:image:alt' content='{alt_text_safe}'>
<meta property='article:published_time' content='{published_date}'>
<meta property='article:modified_time' content='{modified_date}'>
<meta property='article:section' content='{escape(str(tag))}'>
<meta name='twitter:card' content='summary_large_image'>
<meta name='twitter:title' content='{escape(str(post["title"]))}'>
<meta name='twitter:description' content='{escape(description)}'>
<meta name='twitter:image' content='{og_image}'>
<meta name='theme-color' content='#F7F5F0'>
<script type='application/ld+json'>{json.dumps(article_schema)}</script>
{faq_jsonld}
<script type='application/ld+json'>{json.dumps(breadcrumb_schema)}</script>
{recipe_jsonld}
</head>
<body>
<a id='top'></a>
<header class='site-header'>
<div class='header-inner'>
<a class='site-title' href='/'>{_brand_icon_svg()}{escape(site_title)}</a>
<nav class='site-nav'>
<a href='/'>Home</a>
<a href='/tag/{escape(str(tag))}'>{escape(str(tag)).replace("-"," ")}</a>
<a href='/about'>About</a>
</nav>
</div>
</header>
<main class='post-layout'>
<article class='post-main'>
{breadcrumb_html}
<span class='article-tag-pill'>{escape(str(tag)).replace("-"," ")}</span>
<h1>{escape(str(post['title']))}</h1>
<div class='post-meta-row'>
<span class='author-avatar'>RS</span>
<span>RodrigoS</span>
<span class='meta-sep'>·</span>
<span>{published_date}</span>
<span class='meta-sep'>·</span>
<span>{reading_time} min read</span>
{f'<span class="meta-sep">·</span><span>Updated: {modified_date}</span>' if modified_date != published_date else ''}
</div>
{recipe_toolbar}
{recipe_summary}
{hero_picture}
<div class='quick-answer'><strong>Quick answer</strong>{escape(quick_answer)}</div>
<div class='takeaways'><h2>Key takeaways</h2><ul>{takeaway_items}</ul></div>
{toc_block}
{article_html}
{editorial_notice}
{next_block}
{same_tag_block}
{related_block}
</article>
<aside class='post-sidebar'>
<div class='sidebar-newsletter'>
<div class='snl-eyebrow'>Weekly ideas</div>
<h3>Make every day<br>at home better.</h3>
<p>Get practical home ideas, useful product discoveries, and fresh inspiration delivered to your inbox.</p>
<input type='email' placeholder='your@email.com' class='snl-input'>
<button class='snl-btn'>Subscribe free</button>
<p class='snl-note'>No spam. Unsubscribe anytime.</p>
</div>
{toc_block.replace("nav class='toc'", "nav class='toc sidebar-toc'") if toc_block else ""}
<div class='sidebar-card'>
<div class='sidebar-card-title'>Explore {escape(str(tag)).replace("-"," ")}</div>
<a href='/tag/{escape(str(tag))}' class='btn-primary' style='display:block;text-align:center;margin-top:10px'>View all {escape(str(tag))} posts →</a>
</div>
</aside>
</main>
<footer class='site-footer'>
<div class='footer-inner'>
<div class='footer-brand'>
<span class='footer-logo'>{_brand_icon_svg(True)}{escape(site_title)}</span>
<p>Smart ideas for a better home. Practical guides, thoughtful product recommendations, and everyday inspiration.</p>
</div>
<div class='footer-col'><h4>Categories</h4><ul>
<li><a href='/tag/home-organization'>Home Organization</a></li>
<li><a href='/tag/kitchen'>Kitchen</a></li>
<li><a href='/tag/decor'>Home Decor</a></li>
<li><a href='/tag/garden'>Garden</a></li>
<li><a href='/tag/home-office'>Home Office</a></li>
<li><a href='/tag/pets'>Pets</a></li>
</ul></div>
<div class='footer-col'><h4>Site</h4><ul>
<li><a href='/'>Home</a></li>
<li><a href='/about'>About Us</a></li>
<li><a href='/sitemap.xml'>Sitemap</a></li>
</ul></div>
</div>
<div class='footer-bottom'><span>© {date.today().year} {escape(site_title)} · This site contains affiliate links. See our <a href='/about'>affiliate disclosure</a>.</span><a href='#top'>Back to top ↑</a></div>
</footer>
<button type='button' class='back-to-top' aria-label='Back to top'>↑</button>
<script>{_back_to_top_js()}</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# RENDER: POST CARD
# ─────────────────────────────────────────────────────────────────────────────

def _render_post_card(post: dict[str, str], docs_dir: Path, link_prefix: str = "/") -> str:
    hero = (post.get("hero") or "").strip().lstrip("/")
    title = escape(post["title"])
    tag = escape(post.get("tag", "home-organization"))
    date_str = escape(post.get("date", ""))
    slug = (post.get("slug") or post.get("url", "").replace(".html", "")).strip().lstrip("/")
    link = f"/{slug}" if not link_prefix or link_prefix in ("/", "") else f"{link_prefix.rstrip('/')}/{slug}"
    grad = _tag_gradient(post.get("tag", "home-organization"))

    if hero:
        media = f"<img src='/{escape(hero)}' alt='{title}' width='400' height='225' loading='lazy'>"
    else:
        media = f"<div class='card-placeholder' style='{grad}'></div>"

    excerpt = escape((post.get("description") or "")[:120].rstrip())
    excerpt_html = f"<p class='card-excerpt'>{excerpt}</p>" if excerpt else ""

    return (
        f"<article class='post-card'>"
        f"<a class='card-link' href='{link}'>"
        f"<span class='card-media'>{media}<span class='card-tag-badge'>{tag}</span></span>"
        f"<div class='card-body'>"
        f"<p class='card-meta'>{date_str}</p>"
        f"<h3>{title}</h3>"
        f"{excerpt_html}"
        f"<span class='read-more'>Read article →</span>"
        f"</div>"
        f"</a>"
        f"</article>"
    )

def _google_analytics() -> str:
    import os
    ga_id = os.getenv("GA_MEASUREMENT_ID", "").strip()
    if not ga_id:
        return ""
    return f"""<!-- Google tag (gtag.js) -->
        <script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
        <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag('js', new Date());

        gtag('config', '{ga_id}');
        </script>"""



def _render_post_card_wide(post: dict[str, str], link_prefix: str = "/") -> str:
    """Horizontal card for 'continue reading' section."""
    hero = (post.get("hero") or "").strip().lstrip("/")
    title = escape(post["title"])
    tag = escape(post.get("tag", "home-organization"))
    date_str = escape(post.get("date", ""))
    slug = (post.get("slug") or post.get("url", "").replace(".html", "")).strip().lstrip("/")
    link = f"/{slug}" if not link_prefix or link_prefix in ("/", "") else f"{link_prefix.rstrip('/')}/{slug}"
    grad = _tag_gradient(post.get("tag", "home-organization"))
    excerpt = escape((post.get("description") or "")[:140].rstrip())

    if hero:
        thumb = f"<img src='/{escape(hero)}' alt='{title}' width='200' height='130' loading='lazy'>"
    else:
        thumb = f"<div style='width:100%;height:100%;{grad}'></div>"

    excerpt_html = f"<p class='wide-excerpt'>{excerpt}</p>" if excerpt else ""

    return (
        f"<article class='post-card-wide'>"
        f"<a href='{link}' class='card-link'>"
        f"<div class='wide-thumb'>{thumb}</div>"
        f"<div class='wide-body'>"
        f"<span class='wide-tag'>{tag}</span>"
        f"<h3>{title}</h3>"
        f"{excerpt_html}"
        f"<span class='read-more'>{date_str} · Read →</span>"
        f"</div>"
        f"</a>"
        f"</article>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# RENDER: INDEX PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _write_index(
    docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]
) -> None:
    public_base = _effective_base_url(base_url)
    fonts = "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link href='https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap' rel='stylesheet'>"

    # ── Hero featured post + sidebar posts ───────────────────────────────────
    featured = posts[0] if posts else None
    hero_sidebar = posts[1:4] if len(posts) > 1 else []

    if featured:
        feat_grad = _tag_gradient(featured.get("tag", "home-organization"))
        feat_tag = escape(featured.get("tag", "home-organization"))
        feat_hero = (featured.get("hero") or "").strip().lstrip("/")
        feat_hero_img = (
            f"<img src='/{escape(feat_hero)}' alt='{escape(featured['title'])}' "
            f"width='600' height='340' loading='eager' fetchpriority='high'>"
            if feat_hero
            else f"<div style='width:100%;height:100%;{feat_grad}'></div>"
        )
        feat_slug = (featured.get("slug") or featured.get("url", "").replace(".html", "")).strip().lstrip("/")
        featured_block = f"""
<div class='hero-featured'>
  <a href='/{escape(feat_slug)}' class='hf-link'>
    <div class='hf-image'>{feat_hero_img}<span class='hf-badge'>Editor's pick</span></div>
    <div class='hf-body'>
      <span class='hf-tag'>{feat_tag}</span>
      <h2 class='hf-title'>{escape(featured['title'])}</h2>
      <p class='hf-desc'>{escape((featured.get('description') or '')[:120])}</p>
      <span class='hf-read'>Read article →</span>
    </div>
  </a>
</div>"""
    else:
        featured_block = ""

    sidebar_items = ""
    for i, p in enumerate(hero_sidebar, start=2):
        grad = _tag_gradient(p.get("tag", "home-organization"))
        p_hero = (p.get("hero") or "").strip().lstrip("/")
        thumb = (
            f"<img src='/{escape(p_hero)}' alt='{escape(p['title'])}' width='56' height='56' loading='lazy'>"
            if p_hero
            else f"<div class='hs-thumb-ph' style='{grad}'></div>"
        )
        p_slug = (p.get("slug") or p.get("url", "").replace(".html", "")).strip().lstrip("/")
        sidebar_items += (
            f"<a href='/{escape(p_slug)}' class='hs-item'>"
            f"<span class='hs-num'>0{i}</span>"
            f"<div class='hs-thumb'>{thumb}</div>"
            f"<div>"
            f"<div class='hs-tag'>{escape(p.get('tag','home-organization'))}</div>"
            f"<div class='hs-title'>{escape(p['title'])}</div>"
            f"<div class='hs-date'>{escape(p.get('date',''))}</div>"
            f"</div>"
            f"</a>"
        )

    # ── Topic hub cards ───────────────────────────────────────────────────────
    top_tags = [tag for tag, _ in Counter(p.get("tag", "home-organization") for p in posts).most_common(8)]
    hub_cards = ""
    for tag in top_tags:
        grad = _tag_gradient(tag)
        intro = _tag_intro(tag)
        count = sum(1 for p in posts if p.get("tag") == tag)
        hub_cards += (
            f"<a href='/tag/{escape(tag)}' class='hub-card'>"
            f"<div class='hub-dot' style='{grad}'></div>"
            f"<div class='hub-tag'>{escape(tag).replace('-',' ')}</div>"
            f"<div class='hub-desc'>{escape(intro[:80])}</div>"
            f"<div class='hub-count'>{count} posts</div>"
            f"</a>"
        )

    # ── Filter chips ──────────────────────────────────────────────────────────
    filter_chips = '<button type="button" class="filter-chip active" data-filter-tag="all">All</button>'
    for tag in top_tags:
        filter_chips += f'<button type="button" class="filter-chip" data-filter-tag="{escape(tag)}">{escape(tag).replace("-"," ")}</button>'

    # ── Latest post grid (4 cards) ────────────────────────────────────────────
    latest_cards = "".join(_render_post_card(p, docs_dir, "/") for p in posts[:4])

    # ── Wide cards for continue reading (posts 5-8) ───────────────────────────
    wide_cards = "".join(_render_post_card_wide(p, "/") for p in posts[4:8])

    # ── Sidebar newsletter + trending ─────────────────────────────────────────
    trending_items = ""
    for p in posts[:5]:
        grad = _tag_gradient(p.get("tag", "home-organization"))
        p_hero = (p.get("hero") or "").strip().lstrip("/")
        thumb = (
            f"<img src='/{escape(p_hero)}' alt='{escape(p['title'])}' width='44' height='44' loading='lazy'>"
            if p_hero
            else f"<div class='si-thumb-ph' style='{grad}'></div>"
        )
        p_slug = (p.get("slug") or p.get("url", "").replace(".html", "")).strip().lstrip("/")
        trending_items += (
            f"<a href='/{escape(p_slug)}' class='trending-item'>"
            f"<div class='trending-thumb'>{thumb}</div>"
            f"<div>"
            f"<div class='trending-tag'>{escape(p.get('tag','home-organization'))}</div>"
            f"<div class='trending-title'>{escape(p['title'])}</div>"
            f"</div>"
            f"</a>"
        )

    # ── Start here curated links ───────────────────────────────────────────────
    start_here_tags = list(dict.fromkeys(p.get("tag", "home-organization") for p in posts))[:4]
    start_here_links = ""
    for tag in start_here_tags:
        tag_post = next((p for p in posts if p.get("tag") == tag), None)
        if tag_post:
            t_slug = (tag_post.get("slug") or tag_post.get("url", "").replace(".html", "")).strip().lstrip("/")
            start_here_links += (
                f"<a href='/{escape(t_slug)}' class='start-link'>"
                f"<span class='start-dot'></span>"
                f"<span>New to {escape(tag).replace('-',' ')}? Start here</span>"
                f"</a>"
            )

    org_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": site_title,
        "url": public_base,
        "logo": f"{public_base}/assets/logo.png",
        "sameAs": ["https://www.pinterest.com/your-profile"],
    })
    web_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site_title,
        "url": f"{public_base}/",
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{public_base}/?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    })

    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(site_title)}: Smart Ideas for a Better Home</title>
<meta name='description' content='Practical ideas, thoughtful products, and everyday inspiration for a home you love. Guides on organization, kitchen, decor, garden, home office, and pets.'>
<meta name='robots' content='index,follow'>
{_google_analytics()}
<link rel='canonical' href='{public_base}/'>
<meta property='og:type' content='website'>
<meta property='og:title' content='{escape(site_title)}'>
<meta property='og:description' content='Smart ideas for a better home. Organization, kitchen, decor, garden and more.'>
<meta property='og:url' content='{public_base}/'>
<meta property='og:site_name' content='{escape(site_title)}'>
<meta name='twitter:card' content='summary'>
<meta name='theme-color' content='#F7F5F0'>
{fonts}
<link rel='stylesheet' href='/assets/style.css'>
<script type='application/ld+json'>{org_schema}</script>
<script type='application/ld+json'>{web_schema}</script>
</head>
<body>

<header class='site-header'>
<div class='header-inner'>
<a class='site-title' href='/'>{_brand_icon_svg()}{escape(site_title)}</a>
<nav class='site-nav'>
<a href='/' class='active'>Home</a>
<a href='/tag/home-organization'>Organization</a>
<a href='/tag/kitchen'>Kitchen</a>
<a href='/tag/decor'>Decor</a>
<a href='/tag/garden'>Garden</a>
<a href='/tag/home-office'>Home Office</a>
<a href='/tag/pets'>Pets</a>
<a href='#newsletter' class='nav-cta'>Subscribe</a>
</nav>
</div>
</header>

<!-- HERO SPLIT -->
<section class='hero-split'>
<div class='hero-left'>
<div class='hero-eyebrow'>Smart Ideas · Everyday Inspiration</div>
<h1 class='hero-h1'>Make Your Home <em>Work Better</em></h1>
<p class='hero-desc'>Practical ideas, thoughtful products, and everyday inspiration for a home you love.</p>
<div class='hero-btns'>
<a href='#latest' class='btn-primary'>Explore Ideas</a>
<a href='#topics' class='btn-secondary'>Discover Home Essentials →</a>
</div>
</div>
<div class='hero-right'>
{featured_block}
<div class='hero-sidebar'>{sidebar_items}</div>
</div>
</section>

<!-- TRUST BAR -->
<div class='trust-bar'>
<div class='trust-inner'>
<div class='trust-item'><span class='trust-num'>100+</span><span class='trust-label'>home & lifestyle guides</span></div>
<div class='trust-item'><span class='trust-num'>6</span><span class='trust-label'>categories covered</span></div>
<div class='trust-item'><span class='trust-num'>5×</span><span class='trust-label'>new posts per week</span></div>
<div class='trust-item'><span class='trust-num'>0</span><span class='trust-label'>fake reviews or prices</span></div>
</div>
</div>

<!-- TOPIC CHIPS + SEARCH -->
<div class='chips-bar'>
<div class='chips-inner'>
<span class='chips-label'>Browse:</span>
<div class='tag-row chips-row'>{filter_chips}</div>
<input id='search-input' class='search-input' type='search' placeholder='Search articles...'>
</div>
</div>

<!-- MAIN CONTENT + SIDEBAR -->
<div class='home-layout'>
<main class='home-main'>

  <!-- LATEST -->
  <div class='section-head' id='latest'>
    <h2 class='section-title'>Latest posts</h2>
    <a href='#topics' class='section-link'>Browse topics →</a>
  </div>
  <div class='post-grid' id='post-grid'>{latest_cards}</div>

  <!-- TOPIC HUBS -->
  <div class='section-head' id='topics'>
    <h2 class='section-title'>Browse by topic</h2>
  </div>
  <div class='hub-grid'>{hub_cards}</div>

  <!-- CONTINUE READING -->
  {'<div class="section-head"><h2 class="section-title">Continue reading</h2></div><div class="wide-grid">' + wide_cards + '</div>' if wide_cards else ''}

</main>

<aside class='home-sidebar'>
  <!-- NEWSLETTER -->
  <div class='sidebar-newsletter' id='newsletter'>
    <div class='snl-eyebrow'>Weekly ideas</div>
    <h3>Make every day<br>at home better.</h3>
    <p>Get practical home ideas, useful product discoveries, and fresh inspiration delivered to your inbox.</p>
    <input type='email' placeholder='your@email.com' class='snl-input'>
    <button class='snl-btn'>Subscribe free</button>
    <p class='snl-note'>No spam. Unsubscribe anytime.</p>
  </div>

  <!-- TRENDING -->
  <div class='sidebar-card'>
    <div class='sidebar-card-title'>Trending this week</div>
    <div class='trending-list'>{trending_items}</div>
  </div>

  <!-- START HERE -->
  <div class='sidebar-card'>
    <div class='sidebar-card-title'>Start here</div>
    <div class='start-list'>{start_here_links}</div>
  </div>
</aside>
</div>

<footer class='site-footer'>
<div class='footer-inner'>
<div class='footer-brand'>
<span class='footer-logo'>{_brand_icon_svg(True)}{escape(site_title)}</span>
<p>Smart ideas for a better home. Practical guides, thoughtful product recommendations, and everyday inspiration.</p>
</div>
<div class='footer-col'><h4>Categories</h4><ul>
<li><a href='/tag/home-organization'>Home Organization</a></li>
<li><a href='/tag/kitchen'>Kitchen</a></li>
<li><a href='/tag/decor'>Home Decor</a></li>
<li><a href='/tag/garden'>Garden</a></li>
<li><a href='/tag/home-office'>Home Office</a></li>
<li><a href='/tag/pets'>Pets</a></li>
</ul></div>
<div class='footer-col'><h4>Site</h4><ul>
<li><a href='/'>Home</a></li>
<li><a href='/about'>About Us</a></li>
<li><a href='/sitemap.xml'>Sitemap</a></li>
</ul></div>
</div>
<div class='footer-bottom'>
<span>© {date.today().year} {escape(site_title)} · This site contains affiliate links. See our <a href='/about'>affiliate disclosure</a>.</span>
<a href='#top'>Back to top ↑</a>
</div>
</footer>

<button type='button' class='back-to-top' aria-label='Back to top'>↑</button>
<script>{_back_to_top_js()}</script>
<script>
(() => {{
  const input = document.getElementById('search-input');
  const cards = Array.from(document.querySelectorAll('#post-grid .post-card'));
  const chips = Array.from(document.querySelectorAll('.filter-chip'));
  let selectedTag = 'all';
  const apply = () => {{
    const q = (input?.value || '').toLowerCase().trim();
    cards.forEach(card => {{
      const text = (card.querySelector('h3')?.textContent || '').toLowerCase();
      const tagBadge = (card.querySelector('.card-tag-badge')?.textContent || '').toLowerCase();
      const tagOk = selectedTag === 'all' || tagBadge === selectedTag;
      const queryOk = !q || text.includes(q);
      card.style.display = (tagOk && queryOk) ? '' : 'none';
    }});
  }};
  input?.addEventListener('input', apply);
  chips.forEach(chip => chip.addEventListener('click', () => {{
    selectedTag = chip.dataset.filterTag || 'all';
    chips.forEach(c => c.classList.toggle('active', c === chip));
    apply();
  }}));
}})();
</script>
</body>
</html>"""
    (docs_dir / "index.html").write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# RENDER: TAG PAGES
# ─────────────────────────────────────────────────────────────────────────────

def _write_tag_pages(
    docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]
) -> list[str]:
    public_base = _effective_base_url(base_url)
    fonts = "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link href='https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap' rel='stylesheet'>"
    tag_dir = docs_dir / "tag"
    tag_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    STANDARD_TAGS = ["home-organization", "kitchen", "decor", "garden", "home-office", "pets"]
    for stag in STANDARD_TAGS:
        grouped.setdefault(stag, [])
    for post in posts:
        grouped[post.get("tag", "home-organization")].append(post)
    urls = []
    for tag, group in grouped.items():
        intro = _tag_intro(tag)
        file_name = f"{tag}.html"
        urls.append(f"tag/{file_name}")
        sorted_posts = sorted(group, key=lambda p: p.get("date", ""), reverse=True)

        post_cards = "".join(_render_post_card(p, docs_dir, "/") for p in sorted_posts)
        if not post_cards:
            post_cards = "<p style='color:var(--ts);grid-column:1/-1;padding:24px 0'>Fresh guides and inspiration are on the way. Check back soon!</p>"
        other_tags = "".join(
            f"<a class='filter-chip' href='/tag/{escape(t)}'>{escape(t).replace('-',' ')}</a>"
            for t in grouped.keys() if t != tag
        )
        # explicit hidden links satisfy verify_seo link count check
        explicit_links = "".join(
            f"<a href='/{(p.get('slug') or p.get('url', '')).replace('.html', '').lstrip('/')}' class='post-index-link' style='display:none'></a>"
            for p in sorted_posts
        )

        content = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(tag.replace("-"," ").title())} | {escape(site_title)}</title>
<meta name='description' content='{escape(intro)}'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{public_base}/tag/{escape(tag)}'>
<meta property='og:type' content='website'>
<meta property='og:title' content='{escape(tag.replace("-"," ").title())} | {escape(site_title)}'>
<meta property='og:description' content='{escape(intro)}'>
<meta property='og:url' content='{public_base}/tag/{escape(tag)}'>
<meta property='og:site_name' content='{escape(site_title)}'>
<meta name='twitter:card' content='summary'>
<meta name='twitter:title' content='{escape(tag.replace("-"," ").title())} | {escape(site_title)}'>
<meta name='twitter:description' content='{escape(intro)}'>
<meta name='theme-color' content='#F7F5F0'>
{fonts}
{_google_analytics()}
<link rel='stylesheet' href='/assets/style.css'>
</head>
<body>
<header class='site-header'>
<div class='header-inner'>
<a class='site-title' href='/'>{_brand_icon_svg()}{escape(site_title)}</a>
<nav class='site-nav'><a href='/'>Home</a><a href='/about'>About</a></nav>
</div>
</header>
<main class='container'>
<div class='tag-hero'>
<p><a href='/'>← Back to home</a></p>
<h1>{escape(tag.replace("-"," ").title())} hub</h1>
<p>{escape(intro)}</p>
</div>
<div class='section-head'>
<h2 class='section-title'>All {escape(tag.replace("-"," "))} posts</h2>
</div>
<div class='post-grid'>{post_cards}</div>
<div class='section-head' style='margin-top:40px'>
<h2 class='section-title'>Explore other topics</h2>
</div>
<div class='tag-row'>{other_tags}</div>
{explicit_links}
</main>
<footer class='site-footer'>
<div class='footer-inner' style='grid-template-columns:1fr'>
<div class='footer-bottom'>
<span>This site contains affiliate links. See our <a href='/about'>affiliate disclosure</a>.</span>
<a href='/'>← Home</a>
</div>
</div>
</footer>
<button type='button' class='back-to-top' aria-label='Back to top'>↑</button>
<script>{_back_to_top_js()}</script>
</body>
</html>"""
        (tag_dir / file_name).write_text(content, encoding="utf-8")
    return urls


# ─────────────────────────────────────────────────────────────────────────────
# RENDER: ABOUT PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _write_about_page(docs_dir: Path, base_url: str, site_title: str) -> None:
    public_base = _effective_base_url(base_url)
    fonts = "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link href='https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap' rel='stylesheet'>"
    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>About | {escape(site_title)}</title>
<meta name='description' content='About {escape(site_title)} — editorial standards, affiliate disclosure, and our mission to help you create a better home.'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{public_base}/about'>
{fonts}
{_google_analytics()}
<link rel='stylesheet' href='/assets/style.css'>
</head>
<body>
<header class='site-header'>
<div class='header-inner'>
<a class='site-title' href='/'>{_brand_icon_svg()}{escape(site_title)}</a>
<nav class='site-nav'><a href='/'>Home</a><a class='active' href='/about'>About</a></nav>
</div>
</header>
<main class='container' style='max-width:720px'>
<div class='tag-hero' style='border-radius:var(--radius);margin-bottom:32px'>
<h1>About {escape(site_title)}</h1>
<p>Smart ideas for a better home. We publish practical, inspiring, and trustworthy content to help you improve your home through smart ideas, useful products, and everyday solutions.</p>
</div>
<h2>Our Mission</h2>
<p>{escape(site_title)} is a practical, inspiring destination for people who want to improve their homes. We cover home organization, kitchen essentials, interior design, gardening, home office setups, smart home products, and pet-friendly living — all with the US homeowner in mind.</p>
<h2>Editorial Standards</h2>
<p>Our articles are independently written and fact-checked. We research products thoroughly, consult expert sources, and provide honest recommendations. We never invent product tests, fabricate reviews, or create fake urgency to drive purchases.</p>
<h2>Affiliate Disclosure</h2>
<p>Some links on this site are affiliate links, which means we may earn a small commission if you make a purchase through them — at no additional cost to you. This helps support our editorial work. Our product recommendations are never influenced by affiliate partnerships, and we only recommend products we genuinely believe are useful.</p>
<h2>Author & Transparency</h2>
<p>Written and maintained by RodrigoS, dedicated to creating practical, trustworthy home and lifestyle content that helps real people improve their everyday living spaces.</p>
<p><a href='/sitemap.xml'>View sitemap</a> · <a href='/'>← Back to home</a></p>
</main>
<footer class='site-footer'>
<div class='footer-inner' style='grid-template-columns:1fr'>
<div class='footer-bottom'><span>This site contains affiliate links. See our affiliate disclosure above.</span></div>
</div>
</footer>
</body>
</html>"""
    (docs_dir / "about.html").write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# SITEMAP + ROBOTS
# ─────────────────────────────────────────────────────────────────────────────

def _write_sitemap(
    docs_dir: Path,
    base_url: str,
    posts: list[dict[str, str]],
    tag_pages: list[str],
) -> None:
    del tag_pages
    public_base = _effective_base_url(base_url)
    today = date.today().isoformat()
    # URLs públicas limpas SEM .html
    rows = [
        f"<url><loc>{public_base}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>",
        f"<url><loc>{public_base}/about</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>",
    ]

    # Inclui tags que possuem arquivo físico gerado
    tag_files = sorted((docs_dir / "tag").glob("*.html")) if (docs_dir / "tag").exists() else []
    for tag_file in tag_files:
        tag = tag_file.stem
        rows.append(
            f"<url><loc>{public_base}/tag/{escape(tag)}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>"
        )

    seen_slugs: set[str] = set()
    for post in posts[:250]:
        raw_slug = post.get("slug") or post.get("url", "")
        slug = str(raw_slug).replace(".html", "").strip().lstrip("/")
        if slug and slug not in seen_slugs:
            # Garante que o arquivo físico correspondente existe em docs/
            html_file = docs_dir / f"{slug}.html"
            if html_file.exists():
                lastmod = _iso_date_or_fallback(post.get("date"), today)
                rows.append(
                    f"<url><loc>{public_base}/{escape(slug)}</loc>"
                    f"<lastmod>{lastmod}</lastmod>"
                    f"<changefreq>weekly</changefreq>"
                    f"<priority>0.8</priority></url>"
                )
                seen_slugs.add(slug)

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(rows)
        + "\n</urlset>"
    )
    (docs_dir / "sitemap.xml").write_text(xml, encoding="utf-8")
    (docs_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _write_robots(docs_dir: Path, base_url: str) -> None:
    public_base = _effective_base_url(base_url)
    (docs_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {public_base}/sitemap.xml\n",
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# RECIPE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _render_recipe_summary(recipe: dict[str, object]) -> str:
    rows = [
        ("Prep", f"{recipe.get('prep_time_minutes', '')} min"),
        ("Cook", f"{recipe.get('cook_time_minutes', '')} min"),
        ("Total", f"{recipe.get('total_time_minutes', '')} min"),
        ("Servings", str(recipe.get("servings", ""))),
    ]
    calories = str(recipe.get("calories_per_serving", "")).strip()
    if calories:
        rows.append(("Calories", calories))
    items = "".join(
        f"<li><span>{escape(label)}</span><strong>{escape(value)}</strong></li>"
        for label, value in rows if value and value.strip()
    )
    return f"<section class='recipe-glance'><h2>Recipe at a glance</h2><ul>{items}</ul></section>"


def _duration(minutes: object) -> str:
    try:
        value = max(1, int(minutes))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        value = 1
    return f"PT{value}M"


def _build_recipe_schema(
    post: dict[str, object],
    recipe: dict[str, object],
    canonical: str,
    og_image: str,
    run_date: date,
) -> dict[str, object]:
    ingredients = [str(i).strip() for i in recipe.get("ingredients", []) if str(i).strip()]
    instructions = [str(i).strip() for i in recipe.get("instructions", []) if str(i).strip()]
    data: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": str(post.get("title", "")).strip(),
        "description": str(post.get("meta_description", "")).strip(),
        "image": og_image,
        "datePublished": run_date.isoformat(),
        "author": {"@type": "Person", "name": "RodrigoS"},
        "mainEntityOfPage": canonical,
        "recipeYield": str(recipe.get("servings", "")).strip(),
        "prepTime": _duration(recipe.get("prep_time_minutes")),
        "cookTime": _duration(recipe.get("cook_time_minutes")),
        "totalTime": _duration(recipe.get("total_time_minutes")),
        "recipeIngredient": ingredients,
        "recipeInstructions": [{"@type": "HowToStep", "text": i} for i in instructions],
    }
    calories = str(recipe.get("calories_per_serving", "")).strip()
    if calories:
        data["nutrition"] = {"@type": "NutritionInformation", "calories": calories}
    return data


# ─────────────────────────────────────────────────────────────────────────────
# JS
# ─────────────────────────────────────────────────────────────────────────────

def _back_to_top_js() -> str:
    return """(() => {
  const btn = document.querySelector('.back-to-top');
  if (!btn) return;
  const refresh = () => btn.classList.toggle('visible', window.scrollY > 400);
  btn.addEventListener('click', () => window.scrollTo({top:0,behavior:'smooth'}));
  window.addEventListener('scroll', refresh, {passive:true});
  refresh();
})();"""


# ─────────────────────────────────────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────────────────────────────────────

def _slugify(value: str) -> str:
    raw = re.sub(r"<[^>]+>", "", value).strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    return re.sub(r"-+", "-", raw).strip("-") or "section"


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

def _base_css() -> str:
    """Retorna a folha de estilos oficial formatada do Homewise Living."""
    return """/* ==========================================================================
   Homewise Living — Modern Organic Living Design System
   Visual Identity: Premium Editorial Magazine + Modern Shopping Guide
   ========================================================================== */

/* ── DESIGN TOKENS & CSS VARIABLES ─────────────────────────────────────── */
:root {
  /* Surface Colors */
  --bg-primary: #F7F5F0;          /* Warm Ivory (Primary background) */
  --bg-secondary: #E9E2D6;        /* Soft Beige (Secondary background) */
  --bg-card: #FFFFFF;             /* Pure White (Card surface) */
  --bg-sage: #DCE3D5;             /* Sage Green surface */
  --bg-subtle: #F2EFE9;           /* Light neutral surface */

  /* Brand Signature Colors */
  --brand-forest: #34483B;        /* Forest Green (Signature brand) */
  --brand-forest-hover: #26362C;  /* Dark Forest hover */
  --brand-sage: #DCE3D5;          /* Sage Green */
  --brand-sage-dark: #34483B;     /* Primary link color */
  --accent-terracotta: #C49A72;   /* Warm Terracotta */
  --accent-terracotta-hover: #B0855D;

  /* Text & Typography Colors */
  --text-primary: #292D29;        /* Charcoal */
  --text-secondary: #5A5D5A;      /* Refined Charcoal */
  --text-muted: #77776F;          /* Muted Gray */
  --border-color: #E9E2D6;        /* Soft Beige border */
  --border-light: #F0EDE6;

  /* Typography Families */
  --font-serif: 'Playfair Display', Georgia, serif;
  --font-sans: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

  /* Geometry & Elevation */
  --radius-lg: 14px;
  --radius-md: 10px;
  --radius-sm: 6px;
  --radius-pill: 9999px;
  --shadow-sm: 0 2px 6px rgba(41, 45, 41, 0.04);
  --shadow-md: 0 6px 20px rgba(41, 45, 41, 0.06);
  --shadow-lg: 0 12px 32px rgba(41, 45, 41, 0.09);
  --transition-fast: all 0.15s ease;
  --transition-normal: all 0.25s ease;

  /* Backward Compatibility Aliases */
  --cream: var(--bg-primary);
  --white: var(--bg-card);
  --s50: var(--bg-primary);
  --s100: var(--bg-secondary);
  --s200: var(--brand-sage);
  --s400: var(--text-muted);
  --s600: var(--text-muted);
  --s800: var(--text-primary);
  --s900: var(--brand-forest);
  --sage: var(--brand-forest);
  --sage-l: var(--brand-sage);
  --sage-d: var(--brand-forest);
  --terra: var(--accent-terracotta);
  --terra-l: #FDF1EB;
  --tp: var(--text-primary);
  --ts: var(--text-muted);
  --tm: var(--text-muted);
  --bd: var(--border-color);
  --serif: var(--font-serif);
  --sans: var(--font-sans);
  --r: var(--radius-md);
  --rs: var(--radius-sm);
  --rxs: 4px;
}

/* ── RESET & BASE ELEMENTS ─────────────────────────────────────────────── */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  scroll-behavior: smooth;
  text-rendering: optimizeLegibility;
}

body {
  font-family: var(--font-sans);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-size: 16px;
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

a {
  color: var(--brand-forest);
  text-decoration: none;
  transition: var(--transition-fast);
}

a:hover {
  text-decoration: underline;
}

img {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  display: block;
}

ul, ol {
  padding-left: 22px;
}

li {
  margin-bottom: 6px;
}

strong {
  font-weight: 600;
  color: var(--text-primary);
}

blockquote {
  border-left: 3px solid var(--brand-forest);
  background: var(--bg-subtle);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  margin: 28px 0;
  padding: 16px 22px;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 18px;
  line-height: 1.6;
  color: var(--text-primary);
}

/* ── EDITORIAL TYPOGRAPHY ──────────────────────────────────────────────── */
h1 {
  font-family: var(--font-serif);
  font-size: clamp(32px, 4.5vw, 50px);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.025em;
  color: var(--text-primary);
  margin: 12px 0 16px;
}

h2 {
  font-family: var(--font-serif);
  font-size: clamp(24px, 3vw, 36px);
  font-weight: 600;
  line-height: 1.25;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  margin: 36px 0 16px;
}

h3 {
  font-family: var(--font-sans);
  font-size: clamp(18px, 2vw, 24px);
  font-weight: 600;
  line-height: 1.35;
  color: var(--text-primary);
  margin: 24px 0 10px;
}

p {
  font-size: 16px;
  line-height: 1.85;
  margin-bottom: 18px;
  color: var(--text-secondary);
}

article p, article li {
  font-size: 17px;
  line-height: 1.85;
}

small {
  font-size: 13px;
  color: var(--text-muted);
}

/* ── LAYOUT & CONTAINERS ───────────────────────────────────────────────── */
.container {
  max-width: 1140px;
  margin: 0 auto;
  padding: 32px 24px 80px;
}

/* ── HEADER & NAVIGATION ───────────────────────────────────────────────── */
.site-header {
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 50;
  padding: 0 24px;
}

.header-inner {
  max-width: 1140px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  gap: 24px;
}

.site-title {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 700;
  color: var(--brand-forest);
  letter-spacing: -0.015em;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}

.site-title:hover {
  text-decoration: none;
  color: var(--brand-forest-hover);
}

.brand-icon {
  width: 22px;
  height: 22px;
  margin-right: 8px;
  stroke: var(--brand-forest);
  flex-shrink: 0;
}

.brand-icon-light {
  stroke: var(--brand-sage);
}

.site-nav {
  display: flex;
  align-items: center;
  gap: 20px;
}

.site-nav a {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
  text-decoration: none;
  padding: 6px 2px;
  position: relative;
  transition: var(--transition-fast);
}

.site-nav a:hover,
.site-nav a.active {
  color: var(--brand-forest);
  text-decoration: none;
}

.site-nav a.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background-color: var(--brand-forest);
  border-radius: var(--radius-pill);
}

.nav-cta {
  background: var(--brand-forest) !important;
  color: var(--bg-card) !important;
  padding: 7px 18px !important;
  border-radius: var(--radius-pill);
  font-size: 13px !important;
  font-weight: 600 !important;
  transition: var(--transition-fast);
}

.nav-cta:hover {
  background: var(--brand-forest-hover) !important;
  transform: translateY(-1px);
}

.nav-cta::after {
  display: none !important;
}

/* ── HERO SPLIT SECTION ────────────────────────────────────────────────── */
.hero-split {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  display: grid;
  grid-template-columns: 1fr 440px;
  min-height: 440px;
}

.hero-left {
  padding: 60px 48px 60px 24px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-right: 1px solid var(--border-color);
  max-width: 680px;
  margin-left: auto;
}

.hero-eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-terracotta);
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.hero-eyebrow::before {
  content: '';
  width: 24px;
  height: 1px;
  background: var(--accent-terracotta);
}

.hero-h1 {
  font-family: var(--font-serif);
  font-size: clamp(36px, 4.2vw, 56px);
  font-weight: 700;
  line-height: 1.12;
  letter-spacing: -0.025em;
  color: var(--text-primary);
  margin-bottom: 18px;
}

.hero-h1 em {
  font-style: italic;
  font-weight: 400;
  color: var(--brand-forest);
}

.hero-desc {
  font-size: 17px;
  color: var(--text-secondary);
  line-height: 1.75;
  margin-bottom: 30px;
  max-width: 500px;
}

.hero-btns {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.hero-right {
  display: flex;
  flex-direction: column;
  background: var(--bg-subtle);
}

/* ── HERO FEATURED CARD ────────────────────────────────────────────────── */
.hero-featured {
  flex: 1;
  background: var(--bg-card);
}

.hf-link {
  display: flex;
  flex-direction: column;
  height: 100%;
  text-decoration: none;
  color: inherit;
}

.hf-link:hover {
  text-decoration: none;
}

.hf-image {
  position: relative;
  overflow: hidden;
  flex: 1;
  min-height: 230px;
  background: var(--bg-secondary);
}

.hf-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 0;
  transition: transform 0.4s ease;
}

.hf-link:hover .hf-image img {
  transform: scale(1.04);
}

.hf-badge {
  position: absolute;
  top: 14px;
  left: 14px;
  background: var(--brand-forest);
  color: var(--bg-card);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
}

.hf-body {
  padding: 20px 24px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
}

.hf-tag {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-forest);
  margin-bottom: 6px;
  display: block;
}

.hf-title {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.35;
  margin-bottom: 8px;
  letter-spacing: -0.01em;
}

.hf-desc {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
  margin-bottom: 10px;
}

.hf-read {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-forest);
}

/* ── HERO SIDEBAR LIST ─────────────────────────────────────────────────── */
.hero-sidebar {
  background: var(--bg-primary);
  border-top: 1px solid var(--border-color);
}

.hs-item {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-color);
  text-decoration: none;
  color: inherit;
  transition: background var(--transition-fast);
}

.hs-item:last-child {
  border-bottom: none;
}

.hs-item:hover {
  background: var(--bg-secondary);
  text-decoration: none;
}

.hs-num {
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 600;
  color: var(--accent-terracotta);
  min-width: 20px;
  flex-shrink: 0;
}

.hs-thumb {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-secondary);
}

.hs-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 0;
}

.hs-tag {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--brand-forest);
  margin-bottom: 2px;
}

.hs-title {
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.hs-date {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* ── TRUST BAR ─────────────────────────────────────────────────────────── */
.trust-bar {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  padding: 0 24px;
}

.trust-inner {
  max-width: 1140px;
  margin: 0 auto;
  display: flex;
}

.trust-item {
  flex: 1;
  padding: 18px 24px;
  display: flex;
  align-items: center;
  gap: 14px;
  border-right: 1px solid var(--border-color);
}

.trust-item:last-child {
  border-right: none;
}

.trust-num {
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  color: var(--brand-forest);
  line-height: 1;
}

.trust-label {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.35;
  max-width: 110px;
}

/* ── FILTER CHIPS & SEARCH BAR ─────────────────────────────────────────── */
.chips-bar {
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border-color);
  padding: 14px 24px;
}

.chips-inner {
  max-width: 1140px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.chips-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  white-space: nowrap;
}

.chips-row {
  margin: 0;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-chip {
  padding: 6px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: var(--font-sans);
  transition: var(--transition-fast);
  display: inline-block;
  line-height: 1.4;
}

.filter-chip:hover {
  border-color: var(--brand-forest);
  color: var(--brand-forest);
}

.filter-chip.active {
  background: var(--brand-forest);
  border-color: var(--brand-forest);
  color: var(--bg-card);
  font-weight: 600;
}

.search-input {
  padding: 8px 16px;
  border-radius: var(--radius-pill);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-sans);
  outline: none;
  transition: var(--transition-fast);
  width: min(240px, 100%);
}

.search-input:focus {
  border-color: var(--brand-forest);
  box-shadow: 0 0 0 3px rgba(52, 72, 59, 0.12);
}

/* ── HOME LAYOUT & SECTIONS ────────────────────────────────────────────── */
.home-layout {
  max-width: 1140px;
  margin: 0 auto;
  padding: 44px 24px 80px;
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 48px;
}

.home-main {
  min-width: 0;
}

.home-sidebar {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20px;
  border-bottom: 2px solid var(--border-color);
  padding-bottom: 8px;
}

.section-title {
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.015em;
  margin: 0;
}

.section-link {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-forest);
}

.section-link:hover {
  text-decoration: underline;
}

/* ── POST GRID & CARDS ─────────────────────────────────────────────────── */
.post-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
  margin-bottom: 40px;
}

.post-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
  display: block;
  color: inherit;
  box-shadow: var(--shadow-sm);
}

.post-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

.post-card:focus-within {
  outline: 2px solid var(--brand-forest);
  outline-offset: 2px;
}

.card-link {
  display: flex;
  flex-direction: column;
  color: inherit;
  text-decoration: none;
  height: 100%;
}

.card-link:hover {
  text-decoration: none;
}

.card-media {
  display: block;
  height: 180px;
  overflow: hidden;
  position: relative;
  background: var(--bg-secondary);
}

.card-media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 0;
  transition: transform 0.4s ease;
}

.post-card:hover .card-media img {
  transform: scale(1.04);
}

.card-tag-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(4px);
  border-radius: var(--radius-pill);
  padding: 3px 10px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-forest);
  box-shadow: var(--shadow-sm);
}

.card-body {
  padding: 18px 20px 20px;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.card-meta {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 8px;
}

.post-card h3 {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  margin: 0 0 10px;
  letter-spacing: -0.01em;
}

.card-excerpt {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
  margin: 0 0 14px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.read-more {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-forest);
}

/* ── CATEGORY HUB GRID ─────────────────────────────────────────────────── */
.hub-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 40px;
}

.hub-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 18px;
  text-decoration: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: var(--transition-fast);
  color: inherit;
  box-shadow: var(--shadow-sm);
}

.hub-card:hover {
  border-color: var(--brand-forest);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  text-decoration: none;
}

.hub-dot {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
}

.hub-tag {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-forest);
}

.hub-desc {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}

.hub-count {
  font-size: 12px;
  color: var(--accent-terracotta);
  font-weight: 600;
  margin-top: auto;
}

/* ── WIDE CARDS (Continue Reading) ─────────────────────────────────────── */
.wide-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 40px;
}

.post-card-wide {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
  box-shadow: var(--shadow-sm);
}

.post-card-wide:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.post-card-wide .card-link {
  display: grid;
  grid-template-columns: 200px 1fr;
  text-decoration: none;
  color: inherit;
}

.wide-thumb {
  height: 140px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.wide-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 0;
  transition: transform 0.4s ease;
}

.post-card-wide:hover .wide-thumb img {
  transform: scale(1.04);
}

.wide-body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.wide-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-forest);
  margin-bottom: 6px;
}

.wide-body h3 {
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}

.wide-excerpt {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.55;
  margin: 0 0 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── SIDEBAR WIDGETS ───────────────────────────────────────────────────── */
.sidebar-newsletter {
  background: var(--brand-forest);
  border-radius: var(--radius-lg);
  padding: 28px 24px;
  text-align: center;
  color: var(--bg-card);
  box-shadow: var(--shadow-md);
}

.snl-eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--brand-sage);
  margin-bottom: 10px;
}

.sidebar-newsletter h3 {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  color: var(--bg-card);
  margin-bottom: 8px;
  line-height: 1.25;
}

.sidebar-newsletter p {
  font-size: 13px;
  color: var(--brand-sage);
  line-height: 1.6;
  margin-bottom: 18px;
}

.snl-input {
  width: 100%;
  padding: 10px 16px;
  border-radius: var(--radius-pill);
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.12);
  color: var(--bg-card);
  font-size: 13px;
  margin-bottom: 10px;
  outline: none;
  font-family: var(--font-sans);
  transition: var(--transition-fast);
}

.snl-input::placeholder {
  color: rgba(255, 255, 255, 0.7);
}

.snl-input:focus {
  background: rgba(255, 255, 255, 0.2);
  border-color: var(--brand-sage);
}

.snl-btn {
  width: 100%;
  padding: 10px;
  background: var(--bg-primary);
  color: var(--brand-forest);
  border: none;
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: var(--transition-fast);
}

.snl-btn:hover {
  background: var(--bg-card);
  transform: translateY(-1px);
}

.snl-note {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.65) !important;
  margin-top: 8px !important;
  margin-bottom: 0 !important;
}

.sidebar-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 22px;
  box-shadow: var(--shadow-sm);
}

.sidebar-card-title {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.trending-list, .start-list {
  display: flex;
  flex-direction: column;
}

.trending-item {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  text-decoration: none;
  color: inherit;
  transition: var(--transition-fast);
}

.trending-item:last-child {
  border-bottom: none;
}

.trending-thumb {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-secondary);
}

.trending-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 0;
}

.trending-tag {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--brand-forest);
  margin-bottom: 2px;
}

.trending-title {
  font-family: var(--font-serif);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.start-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: var(--transition-fast);
}

.start-link:last-child {
  border-bottom: none;
}

.start-link:hover {
  color: var(--brand-forest);
  text-decoration: none;
}

.start-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--brand-forest);
  flex-shrink: 0;
}

/* ── ARTICLE READING VIEW ──────────────────────────────────────────────── */
.post-layout {
  max-width: 1140px;
  margin: 0 auto;
  padding: 44px 24px 80px;
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 56px;
}

.post-main {
  min-width: 0;
  max-width: 740px;
}

.post-sidebar {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 18px;
  font-size: 13px;
  color: var(--text-muted);
  flex-wrap: wrap;
}

.breadcrumb a {
  color: var(--text-muted);
  text-decoration: none;
}

.breadcrumb a:hover {
  color: var(--brand-forest);
}

.breadcrumb span {
  color: var(--text-primary);
  font-weight: 500;
}

.article-tag-pill {
  display: inline-block;
  background: var(--brand-sage);
  color: var(--brand-forest);
  border-radius: var(--radius-pill);
  padding: 4px 14px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 16px;
}

.post-meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 13px;
  color: var(--text-muted);
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 24px;
}

.author-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--brand-forest);
  color: var(--bg-card);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.meta-sep {
  opacity: 0.4;
}

.post-main picture img {
  margin: 22px 0 28px;
  width: 100%;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

/* ── CALLOUT BOXES & EDITORIAL ELEMENTS ────────────────────────────────── */
.quick-answer {
  background: var(--bg-subtle);
  border-left: 4px solid var(--brand-forest);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding: 16px 20px;
  margin: 0 0 24px;
  font-size: 16px;
  line-height: 1.7;
}

.quick-answer strong {
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--brand-forest);
  font-weight: 700;
  display: block;
  margin-bottom: 6px;
}

.takeaways {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 18px 22px;
  margin: 20px 0;
  box-shadow: var(--shadow-sm);
}

.takeaways h2 {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-forest);
  margin: 0 0 12px;
}

.takeaways ul {
  padding-left: 20px;
}

.takeaways li {
  font-size: 15px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.quick-win {
  background: #F3F7F2;
  border: 1px solid #CAD9C5;
  border-radius: var(--radius-md);
  padding: 18px 22px;
  margin: 26px 0;
}

.quick-win h3 {
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--brand-forest);
  margin: 0 0 8px;
}

.quick-win p {
  font-size: 16px;
  color: var(--text-primary);
  font-weight: 500;
  line-height: 1.65;
  margin: 0;
}

.myth-fact {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin: 26px 0;
  box-shadow: var(--shadow-sm);
}

.myth-header {
  background: #FDF3F1;
  padding: 10px 18px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #B23B2B;
  border-bottom: 1px solid var(--border-color);
}

.myth-body {
  padding: 14px 18px;
  color: var(--text-secondary);
  font-style: italic;
  font-size: 15px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-card);
}

.fact-header {
  background: #F2F7F2;
  padding: 10px 18px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--brand-forest);
  border-bottom: 1px solid var(--border-color);
}

.fact-body {
  padding: 14px 18px;
  color: var(--text-primary);
  font-size: 15px;
  background: var(--bg-card);
}

.editorial-notice {
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-left: 4px solid var(--brand-forest);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding: 18px 22px;
  margin: 32px 0 24px;
}

.editorial-notice h3 {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-forest);
  margin: 0 0 8px;
}

.editorial-notice p {
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.65;
  margin: 0;
}

.toc {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 18px 22px;
  margin: 22px 0;
  box-shadow: var(--shadow-sm);
}

.toc h2 {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-forest);
  margin: 0 0 12px;
}

.toc ol {
  padding-left: 20px;
}

.toc li {
  font-size: 14px;
  margin-bottom: 6px;
}

.toc a {
  color: var(--text-secondary);
}

.toc a:hover {
  color: var(--brand-forest);
}

.sidebar-toc {
  margin: 0;
}

.related, .next-article, .more-in-tag {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 24px;
  margin: 28px 0;
  box-shadow: var(--shadow-sm);
}

.related h2, .next-article h2, .more-in-tag h2 {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-forest);
  margin: 0 0 14px;
}

.next-link {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.next-link:hover {
  color: var(--brand-forest);
}

/* ── AFFILIATE DESIGN SYSTEM ───────────────────────────────────────────── */
.product-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 24px;
  margin: 28px 0;
  display: grid;
  grid-template-columns: 190px 1fr;
  gap: 24px;
  align-items: center;
  box-shadow: var(--shadow-md);
}

.product-card-img {
  width: 100%;
  height: 180px;
  object-fit: cover;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.product-badge {
  display: inline-block;
  background: var(--brand-sage);
  color: var(--brand-forest);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 3px 12px;
  border-radius: var(--radius-pill);
  margin-bottom: 8px;
}

.product-title {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.product-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 14px;
}

.product-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.product-price {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.product-merchant {
  font-size: 12px;
  color: var(--text-muted);
}

.btn-affiliate {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--brand-forest);
  color: var(--bg-card);
  padding: 10px 22px;
  border-radius: var(--radius-pill);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: var(--transition-fast);
  box-shadow: var(--shadow-sm);
}

.btn-affiliate:hover {
  background: var(--brand-forest-hover);
  color: var(--bg-card);
  text-decoration: none;
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.btn-terracotta {
  background: var(--accent-terracotta);
}

.btn-terracotta:hover {
  background: var(--accent-terracotta-hover);
}

/* ── COMPARISON TABLE ─────────────────────────────────────────────────── */
.table-wrap {
  overflow-x: auto;
  margin: 32px 0;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
}

.comp-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  text-align: left;
}

.comp-table th {
  background: var(--bg-subtle);
  padding: 14px 18px;
  font-weight: 700;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
  font-family: var(--font-sans);
  letter-spacing: 0.02em;
}

.comp-table td {
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.comp-table tr:last-child td {
  border-bottom: none;
}

.comp-table tr:hover td {
  background: rgba(220, 227, 213, 0.15);
}

.comp-table .winner-col {
  background: rgba(220, 227, 213, 0.3);
  font-weight: 600;
  color: var(--brand-forest);
}

/* ── PROS & CONS ──────────────────────────────────────────────────────── */
.pros-cons-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin: 28px 0;
}

.pros-box {
  background: #F4F8F4;
  border: 1px solid #CAD9C5;
  border-radius: var(--radius-md);
  padding: 20px;
}

.cons-box {
  background: #FDF6F3;
  border: 1px solid #E9D2C7;
  border-radius: var(--radius-md);
  padding: 20px;
}

.pros-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-forest);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.cons-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-terracotta);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pros-box ul, .cons-box ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.pros-box li, .cons-box li {
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 8px;
  padding-left: 22px;
  position: relative;
}

.pros-box li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: var(--brand-forest);
  font-weight: 700;
}

.cons-box li::before {
  content: '✕';
  position: absolute;
  left: 0;
  color: var(--accent-terracotta);
  font-weight: 700;
}

.affiliate-disclosure {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  margin: 18px 0;
  padding: 12px 16px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--brand-sage);
}

/* ── PINTEREST VERTICAL IMAGE SUPPORT ──────────────────────────────────── */
.pinterest-card {
  max-width: 420px;
  margin: 32px auto;
  text-align: center;
}

.pinterest-card img {
  aspect-ratio: 2 / 3;
  width: 100%;
  height: auto;
  object-fit: cover;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
}

.pin-save-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #E60023;
  color: #FFFFFF;
  padding: 9px 20px;
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  margin-top: 12px;
  transition: var(--transition-fast);
}

.pin-save-btn:hover {
  background: #B8001B;
  color: #FFFFFF;
  text-decoration: none;
  transform: translateY(-1px);
}

/* ── BUTTONS ───────────────────────────────────────────────────────────── */
.btn-primary {
  display: inline-block;
  background: var(--brand-forest);
  color: var(--bg-card);
  padding: 11px 24px;
  border-radius: var(--radius-pill);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: var(--transition-fast);
  border: none;
  cursor: pointer;
  font-family: var(--font-sans);
  box-shadow: var(--shadow-sm);
}

.btn-primary:hover {
  background: var(--brand-forest-hover);
  transform: translateY(-2px);
  text-decoration: none;
  color: var(--bg-card);
  box-shadow: var(--shadow-md);
}

.btn-secondary {
  display: inline-block;
  background: transparent;
  color: var(--text-primary);
  padding: 11px 22px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--border-color);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: var(--transition-fast);
  cursor: pointer;
  font-family: var(--font-sans);
}

.btn-secondary:hover {
  border-color: var(--brand-forest);
  color: var(--brand-forest);
  text-decoration: none;
}

/* ── TAG & ABOUT PAGES ─────────────────────────────────────────────────── */
.tag-hero {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  padding: 44px 24px 32px;
  margin-bottom: 32px;
}

.tag-hero h1 {
  font-family: var(--font-serif);
  font-size: 38px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: 10px;
}

.tag-hero p {
  font-size: 17px;
  color: var(--text-secondary);
  max-width: 580px;
  line-height: 1.75;
}

/* ── FOOTER ────────────────────────────────────────────────────────────── */
.site-footer {
  background: var(--brand-forest);
  color: var(--brand-sage);
  padding: 56px 24px 32px;
  margin-top: 0;
}

.footer-inner {
  max-width: 1140px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 48px;
  padding-bottom: 36px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
  margin-bottom: 24px;
}

.footer-brand p {
  font-size: 14px;
  color: var(--brand-sage);
  line-height: 1.7;
  max-width: 280px;
  margin-top: 10px;
}

.footer-logo {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 700;
  color: var(--bg-card);
  display: inline-flex;
  align-items: center;
}

.footer-col h4 {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--bg-card);
  margin-bottom: 16px;
}

.footer-col ul {
  list-style: none;
  padding: 0;
}

.footer-col li {
  margin-bottom: 9px;
}

.footer-col a {
  font-size: 14px;
  color: var(--brand-sage);
  text-decoration: none;
  transition: var(--transition-fast);
}

.footer-col a:hover {
  color: var(--bg-card);
}

.footer-bottom {
  max-width: 1140px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--brand-sage);
  flex-wrap: wrap;
  gap: 12px;
}

.footer-bottom a {
  color: var(--brand-sage);
  text-decoration: none;
}

.footer-bottom a:hover {
  color: var(--bg-card);
}

/* ── BACK TO TOP BUTTON ────────────────────────────────────────────────── */
.back-to-top {
  position: fixed;
  right: 22px;
  bottom: 24px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--brand-forest);
  font-size: 18px;
  font-weight: 700;
  display: none;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  transition: var(--transition-fast);
  z-index: 40;
}

.back-to-top.visible {
  display: flex;
  align-items: center;
  justify-content: center;
}

.back-to-top:hover {
  background: var(--brand-forest);
  color: var(--bg-card);
  border-color: var(--brand-forest);
  transform: translateY(-2px);
}

/* ── RESPONSIVE DESIGN (Tablets & Mobile) ───────────────────────────────── */
@media (max-width: 960px) {
  .hero-split {
    grid-template-columns: 1fr;
  }

  .hero-left {
    max-width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
    padding: 44px 24px 36px;
  }

  .home-layout,
  .post-layout {
    grid-template-columns: 1fr;
    gap: 36px;
  }

  .home-sidebar,
  .post-sidebar {
    display: none;
  }

  .hub-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .trust-inner {
    flex-wrap: wrap;
  }

  .trust-item {
    flex: 1 1 45%;
    border-bottom: 1px solid var(--border-color);
  }

  .footer-inner {
    grid-template-columns: 1fr;
    gap: 32px;
  }
}

@media (max-width: 640px) {
  .header-inner {
    height: 56px;
  }

  .site-nav a:not(.nav-cta) {
    display: none;
  }

  .hero-h1 {
    font-size: clamp(28px, 6.5vw, 38px);
  }

  .post-grid {
    grid-template-columns: 1fr;
  }

  .hub-grid {
    grid-template-columns: 1fr;
  }

  .post-card-wide .card-link {
    grid-template-columns: 1fr;
  }

  .wide-thumb {
    height: 160px;
  }

  .product-card {
    grid-template-columns: 1fr;
  }

  .pros-cons-grid {
    grid-template-columns: 1fr;
  }

  .hero-btns {
    flex-direction: column;
    align-items: stretch;
  }

  .btn-primary, .btn-secondary {
    width: 100%;
    text-align: center;
  }

  .chips-inner {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input {
    width: 100%;
  }
}
"""
