#!/usr/bin/env python3
"""Generate the HabitFlame site from scripts/pages.json, scripts/template.html
and the policy fragments in scripts/policies/, so every page shares one
header, footer, stylesheet and structured data shape.

Run from anywhere:  python3 scripts/build-pages.py

Outputs (all at the repo root):
  index.html                 the landing page
  <slug>.html                one guide page per entry in pages.json "pages"
  support.html, privacy-policy.html, terms-of-service.html
                             the policy pages, one per entry in "policies"
  sitemap.xml                landing, guides and the three policy pages
  robots.txt

The site is served by Vercel with cleanUrls and no trailing slash (see
vercel.json), so a file <name>.html is published at /<name> and the landing
at /. Every URL the generator writes is that clean form.

Rendering is deterministic: the same inputs give the same bytes. The only
dates are the sitemap lastmod values, each page's "lastmod" in pages.json,
so a rebuild on another day changes nothing. The stylesheet version in the
page head is a hash of site.css, so it changes exactly when the file does.
"""
import datetime
import hashlib
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
CONFIG = json.loads((SCRIPTS / "pages.json").read_text(encoding="utf-8"))
TEMPLATE = (SCRIPTS / "template.html").read_text(encoding="utf-8")

SITE = CONFIG["site"]
FACTS = CONFIG["facts"]
LANDING = CONFIG["landing"]
PAGES = CONFIG["pages"]
POLICIES = CONFIG["policies"]

BASE = SITE["base_url"].rstrip("/")
YEAR = "2026"
STYLESHEET = "site.css"
# Published files under /assets are cached for a year and never change in
# place, so each of these names belongs to one version of its file.
FONT = "assets/fonts/bricolage-grotesque-opsz-wght-latin.woff2"
OG_IMAGE = "assets/og/site-2026-10-16.png"
OG_IMAGE_ALT = ("HabitFlame: habits stick when someone is watching. The Partners tab, "
                "with a flame from Jordan for your Morning Run.")
POLICY_PAGES = [p["file"] for p in POLICIES]

STORE_BUTTON_TEXT = "Download on the App Store"
STORE_NOTE = "Free to download for iPhone and iPad. Premium is a one-time $9.99 purchase."
CTA_HEADING = "Start with one habit and one person"
CTA_TEXT = "Download HabitFlame, add a habit, and send one invite link."
# The landing's second action: send the page to the person you would pair
# with. The button stays hidden until the script below finds a way to share.
SHARE_BUTTON_TEXT = "Send this page to your partner"
SHARE_TEXT = "Be my accountability partner on HabitFlame?"
SHARE_SCRIPT = """<script>
(function () {
  var canShare = typeof navigator.share === "function";
  var canCopy = !!(navigator.clipboard && navigator.clipboard.writeText);
  if (!canShare && !canCopy) return;
  var canonical = document.querySelector('link[rel="canonical"]');
  var url = canonical ? canonical.href : window.location.href;
  Array.prototype.forEach.call(document.querySelectorAll("[data-share]"), function (button) {
    var label = button.textContent;
    var timer = null;
    button.hidden = false;
    button.addEventListener("click", function () {
      if (canShare) {
        navigator.share({ title: document.title, text: button.getAttribute("data-share"), url: url }).catch(function () {});
        return;
      }
      navigator.clipboard.writeText(url).then(function () {
        button.textContent = "Link copied";
        clearTimeout(timer);
        timer = setTimeout(function () { button.textContent = label; }, 2400);
      }, function () {});
    });
  });
})();
</script>"""


def esc(text: str) -> str:
    """Escape text for an HTML text node or a double quoted attribute."""
    return html.escape(text, quote=True)


# Inline link form for copy in pages.json: [link text](path), where path is a
# clean URL path on this site (no .html, no trailing slash), relative to
# base_url, or a mailto: address. Everything else in the string is escaped;
# structured data gets the link text only.
LINK = re.compile(r"\[([^\[\]]+)\]\((mailto:[a-z0-9.+-]+@[a-z0-9.-]+|[a-z0-9][a-z0-9./-]*(?:#[a-z0-9-]+)?)\)")


def rich(text: str) -> str:
    """Escaped HTML with the inline link form turned into links."""
    out, pos = [], 0
    for m in LINK.finditer(text):
        out.append(esc(text[pos:m.start()]))
        target = m.group(2)
        href = target if target.startswith("mailto:") else BASE + "/" + target
        out.append(f'<a href="{esc(href)}">{esc(m.group(1))}</a>')
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def plain(text: str) -> str:
    """The text a reader sees: the inline link form reduced to its link text."""
    return LINK.sub(r"\1", text)


def is_policy(page: dict | None) -> bool:
    return page is not None and "file" in page


