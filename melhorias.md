TASK: Design and Implement the Complete Visual Identity of Homewise Living

Act as a Senior UI/UX Designer, Brand Designer, and Frontend Engineer specializing in premium American home, lifestyle, and affiliate content websites.

Your task is to redesign and implement the visual identity of Homewise Living, a US-focused editorial website covering home organization, interior design, kitchen essentials, gardening, home office, smart home products, and pet-friendly living.

The website must look like a premium American lifestyle magazine combined with a modern affiliate shopping guide.

IMPORTANT:

- [x] First inspect the existing repository and identify its framework, architecture, templates, CSS structure, and current functionality.
- [x] Preserve all existing working functionality.
- [x] Do not unnecessarily replace the existing architecture.
- [x] Implement the design directly in the current project.
- [x] Do not create a disconnected mockup or prototype.

---

### STATUS DE EXECUÇÃO: TODAS AS ETAPAS CONCLUÍDAS ✅
*(As alterações foram implementadas diretamente no código-fonte em `src/app/site.py`, `src/app/topics.py`, `src/app/config.py`, `src/app/repair_site.py`, `src/app/verify_seo.py`, `src/app/content.py`, `docs/assets/style.css` e nas páginas geradas em `docs/`).*

---

## 1. BRAND IDENTITY
- [x] **Brand name:** Homewise Living
- [x] **Tagline:** "Smart Ideas for a Better Home."
- [x] **Brand positioning:** A practical, inspiring, and trustworthy destination for people who want to improve their homes through smart ideas, useful products, organization, and everyday solutions.
- [x] **Target audience:** United States, primarily adults interested in home organization, home improvement, interior design, cooking, gardening, and lifestyle products.
- [x] **Brand personality:**
  - [x] Elegant
  - [x] Warm
  - [x] Trustworthy
  - [x] Modern
  - [x] Practical
  - [x] Editorial
  - [x] Approachable
  - [x] Premium but not luxurious or inaccessible
- [x] **Visual direction:** Modern Organic Living.
- [x] Use inspiration from premium American home and lifestyle magazines, contemporary interior design publications, and minimalist editorial websites.
- [x] Do not copy any existing brand or website.

## 2. COLOR PALETTE
- [x] Escolha visual: o verde Forest Green como assinatura da marca, complementado por Warm Ivory e Soft Beige, evitando aparência excessivamente bege.
- [x] Implement exact design tokens using CSS variables:
  - [x] **Primary background:** Warm Ivory — `#F7F5F0` (`--cream`, `--s50`)
  - [x] **Secondary background:** Soft Beige — `#E9E2D6` (`--s100`, `--bd`)
  - [x] **Primary brand:** Forest Green — `#34483B` (`--sage`, `--sage-d`)
  - [x] **Secondary brand:** Sage Green — `#DCE3D5` (`--sage-l`, `--s200`)
  - [x] **Accent:** Warm Terracotta — `#C49A72` (`--terra`)
  - [x] **Primary text:** Charcoal — `#292D29` (`--tp`, `--s800`, `--s900`)
  - [x] **Secondary text:** Muted Gray — `#77776F` (`--ts`, `--tm`, `--s400`, `--s600`)
  - [x] **White:** `#FFFFFF` (`--white`)
- [x] Token ratios e contrastes acessíveis implementados em `_base_css()` e `style.css`.
- [x] Forest Green como cor dos botões principais, cabeçalhos, destaques e rodapé.
- [x] Terracotta usado com moderação em badges, detalhes e contrastes de prós/contras.

## 3. TYPOGRAPHY
- [x] Google Fonts configurados no HTML e CSS:
  - [x] **Headings:** `Playfair Display` (serif editorial)
  - [x] **Body text e interface:** `DM Sans` (clean sans-serif)
- [x] Regras tipográficas e escala responsiva com `clamp()`:
  - [x] Homepage hero: `clamp(36px, 4.5vw, 64px)` desktop.
  - [x] H1 article title: `clamp(32px, 4.5vw, 50px)` desktop.
  - [x] H2: `clamp(24px, 3vw, 36px)`.
  - [x] H3: `clamp(18px, 2vw, 26px)`.
  - [x] Body: 16–18px (line-height confortável de 1.75–1.85).
  - [x] Small labels: 11–14px.
  - [x] Mobile naturalmente escalado sem overflow horizontal.

## 4. LOGO AND BRAND PRESENTATION
- [x] Wordmark em texto limpo: **Homewise Living** em Playfair Display / serif elegante.
- [x] Símbolo arquitetônico minimalista de casa (`_brand_icon_svg`) integrado.
- [x] Aplicação consistente do logotipo em:
  - [x] Header desktop.
  - [x] Header mobile.
  - [x] Footer (com variante clara `brand-icon-light`).
  - [x] Suporte a favicon e meta tags.

## 5. WEBSITE STRUCTURE
- [x] **Header:**
  - [x] Limpo e elegante com bordas sutis.
  - [x] Logotipo proeminente com ícone da marca.
  - [x] Menu de navegação temático completo: Home, Organization, Kitchen, Decor, Garden, Home Office, Pets.
  - [x] Campo de busca responsivo integrado.
  - [x] Botão CTA de inscrição ("Subscribe").
- [x] **Hero Section:**
  - [x] Headline: "Make Your Home Work Better."
  - [x] Supporting text: "Practical ideas, thoughtful products, and everyday inspiration for a home you love."
  - [x] Primary CTA: "Explore Ideas"
  - [x] Secondary CTA: "Discover Home Essentials →"
  - [x] Card em destaque editorial e lista lateral curada.
