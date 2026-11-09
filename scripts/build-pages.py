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
  invite.html                the invite page, from the hand written
                             scripts/invite.html with its App Store links
                             filled in
  sitemap.xml                landing, guides and the three policy pages
  robots.txt

The site is served by Vercel with cleanUrls and no trailing slash (see
vercel.json), so a file <name>.html is published at /<name> and the landing
at /. Every URL the generator writes is that clean form.

Rendering is deterministic: the same inputs give the same bytes. The only
dates are the sitemap lastmod values, each page's "lastmod" in pages.json,
so a rebuild on another day changes nothing. The stylesheet version in the
page head is a hash of site.css, so it changes exactly when the file does.

App Store links carry Apple's campaign parameters once the account's
provider token is set in pages.json (site.app_store_campaign.pt); each page
has its own campaign token, "ct". With the provider token empty every link is
the bare listing URL, exactly as before campaigns existed.

Every page but the privacy policy loads measure.js, the site's own
measurement module (hand written at the repo root, not generated), and every
App Store link names its place on the page in data-placement.

Checks, from the repository root:
  python3 scripts/verify-pages.py                    the site gate
  python3 -m unittest discover -s scripts/tests      the generator's tests
  node --test scripts/tests/measure.test.mjs         the measurement module's tests
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
INVITE = CONFIG["invite"]
INVITE_FILE = "invite.html"

BASE = SITE["base_url"].rstrip("/")
YEAR = "2026"
STYLESHEET = "site.css"
# Published files under /assets are cached for a year and never change in
# place, so each of these names belongs to one version of its file.
FONT = "assets/fonts/bricolage-grotesque-opsz-wght-latin.woff2"
OG_IMAGE = "assets/og/site-2026-10-16-app.png"
OG_IMAGE_ALT = ("HabitFlame: habits stick when someone is watching. The Partners tab, "
                "with a flame from Jordan for your Morning Run.")
POLICY_PAGES = [p["file"] for p in POLICIES]
# The app's own 1024 pixel icon, byte for byte the AppIcon.png the app ships.
APP_ICON = "app-icon.png"

# App Store campaign links. App Analytics credits App Store page views and
# downloads to a campaign when the link carries the developer account's
# provider token (pt) and a campaign token (ct), in the form the campaign
# link generator in App Store Connect writes: pt, ct, then mt=8. Every page
# has its own ct, so App Analytics can tell the pages apart. Apple allows a
# ct of up to 30 characters; this site keeps to lowercase letters, digits
# and hyphens. The provider token is the account's number, shown only in
# App Store Connect (App Analytics, Campaigns); while it is empty, every
# link stays the bare listing URL.
CAMPAIGN = SITE["app_store_campaign"]
PROVIDER_TOKEN = re.compile(r"[0-9]{1,20}")
CAMPAIGN_TOKEN = re.compile(r"[a-z0-9-]{1,30}")

# Site measurement: measure.js, this site's own module, posts a page view
# and every App Store link click to the shared PostHog project. Every page
# loads it but the privacy policy, which is never measured. Each App Store
# link names its place in data-placement: the page's kind, then the slot.
MEASURE_SCRIPT = "measure.js"
NOT_MEASURED = {"privacy-policy.html"}

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

# The hero's back plane is the app's year grid (YearGridView.swift): one band
# per habit, a column per week (oldest on the left) and a row per day, Monday
# at the top. The marks are the app's day states: b before the habit existed,
# 0 scheduled and missed, 1 to 4 done at 0.3, 0.5, 0.75 and full strength,
# t today (done, with the app's stroke), f the future. The three habits are
# the partner's from the Partners screenshot: Journaling ends on an 11 day
# streak, Evening Run on a 20 day streak, and Morning Run on the long one.
# Narrow screens show the last two bands.
FIELD_WEEKS = 20
FIELD_TODAY = FIELD_WEEKS * 7 - 4  # the Thursday of the last week
FIELD_HABITS = (
    # (first week of the habit, current streak in days, share of other days done, seed)
    (7, 11, 0.45, 3),
    (2, 20, 0.55, 11),
    (0, 64, 0.7, 29),
)
FIELD_CLASS = {"b": "b", "t": "t", "f": "f", "0": "l0", "1": "l1", "2": "l2", "3": "l3", "4": "l4"}