def page_file(page: dict | None) -> str:
    """Output path relative to the repo root."""
    if page is None:
        return "index.html"
    return page["file"] if is_policy(page) else f"{page['slug']}.html"


def page_url(page: dict | None) -> str:
    """Canonical URL, the clean form Vercel serves: the landing is base_url + "/",
    any other page is base_url + "/" + its file name without ".html"."""
    if page is None:
        return f"{BASE}/"
    return f"{BASE}/{page_file(page)[:-len('.html')]}"


def page_title(page: dict | None) -> str:
    return LANDING["title"] if page is None else page["title"]


def page_description(page: dict | None) -> str:
    return LANDING["description"] if page is None else page["description"]


def css_version() -> str:
    """First 12 hex digits of the stylesheet's SHA-256."""
    return hashlib.sha256((ROOT / STYLESHEET).read_bytes()).hexdigest()[:12]


# ---- Shared fragments --------------------------------------------------------

def store_button() -> str:
    return f'<a class="store" href="{esc(SITE["app_store_url"])}">{esc(STORE_BUTTON_TEXT)}</a>'


def store_note() -> str:
    return f'<p class="store-note">{esc(STORE_NOTE)}</p>'


def actions() -> str:
    """The landing's two actions: the store button and the share button."""
    return (
        '<div class="actions">\n'
        f"{store_button()}\n"
        f'<button type="button" class="share" data-share="{esc(SHARE_TEXT)}" hidden>{esc(SHARE_BUTTON_TEXT)}</button>\n'
        "</div>"
    )


def shot(spec: dict, sizes: str, eager: bool) -> str:
    """A screenshot from /assets/shots at 600 and 900 pixels wide."""
    src = f"{BASE}/assets/shots/{spec['stem']}"
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (
        f'<img src="{esc(src)}-600.webp" srcset="{esc(src)}-600.webp 600w, {esc(src)}-900.webp 900w" '
        f'sizes="{esc(sizes)}" width="{int(spec["width"])}" height="{int(spec["height"])}" '
        f'alt="{esc(spec["alt"])}" {load} decoding="async">'
    )


def rows(items: list, tag: str = "ul", cls: str = "rows") -> str:
    lis = "\n".join(f"<li><h3>{esc(title)}</h3>\n<p>{rich(body)}</p></li>" for title, body in items)
    return f'<{tag} class="{cls}">\n{lis}\n</{tag}>'


def cta_section() -> str:
    return (
        '<section class="cta">\n'
        f"<h2>{esc(CTA_HEADING)}</h2>\n"
        f"<p>{esc(CTA_TEXT)}</p>\n"
        f"{store_button()}\n"
        "</section>"
    )


def guides_list(pages: list[dict]) -> str:
    items = "\n".join(
        f'<li><a href="{esc(page_url(p))}">{esc(p["title"])}</a>\n<p>{esc(p["description"])}</p></li>'
        for p in pages
    )
    return f'<ul class="guides">\n{items}\n</ul>'


def faq_list(entries: list[dict]) -> str:
    rows = "\n".join(f"<dt>{esc(e['q'])}</dt>\n<dd>{rich(e['a'])}</dd>" for e in entries)
    return f"<dl>\n{rows}\n</dl>"


# ---- Landing -----------------------------------------------------------------

# The phone shot widths, matching --phone-shot in site.css: 60% of the
# screen on a phone, 300px from a laptop up.
HERO_SIZES = "(max-width: 47.99em) min(60vw, 300px), 300px"
FEATURE_SIZES = "(max-width: 47.99em) min(60vw, 280px), 280px"


def rail(cls: str, head: str, body: str, section_id: str = "") -> str:
    """A landing section: the heading block in the left rail, the content in
    the wide column beside it."""
    ident = f' id="{section_id}"' if section_id else ""
    return f'<section{ident} class="rail {cls}">\n<div class="rail-head">\n{head}\n</div>\n{body}\n</section>'