- [x] **Category Section & Hubs:**
  - [x] Home Organization
  - [x] Kitchen & Cooking
  - [x] Home Decor & Improvement
  - [x] Garden & Outdoor Living
  - [x] Home Office & Smart Living
  - [x] Pet-Friendly Home
  - [x] Hub cards com cores de acento, descrições claras e contagem de posts.
- [x] **Trust Bar:**
  - [x] 100+ home & lifestyle guides
  - [x] 6 categories covered
  - [x] 5× new posts per week
  - [x] 0 fake reviews or prices
- [x] **Featured Articles & Grid:**
  - [x] Article cards com proporção consistente, badge de categoria, data, meta e hover suave.
- [x] **Newsletter:**
  - [x] Headline: "Make Every Day at Home a Little Better."
  - [x] Supporting text: "Get practical home ideas, useful product discoveries, and fresh inspiration delivered to your inbox."
  - [x] Formulário limpo estilizado em Forest Green com input e botão contrastantes.
- [x] **Footer:**
  - [x] Logo com símbolo e tagline da marca.
  - [x] Links de categorias organizados.
  - [x] About Us, Sitemap, Termos e Divulgação de Afiliados.
  - [x] Copyright atualizado e link Back to Top funcional.

## 6. ARTICLE PAGE DESIGN
- [x] Breadcrumb navigation estruturado com Schema BreadcrumbList.
- [x] Category label destacada com pill tag.
- [x] Large H1 editorial com Playfair Display.
- [x] Informações de autor, data de publicação e tempo de leitura.
- [x] Quick Answer box e Key Takeaways no topo.
- [x] Table of Contents dinâmica e acessível.
- [x] Imagem hero destacada com suporte WebP e picture tag.
- [x] Blocos para recomendações de produtos de afiliados visualmente distintos.
- [x] Seção de artigos relacionados e "More in [Category]".
- [x] Bloco de newsletter na barra lateral.
- [x] Aviso editorial e transparência de afiliados no rodapé do artigo.

## 7. AFFILIATE DESIGN SYSTEM
- [x] **Componentes de Afiliados implementados no CSS e templates:**
  - [x] `.product-card`: Card com grid imagem + detalhes, badge, título, descrição e meta.
  - [x] Preço verificado e atribuição de merchant (`.product-price`, `.product-merchant`).
  - [x] Botões de CTA claros e não apelativos: `.btn-affiliate` ("Check Price", "View on Amazon", "See Product Details").
  - [x] Variante Terracotta para destaques especiais (`.btn-terracotta`).
  - [x] `.table-wrap` e `.comp-table`: Tabelas de comparação responsivas com coluna vencedora destacada.
  - [x] `.pros-cons-grid`: Caixas de prós e contras estilizadas com ícones e cores orgânicas.
  - [x] `.affiliate-disclosure`: Caixa de divulgação clara e visível de links afiliados.
  - [x] Suporte para atributos `rel="sponsored nofollow"` em links comerciais.

## 8. PINTEREST OPTIMIZATION
- [x] Suporte a imagens verticais proporção 2:3 (1000x1500) via `.pinterest-card`.
- [x] Botão de salvar no Pinterest (`.pin-save-btn`).
- [x] Metadados Open Graph e Twitter Cards atualizados para Homewise Living.
- [x] Alt text descritivo em todas as imagens.
- [x] URLs amigáveis e canônicas preservadas.

## 9. RESPONSIVE DESIGN
- [x] Layout totalmente responsivo (Desktop, Laptop, Tablet, Mobile).
- [x] Grid adaptativo do hero split, artigos e hubs.
- [x] Navegação móvel sem quebra ou overflow horizontal.
- [x] Espaçamentos confortáveis e áreas de toque acessíveis em botões móveis.

## 10. TECHNICAL REQUIREMENTS
- [x] SEO e URLs canônicas preservadas (todas as URLs limpas sem `.html`).
- [x] Geração e integridade do `sitemap.xml` verificadas.
- [x] `robots.txt` apontando para o sitemap canônico.
- [x] Structured data Schema.org (Article, WebSite, Organization, BreadcrumbList, FAQPage) preservados e válidos.
- [x] Links internos íntegros validados por teste automatizado.
- [x] Conteúdo dos artigos preservado.
- [x] Busca e filtragem por categoria funcionando no frontend sem dependências pesadas.
- [x] 100% dos testes automatizados passando (`test_seo_and_quality.py` e `test_pinterest_features.py`).

## 11. DESIGN QUALITY REQUIREMENTS
- [x] Estética editorial premium American home & lifestyle (Modern Organic Living).
- [x] Cores refinadas: Forest Green, Warm Ivory, Soft Beige e Terracotta.
- [x] Tipografia nobre com Playfair Display e DM Sans.
- [x] Sem elementos genéricos, sombras excessivas ou banners apelativos.

## 12. IMPLEMENTATION WORKFLOW
- [x] 1. Inspeção da arquitetura e repositório realizada.
- [x] 2. Templates de homepage, artigos, categorias e CSS identificados.
- [x] 3. Design system reutilizável implementado com tokens CSS.
- [x] 4. Header e footer atualizados com a nova marca e símbolo.
- [x] 5. Homepage e páginas de categoria atualizadas.
- [x] 6. Páginas de artigos e layout editorial atualizados.
- [x] 7. Componentes de afiliados e prós/contras criados no CSS.
- [x] 8. Responsividade validada.
- [x] 9. Todas as rotas, links internos e arquivos estáticos verificados.
- [x] 10. Testes automatizados executados com sucesso (10/10 OK).
- [x] 11. Resumo das alterações registrado neste arquivo.