def year_grid(first_week: int, streak: int, rate: float, seed: int) -> str:
    """One habit's days as marks, in the app's order (week by week, Monday
    first). The scatter before the streak comes from a fixed seed, so the
    page renders the same bytes every time."""
    state, marks = seed, []
    for day in range(FIELD_WEEKS * 7):
        state = (state * 1103515245 + 12345) % 2147483648
        draw = state / 2147483648
        if day > FIELD_TODAY:
            marks.append("f")
        elif day == FIELD_TODAY:
            marks.append("t")
        elif day < first_week * 7:
            marks.append("b")
        elif day > FIELD_TODAY - streak:
            marks.append("4")
        elif day == FIELD_TODAY - streak or draw >= rate:
            marks.append("0")
        else:
            marks.append("4" if draw < rate * 0.6 else "3" if draw < rate * 0.8 else "2" if draw < rate * 0.92 else "1")
    return "".join(marks)


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


# ---- App Store links ---------------------------------------------------------

def page_ct(page: dict | None) -> str:
    """The page's campaign token, from its own entry in pages.json."""
    return (LANDING if page is None else page)["ct"]


def campaign_tokens() -> dict[str, str]:
    """Every page's campaign token by output file, after checking the whole
    campaign config: a provider token of digits or none at all, and one well
    formed ct per page that no other page uses."""
    pt = CAMPAIGN.get("pt")
    if not isinstance(pt, str) or (pt and not PROVIDER_TOKEN.fullmatch(pt)):
        raise ValueError(f"site.app_store_campaign.pt must be empty or digits, got {pt!r}")
    tokens = {page_file(p): (LANDING if p is None else p).get("ct") for p in [None, *PAGES, *POLICIES]}
    tokens[INVITE_FILE] = INVITE.get("ct")
    for rel, ct in tokens.items():
        if not isinstance(ct, str) or not CAMPAIGN_TOKEN.fullmatch(ct):
            raise ValueError(f"{rel}: ct must be 1 to 30 lowercase letters, digits or hyphens, got {ct!r}")
    repeated = sorted({ct for ct in tokens.values() if list(tokens.values()).count(ct) > 1})
    if repeated:
        raise ValueError(f"campaign tokens used by more than one page: {repeated}")
    return tokens


def store_url(ct: str, listing: str | None = None) -> str:
    """An App Store link: the listing URL (the site's, unless another is
    given), with the campaign parameters once a provider token is set."""
    listing = SITE["app_store_url"] if listing is None else listing
    if not CAMPAIGN["pt"]:
        return listing
    return f"{listing}?pt={CAMPAIGN['pt']}&ct={ct}&mt=8"


# ---- Shared fragments --------------------------------------------------------

def measure_version() -> str:
    """First 12 hex digits of measure.js's SHA-256, its version in every tag."""
    return hashlib.sha256((ROOT / MEASURE_SCRIPT).read_bytes()).hexdigest()[:12]


def placement_kind(page: dict | None) -> str:
    """The first half of every placement on a page: home, guide, or the
    policy page's first word (support, privacy, terms)."""
    if page is None:
        return "home"
    if is_policy(page):
        return page["file"].split("-")[0].removesuffix(".html")
    return "guide"


def placement(page: dict | None, slot: str) -> str:
    """An App Store link's data-placement: the page's kind, then the link's
    slot on the page (nav, hero, head, cta, footer)."""
    return f"{placement_kind(page)}_{slot}"


def store_button(page: dict | None, slot: str) -> str:
    return (f'<a class="store" href="{esc(store_url(page_ct(page)))}" data-placement="{esc(placement(page, slot))}">'
            f'{esc(STORE_BUTTON_TEXT)}</a>')


def store_note() -> str:
    return f'<p class="store-note">{esc(STORE_NOTE)}</p>'