def landing_main() -> str:
    hero, pairing, features, pricing = LANDING["hero_shot"], LANDING["pairing"], LANDING["features"], LANDING["pricing"]
    price = esc(FACTS["price"])
    price_heading = (esc(pricing["heading"]).replace(price, f'<span class="price">{price}</span>')
                     + f' <span class="terms">{esc(pricing["terms"])}</span>')
    parts = [
        '<section class="hero">\n'
        '<div class="hero-copy">\n'
        f"<h1>{esc(LANDING['headline'])}</h1>\n"
        f'<p class="lede">{esc(LANDING["lede"])}</p>\n'
        f"{actions()}\n"
        f'<p class="store-note">{esc(LANDING["store_note"])}</p>\n'
        "</div>\n"
        '<figure class="hero-shot">\n'
        '<div class="shot-clip"><div class="device"><div class="screen">'
        f"{shot(hero, HERO_SIZES, eager=True)}"
        '<span class="ring" aria-hidden="true"></span></div></div></div>\n'
        f'<figcaption class="callout">{esc(LANDING["callout"])}</figcaption>\n'
        "</figure>\n"
        "</section>",
        rail("pairing",
             f"<h2>{esc(pairing['heading'])}</h2>\n"
             f'<p class="section-intro">{rich(pairing["intro"])}</p>',
             rows(pairing["steps"], "ol", "rows steps")),
        rail("features",
             f"<h2>{esc(features['heading'])}</h2>\n"
             f'<figure class="features-shot"><div class="device whole"><div class="screen">'
             f'{shot(features["shot"], FEATURE_SIZES, eager=False)}</div></div></figure>',
             rows(features["items"])),
        '<section class="pricing">\n'
        f'<h2 class="price-row">{price_heading}</h2>\n'
        f'{rows(pricing["tiers"], "ul", "tiers")}\n'
        "</section>",
        rail("guides-list",
             f"<h2>{esc(LANDING['guides_heading'])}</h2>\n"
             f'<p class="section-intro">{esc(LANDING["guides_intro"])}</p>',
             guides_list(PAGES), section_id="guides"),
        rail("faq", "<h2>Questions</h2>", faq_list(LANDING["faq"])),
        '<section class="cta">\n'
        f"<h2>{esc(CTA_HEADING)}</h2>\n"
        f"<p>{esc(CTA_TEXT)}</p>\n"
        f"{actions()}\n"
        "</section>",
        SHARE_SCRIPT,
    ]
    return "\n".join(parts)


# ---- Guide pages -------------------------------------------------------------

def render_block(block: dict, page: dict) -> str:
    if len(block) != 1:
        raise ValueError(f"{page['slug']}: a block must have exactly one key, got {sorted(block)}")
    kind, value = next(iter(block.items()))
    if kind == "h2":
        return f"<h2>{esc(value)}</h2>"
    if kind == "p":
        return f"<p>{rich(value)}</p>"
    if kind == "ul":
        return "<ul>\n" + "\n".join(f"<li>{rich(item)}</li>" for item in value) + "\n</ul>"
    if kind == "table":
        head = "".join(f'<th scope="col">{esc(c)}</th>' for c in value["head"])
        body = "\n".join(
            f'<tr><th scope="row">{esc(row[0])}</th>' + "".join(f"<td>{esc(c)}</td>" for c in row[1:]) + "</tr>"
            for row in value["rows"]
        )
        return f'<table class="compare">\n<thead><tr>{head}</tr></thead>\n<tbody>\n{body}\n</tbody>\n</table>'
    if kind == "faq":
        return f'<section class="faq">\n<h2>{esc(page["faq_heading"])}</h2>\n{faq_list(value)}\n</section>'
    raise ValueError(f"{page['slug']}: unknown block type {kind!r}")


def page_faq(page: dict) -> list[dict]:
    return [e for b in page["blocks"] if "faq" in b for e in b["faq"]]


def article_main(page: dict) -> str:
    blocks = "\n".join(render_block(b, page) for b in page["blocks"])
    others = [p for p in PAGES if p["slug"] != page["slug"]]
    return (
        '<div class="guide">\n'
        '<header class="article-head">\n'
        f"<h1>{esc(page['h1'])}</h1>\n"
        f'<p class="deck">{esc(page["deck"])}</p>\n'
        f"{store_button()}\n"
        f"{store_note()}\n"
        "</header>\n"
        f'<div class="article-body">\n{blocks}\n</div>\n'
        '<section class="related">\n<h2>More guides</h2>\n'
        f"{guides_list(others)}\n"
        "</section>\n"
        f"{cta_section()}\n"
        "</div>"
    )


# ---- Policy pages ------------------------------------------------------------

def policy_body(page: dict) -> str:
    """A policy page's body: a hand written HTML fragment from scripts/policies/,
    or, for the support page, an intro plus a question list from pages.json."""
    if "fragment" in page:
        return (SCRIPTS / "policies" / page["fragment"]).read_text(encoding="utf-8").strip()
    parts = [f"<p>{rich(t)}</p>" for t in page["intro"]]
    parts.append(f'<section class="faq">\n<h2>{esc(page["faq_heading"])}</h2>\n{faq_list(page["faq"])}\n</section>')
    return "\n".join(parts)


def policy_main(page: dict) -> str:
    return (
        '<div class="guide">\n'
        '<header class="article-head">\n'
        f"<h1>{esc(page['h1'])}</h1>\n"
        f'<p class="deck">{esc(page["deck"])}</p>\n'
        "</header>\n"
        f'<div class="article-body">\n{policy_body(page)}\n</div>\n'
        "</div>"
    )


