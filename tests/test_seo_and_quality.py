from __future__ import annotations

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from src.app.content import ensure_scientific_links, validate_article_quality
from src.app.pinterest_seo import generate_triple_pins
from src.app.topics import Topic
from src.app.validate_links import validate_links


class TestSEOAndQuality(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.docs_dir = self.repo_root / "docs"
        self.posts_json_path = self.docs_dir / "posts.json"
        self.sitemap_path = self.docs_dir / "sitemap.xml"
        self.robots_path = self.docs_dir / "robots.txt"
        self.headers_path = self.docs_dir / "_headers"

    def test_1_and_2_sitemap_validity_and_absence_of_html(self) -> None:
        """Verifica se o sitemap é um XML válido e NÃO contém URLs terminadas em .html."""
        self.assertTrue(self.sitemap_path.exists(), "sitemap.xml não encontrado")
        content = self.sitemap_path.read_text(encoding="utf-8")

        tree = ET.parse(self.sitemap_path)
        root = tree.getroot()
        self.assertTrue(root.tag.endswith("urlset"), "Tag raiz do sitemap deve ser <urlset>")

        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("ns:url", ns)
        self.assertGreaterEqual(len(urls), 5, "Sitemap deve conter pelo menos as páginas essenciais (home, about, tags)")

        loc_tags = root.findall("ns:url/ns:loc", ns)
        for loc in loc_tags:
            url_str = str(loc.text).strip()
            self.assertFalse(
                url_str.endswith(".html"),
                f"Sitemap NUNCA deve conter URLs terminadas em .html: {url_str}",
            )
            self.assertTrue(
                url_str.startswith("https://homewise-living.pages.dev"),
                f"URL fora do domínio canônico: {url_str}",
            )

    def test_3_canonical_urls_map_to_200_physical_files(self) -> None:
        """Verifica se cada URL canônica do sitemap corresponde a um arquivo físico em docs/ (status 200 no Cloudflare Pages)."""
        tree = ET.parse(self.sitemap_path)
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = tree.findall("ns:url/ns:loc", ns)

        for loc in locs:
            url_str = str(loc.text).strip()
            rel = url_str.replace("https://homewise-living.pages.dev", "").strip("/")

            if rel == "":
                target_file = self.docs_dir / "index.html"
            elif rel.startswith("tag/"):
                tag_name = rel.replace("tag/", "").strip()
                target_file = self.docs_dir / "tag" / f"{tag_name}.html"
            else:
                target_file = self.docs_dir / f"{rel}.html"

            self.assertTrue(
                target_file.exists(),
                f"URL canônica do sitemap {url_str} não possui arquivo físico {target_file.name} (resultaria em 404)",
            )

    def test_4_headers_no_conflicting_canonical_or_redirect_loops(self) -> None:
        """Verifica se _headers NÃO possui a regra quebrada de Link: rel='canonical' apontando para .html."""
        if not self.headers_path.exists():
            return
        headers_content = self.headers_path.read_text(encoding="utf-8")
        self.assertNotIn(
            ":splat.html",
            headers_content,
            "Regra conflitante :splat.html encontrada em _headers!",
        )
        self.assertNotIn(
            'rel="canonical"',
            headers_content,
            "Headers HTTP não devem injetar canonical genérico conflitante com o HTML",
        )

    def test_5_internal_links_integrity(self) -> None:
        """Verifica integridade de todos os links internos no docs/."""
        errors = validate_links(self.docs_dir)
        self.assertEqual(errors, [], f"Erros de links internos encontrados: {errors}")

    def test_6_robots_txt_allows_pages_and_declares_sitemap(self) -> None:
        """Verifica se robots.txt permite rastreamento e declara o sitemap oficial."""
        self.assertTrue(self.robots_path.exists(), "robots.txt não encontrado")
        content = self.robots_path.read_text(encoding="utf-8")

        self.assertIn("User-agent: *", content)
        self.assertIn("Allow: /", content)
        self.assertIn("Sitemap: https://homewise-living.pages.dev/sitemap.xml", content)
        self.assertNotIn("Disallow: /", [line.strip() for line in content.splitlines()])

    def test_7_metadata_uniqueness_no_duplicates(self) -> None:
        """Verifica ausência de títulos e slugs duplicados em posts.json."""
        self.assertTrue(self.posts_json_path.exists(), "posts.json não encontrado")
        posts = json.loads(self.posts_json_path.read_text(encoding="utf-8"))

        slugs = [p.get("slug") for p in posts if p.get("slug")]
        titles = [p.get("title") for p in posts if p.get("title")]

        self.assertEqual(len(slugs), len(set(slugs)), "Slugs duplicados detectados em posts.json")
        self.assertEqual(len(titles), len(set(titles)), "Títulos duplicados detectados em posts.json")

    def test_8_article_canonical_matches_clean_url(self) -> None:
        """Verifica se as páginas HTML dos posts têm canonical absoluto apontando para sua própria URL definitiva sem .html."""
        posts = json.loads(self.posts_json_path.read_text(encoding="utf-8"))
        for p in posts[:15]:
            slug = p["slug"]
            html_file = self.docs_dir / f"{slug}.html"
            if not html_file.exists():
                continue
            html_text = html_file.read_text(encoding="utf-8")

            canonical_match = re.search(r"<link\s+rel=['\"]canonical['\"]\s+href=['\"]([^'\"]+)['\"]", html_text)
            self.assertTrue(canonical_match, f"Canonical ausente em {slug}.html")
            canonical_url = canonical_match.group(1)

            self.assertFalse(
                canonical_url.endswith(".html"),
                f"Canonical com .html detectado em {slug}.html: {canonical_url}",
            )
            self.assertTrue(
                canonical_url.endswith(f"/{slug}") or canonical_url.endswith(slug),
                f"Canonical incorreto em {slug}.html: {canonical_url}",
            )

    def test_9_editorial_and_lifestyle_quality_validation(self) -> None:
        """Testa o motor de validação editorial para detectar conteúdo superficial ou sem vocabulário de casa."""
        good_article = {
            "title": "Smart Closet Organization Ideas for Modern Homes",
            "slug": "smart-closet-organization-ideas-modern-homes",
            "html": (
                "<p>Creating an organized home environment requires intentional spatial design and functional storage solutions. "
                "Thoughtful room zoning helps maintain order across your living space and closet. "
                "When your surroundings are orderly, daily routines become smoother, less stressful, and far more enjoyable. "
                "A well-structured space provides clarity, allowing you to focus on what matters most throughout your busy week.</p>"
                "<h2>Designing a Functional Closet Setup</h2>"
                "<p>When planning your storage setup, start by assessing vertical room space. "
                "Utilizing stackable bins and tiered shelving allows you to double your usable hanging capacity. "
                "Design experts emphasize that maintaining clear visual categories helps keep spaces clutter-free. "
                "Take inventory of seasonal garments, outerwear, and delicate items before assigning designated zones. "
                "Installing pull-out organizers or modular baskets keeps accessories accessible yet neatly concealed.</p>"
                "<h2>Material Selection and Aesthetic Harmony</h2>"
                "<p>Integrating natural wood hangers and linen storage baskets creates a cohesive Modern Organic aesthetic. "
                "These tactile materials bring warmth to everyday routines while protecting clothing fibers. "
                "Consistent organizational habits ensure your bedroom retreat remains peaceful and inviting. "
                "Coordinated color palettes and natural textures turn standard utility storage into an elevated dressing space. "
                "Lighting also plays a transformative role: installing warm LED strip lights brightens dark corners and accents your wardrobe.</p>"
                "<h2>Spatial Optimization and Storage Workflows</h2>"
                "<p>Streamlining daily routines begins with strategic placement of frequently used items. "
                "Organizing by category and color creates visual calm and simplifies morning dressing rituals. "
                "Incorporating discreet shelf dividers prevents stacks from toppling and maximizes compact corners. "
                "Clear storage boxes for footwear protect seasonal shoes while maintaining immediate visibility at a glance. "
                "Hooks placed along interior closet doors offer immediate drop zones for hats, scarves, and everyday tote bags.</p>"
                "<h2>Long-Term Maintenance and Decluttering Systems</h2>"
                "<p>Maintaining a clutter-free closet requires manageable seasonal routines rather than drastic overhauls. "
                "Scheduling semi-annual reviews helps you curate wardrobe essentials and donate unused pieces with clarity. "
                "Sustainable home organization blends effortless functionality with inviting interior design principles. "
                "Establishing a one-in, one-out approach prevents accumulation over time and preserves open, breathing room. "
                "When every item has an intuitive home, tidying up takes merely minutes rather than becoming a weekend chore.</p>"
                "<section class='scientific-sources'><h2>Helpful Resources & Guides</h2>"
                "<ul><li><a href='https://www.thespruce.com/closet-organization-guide' target='_blank' rel='noopener noreferrer'>The Spruce — Closet Organization Guide</a></li>"
                "<li><a href='https://www.architecturaldigest.com/closet-design' target='_blank' rel='noopener noreferrer'>Architectural Digest — Interior Inspiration</a></li></ul></section>"
            ),
            "faq": [
                {"question": "How often should you reorganize a closet?", "answer": "A quick seasonal refresh twice a year keeps organization systems functional."},
                {"question": "What storage solutions work best for small spaces?", "answer": "Stackable clear bins and vertical hanging organizers maximize compact spaces."},
            ],
        }
        is_valid, reason = validate_article_quality(good_article, "Closet Organization")
        self.assertTrue(is_valid, f"Artigo legítimo de casa foi rejeitado indevidamente: {reason}")

        # Caso 2: Artigo com promessa de cura perigosa (deve falhar)
        cure_article = dict(good_article)
        cure_article["html"] = good_article["html"] + "<p>This is a miracle cure that cures cancer instantly!</p>"
        is_valid, reason = validate_article_quality(cure_article, "Closet Organization")
        self.assertFalse(is_valid, "Validação deve barrar promessas de cura perigosas")

        # Caso 3: Artigo com anedota pessoal fictícia em 1ª pessoa (deve falhar)
        fake_story_article = dict(good_article)
        fake_story_article["html"] = "<p>When I was diagnosed with clutter, in my personal experience I suffered...</p>" + good_article["html"]
        is_valid, reason = validate_article_quality(fake_story_article, "Closet Organization")
        self.assertFalse(is_valid, "Validação deve barrar relatos em 1ª pessoa fabricados")

        # Caso 4: Artigo muito curto / superficial (deve falhar)
        short_article = dict(good_article)
        short_article["html"] = "<p>Short article with too few words.</p>"
        is_valid, reason = validate_article_quality(short_article, "Closet Organization")
        self.assertFalse(is_valid, "Validação deve barrar artigos superficiais e curtos")

        # Caso 5: Helper ensure_scientific_links deve enriquecer artigos sem link com portais de autoridade
        no_links_article = dict(good_article)
        no_links_article["html"] = re.sub(r"<a [^>]+>(.*?)</a>", r"\1", good_article["html"])
        fixed_html = ensure_scientific_links(no_links_article["html"], "Closet Organization", "home-organization")
        no_links_article["html"] = fixed_html
        is_valid, reason = validate_article_quality(no_links_article, "Closet Organization")
        self.assertTrue(is_valid, f"ensure_scientific_links deveria ter corrigido os links: {reason}")
        self.assertIn("thespruce.com", fixed_html)

    def test_10_triple_pins_generation(self) -> None:
        """Testa a geração dos 3 pins estratégicos por post: Educacional, Problema/Solução e SEO/Buscas."""
        topic = Topic(slug="closet-organization", name="Closet Organization", angle="practical storage ideas", tag="home-organization")
        article_data = {
            "title": "Smart Closet Organization Ideas for Modern Homes",
            "slug": "smart-closet-organization-ideas",
            "meta_description": "Discover practical storage ideas and tips to transform your bedroom closet into an organized retreat.",
            "html": "<p>Practical home ideas for closets.</p>",
            "tag": "home-organization",
            "pin_educational": {
                "pin_title": "The Complete Closet Organization Guide for Beginners",
                "pin_description": "Discover smart shelving and storage solutions to elevate your bedroom closet. Save this practical home guide today!",
                "pin_keywords": "closet organization ideas, home storage hacks, bedroom makeover tips",
            },
            "pin_problem_solution": {
                "pin_title": "Common Closet Mistakes That Create Endless Clutter",
                "pin_description": "Are you wasting precious closet space? Learn what commonly goes wrong and easy storage solutions that work.",
                "pin_keywords": "closet mistakes to avoid, small space storage, declutter your closet",
            },
            "pin_seo_search": {
                "pin_title": "Top Closet Storage Solutions for Every Budget",
                "pin_description": "Explore the most popular closet organization hacks and storage bins. Save this pin for your next home weekend project!",
                "pin_keywords": "closet organization ideas, decluttering tips, storage hacks for small spaces",
            },
        }

        pins = generate_triple_pins(topic, article_data)
        self.assertEqual(len(pins), 3, "Deve gerar exatamente 3 pins distintos por post")

        pin_types = [p["pin_type"] for p in pins]
        self.assertEqual(pin_types, ["educational", "problem_solution", "seo_search"])

        utms = [p["utm_content"] for p in pins]
        self.assertEqual(utms, ["pin_educational", "pin_problem_solution", "pin_seo_search"])

        slots = [p["slot_index"] for p in pins]
        self.assertEqual(slots, [0, 2, 4])

        for p in pins:
            self.assertTrue(40 <= len(p["pin_title"]) <= 70, f"Título fora dos limites: '{p['pin_title']}' ({len(p['pin_title'])})")
            self.assertTrue(140 <= len(p["pin_description"]) <= 260, f"Descrição fora dos limites: '{p['pin_description']}' ({len(p['pin_description'])})")
            self.assertGreaterEqual(len(p["keywords_list"]), 5, "Cada pin deve conter pelo menos 5 keywords")

    def test_11_clean_configuration_without_legacy_dependencies(self) -> None:
        """Verifica que configurações obsoletas foram completamente removidas."""
        from src.app.config import Settings
        import dataclasses
        field_names = [f.name for f in dataclasses.fields(Settings)]
        self.assertNotIn(
            "google_indexing_json_path",
            field_names,
            "google_indexing_json_path deve ser removido de Settings",
        )


if __name__ == "__main__":
    unittest.main()