def actions(page: dict | None, slot: str) -> str:
    """The landing's two actions: the store button and the share button."""
    return (
        '<div class="actions">\n'
        f"{store_button(page, slot)}\n"
        f'<button type="button" class="share" data-share="{esc(SHARE_TEXT)}" hidden>{esc(SHARE_BUTTON_TEXT)}</button>\n'
        "</div>"
    )


def shot(spec: dict, sizes: str, eager: bool, cutout: bool = False) -> str:
    """A screenshot from /assets/shots at 600 and 900 pixels wide. A cutout
    is a second, decorative copy of a shot already on the page: the same src,
    srcset and sizes, so it resolves to the file already loaded."""
    src = f"{BASE}/assets/shots/{spec['stem']}"
    load = "" if cutout else ' fetchpriority="high"' if eager else ' loading="lazy"'
    alt = "" if cutout else spec["alt"]
    return (
        f'<img src="{esc(src)}-600.webp" srcset="{esc(src)}-600.webp 600w, {esc(src)}-900.webp 900w" '
        f'sizes="{esc(sizes)}" width="{int(spec["width"])}" height="{int(spec["height"])}" '
        f'alt="{esc(alt)}"{load} decoding="async">'
    )


def field() -> str:
    """The hero's back plane: the app's year grid, a band per habit."""
    bands = "".join(
        '<div class="habit">' + "".join(f'<i class="{FIELD_CLASS[m]}"></i>' for m in year_grid(*h)) + "</div>"
        for h in FIELD_HABITS
    )
    return f'<div class="field" aria-hidden="true">{bands}</div>'


def rows(items: list, tag: str = "ul", cls: str = "rows") -> str:
    lis = "\n".join(f"<li><h3>{esc(title)}</h3>\n<p>{rich(body)}</p></li>" for title, body in items)
    return f'<{tag} class="{cls}">\n{lis}\n</{tag}>'