# ---- Structured data ---------------------------------------------------------

def jsonld(page: dict | None) -> str:
    url = page_url(page)
    title = page_title(page)
    description = page_description(page)
    if page is None:
        faq = LANDING["faq"]
    elif is_policy(page):
        faq = page.get("faq", [])
    else:
        faq = page_faq(page)
    # Every page carries its own WebSite node, so the WebPage isPartOf
    # reference resolves on the page that makes it.
    graph: list[dict] = [{
        "@type": "WebSite",
        "@id": f"{BASE}/#website",
        "name": SITE["name"],
        "url": f"{BASE}/",
    }]
    if page is None:
        graph.append({
            "@type": "SoftwareApplication",
            "name": SITE["name"],
            "operatingSystem": "iOS",
            "applicationCategory": "HealthApplication",
            "url": SITE["app_store_url"],
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        })
    graph.append({
        "@type": "WebPage",
        "@id": f"{url}#webpage",
        "name": title,
        "description": description,
        "url": url,
        "isPartOf": {"@id": f"{BASE}/#website"},
    })
    if page is not None:
        graph.append({
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{BASE}/"},
                {"@type": "ListItem", "position": 2, "name": page["title"], "item": url},
            ],
        })
    if faq:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": e["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": plain(e["a"])}}
                for e in faq
            ],
        })
    text = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1)
    # A literal "</" would end the script element early; "<\/" is the same JSON string.
    return text.replace("</", "<\\/")


# ---- Page assembly -----------------------------------------------------------

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def fill(values: dict[str, str]) -> str:
    """Single pass substitution, so content can never be re-read as a placeholder."""
    missing = set(_PLACEHOLDER.findall(TEMPLATE)) - set(values)
    if missing:
        raise KeyError(f"template placeholders without a value: {sorted(missing)}")
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], TEMPLATE)


def render(page: dict | None) -> str:
    """Render the landing (page is None), a guide page or a policy page."""
    if page is None:
        main, body_class = landing_main(), "landing"
    elif is_policy(page):
        main, body_class = policy_main(page), "article policy"
    else:
        main, body_class = article_main(page), "article"
    return fill({
        "title": esc(page_title(page)),
        "description": esc(page_description(page)),
        "url": esc(page_url(page)),
        "base": esc(BASE),
        "stylesheet": esc(STYLESHEET),
        "css_version": esc(css_version()),
        "font": esc(FONT),
        "og_image": esc(OG_IMAGE),
        "og_image_alt": esc(OG_IMAGE_ALT),
        "jsonld": jsonld(page),
        "body_class": body_class,
        "main": main,
        "app_store_url": esc(SITE["app_store_url"]),
        "contact_email": esc(SITE["contact_email"]),
        "brand_url": esc(SITE["brand_url"]),
        "brand_footer": esc(SITE["brand_footer"]),
        "year": YEAR,
    })


def sitemap_urls() -> list[str]:
    return [page_url(p) for p in [None, *PAGES, *POLICIES]]


def checked_date(date: str, where: str) -> str:
    if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError(f"{where} must be YYYY-MM-DD, got {date!r}")
    datetime.date.fromisoformat(date)  # and a real date
    return date


def sitemap_entries() -> list[tuple[str, str]]:
    """(URL, lastmod) for the landing, every guide and the policy pages."""
    entries = [(f"{BASE}/", checked_date(LANDING["lastmod"], "landing.lastmod"))]
    entries += [(page_url(p), checked_date(p["lastmod"], f"{p['slug']}.lastmod")) for p in PAGES]
    entries += [(page_url(p), checked_date(p["lastmod"], f"{p['file']}.lastmod")) for p in POLICIES]
    return entries


def render_sitemap() -> str:
    entries = "\n".join(f"  <url>\n    <loc>{esc(u)}</loc>\n    <lastmod>{d}</lastmod>\n  </url>"
                        for u, d in sitemap_entries())
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{entries}\n</urlset>\n")


def render_robots() -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n"


def outputs() -> dict[str, str]:
    """Every generated file, keyed by its path relative to the repo root."""
    files = {page_file(p): render(p) for p in [None, *PAGES, *POLICIES]}
    files["sitemap.xml"] = render_sitemap()
    files["robots.txt"] = render_robots()
    return files


def main() -> None:
    slugs = [p["slug"] for p in PAGES] + [p["file"][:-len(".html")] for p in POLICIES]
    if len(set(slugs)) != len(slugs) or any(not re.fullmatch(r"[a-z0-9-]+", s) for s in slugs):
        raise SystemExit(f"slugs and policy names must be unique lowercase words joined by hyphens: {slugs}")
    for rel, text in outputs().items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {rel}")


if __name__ == "__main__":
    main()