def cta_section(page: dict | None) -> str:
    return (
        '<section class="cta">\n'
        f"<h2>{esc(CTA_HEADING)}</h2>\n"
        f"<p>{esc(CTA_TEXT)}</p>\n"
        f"{store_button(page, 'cta')}\n"
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

# The phone shot widths, matching --phone-shot in site.css: 66% of the
# screen on a phone, up to 348px from a laptop up.
HERO_SIZES = "(max-width: 47.99em) min(66vw, 348px), 348px"


def piece(spec: dict) -> str:
    """One piece of an app screen, cut to its card from a 4.6.0 capture: a
    single file 840 pixels wide, shown at half that or less."""
    cls = "piece " + spec["class"] if spec.get("class") else "piece"
    return (
        f'<img class="{esc(cls)}" src="{esc(BASE)}/assets/shots/{esc(spec["stem"])}-840.webp" '
        f'width="840" height="{int(spec["height"])}" alt="{esc(spec["alt"])}" loading="lazy" decoding="async">'
    )


def piece_rows(items: list, pieces: list, tag: str, cls: str) -> str:
    """Rows that each show their own piece of the app beside the text."""
    if len(items) != len(pieces):
        raise ValueError(f"{cls}: {len(items)} rows but {len(pieces)} pieces")
    lis = "\n".join(
        f'<li><div class="copy"><h3>{esc(title)}</h3>\n<p>{rich(body)}</p></div>\n{piece(spec)}</li>'
        for (title, body), spec in zip(items, pieces)
    )
    return f'<{tag} class="{cls}">\n{lis}\n</{tag}>'


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
    shown = len(features["pieces"])
    parts = [
        '<section class="hero">\n'
        '<div class="hero-copy">\n'
        f"<h1>{esc(LANDING['headline'])}</h1>\n"
        f'<p class="lede">{esc(LANDING["lede"])}</p>\n'
        f"{actions(None, 'hero')}\n"
        f'<p class="store-note">{esc(LANDING["store_note"])}</p>\n'
        "</div>\n"
        # The Partners screen upright, standing on the hero's hairline over
        # the year grid, with the partner's reaction lifted off the glass
        # and enlarged, as the App Store slides lift a piece (see site.css).
        '<figure class="hero-shot">\n'
        '<div class="scene">\n'
        f"{field()}\n"
        '<div class="device phone"><div class="screen">'
        f"{shot(hero, HERO_SIZES, eager=True)}"
        '<div class="lift" aria-hidden="true">'
        f"{shot(hero, HERO_SIZES, eager=True, cutout=True)}"
        "</div>"
        "</div></div>\n"
        "</div>\n"
        f'<figcaption class="callout">{esc(LANDING["callout"])}</figcaption>\n'
        "</figure>\n"
        "</section>",
        rail("pairing",
             f"<h2>{esc(pairing['heading'])}</h2>\n"
             f'<p class="section-intro">{rich(pairing["intro"])}</p>',
             piece_rows(pairing["steps"], pairing["pieces"], "ol", "rows steps")),
        # The first features each show their piece of the app; the rest are
        # text, three across.
        '<section class="features">\n'
        f"<h2>{esc(features['heading'])}</h2>\n"
        f'{piece_rows(features["items"][:shown], features["pieces"], "ul", "shown")}\n'
        f'{rows(features["items"][shown:], "ul", "more")}\n'
        "</section>",
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
        f"{actions(None, 'cta')}\n"
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
        f"{store_button(page, 'head')}\n"
        f"{store_note()}\n"
        "</header>\n"
        f'<div class="article-body">\n{blocks}\n</div>\n'
        '<section class="related">\n<h2>More guides</h2>\n'
        f"{guides_list(others)}\n"
        "</section>\n"
        f"{cta_section(page)}\n"
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
        # The app as it is sold: a free download, with Premium as an add-on
        # offer at its one-time price. The url is the listing itself, never a
        # campaign link. No rating: the site states none it cannot show.
        graph.append({
            "@type": "SoftwareApplication",
            "name": SITE["name"],
            "description": LANDING["app_description"],
            "operatingSystem": "iOS, iPadOS",
            "applicationCategory": "HealthApplication",
            "url": SITE["app_store_url"],
            "image": f"{BASE}/{APP_ICON}",
            "screenshot": f"{BASE}/assets/shots/{LANDING['hero_shot']['stem']}-900.webp",
            "publisher": {"@type": "Organization", "name": SITE["publisher"], "url": SITE["brand_url"]},
            "offers": {
                "@type": "Offer", "price": "0", "priceCurrency": "USD",
                "addOn": {"@type": "Offer", "name": FACTS["tier"], "description": LANDING["premium_description"],
                          "price": FACTS["price"].lstrip("$"), "priceCurrency": "USD"},
            },
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


def fill(values: dict[str, str], template: str = TEMPLATE) -> str:
    """Single pass substitution, so content can never be re-read as a placeholder."""
    missing = set(_PLACEHOLDER.findall(template)) - set(values)
    if missing:
        raise KeyError(f"template placeholders without a value: {sorted(missing)}")
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


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
        "app_store_url": esc(store_url(page_ct(page))),
        "app_store_id": esc(SITE["app_store_id"]),
        "placement": esc(placement_kind(page)),
        "measure": "" if page_file(page) in NOT_MEASURED else
                   f'\n<script type="module" async src="{esc(BASE)}/{MEASURE_SCRIPT}?v={measure_version()}"></script>',
        "contact_email": esc(SITE["contact_email"]),
        "brand_url": esc(SITE["brand_url"]),
        "brand_footer": esc(SITE["brand_footer"]),
        "year": YEAR,
    })


def render_invite() -> str:
    """The invite page: the hand written scripts/invite.html with its App
    Store links filled in. Its code parsing and deep link are its own script,
    which the generator never touches."""
    source = (SCRIPTS / INVITE["source"]).read_text(encoding="utf-8")
    return fill({"app_store_url": esc(store_url(INVITE["ct"], INVITE["app_store_url"])),
                 "measure_version": measure_version()}, source)


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
    campaign_tokens()  # a malformed campaign config stops the build here
    files = {page_file(p): render(p) for p in [None, *PAGES, *POLICIES]}
    files[INVITE_FILE] = render_invite()
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
