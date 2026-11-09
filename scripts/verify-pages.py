#!/usr/bin/env python3
"""Read-only checks over the generated HabitFlame site. Prints every failure
and exits 1 if there is any.

  python3 scripts/verify-pages.py

Checks: committed output equals a fresh render, deployment facts, numbers and
Premium claims agree with the facts in pages.json, banned and negated phrases,
the competitor rule, links (resolved the way Vercel serves this site: clean
URLs, no trailing slash), App Store links and their campaign tokens on every
page, the invite page included, metadata, structured data references, word counts,
prose hygiene, the sitemap, the policy pages, stale output, vercel.json, the
app site association file and published assets.
"""
import codecs
import colorsys
import datetime
import hashlib
import html as htmlmod
import json
import os
import pathlib
import re
import subprocess
import sys
import types
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEN_PATH = ROOT / "scripts" / "build-pages.py"

# Execute the generator's source directly rather than importing it: an import
# goes through the bytecode cache, keyed by mtime at one second resolution, so
# an edit made within a second of the last run would verify stale code.
gen = types.ModuleType("gen")
gen.__file__ = str(GEN_PATH)
exec(compile(GEN_PATH.read_text(encoding="utf-8"), gen.__file__, "exec"), gen.__dict__)

SITE, FACTS, LANDING, PAGES, BASE = gen.SITE, gen.FACTS, gen.LANDING, gen.PAGES, gen.BASE
POLICIES = gen.POLICIES

# Deployment facts, pinned here so a typo in pages.json cannot move the site,
# the store link or the product name without this file changing too. The
# custom domain is the one canonical HabitFlame site; the old GitHub Pages
# copy points its canonical links here.
PINNED_BASE_URL = "https://habitflame.vishutdhar.com"
# Rule for every public surface: this address, pinned here so a typo in
# pages.json cannot move support and deletion requests.
PINNED_CONTACT = "support@freedom-terminal.com"
PINNED_ROBOTS_META = "index, follow, max-image-preview:large, max-snippet:-1"
# The share card and the one font file, both under /assets (published files
# there never change in place, so a new version gets a new name).
PINNED_OG_IMAGE = "assets/og/site-2026-10-16-app.png"
PINNED_FONT = "assets/fonts/bricolage-grotesque-opsz-wght-latin.woff2"
# The page wears the app's palette (landing pass 2, 2026-10-16). Sources in
# the app repository: the app opens dark (UserSettings.swift appearanceModeRaw
# "dark", MainTabView.swift colorScheme), so the ground is iOS systemBackground
# in dark; surface is secondarySystemBackground and systemGray6 in dark, the
# grouped cards and the empty year grid cell; flame is Color.themeOrange in
# ColorHelpers.swift, the tint of the whole tab view. Every chromatic colour
# in site.css sits on flame's hue, within APP_HUE_TOLERANCE degrees.
PINNED_PALETTE = {"ground": "#000000", "surface": "#1C1C1E", "flame": "#E67E00"}
APP_HUE_TOLERANCE = 1.0
TITLE_LIMIT = 63
# App facts, pinned here as well as in pages.json so a change to both at once
# still has to touch this file. Sources in the app repository:
# Constants.swift freeHabitLimit and freeNudgeMonthlyQuota,
# PomodoroTimerService.swift durations, AchievementType.swift (16 badges),
# and the App Store Connect product "Premium" at $9.99.
PINNED_FACTS = {"price": "$9.99", "tier": "Premium", "free_habit_limit": "5", "free_nudges_per_month": "3",
                "pomodoro_work_minutes": "25", "pomodoro_short_break_minutes": "5",
                "pomodoro_long_break_minutes": "15", "achievement_badges": "16", "multi_checkin_range": ["2", "4"],
                # Constants.swift streakMilestones.
                "streak_milestones": ["7", "14", "21", "30", "50", "75", "100", "150", "200", "365", "500", "1000"]}
PINNED_APP_STORE_URL = "https://apps.apple.com/us/app/habit-flame-streak-tracker/id6756961710"
# The invite page links the short form of the same listing.
PINNED_INVITE_STORE_URL = "https://apps.apple.com/app/id6756961710"
# The App Store id of HabitFlame, which the Smart App Banner names.
PINNED_APP_ID = "6756961710"
# Every App Store link names its place on the page in data-placement, which
# measure.js sends with each click. Funnel queries filter on these names, so
# they are pinned per page, in page order; every guide has the same four.
PINNED_PLACEMENTS = {
    "index.html": ["home_nav", "home_hero", "home_cta", "home_footer"],
    "support.html": ["support_nav", "support_footer"],
    "privacy-policy.html": ["privacy_nav", "privacy_footer"],
    "terms-of-service.html": ["terms_nav", "terms_footer"],
    "invite.html": ["invite_step", "invite_fallback", "invite_footer"],
}
GUIDE_PLACEMENTS = ["guide_nav", "guide_head", "guide_cta", "guide_footer"]
# The landing's structured data, shown in search results with no page around
# it to qualify it, so every limit is in the sentence itself: a completion
# reaches the partner only when made in the app for today (a widget
# completion or a backfilled day sends no alert: HabitCompletionEffects and
# WidgetIntents), and only with Premium. Pinned here so a change to
# pages.json alone cannot move it.
PINNED_APP_DESCRIPTION = (
    "HabitFlame is a habit tracker for iPhone and iPad. Track habits your way, keep streaks alive and pair with an "
    "accountability partner who can nudge you when you go quiet. With Premium, each shared habit you complete in the "
    "app for today reaches your partner the moment you do it.")
PINNED_PREMIUM_DESCRIPTION = (
    "A one-time in-app purchase, not a subscription, that removes the 5 habit limit and adds habit stacking, smart "
    "insights, real-time partner updates and unlimited partner nudges.")
# Campaign tokens, one per page. App Analytics reports App Store page views
# and downloads by these exact strings, so renaming one splits a page's
# history in two: they are pinned here as well as set in pages.json. Apple
# allows up to 30 characters.
PINNED_CT = {
    "index.html": "site-home",
    "accountability-partner-habit-tracker.html": "site-guide-partner",
    "streak-tracker-app.html": "site-guide-streak",
    "pomodoro-habit-app.html": "site-guide-pomodoro",
    "habit-app-for-couples.html": "site-guide-couples",
    "daily-habit-tracker-with-reminders.html": "site-guide-reminders",
    "habitflame-vs-habitshare.html": "site-guide-vs-habitshare",
    "habit-tracker-with-friends.html": "site-guide-friends",
    "new-year-habits-with-a-friend.html": "site-guide-new-year",
    "support.html": "site-support",
    "privacy-policy.html": "site-privacy",
    "terms-of-service.html": "site-terms",
    "invite.html": "site-invite",
}
PINNED_NAME = "HabitFlame"
BRAND_URL = "https://freedom-terminal.com/"
BRAND_TEXT = "A Freedom Terminal product"
# Numbers allowed in copy that are not a fact value: the footer year and the
# small counts the copy uses in prose (2 sessions, 3 times a week, a set of 4).
EXTRA_ALLOWED_NUMBERS = {"2026", "2", "3", "4"}
GUIDE_TABLE_HEAD = ["", "Free", "Premium"]

failures: list[str] = []
notes: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


# ---- A small DOM, enough to pull visible text out of our own markup ---------

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
INLINE = {"a", "b", "strong", "em", "i", "span", "small", "abbr", "code"}
HIDDEN = {"script", "style", "head", "title", "template", "noscript"}


class Node:
    def __init__(self, tag: str, attrs: dict, parent: "Node | None"):
        self.tag, self.attrs, self.parent, self.children = tag, attrs, parent, []

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.walk()

    def find_all(self, pred):
        return [n for n in self.walk() if pred(n)]

    def ancestors(self):
        n = self.parent
        while n is not None:
            yield n
            n = n.parent

    def text(self, skip=lambda n: False) -> str:
        """Visible text; block boundaries become spaces, inline tags do not."""
        out: list[str] = []

        def rec(node: Node) -> None:
            for c in node.children:
                if isinstance(c, str):
                    out.append(c)
                elif c.tag in HIDDEN or skip(c):
                    continue
                else:
                    sep = "" if c.tag in INLINE else " "
                    out.append(sep)
                    rec(c)
                    out.append(sep)

        rec(self)
        return re.sub(r"\s+", " ", "".join(out)).strip()


class Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is None:
            failures.append(f"unmatched </{tag}>")
            return
        self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(text: str) -> Node:
    b = Builder()
    b.feed(text)
    b.close()
    return b.root


def by_tag(root: Node, tag: str) -> list[Node]:
    return root.find_all(lambda n: n.tag == tag)


def first(root: Node, pred) -> "Node | None":
    found = root.find_all(pred)
    return found[0] if found else None


def meta(root: Node, key: str, value: str) -> "str | None":
    n = first(root, lambda n: n.tag == "meta" and n.attrs.get(key) == value)
    return None if n is None else n.attrs.get("content")


def whole(phrase: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.I)


def whole_or_plural(phrase: str) -> re.Pattern:
    """The phrase as a whole word or phrase, also with a trailing s or es."""
    return re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?:es|s)?(?!\w)", re.I)


# A sentence ends at . ! or ? followed by an optional closing quote or bracket
# and whitespace, so a closing quotation mark never glues two sentences.
# Text is normalised before any phrase check: NFKC, curly quotes and
# apostrophes to straight ones, hyphen variants to "-".
NORM_MAP = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
                          "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
                          "\u2010": "-", "\u2011": "-", "\u00ad": "-", "\u2212": "-"})


def norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(NORM_MAP)


# A sentence ends at . ! or ? plus any run of closing quotes or brackets
# (straight or curly, single or double), then whitespace.
SENTENCE_END = re.compile(r"[.!?][\"'\u2018\u2019\u201c\u201d)\]]*\s+")


def sentences(text: str) -> list[str]:
    text = norm(text)
    out, pos = [], 0
    for m in SENTENCE_END.finditer(text):
        out.append(text[pos:m.end()].strip())
        pos = m.end()
    out.append(text[pos:].strip())
    return [s for s in out if s]


def words_with_spans(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0).lower(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z0-9$']+(?:\.[0-9]+)?", text)]


def table_head(table: Node) -> list[str]:
    thead = first(table, lambda n: n.tag == "thead")
    return [th.text() for th in by_tag(thead, "th")] if thead else []


def row_cells(tr: Node) -> list[Node]:
    return [c for c in tr.children if isinstance(c, Node) and c.tag in {"th", "td"}]


# ---- 4. Deployment facts ----------------------------------------------------

check(SITE["base_url"] == PINNED_BASE_URL, f"site.base_url is {SITE['base_url']!r}, pinned {PINNED_BASE_URL!r}")
check(BASE == PINNED_BASE_URL, f"generator base is {BASE!r}, pinned {PINNED_BASE_URL!r}")
check(SITE["app_store_url"] == PINNED_APP_STORE_URL, f"site.app_store_url is {SITE['app_store_url']!r}, pinned {PINNED_APP_STORE_URL!r}")
check(SITE["name"] == PINNED_NAME, f"site.name is {SITE['name']!r}, pinned {PINNED_NAME!r}")
check(SITE["contact_email"] == PINNED_CONTACT, f"site.contact_email is {SITE['contact_email']!r}, pinned {PINNED_CONTACT!r}")
for key, value in PINNED_FACTS.items():
    check(FACTS.get(key) == value, f"facts.{key} is {FACTS.get(key)!r}, pinned {value!r} from the app")

# The provider token is the account's number from App Store Connect, so it is
# not pinned, only its form: digits, or empty until the owner has read it.
# Empty means every App Store link is the bare listing URL; set means every
# one carries pt, the page's pinned ct and mt=8, the form Apple's campaign
# link generator writes.
PROVIDER_TOKEN = (SITE.get("app_store_campaign") or {}).get("pt")
check(isinstance(PROVIDER_TOKEN, str) and re.fullmatch(r"[0-9]{0,20}", PROVIDER_TOKEN) is not None,
      f"site.app_store_campaign.pt is {PROVIDER_TOKEN!r}, want digits or an empty string")
for _rel, _ct in PINNED_CT.items():
    check(re.fullmatch(r"[a-z0-9-]{1,30}", _ct) is not None, f"pinned ct {_ct!r} for {_rel} is not 1 to 30 lowercase letters, digits or hyphens")
check(len(set(PINNED_CT.values())) == len(PINNED_CT), "two pages share a pinned ct")
_config_ct = {gen.page_file(p): (LANDING if p is None else p).get("ct") for p in [None, *PAGES, *POLICIES]}
_config_ct["invite.html"] = (gen.CONFIG.get("invite") or {}).get("ct")
check(_config_ct == PINNED_CT, f"pages.json campaign tokens differ from the pinned ones: "
      f"{sorted(set(_config_ct.items()) ^ set(PINNED_CT.items()))}")
check((gen.CONFIG.get("invite") or {}).get("app_store_url") == PINNED_INVITE_STORE_URL,
      f"invite.app_store_url is not the pinned {PINNED_INVITE_STORE_URL}")


def expected_store_link(rel: str) -> str:
    """The one App Store href a page may carry."""
    listing = PINNED_INVITE_STORE_URL if rel == "invite.html" else PINNED_APP_STORE_URL
    if not PROVIDER_TOKEN:
        return listing
    return f"{listing}?pt={PROVIDER_TOKEN}&ct={PINNED_CT.get(rel, '')}&mt=8"

# ---- 9. Minimum lists pages.json may extend but never shrink ----------------

REQUIRED_BANNED = {
    "google play", "web app", "browser version", "mac app", "apple watch", "watch app",
    "custom app icon", "duo quest", "weekly quest", "quest", "free trial",
    "thousands of", "millions", "million", "guarantee", "guaranteed", "proven to", "clinically", "scientifically",
    "#1", "number one", "best habit app", "world's best",
    "ai-powered", "ai powered", "artificial intelligence", "machine learning",
    "unlimited free", "free forever", "lifetime free",
    "shared streak", "joint streak", "couple streak", "team streak",
    "chat", "messaging", "video call", "leaderboard", "challenge",
    "no analytics", "no tracking", "no servers", "never leaves your device", "not accessible by",
    "receives only a weekly count",
}
REQUIRED_PREMIUM_ONLY = {
    "unlimited habits", "habit stacking", "smart insights", "real-time partner updates",
    "instant partner notifications", "unlimited partner nudges", "unlimited nudges", "stack habits", "stacking",
}
REQUIRED_NEGATED_ONLY = {"subscription", "android", "web version", "trial"}
for key, required in [("banned_phrases", REQUIRED_BANNED), ("premium_only", REQUIRED_PREMIUM_ONLY), ("negated_only", REQUIRED_NEGATED_ONLY)]:
    missing = required - {x.lower() for x in FACTS.get(key, [])}
    check(not missing, f"facts.{key} dropped required entries {sorted(missing)}")

# ---- 3. The one date --------------------------------------------------------

def iso_date(value) -> bool:
    """Exactly YYYY-MM-DD and a real date. fromisoformat alone also accepts
    forms such as 20260924 and 2026-W39-4."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.date.fromisoformat(value)
        return True
    except ValueError:
        return False


POLICY_NAMES = ["support.html", "privacy-policy.html", "terms-of-service.html"]
DATES = {"landing": LANDING.get("lastmod")}
DATES.update({p["slug"]: p.get("lastmod") for p in PAGES})
check([p.get("file") for p in POLICIES] == POLICY_NAMES, f"policies are {[p.get('file') for p in POLICIES]}, want {POLICY_NAMES}")
DATES.update({p.get("file"): p.get("lastmod") for p in POLICIES})
for retired in ("lastmod", "policy_lastmod", "css_version", "verification_file"):
    check(retired not in SITE, f"site.{retired} is retired; dates live on each page and the stylesheet version is a hash")
TODAY = datetime.date.today().isoformat()
for key, value in DATES.items():
    check(iso_date(value), f"lastmod for {key} is {value!r}, not a YYYY-MM-DD date")
    check(not iso_date(value) or value <= TODAY, f"lastmod for {key} is {value}, a future date (today is {TODAY})")

# ---- 5. Facts and the number allowlist --------------------------------------

allowed_numbers = set(FACTS["allowed_numbers"])
fact_numbers = {FACTS["price"].lstrip("$"), FACTS["free_habit_limit"], FACTS["free_nudges_per_month"],
                FACTS["pomodoro_work_minutes"], FACTS["pomodoro_short_break_minutes"],
                FACTS["pomodoro_long_break_minutes"], FACTS["achievement_badges"],
                *FACTS["streak_milestones"], *FACTS["multi_checkin_range"]}
for n in sorted(fact_numbers - allowed_numbers, key=float):
    failures.append(f"facts value {n} is missing from facts.allowed_numbers")
for n in sorted(allowed_numbers - fact_numbers - EXTRA_ALLOWED_NUMBERS, key=float):
    failures.append(f"facts.allowed_numbers has {n}, which is neither a fact value nor a listed extra")
check(re.fullmatch(r"\$\d+\.\d\d", FACTS["price"]) is not None, f"facts.price {FACTS['price']!r} is not a dollar amount")

# ---- Rendering ---------------------------------------------------------------

try:
    FRESH = gen.outputs()
except Exception as e:  # a malformed or missing lastmod raises here; report and stop
    print(f"FAIL   generator raised {type(e).__name__}: {e}")
    for f in failures:
        print(f"FAIL   {f}")
    sys.exit(1)

# a. Committed output is byte-identical to a fresh render.
for rel, text in FRESH.items():
    path = ROOT / rel
    if not path.exists():
        failures.append(f"{rel}: missing, run scripts/build-pages.py")
        continue
    check(path.read_bytes() == text.encode("utf-8"), f"{rel}: differs from a fresh render, run scripts/build-pages.py")

# 8. Stale output. Every HTML file at the root is generated; the invite page
#    is rendered from its hand written source, scripts/invite.html. A
#    directory index would be served at /<dir>/ and redirected by
#    trailingSlash, so none may exist.
for f in sorted(ROOT.glob("*.html")):
    if f.name not in FRESH:
        failures.append(f"{f.name}: an HTML file the generator does not write (stale output?)")
# Directories kept out of the deployment by .vercelignore (the generator's
# sources, whose template and fragments would otherwise be served as pages).
NOT_DEPLOYED = {".git", ".vercel", "node_modules", "scripts", "docs"}
try:
    vercelignore = (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
except OSError:
    vercelignore = []
ignore_rules = [l.strip() for l in vercelignore if l.strip() and not l.strip().startswith("#")]
# The generator's sources and the design notes in docs/ are not part of the site.
check(ignore_rules == ["/scripts/", "/docs/"], f".vercelignore: rules are {ignore_rules}, want exactly ['/scripts/', '/docs/'] so nothing the site needs is left out")
# Only what git would deploy counts: a file git ignores (a local tool's
# folder, an editor's scratch) never reaches Vercel, which deploys from git.
# A copy of the repository without .git (the gate's own tests) has nothing
# ignored, so there every file outside a dot folder counts.
def deployable_files() -> list[pathlib.Path]:
    """Every file git would deploy: tracked or untracked and not ignored.
    Git answers only when the site root is itself the repository's top
    level; a copy below another repository (the gate tests' temp folder)
    would inherit that repository's ignore rules, so it takes the fallback."""
    try:
        top = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"],
            capture_output=True, check=True,
        ).stdout
        # Filesystem identity, not spelling: this Mac treats two casings as one folder.
        if not os.path.samefile(os.fsdecode(top.strip()), ROOT):
            raise subprocess.CalledProcessError(1, "git rev-parse")
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return sorted(f for f in ROOT.rglob("*") if f.is_file() and not any(part.startswith(".") for part in f.relative_to(ROOT).parts))
    # Raw file name bytes: a name that is not UTF-8 is still a file.
    return sorted(ROOT / os.fsdecode(rel) for rel in out.split(b"\0") if rel)

for f in deployable_files():
    if f.suffix != ".html":
        continue
    rel_f = f.relative_to(ROOT)
    if rel_f.parts[0] in NOT_DEPLOYED or len(rel_f.parts) == 1:
        continue
    failures.append(f"{rel_f}: an HTML file below the root would be served as a page; pages are flat <name>.html files")

HTML_PAGES = [(p, gen.page_file(p)) for p in [None, *PAGES, *POLICIES]]


def page_text_units(root: Node) -> list[str]:
    """Blocks of visible text outside tables, used to judge Premium claims."""
    units = []
    for n in root.find_all(lambda n: n.tag in {"p", "li", "dt", "dd", "h1", "h2", "h3"}):
        if any(a.tag in HIDDEN or a.tag == "table" for a in n.ancestors()):
            continue
        units.append(n.text())
    return units


def visible_units(root: Node) -> list[tuple[str, Node, "Node | None"]]:
    """All visible text exactly once, as (text, owner, table): owner is the
    nearest block element; inside a table each cell is its own unit."""
    units: list = []

    def rec(node: Node, table) -> None:
        buf: list[str] = []

        def flush() -> None:
            t = re.sub(r"\s+", " ", "".join(buf)).strip()
            if t:
                units.append((t, node, table))
            buf.clear()

        for c in node.children:
            if isinstance(c, str):
                buf.append(c)
            elif c.tag in HIDDEN:
                continue
            elif c.tag in INLINE:
                buf.append(c.text())
            else:
                flush()
                rec(c, c if c.tag == "table" else table)
        flush()

    rec(root, None)
    return units


premium_word = whole("Premium")
free_word = whole("free")
TIMER_MINUTES = {FACTS["pomodoro_work_minutes"], FACTS["pomodoro_short_break_minutes"], FACTS["pomodoro_long_break_minutes"]}
PERIOD_WORDS = {"month", "monthly", "year", "yearly", "annual", "week"}
TOKEN = re.compile(r"\$?\d+(?:\.\d+)?|[A-Za-z']+")
premium_free_forms = {f.lower(): 0 for f in FACTS.get("premium_free_forms", [])}


MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"}


def bind_numbers(text: str, ctx: "dict | None", dated_ok: bool = False) -> list[tuple[str, "str | None"]]:
    """Each number in text with the problem its context finds, or None.
    ctx is {"label": row label, "col": column head} for a table cell.
    dated_ok allows a year right after a month name (the comparison page)."""
    toks = list(TOKEN.finditer(text))
    ranges = [(m.group(1), f"range '{m.group(0)}' is not the multi check-in range {' to '.join(FACTS['multi_checkin_range'])}")
              for m in re.finditer(r"(?<![\w.])(\d+) to (\d+)(?![\w.])", text)
              if [m.group(1), m.group(2)] != FACTS["multi_checkin_range"]]
    free_ctx = bool(free_word.search(text)) or bool(ctx and ctx["col"] == "Free")
    nudge_ctx = bool(re.search(r"\bnudges?\b", text, re.I)) or bool(ctx and re.search(r"nudge", ctx["label"], re.I))
    habit_cell = bool(ctx and re.fullmatch(r"habits?", ctx["label"], re.I))
    range_spans = [(m.start(), m.end()) for m in re.finditer(r"(?<![\w.])(\d+) to (\d+)(?![\w.])", text)
                   if [m.group(1), m.group(2)] == FACTS["multi_checkin_range"]]
    milestone_ctx = bool(re.search(r"\b(milestones?|days)\b", text, re.I))
    out = []
    for i, m in enumerate(toks):
        s = m.group(0)
        if not (s[0].isdigit() or s[0] == "$"):
            continue
        num = s.lstrip("$")
        nxt = [x.group(0).lower() for x in toks[i + 1:i + 5]]
        prv = [x.group(0).lower() for x in toks[max(0, i - 4):i]]
        if s.startswith("$"):
            if s != FACTS["price"]:
                out.append((num, f"amount {s} is not facts.price {FACTS['price']}"))
            elif any(w in PERIOD_WORDS for w in nxt[:4]):
                out.append((num, f"amount {s} is followed by a billing period"))
            elif any(w in PERIOD_WORDS for w in prv):
                out.append((num, f"amount {s} is preceded by a billing period"))
            else:
                out.append((num, None))
        elif any(w in ("minute", "minutes") for w in nxt[:2]):
            k = next(j for j, w in enumerate(nxt[:2]) if w in ("minute", "minutes"))
            after = nxt[k + 1:k + 3]
            if after[:1] == ["work"]:
                want = {FACTS["pomodoro_work_minutes"]}
            elif after[:1] == ["short"] and after[1:2] and after[1].startswith("break"):
                want = {FACTS["pomodoro_short_break_minutes"]}
            elif after[:1] == ["long"] and after[1:2] and after[1].startswith("break"):
                want = {FACTS["pomodoro_long_break_minutes"]}
            else:
                want = TIMER_MINUTES
            out.append((num, None if num in want else f"'{' '.join([num, 'minute', *after])}' is not {sorted(want, key=int)}"))
        elif any(w in ("achievement", "achievements", "badge", "badges") for w in nxt[:2]):
            out.append((num, None if num == FACTS["achievement_badges"] else f"'{num} badges' is not facts.achievement_badges {FACTS['achievement_badges']}"))
        elif (any(w in ("nudge", "nudges") for w in nxt[:2]) or any(w in ("nudge", "nudges") for w in prv[-2:])
              or (nudge_ctx and nxt[:2] == ["a", "month"])):
            k = next((j for j, w in enumerate(nxt[:2]) if w in ("nudge", "nudges")), -1)
            period = nxt[k + 1:k + 3]
            if num != FACTS["free_nudges_per_month"]:
                out.append((num, f"'{num}' nudges is not facts.free_nudges_per_month {FACTS['free_nudges_per_month']}"))
            elif len(period) == 2 and period[0] in ("a", "per", "each", "every") and period[1] != "month":
                out.append((num, f"'{num} nudges {' '.join(period)}': only 'a month' may follow the nudge count"))
            else:
                out.append((num, None))
        elif any(w in ("habit", "habits") for w in nxt[:2]) and (free_ctx or "limit" in nxt[:2]):
            out.append((num, None if num == FACTS["free_habit_limit"] else f"'{num} habits' about the free tier is not facts.free_habit_limit {FACTS['free_habit_limit']}"))
        elif habit_cell and free_ctx and text.strip() == s:
            out.append((num, None if num == FACTS["free_habit_limit"] else f"Habits under Free is {num}, not facts.free_habit_limit {FACTS['free_habit_limit']}"))
        elif num in FACTS["streak_milestones"] and milestone_ctx:
            out.append((num, None))
        elif num in FACTS["multi_checkin_range"] and any(a <= m.start() < b for a, b in range_spans):
            out.append((num, None))
        elif num == "3" and nxt[:2] == ["or", "more"]:
            out.append((num, None))
        elif num == "2026" and dated_ok and prv[-1:] and prv[-1] in MONTHS:
            out.append((num, None))
        else:
            out.append((num, f"number {num} is outside every allowed context (a bound fact, a milestone with 'milestone' or 'days', '2 to 4', '3 or more', a dated year on the comparison page)"))
    return ranges + out
premium_phrases = [(p, whole(p)) for p in FACTS["premium_only"]]
VIS_SUBJ = re.compile(r"\b(partner|partners|friend|friends|they|them|their|sister|someone|person|other)\b", re.I)
VIS_VERB = re.compile(r"\b(see|sees|seen|watch|watches|told|show|shows|shown|notice|notices|follow|appear|appears|reach|reaches)\b", re.I)
VIS_OBJ = re.compile(r"\b(completion|completions|complete|completed|streak|streaks|done today|widget|feed|progress|did|habit|habits)\b", re.I)
EVERY_COMPLETION = re.compile(r"\b(every|each)\b(?:\s+[\w']+){0,2}?\s+(habit you complete|habits you complete|completions?|win|wins)\b|\b(every|each)\s+(completion|win)\b", re.I)
RECEIVER = re.compile(r"\b(partner|partners|their phone|receives|they see|sees|gets)\b", re.I)
VIS_OK = re.compile(r"\bPremium\b|weekly count|nudge", re.I)
visibility_forms = {f.strip().lower(): 0 for f in FACTS.get("visibility_forms", [])}
banned = [(p, whole_or_plural(p)) for p in FACTS["banned_phrases"]]
negated = [(p, whole_or_plural(p)) for p in FACTS.get("negated_only", [])]
negated_forms = [(f, whole(f)) for f in FACTS.get("negated_forms", [])]
negated_forms_used = {f: 0 for f, _ in negated_forms}
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
DOLLAR = re.compile(r"\$\d+(?:\.\d+)?")
HABIT_COUNT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?) habits?(?!\w)", re.I)
NUDGE_COUNT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?) nudges?(?!\w)", re.I)
EMAIL = re.compile(r"(?:\"[^\"\r\n<>]+\"|[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+)@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def emails_in(text: str) -> set[str]:
    """Addresses in the raw source and in its entity-decoded form."""
    return set(EMAIL.findall(text)) | set(EMAIL.findall(htmlmod.unescape(text)))

word_counts: list[tuple[str, int]] = []

def page_kind(page) -> str:
    if page is None:
        return "landing"
    return "policy" if gen.is_policy(page) else "guide"


# Copy about the app, checked sentence by sentence, lives on the landing and
# the guides. The support page's answers get the phrase checks too; the
# privacy policy and terms are legal text with their own pins below.
for page, rel in HTML_PAGES:
    kind = page_kind(page)
    copy_checks = kind != "policy"
    phrase_checks = copy_checks or rel == "support.html"
    raw = FRESH[rel]
    root = parse(raw)
    body = first(root, lambda n: n.tag == "body")
    main = first(root, lambda n: n.tag == "main")
    footer = first(root, lambda n: n.tag == "footer")
    title_node = first(root, lambda n: n.tag == "title")
    title = title_node.text() if title_node else ""
    description = meta(root, "name", "description") or ""
    want_title = gen.page_title(page)
    want_desc = gen.page_description(page)
    url = gen.page_url(page)
    footer_copy = first(root, lambda n: "foot-copy" in n.classes)

    ld_nodes = root.find_all(lambda n: n.tag == "script" and n.attrs.get("type") == "application/ld+json")
    ld_raw = "".join(c for n in ld_nodes for c in n.children if isinstance(c, str))
    try:
        graph = json.loads(ld_raw)["@graph"]
    except (ValueError, KeyError, TypeError) as e:
        failures.append(f"{rel}: JSON-LD does not parse: {e}")
        graph = []

    # Every piece of text a reader or a crawler sees, as sentence sized units,
    # each marked with whether the competitor rule exempts it. On a page with
    # "competitor", a competitor phrase or number may appear only in a sentence
    # naming the competitor, in the row label or the competitor's own column of
    # a table whose head names it, or in the page's own title, description and
    # JSON-LD page name or description. The h1 is never exempt.
    competitor = page.get("competitor") if page else None
    comp_rx = whole(competitor) if competitor else None
    comp_phrases = {p.lower() for p in page.get("competitor_phrases", [])} if page else set()
    comp_numbers = set(page.get("competitor_numbers", [])) if page else set()

    def names_competitor(text: str) -> bool:
        return bool(comp_rx and comp_rx.search(text))

    units: list[tuple[str, bool, str]] = []  # (text, exempt, where)
    number_units: list[tuple[str, bool, str, "dict | None"]] = []
    for text, node, table in visible_units(body) if body else []:
        if table is not None and node.tag in {"th", "td"}:
            head = table_head(table)
            tr = node.parent
            col = row_cells(tr).index(node) if tr is not None and node in row_cells(tr) else -1
            in_body = any(a.tag == "tbody" for a in node.ancestors())
            exempt = bool(competitor) and in_body and competitor in head and (col == 0 or (0 <= col < len(head) and head[col] == competitor))
            label = f"table cell (column {head[col]!r})" if 0 <= col < len(head) else "table cell"
            parts = [(norm(text), exempt, label)]
            cell_ctx = {"label": row_cells(tr)[0].text() if tr is not None else "", "col": head[col] if 0 <= col < len(head) else ""}
        elif node.tag == "h1":
            parts = [(s, False, "h1") for s in sentences(text)]
            cell_ctx = None
        else:
            parts = [(s, names_competitor(s), node.tag) for s in sentences(text)]
            cell_ctx = None
        units += parts
        if node is not footer_copy:
            number_units += [(*u, cell_ctx) for u in parts]
    for text, where in [(title, "title"), (description, "meta description")]:
        units.append((norm(text), bool(competitor), where))
        number_units.append((norm(text), bool(competitor), where, None))
    for key, value in [("og:title", meta(root, "property", "og:title")), ("og:description", meta(root, "property", "og:description")),
                       ("twitter:title", meta(root, "name", "twitter:title")), ("twitter:description", meta(root, "name", "twitter:description"))]:
        if value:
            units.append((norm(value), bool(competitor) and value in (title, description), key))
    for n in root.walk():
        for attr in ("aria-label", "alt"):
            if n.attrs.get(attr):
                units += [(s, names_competitor(s), attr) for s in sentences(n.attrs[attr])]

    def ld_strings(obj):
        if isinstance(obj, dict):
            page_node = obj.get("@type") in ("WebPage", "ListItem")
            for k, v in obj.items():
                if isinstance(v, str):
                    if k in ("@type", "@id", "@context", "url", "item"):
                        continue
                    if page_node and k in ("name", "description"):
                        yield norm(v), bool(competitor), f"JSON-LD {obj.get('@type')} {k}"
                    else:
                        for s in sentences(v):
                            yield s, names_competitor(s), f"JSON-LD {k}"
                else:
                    yield from ld_strings(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from ld_strings(v)
    units += list(ld_strings(graph))

    # b. Every number is an allowed fact, and bound to the right fact by its
    #    context: minutes, badges, nudges, free habits and dollar amounts.
    #    Competitor numbers pass only where the competitor rule exempts them.
    for text, exempt, where, ctx in (number_units if copy_checks else []):
        for num in NUMBER.findall(text):
            if num in allowed_numbers or (num in comp_numbers and exempt):
                continue
            extra = " (a competitor number outside the places the competitor rule allows)" if num in comp_numbers else ""
            failures.append(f"{rel}: number {num} is not in facts.allowed_numbers{extra}, in {where}: {text!r}")
        for num, problem in bind_numbers(text, ctx, dated_ok=bool(competitor)):
            if problem and not (num in comp_numbers and exempt):
                failures.append(f"{rel}: {problem}, in {where}: {text!r}")
    if footer_copy is not None:
        check(footer_copy.text() == f"© {gen.YEAR} HabitFlame", f"{rel}: footer copyright line changed: {footer_copy.text()!r}")

    # c. Premium-only features are only ever named next to the word Premium.
    #    A sentence with the word "free" and a Premium-only feature fails
    #    unless it is, word for word, one of facts.premium_free_forms.
    def premium_free(sentence: str, where: str) -> None:
        sentence = norm(sentence)
        if free_word.search(sentence) and any(rx.search(sentence) for _, rx in premium_phrases):
            key = re.sub(r"\s+", " ", sentence).strip().lower()
            if key in premium_free_forms:
                premium_free_forms[key] += 1
            else:
                failures.append(f"{rel}: {where} has 'free' and a Premium-only feature and is not in facts.premium_free_forms: {sentence!r}")

    for unit in (page_text_units(root) + [title, description]) if phrase_checks else []:
        for sentence in sentences(unit):
            for phrase, rx in premium_phrases:
                if rx.search(sentence) and not premium_word.search(sentence):
                    kind = "free sentence" if free_word.search(sentence) else "sentence"
                    failures.append(f"{rel}: {kind} names Premium-only '{phrase}' without 'Premium': {sentence!r}")
            premium_free(sentence, "sentence")
    for table in by_tag(root, "table") if phrase_checks else []:
        head = table_head(table)
        comp_heads = [["", competitor, "HabitFlame"], ["", "HabitFlame", competitor]] if competitor else []
        for tr in by_tag(first(table, lambda n: n.tag == "tbody") or table, "tr"):
            for c in row_cells(tr):
                premium_free(c.text(), "table cell")
        if head == GUIDE_TABLE_HEAD:
            free_col = head.index("Free")
            for tr in by_tag(first(table, lambda n: n.tag == "tbody") or table, "tr"):
                cells = [c.text() for c in row_cells(tr)]
                if free_col < len(cells) and any(rx.search(cells[free_col]) for _, rx in premium_phrases):
                    failures.append(f"{rel}: Free column cell names a Premium-only feature: {cells[free_col]!r}")
                if any(rx.search(cells[0]) for _, rx in premium_phrases) or cells[0].lower() in {p.lower() for p in FACTS["premium_only"]}:
                    check(free_col < len(cells) and cells[free_col].lower() in {"no", "not included"},
                          f"{rel}: table row {cells[0]!r} marks a Premium-only feature as available under Free")
        elif head in comp_heads:
            for tr in by_tag(first(table, lambda n: n.tag == "tbody") or table, "tr"):
                row = " ".join(c.text() for c in row_cells(tr))
                if any(rx.search(row) for _, rx in premium_phrases) and not premium_word.search(row):
                    failures.append(f"{rel}: table row names a Premium-only feature without 'Premium': {row!r}")
        else:
            failures.append(f"{rel}: table head {head!r} is neither {GUIDE_TABLE_HEAD!r} nor a competitor head {comp_heads!r}")

    # d. Banned phrases (whole phrase, or with a trailing s or es), anywhere a
    #    reader or a crawler sees text. A negated-only phrase must sit inside
    #    one of the exact facts.negated_forms.
    for text, exempt, where in (units if phrase_checks else []):
        for phrase, rx in banned:
            if rx.search(text) and not (phrase.lower() in comp_phrases and exempt):
                failures.append(f"{rel}: banned phrase '{phrase}' in {where}: {text!r}")
        form_spans = []
        for form, frx in negated_forms:
            for fm in frx.finditer(text):
                form_spans.append((fm.start(), fm.end()))
                negated_forms_used[form] += 1
        for phrase, rx in negated:
            for m in rx.finditer(text):
                if any(s <= m.start() and m.end() <= e for s, e in form_spans):
                    continue
                if phrase.lower() in comp_phrases and exempt:
                    continue
                failures.append(f"{rel}: '{phrase}' outside every facts.negated_forms entry, in {where}: {text!r}")

    # o. Where a partner receives "each" or "every" completion, habit or win,
    #    the sentence says the completions are shared ones.
    for text, _exempt, where in (units if phrase_checks else []):
        if where.startswith(("JSON-LD", "og:", "twitter:")):
            continue
        if EVERY_COMPLETION.search(text) and RECEIVER.search(text) and not re.search(r"\bshare(d)?\b", text, re.I):
            failures.append(f"{rel}: a partner receives every completion without 'shared', in {where}: {text!r}")

    # m. A sentence where a partner sees, is shown or follows a completion,
    #    streak, widget, feed or progress must carry the Premium condition, the
    #    weekly count or a nudge, or be one of facts.visibility_forms.
    for text, _exempt, where in (units if phrase_checks else []):
        if where.startswith("JSON-LD") or where.startswith(("og:", "twitter:")):
            continue
        if VIS_SUBJ.search(text) and VIS_VERB.search(text) and VIS_OBJ.search(text):
            if VIS_OK.search(text):
                continue
            key = text.strip().lower()
            if key in visibility_forms:
                visibility_forms[key] += 1
                continue
            failures.append(f"{rel}: partner visibility without a Premium condition, in {where}: {text!r}")

    # e. Links, store link, brand footer, contact email. Internal hrefs are
    #    resolved as a browser would; a path with an empty or dot segment fails
    #    outright, and the result must sit under base_url and be a URL Vercel
    #    serves without a redirect: "/" is index.html, "/<name>" is <name>.html
    #    or a non HTML file, and a ".html" or trailing slash form fails because
    #    cleanUrls and trailingSlash redirect it.
    for n in root.walk():
        for attr in ("href", "src"):
            href = n.attrs.get(attr)
            if href is None or href.startswith(("mailto:", "tel:")):
                continue
            # The GitHub Pages mirror serves these same bytes on another host,
            # so every link and asset must be absolute; a relative or root
            # relative one would resolve to the mirror's host.
            if not href.startswith("https://") and not href.startswith("#"):
                failures.append(f"{rel}: {attr} {href!r} is not an absolute https URL")
                continue
            split = urlsplit(href)
            if split.scheme or split.netloc:
                if not href.startswith(BASE + "/") and href != BASE:
                    continue  # external
            path = split.path
            if "//" in path or "/./" in path or "/../" in path or path.startswith(("./", "../")) or path.endswith(("/.", "/..")) or path in (".", ".."):
                failures.append(f"{rel}: link {href!r} has an empty or dot path segment")
                continue
            target_url = urljoin(url, href)
            if not target_url.startswith(BASE + "/"):
                failures.append(f"{rel}: link {href!r} resolves to {target_url}, outside {BASE}/")
                continue
            path_part, _, frag = target_url[len(BASE):].partition("#")
            path_part = path_part.split("?", 1)[0].lstrip("/")
            if path_part.endswith(".html") or path_part.endswith("/"):
                failures.append(f"{rel}: link {href!r} is not a clean URL (Vercel redirects it)")
                continue
            if path_part == "":
                fpath = ROOT / "index.html"
            elif (ROOT / path_part).is_file() and not path_part.endswith(".html"):
                fpath = ROOT / path_part
            else:
                fpath = ROOT / (path_part + ".html")
            if not fpath.is_file():
                failures.append(f"{rel}: link {href!r} does not resolve to a file ({fpath.relative_to(ROOT)})")
                continue
            if fpath.relative_to(ROOT).parts[0] in {"scripts", ".git", ".vercel", "node_modules"}:
                failures.append(f"{rel}: link {href!r} points at a file that is not deployed")
                continue
            if frag:
                trel = str(fpath.relative_to(ROOT))
                ttext = FRESH.get(trel) or fpath.read_text(encoding="utf-8", errors="replace")
                check(re.search(r'\bid="' + re.escape(frag) + '"', ttext) is not None,
                      f"{rel}: link {href!r} points at #{frag}, which {trel} does not have")
    want_store = 1 if kind == "policy" else 2
    check(raw.count(PINNED_APP_STORE_URL) >= want_store, f"{rel}: App Store URL appears {raw.count(PINNED_APP_STORE_URL)} times, want {want_store} or more")
    if kind != "policy":
        store_buttons = root.find_all(lambda n: n.tag == "a" and "store" in n.classes and n.attrs.get("href") == expected_store_link(rel))
        check(len(store_buttons) >= 1, f"{rel}: no App Store button")
    brand = footer and first(footer, lambda n: n.tag == "a" and n.attrs.get("href") == BRAND_URL)
    check(bool(brand) and brand.text() == BRAND_TEXT, f"{rel}: footer lacks <a href=\"{BRAND_URL}\">{BRAND_TEXT}</a>")
    check("nofollow" not in raw.lower(), f"{rel}: contains nofollow")
    emails = emails_in(raw)
    check(emails <= {SITE["contact_email"]}, f"{rel}: unexpected email addresses {sorted(emails - {SITE['contact_email']})}")
    check(SITE["contact_email"] in emails, f"{rel}: contact email missing")

    # f. Metadata.
    check(title == want_title, f"{rel}: <title> is {title!r}, want {want_title!r}")
    check(len(title) <= TITLE_LIMIT, f"{rel}: title is {len(title)} chars, limit {TITLE_LIMIT}")
    check(description == want_desc, f"{rel}: meta description differs from pages.json")
    check(len(description) <= 160, f"{rel}: description is {len(description)} chars, limit 160")
    check(meta(root, "property", "og:title") == title, f"{rel}: og:title differs from title")
    check(meta(root, "name", "twitter:title") == title, f"{rel}: twitter:title differs from title")
    check(meta(root, "property", "og:description") == description, f"{rel}: og:description differs from description")
    check(meta(root, "name", "twitter:description") == description, f"{rel}: twitter:description differs from description")
    sheets = [n.attrs.get("href") for n in root.walk() if n.tag == "link" and n.attrs.get("rel") == "stylesheet" and n.attrs.get("href", "").startswith(PINNED_BASE_URL)]
    check(sheets == [f"{PINNED_BASE_URL}/{gen.STYLESHEET}?v={gen.css_version()}"], f"{rel}: site stylesheet links are {sheets}")
    canons = root.find_all(lambda n: n.tag == "link" and n.attrs.get("rel") == "canonical")
    canon_href = canons[0].attrs.get("href") if len(canons) == 1 else None
    check(len(canons) == 1, f"{rel}: {len(canons)} canonical links, want 1")
    check(canon_href == url, f"{rel}: canonical is {canon_href!r}, want {url}")
    check(url.startswith(PINNED_BASE_URL + "/"), f"{rel}: page URL {url} is not on {PINNED_BASE_URL}")
    check(url == PINNED_BASE_URL + "/" or not (url.endswith("/") or url.endswith(".html")),
          f"{rel}: page URL {url} is not the clean form Vercel serves")
    check(meta(root, "property", "og:url") == canon_href, f"{rel}: og:url is not byte equal to the canonical")
    # Every robots style directive on the page: exactly one, the pinned one.
    # A second, stricter tag (or a googlebot one) would win at Google.
    robot_tags = [(n.attrs.get("name") or "").lower() for n in root.walk() if n.tag == "meta"
                  and (n.attrs.get("name") or "").lower() in {"robots", "googlebot", "googlebot-news", "bingbot"}]
    check(robot_tags == ["robots"], f"{rel}: robots directives {robot_tags}, want exactly one robots tag")
    check(meta(root, "name", "robots") == PINNED_ROBOTS_META, f"{rel}: robots meta is {meta(root, 'name', 'robots')!r}, want {PINNED_ROBOTS_META!r}")
    check(meta(root, "property", "og:site_name") == PINNED_NAME, f"{rel}: og:site_name is not {PINNED_NAME}")
    check(meta(root, "property", "og:locale") == "en_US", f"{rel}: og:locale is not en_US")
    check(meta(root, "name", "theme-color") == PINNED_PALETTE["ground"],
          f"{rel}: theme-color is {meta(root, 'name', 'theme-color')!r}, want the ground {PINNED_PALETTE['ground']}")
    for key, attr in (("og:image", "property"), ("twitter:image", "name")):
        check(meta(root, attr, key) == f"{PINNED_BASE_URL}/{PINNED_OG_IMAGE}", f"{rel}: {key} is {meta(root, attr, key)!r}")
    check((meta(root, "property", "og:image:width"), meta(root, "property", "og:image:height")) == ("1200", "630"),
          f"{rel}: og:image size is not declared as 1200 by 630")
    check(bool(meta(root, "property", "og:image:alt")), f"{rel}: og:image:alt is missing")
    check(meta(root, "name", "twitter:card") == "summary_large_image", f"{rel}: twitter:card is {meta(root, 'name', 'twitter:card')!r}")
    # One family, self hosted and preloaded. No stylesheet, font, script or
    # connection hint for another host: no font service, analytics SDK or
    # widget. The one script file a page may load, this site's own
    # measure.js, is pinned in u.
    preloads = [n.attrs.get("href") for n in root.walk() if n.tag == "link" and n.attrs.get("rel") == "preload"]
    check(preloads == [f"{PINNED_BASE_URL}/{PINNED_FONT}"], f"{rel}: font preloads are {preloads}")
    for n in root.walk():
        if n.tag == "link" and n.attrs.get("rel") in {"stylesheet", "preload", "preconnect", "dns-prefetch", "modulepreload"} \
                and not (n.attrs.get("href") or "").startswith(PINNED_BASE_URL + "/"):
            failures.append(f"{rel}: {n.attrs.get('rel')} link to another host: {n.attrs.get('href')!r}")
    for host in ("fonts.googleapis.com", "fonts.gstatic.com"):
        check(host not in raw, f"{rel}: mentions {host}; the font is self hosted")
    check(len(by_tag(root, "h1")) == 1, f"{rel}: expected exactly one h1")
    dts = [n.text() for n in by_tag(root, "dt")]
    dds = [n.text() for n in by_tag(root, "dd")]
    faqs = [g for g in graph if g.get("@type") == "FAQPage"]
    if dts:
        check(len(faqs) == 1, f"{rel}: visible FAQ but {len(faqs)} FAQPage nodes")
        if faqs:
            ents = faqs[0].get("mainEntity", [])
            check([e.get("name") for e in ents] == dts, f"{rel}: FAQPage questions differ from the visible questions")
            check([e.get("acceptedAnswer", {}).get("text") for e in ents] == dds, f"{rel}: FAQPage answers differ from the visible answers")
    else:
        check(not faqs, f"{rel}: FAQPage without a visible FAQ")
    for bad in ("AggregateRating", "ratingValue", "reviewCount"):
        check(bad.lower() not in raw.lower(), f"{rel}: contains {bad}")
    types_present = [g.get("@type") for g in graph]
    want_types = {"WebSite", "WebPage"} | ({"SoftwareApplication"} if page is None else {"BreadcrumbList"})
    check(want_types <= set(types_present), f"{rel}: JSON-LD types {types_present} lack {sorted(want_types - set(types_present))}")

    # Every "@id" reference (an object holding only "@id") resolves to a node
    # defined on this page, and no "@id" is defined twice.
    defined: list[str] = []
    referenced: list[str] = []

    def ld_ids(obj) -> None:
        if isinstance(obj, dict):
            if "@id" in obj:
                (referenced if set(obj) == {"@id"} else defined).append(obj["@id"])
            for v in obj.values():
                ld_ids(v)
        elif isinstance(obj, list):
            for v in obj:
                ld_ids(v)
    ld_ids(graph)
    for ref in referenced:
        check(ref in defined, f"{rel}: JSON-LD references {ref!r}, which no node on the page defines")
    check(len(defined) == len(set(defined)), f"{rel}: JSON-LD defines an @id more than once: {defined}")
    for g in graph:
        for key in ("url", "item"):
            v = g.get(key)
            if isinstance(v, str) and v.startswith("https://") and g.get("@type") != "SoftwareApplication":
                check(v.startswith(PINNED_BASE_URL + "/"), f"{rel}: JSON-LD {g.get('@type')} {key} {v} is not on {PINNED_BASE_URL}")
        for item in g.get("itemListElement", []) if isinstance(g.get("itemListElement"), list) else []:
            check(str(item.get("item", "")).startswith(PINNED_BASE_URL + "/"), f"{rel}: breadcrumb item {item.get('item')!r} is not on {PINNED_BASE_URL}")
    for g in graph:
        if g.get("@type") == "WebPage":
            check(g.get("name") == title and g.get("description") == description and g.get("url") == url,
                  f"{rel}: WebPage name, description or url differs from the page")
        if g.get("@type") in ("WebSite", "SoftwareApplication"):
            check(g.get("name") == PINNED_NAME, f"{rel}: JSON-LD {g.get('@type')} name is {g.get('name')!r}, pinned {PINNED_NAME!r}")
        if g.get("@type") == "SoftwareApplication":
            check(g.get("url") == PINNED_APP_STORE_URL, f"{rel}: SoftwareApplication url is not the pinned App Store URL")
            check("review" not in g and "aggregateRating" not in g, f"{rel}: SoftwareApplication carries ratings")
            # The app as it is sold: a free download, with Premium as an
            # add-on offer at the one-time price (schema.org Offer.addOn,
            # "an additional offer that can only be obtained in combination
            # with the first base offer"). The icon is the app's own
            # AppIcon.png, the screenshot the hero's Partners shot. The two
            # descriptions are pinned here, word for word, so pages.json
            # alone cannot move what a search result shows about the app.
            check(g.get("description") == PINNED_APP_DESCRIPTION,
                  f"{rel}: SoftwareApplication description is not the pinned text: {g.get('description')!r}")
            _addon = (g.get("offers") or {}).get("addOn") or {}
            check(_addon.get("description") == PINNED_PREMIUM_DESCRIPTION,
                  f"{rel}: Premium offer description is not the pinned text: {_addon.get('description')!r}")
            want_app = {
                "@type": "SoftwareApplication",
                "name": PINNED_NAME,
                "description": PINNED_APP_DESCRIPTION,
                "operatingSystem": "iOS, iPadOS",
                "applicationCategory": "HealthApplication",
                "url": PINNED_APP_STORE_URL,
                "image": f"{PINNED_BASE_URL}/app-icon.png",
                "screenshot": f"{PINNED_BASE_URL}/assets/shots/partners-2026-11-09-900.webp",
                "publisher": {"@type": "Organization", "name": "Freedom Terminal", "url": BRAND_URL},
                "offers": {
                    "@type": "Offer", "price": "0", "priceCurrency": "USD",
                    "addOn": {"@type": "Offer", "name": PINNED_FACTS["tier"],
                              "description": PINNED_PREMIUM_DESCRIPTION,
                              "price": PINNED_FACTS["price"].lstrip("$"), "priceCurrency": "USD"},
                },
            }
            check(g == want_app, f"{rel}: SoftwareApplication differs from the pinned node: "
                  f"{sorted(k for k in set(g) | set(want_app) if g.get(k) != want_app.get(k))}")
            for _asset in ("app-icon.png", "assets/shots/partners-2026-11-09-900.webp"):
                check((ROOT / _asset).is_file(), f"{rel}: structured data names {_asset}, which is missing")

    # g. Word counts.
    if kind == "policy":
        pass
    elif page is None:
        n_words = len(re.findall(r"\S*[A-Za-z0-9]\S*", main.text() if main else ""))
        word_counts.append((rel + " (main)", n_words))
        check(n_words >= 500, f"{rel}: main has {n_words} words, want at least 500")
    else:
        art = first(root, lambda n: "article-body" in n.classes)
        n_words = len(re.findall(r"\S*[A-Za-z0-9]\S*", art.text() if art else ""))
        word_counts.append((rel + " (article-body)", n_words))
        check(900 <= n_words <= 1500, f"{rel}: article body has {n_words} words, want 900 to 1500")

# s. App Store links on every page the generator writes, the invite page
#    included: every link to the store host is exactly the page's expected
#    link (bare while the provider token is empty, carrying pt, the page's
#    ct and mt=8 once it is set), and nothing else on the page names the
#    store host except the landing's structured data, which names the listing
#    itself and never a campaign.
HTML_OUTPUTS = sorted(rel for rel in FRESH if rel.endswith(".html"))
check(sorted(PINNED_CT) == HTML_OUTPUTS, f"pages without a pinned ct, or pinned pages that are not generated: "
      f"{sorted(set(PINNED_CT) ^ set(HTML_OUTPUTS))}")
for rel in HTML_OUTPUTS:
    raw = FRESH[rel]
    store_links = [n for n in parse(raw).walk()
                   if any(urlsplit(n.attrs.get(a) or "").hostname == "apps.apple.com" for a in ("href", "src"))]
    check(bool(store_links), f"{rel}: no App Store link")
    want = expected_store_link(rel)
    for n in store_links:
        check(n.tag == "a" and n.attrs.get("href") == want and "src" not in n.attrs,
              f"{rel}: App Store {n.tag} {n.attrs.get('href') or n.attrs.get('src')!r}, want <a href={want!r}>")
    placements = [n.attrs.get("data-placement") for n in store_links]
    want_placements = PINNED_PLACEMENTS.get(rel, GUIDE_PLACEMENTS)
    check(placements == want_placements, f"{rel}: App Store link placements are {placements}, want {want_placements} in page order")
    mentions = raw.count("apps.apple.com")
    named = len(store_links) + (1 if rel == "index.html" else 0)
    check(mentions == named, f"{rel}: the store host appears {mentions} times, but the page has {len(store_links)} App Store links"
          f"{' and the structured data' if rel == 'index.html' else ''}")

# t. Smart App Banner: every page, the invite page included, names the app
#    once, so Safari on iPhone and iPad shows its own Get or Open banner. The
#    banner carries no app-argument anywhere: the invite page is one static
#    file served for every invite code (the /invite/:code rewrite), so a
#    banner argument could never carry the code, and the page's own Open
#    button already does.
check(SITE.get("app_store_id") == PINNED_APP_ID, f"site.app_store_id is {SITE.get('app_store_id')!r}, pinned {PINNED_APP_ID!r}")
for _listing in (PINNED_APP_STORE_URL, PINNED_INVITE_STORE_URL):
    check(_listing.endswith(f"/id{PINNED_APP_ID}"), f"{_listing} is not the listing of app {PINNED_APP_ID}")
for rel in HTML_OUTPUTS:
    banners = [n for n in parse(FRESH[rel]).walk() if n.tag == "meta" and (n.attrs.get("name") or "").lower() == "apple-itunes-app"]
    check([n.attrs.get("content") for n in banners] == [f"app-id={PINNED_APP_ID}"],
          f"{rel}: Smart App Banner tags {[n.attrs.get('content') for n in banners]}, want exactly one 'app-id={PINNED_APP_ID}'")
    check(all(any(a.tag == "head" for a in n.ancestors()) for n in banners), f"{rel}: the Smart App Banner tag is outside the head")

# u. Measurement. Every page but the privacy policy loads this site's own
#    measure.js, and nothing else by source: one async module in the head,
#    versioned by the file's hash, absolute like every other asset on the
#    generated pages and root relative on the invite page, like the rest of
#    its assets. The privacy policy loads no script file and never names the
#    module. The module itself posts only a page view and a store click to
#    the shared project's capture endpoint, with the app's slug, and keeps no
#    cookie and nothing in localStorage. Its behaviour is pinned by
#    scripts/tests/measure.test.mjs.
NOT_MEASURED = {"privacy-policy.html"}
try:
    MEASURE_BYTES = (ROOT / "measure.js").read_bytes()
except OSError:
    MEASURE_BYTES = b""
    failures.append("measure.js: missing")
MEASURE_TEXT = MEASURE_BYTES.decode("utf-8", errors="replace")
MEASURE_VERSION = hashlib.sha256(MEASURE_BYTES).hexdigest()[:12]
check(getattr(gen, "NOT_MEASURED", None) == NOT_MEASURED, f"generator NOT_MEASURED is {getattr(gen, 'NOT_MEASURED', None)}, want {NOT_MEASURED}")
for rel in HTML_OUTPUTS:
    raw = FRESH[rel]
    sourced = [n for n in parse(raw).walk() if n.tag == "script" and "src" in n.attrs]
    if rel in NOT_MEASURED:
        check(sourced == [] and "measure.js" not in raw, f"{rel}: loads {[n.attrs.get('src') for n in sourced]}; this page is never measured")
        continue
    want_src = (f"/measure.js?v={MEASURE_VERSION}" if rel == "invite.html"
                else f"{PINNED_BASE_URL}/measure.js?v={MEASURE_VERSION}")
    check([n.attrs.get("src") for n in sourced] == [want_src], f"{rel}: script files {[n.attrs.get('src') for n in sourced]}, want only {want_src}")
    for n in sourced:
        check(n.attrs.get("type") == "module" and "async" in n.attrs and "defer" not in n.attrs and not n.text().strip(),
              f"{rel}: the measure.js tag is not an empty async module script: {n.attrs}")
        check(any(a.tag == "head" for a in n.ancestors()), f"{rel}: the measure.js tag is outside the head")
    check(raw.count("measure.js") == 1, f"{rel}: names measure.js {raw.count('measure.js')} times, want the one tag")
for must in ("export const ENDPOINT = 'https://us.i.posthog.com/i/v0/e/';",
             "export const TOKEN = 'phc_J1tSpBnq3nRgP8VrUlkhQCoB0wIORi3m6EU2q2N537O';",
             "app: 'habitflame',", "bundle_id: 'habitflame.vishutdhar.com',", "$process_person_profile: false,",
             "nav?.globalPrivacyControl === true", "nav?.doNotTrack === '1'", "win.sessionStorage",
             "path: reportedPath(location.pathname),", "$referrer: referrerAddress(page.referrer),"):
    check(must in MEASURE_TEXT, f"measure.js: missing {must!r}")
_measure_code = "\n".join(l for l in MEASURE_TEXT.splitlines() if not l.lstrip().startswith("//"))
for banned_use in (r"\bcookie\b", r"\blocalStorage\b", r"\bindexedDB\b", r"\blocation\.(?:href|hash)\b", r"\bimport\b"):
    check(re.search(banned_use, _measure_code) is None, f"measure.js: matches {banned_use!r}, which the module never uses")
_measure_events = sorted(set(re.findall(r"send\('([^']+)'", _measure_code)))
check(_measure_events == ["$pageview", "store_link_clicked"], f"measure.js: sends {_measure_events}, want only $pageview and store_link_clicked")

# u2. measure.js is deployed with the pages, so its comments and strings are
#     held to the copy rules too (banned phrases, no spaced hyphen), read the
#     way JavaScript produces them: escapes are decoded, and a template
#     literal's interpolations are code, not prose, so a subtraction inside
#     one passes while any string literal inside one is still read. It must
#     also parse as a module. The parse uses node with the module type given,
#     so it does not depend on a package.json; without node the gate cannot
#     vouch for the file and fails.
JS_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
# Escapes JavaScript rejects in a string or untagged template: a code point
# past U+10FFFF, or a \u or \x without its hex digits. Reported as gate
# failures, never raised.
JS_BAD_ESCAPES: list[str] = []
# Words after which a backtick opens an untagged template, not a tag's.
JS_EXPRESSION_KEYWORDS = {"return", "typeof", "case", "in", "of", "yield", "await", "void", "delete", "new", "throw",
                          "else", "do", "instanceof"}


def js_literal(text: str, i: int, quote: str, decode: bool = True) -> "tuple[list[str], list[str], int]":
    """Read a string or template literal whose opening quote is just before
    index i: its prose pieces with escapes decoded, the source of its
    interpolations, and the index after its closing quote. With decode off
    (a tagged template, which JavaScript lets carry any escape) escapes are
    stepped over unread."""
    pieces, exprs, buf, n = [], [], [], len(text)
    while i < n and text[i] != quote:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            esc_ch = text[i + 1]
            if not decode:
                i += 2
                continue
            if esc_ch == "u" and text.startswith("{", i + 2):
                end = text.find("}", i + 3)
                digits = text[i + 3:end] if end > 0 else ""
                if re.fullmatch(r"[0-9a-fA-F]+", digits) and int(digits, 16) <= 0x10FFFF:
                    buf.append(chr(int(digits, 16)))
                    i = end + 1
                    continue
                JS_BAD_ESCAPES.append(text[i:end + 1] if end > 0 else text[i:i + 3])
                i = end + 1 if end > 0 else i + 2
                continue
            if esc_ch == "u":
                if re.fullmatch(r"[0-9a-fA-F]{4}", text[i + 2:i + 6]):
                    buf.append(chr(int(text[i + 2:i + 6], 16)))
                    i += 6
                    continue
                JS_BAD_ESCAPES.append(text[i:i + 6])
                i += 2
                continue
            if esc_ch == "x":
                if re.fullmatch(r"[0-9a-fA-F]{2}", text[i + 2:i + 4]):
                    buf.append(chr(int(text[i + 2:i + 4], 16)))
                    i += 4
                    continue
                JS_BAD_ESCAPES.append(text[i:i + 4])
                i += 2
                continue
            buf.append(JS_ESCAPES.get(esc_ch, esc_ch))
            i += 2
            continue
        if quote == "`" and text.startswith("${", i):
            pieces.append("".join(buf))
            buf = []
            depth, j = 1, i + 2
            while j < n and depth:
                if text[j] in "'\"`":
                    j = js_literal(text, j + 1, text[j], decode)[2]
                    continue
                depth += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            exprs.append(text[i + 2:j - 1])
            i = j
            continue
        buf.append(ch)
        i += 1
    pieces.append("".join(buf))
    return pieces, exprs, i + 1


def js_prose(text: str) -> list[str]:
    """The comments and string literals of a JavaScript file, including those
    inside template interpolations. A tagged template (String.raw`...`) is
    code: its text is not prose, only its interpolations are read. Regular
    expression literals are skipped, so a slash inside one is not read as
    the start of a comment."""
    out, i, n, last = [], 0, len(text), ""
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(text[i + 2:j])
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j
            out.append(text[i + 2:j])
            i = j + 2
        elif c in "'\"`":
            tag = re.search(r"([A-Za-z_$][\w$]*)\s*$", text[:i])
            tagged = c == "`" and ((tag is not None and tag.group(1) not in JS_EXPRESSION_KEYWORDS) or last in ")]")
            pieces, exprs, j = js_literal(text, i + 1, c, decode=not tagged)
            if not tagged:
                out.extend(pieces)
            for expr in exprs:
                out.extend(js_prose(expr))
            i, last = j, c
        elif c == "/" and (last == "" or last in "(,=:[!&|?{};+-*%<>~^" or re.search(r"\b(?:return|typeof|case|in|of)$", text[:i].rstrip())):
            j, in_class = i + 1, False
            while j < n and (text[j] != "/" or in_class):
                if text[j] == "\\":
                    j += 1
                elif text[j] == "[":
                    in_class = True
                elif text[j] == "]":
                    in_class = False
                j += 1
            i, last = j + 1, "/"
        else:
            if not c.isspace():
                last = c
            i += 1
    return out


_measure_prose = js_prose(MEASURE_TEXT)
for _bad in JS_BAD_ESCAPES:
    failures.append(f"measure.js: invalid escape {_bad!r} in a string literal")
for _prose in _measure_prose:
    _flat = norm(re.sub(r"\s+", " ", _prose))
    for phrase, rx in banned:
        if rx.search(_flat):
            failures.append(f"measure.js: banned phrase {phrase!r} in a comment or string: {_flat.strip()[:80]!r}")
    if " - " in _flat:
        failures.append(f"measure.js: spaced hyphen in a comment or string: {_flat.strip()[:80]!r}")
try:
    _parsed = subprocess.run(["node", "--input-type=module", "--check"], input=MEASURE_BYTES, capture_output=True)
    check(_parsed.returncode == 0, f"measure.js: does not parse as a module: "
          f"{(_parsed.stderr.decode('utf-8', 'replace').strip().splitlines() or [''])[-1]}")
except OSError:
    failures.append("measure.js: node is not available to check that it parses")

# Words that turn a sentence into a denial, shared by the copy rules below.
NEGATION = re.compile(r"\b(?:not|cannot|never|no)\b|n't\b", re.I)


def negated_before(sentence: str, start: int) -> bool:
    """Whether one of the three words before a position negates it."""
    words = re.findall(r"[\w']+", sentence[:start])[-3:]
    return any(w.lower() in {"not", "never", "no", "cannot"} or w.lower().endswith("n't") for w in words)


# v. Nothing a reader comes for is hidden. On every generated page the h1,
#    the article (the landing's main, a guide's or policy's article body)
#    and, on the landing and the guides, the first App Store button sit in
#    no element that is hidden, aria-hidden, inert or styled display none or
#    visibility hidden, and in no template or noscript; and nothing inside
#    the article that hides that way wraps its text (a paragraph, list,
#    heading, definition, table, quote or caption) or a store button. Inline
#    styles are read as a browser reads them: whitespace anywhere,
#    declarations in order, the last display and visibility values winning.
TEXT_BLOCKS = {"p", "li", "ul", "ol", "dl", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote", "figcaption"}


# CSS keywords a display or visibility value may be made of. Any other value
# is read as not visible, so a typo cannot pass a hidden element as shown.
DISPLAY_KEYWORDS = {"block", "inline", "run-in", "flow", "flow-root", "table", "flex", "grid", "ruby", "math",
                    "list-item", "contents", "inline-block", "inline-table", "inline-flex", "inline-grid",
                    "table-row-group", "table-header-group", "table-footer-group", "table-row", "table-cell",
                    "table-column-group", "table-column", "table-caption", "ruby-base", "ruby-text",
                    "ruby-base-container", "ruby-text-container"}
CSS_WIDE_KEYWORDS = {"inherit", "initial", "unset", "revert", "revert-layer"}


def css_hides(style: str) -> bool:
    """Whether an inline style hides its element, read as a browser reads it:
    whitespace collapsed, declarations in order, a later declaration winning
    unless an earlier one for the same property is !important. display: none,
    visibility: hidden or collapse, and any display or visibility value that
    is not made of CSS keywords count as hiding."""
    won: dict[str, tuple[str, bool]] = {}
    for part in re.sub(r"\s+", " ", style.lower()).split(";"):
        prop, sep, value = part.partition(":")
        if not sep:
            continue
        prop = prop.strip()
        important = re.search(r"!\s*important\s*$", value) is not None
        value = re.sub(r"!\s*important\s*$", "", value).strip()
        if prop in won and won[prop][1] and not important:
            continue
        won[prop] = (value, important)
    display = won.get("display", ("", False))[0]
    if display and display not in CSS_WIDE_KEYWORDS:
        if display == "none" or not all(t in DISPLAY_KEYWORDS for t in display.split()):
            return True
    visibility = won.get("visibility", ("", False))[0]
    if visibility and visibility not in CSS_WIDE_KEYWORDS | {"visible"}:
        return True
    return False


def hidden_itself(n) -> "str | None":
    if "hidden" in n.attrs:
        return f"<{n.tag}> has the hidden attribute"
    if (n.attrs.get("aria-hidden") or "").lower() == "true":
        return f"<{n.tag}> is aria-hidden"
    if "inert" in n.attrs:
        return f"<{n.tag}> is inert"
    if css_hides(n.attrs.get("style") or ""):
        return f"<{n.tag}> is styled {n.attrs.get('style')!r}"
    if n.tag in {"template", "noscript"}:
        return f"it sits in <{n.tag}>"
    return None


def hidden_reason(node) -> "str | None":
    for n in [node, *node.ancestors()]:
        why = hidden_itself(n)
        if why:
            return why
    return None


def hidden_inside(node) -> "str | None":
    """A hidden element inside node that wraps text or a store button."""
    for d in node.walk():
        if d is node:
            continue
        why = hidden_itself(d)
        if why and any(x.tag in TEXT_BLOCKS or (x.tag == "a" and "store" in x.classes) for x in d.walk()):
            return f"{why} inside it"
    return None


for page, rel in HTML_PAGES:
    _root = parse(FRESH[rel])
    _main = first(_root, lambda n: n.tag == "main")
    _parts = [("h1", first(_root, lambda n: n.tag == "h1")),
              ("article", first(_root, lambda n: "article-body" in n.classes) if page is not None else _main)]
    if page_kind(page) != "policy":
        _parts.append(("App Store button", first(_root, lambda n: n.tag == "a" and "store" in n.classes)))
    for _name, _node in _parts:
        if _node is None:
            failures.append(f"{rel}: the {_name} is missing")
            continue
        _why = hidden_reason(_node) or (hidden_inside(_node) if _name == "article" else None)
        check(_why is None, f"{rel}: the {_name} is hidden ({_why})")

# w. Choosing which habits each partner follows is a Premium feature: the
#    app shows Shared Habits only when PartnersPresentation.showsPushOptions
#    holds, which is hasPro && isReachable (PartnerReachability.swift). So a
#    sentence about choosing which habits a partner or friend gets says
#    Premium in that same sentence, as a condition ("without Premium" is not
#    one); a sentence saying the free version can choose fails unless it
#    denies it; and a guide table row about the choice says No or Not
#    included under Free. Choosing habits to build, with no word about
#    sharing, partners, friends or following, is planning advice and passes.
#    Every page is read, the policy pages included. On the comparison page a
#    sentence about the competitor alone (it names the competitor and not
#    HabitFlame) describes the competitor and is exempt.
SELECTION = re.compile(
    r"\bshare all habits\b|\bwhich (?:of your )?habits (?:each|to share|they are part of|you (?:will )?share|you choose)\b"
    r"|\b(?:choose|chooses|decide|decides|pick|picks) which habits\b|\b(?:choose|chooses|pick|picks|select|selects) the habits\b"
    r"|\bhabits to share\b|\bhabits per (?:friend|partner)\b|\bhabits you choose\b|\bones you choose\b", re.I)
SHARING = re.compile(r"\bshar\w*|\bpartners?\b|\bfriends?\b|\bfollow\w*|\bpart of\b|\bhears? about\b|\bsent\b|\bsends?\b", re.I)
PREMIUM_CONDITION = re.compile(r"(?<!without )\bPremium\b", re.I)
FREE_CHOICE = re.compile(
    r"\bfree\b(?:\s+[\w']+){0,4}?\s+(?:choose|chooses|pick|picks|decide|decides|select|selects)\b"
    r"|\b(?:choose|chooses|pick|picks|decide|decides|select|selects)\b(?:\s+[\w']+){0,5}?\s+(?:for free|free of charge|on the free version|in the free version)\b",
    re.I)
for page, rel in HTML_PAGES:
    _root = parse(FRESH[rel])
    _comp = page.get("competitor") if page else None
    _units = [(n.tag, n.text()) for n in _root.find_all(lambda n: n.tag in {"p", "li", "dt", "dd", "h1", "h2", "h3"})
              if not any(a.tag in HIDDEN or a.tag == "table" for a in n.ancestors())]
    _units += [("title", gen.page_title(page)), ("meta description", gen.page_description(page))]
    for _where, _text in _units:
        for _sentence in sentences(_text):
            if not SELECTION.search(_sentence) or not SHARING.search(_sentence):
                continue
            if _comp and whole(_comp).search(_sentence) and not whole(PINNED_NAME).search(_sentence):
                continue
            if FREE_CHOICE.search(_sentence):
                _ok = NEGATION.search(_sentence) is not None
            else:
                _ok = PREMIUM_CONDITION.search(_sentence) is not None
            check(_ok, f"{rel}: habit selection is Premium only, but this {_where} sentence does not make it a Premium "
                       f"feature: {_sentence!r}")
    for _table in by_tag(_root, "table"):
        _head = table_head(_table)
        for _tr in by_tag(first(_table, lambda n: n.tag == "tbody") or _table, "tr"):
            _cells = [c.text() for c in row_cells(_tr)]
            if not _cells or not SELECTION.search(_cells[0]):
                continue
            if _head == GUIDE_TABLE_HEAD:
                check(len(_cells) > 1 and _cells[1].lower() in {"no", "not included"},
                      f"{rel}: table row {_cells[0]!r} offers habit selection under Free")
            else:
                check(PREMIUM_CONDITION.search(" ".join(_cells)) is not None,
                      f"{rel}: table row {_cells[0]!r} offers habit selection without saying Premium")

# y. A partner hears about a completion at once only when it is made in the
#    app for today: a completion from a widget or for a past day sends no
#    alert (HabitCompletionEffects runs the push only when !isBackfill, and
#    WidgetIntents writes the entry with no partner effects). So any visible
#    sentence, heading, table cell, title or description that says a
#    completion reaches the partner at once, in any wording (the moment,
#    instantly, an instant notification, as it happens, right away, live,
#    immediately, in real time, real-time), says "in the app for today". A
#    sentence that denies it ("does not instantly notify") says nothing at
#    once and passes; Live Activity is the lock screen timer, not a claim.
IMMEDIATE = re.compile(
    r"\bthe moment\b|\binstantly\b|\binstant notifications?\b|\bas (?:it|they) happens?\b|\bright away\b"
    r"|\blive\b(?!\s+activit)|\bimmediately\b|\bin real[- ]time\b|\breal[- ]time\b", re.I)
COMPLETING = re.compile(r"\bcomplet(?:e|es|ed|ing|ion|ions)\b", re.I)
for page, rel in HTML_PAGES:
    _body = first(parse(FRESH[rel]), lambda n: n.tag == "body")
    _texts = [t for t, _owner, _table in (visible_units(_body) if _body else [])]
    _texts += [gen.page_title(page), gen.page_description(page)]
    for _text in _texts:
        for _sentence in sentences(_text):
            if not COMPLETING.search(_sentence) or "in the app for today" in _sentence.lower():
                continue
            if any(not negated_before(_sentence, m.start()) for m in IMMEDIATE.finditer(_sentence)):
                failures.append(f"{rel}: a completion reaches the partner at once without 'in the app for today': {_sentence!r}")

# x. Milestones reached by calendar week hold only for a habit done every
#    day: a streak counts only scheduled days (HabitHistory), so a habit on
#    specific days reaches each milestone later. A page that sets a week,
#    in any wording (week two, the second week, after two weeks, by week
#    two), beside a day milestone carries a daily qualification ("for a
#    habit you do every day", "assumes a daily habit", "scheduled days
#    only" and their like); a sentence that denies the timing passes.
WEEK_ORDINAL = (r"(?:\bweek (?:one|two|three|four|five|[1-5])\b|\b(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th) week\b"
                r"|\bafter (?:a|one|two|three|four|five|[1-5]) weeks?\b|\bby week\b|\bwithin (?:a|one|two|three|four|five|[1-5]) weeks?\b)")
DAY_MILESTONE = r"\b\d+ day milestones?\b"
WEEK_MILESTONE = re.compile(f"{WEEK_ORDINAL}.*{DAY_MILESTONE}|{DAY_MILESTONE}.*{WEEK_ORDINAL}", re.I | re.S)
DAILY_QUALIFIERS = re.compile(
    r"\bfor a habit you do every day\b|\bassumes? a daily habit\b|\bfor a daily habit\b(?! or)"
    r"|\bonly the scheduled days count\b|\bscheduled days only\b|\bcounts? only (?:the )?scheduled days\b", re.I)
for page, rel in HTML_PAGES:
    if page_kind(page) == "policy":
        continue
    _root = parse(FRESH[rel])
    _main = first(_root, lambda n: n.tag == "main")
    _plans = []
    for _n in _root.find_all(lambda n: n.tag in {"p", "li", "dd"}):
        _text = _n.text()
        if not WEEK_MILESTONE.search(_text):
            continue
        _claims = [s for s in sentences(_text) if re.search(DAY_MILESTONE, s, re.I)]
        if _claims and all(NEGATION.search(s) for s in _claims):
            continue
        _plans.append(_text)
    if _plans:
        _flat = norm(_main.text()) if _main else ""
        check(DAILY_QUALIFIERS.search(_flat) is not None,
              f"{rel}: a week by week milestone plan without the daily qualification: {_plans[0]!r}")

# z. A weekly target's streak grows a week at a time, by that week's
#    completions once its target is met (WeeklyStreakCalculator), and a
#    milestone is celebrated only when the streak lands on it exactly
#    (HabitCompletionEffects): three a week makes three, six, nine and never
#    seven. A sentence about a weekly target and milestones says a milestone
#    can be stepped past, never that the same milestones come later.
STEPS_PAST = re.compile(r"\bwithout landing\b|\bstep\w* past\b|\bskip\w*\b|\bnever lands?\b|\bnot every milestone\b|\bnot celebrated\b", re.I)
for page, rel in HTML_PAGES:
    _body = first(parse(FRESH[rel]), lambda n: n.tag == "body")
    for _text, _owner, _table in (visible_units(_body) if _body else []):
        for _sentence in sentences(_text):
            if re.search(r"\bweekly targets?\b", _sentence, re.I) and re.search(r"\bmilestones?\b", _sentence, re.I):
                check(STEPS_PAST.search(_sentence) is not None,
                      f"{rel}: a weekly target is promised milestones it can step past: {_sentence!r}")

# 9. Every allowed negated form is one the copy actually uses.
for form, count in negated_forms_used.items():
    check(count > 0, f"facts.negated_forms has {form!r}, which no page uses (remove it)")

# c. Every allowlisted free and Premium sentence is one the copy uses.
for form, count in premium_free_forms.items():
    check(count > 0, f"facts.premium_free_forms has {form!r}, which no page uses (remove it)")

# m. Every allowlisted visibility sentence is one the copy uses.
for form, count in visibility_forms.items():
    check(count > 0, f"facts.visibility_forms has {form!r}, which no page uses (remove it)")

# l. Text colors in site.css. The site is dark only, like the app. Every text
#    color meets 4.5:1 on every ground, and the briefs' APCA rules hold:
#    headings (ink) reach Lc 90, running text Lc 75, ember text on the ground
#    Lc 60, ink on an ember button Lc 75, and fine print (muted) stays at
#    Lc 45 or more. The palette is pinned to the app's values and has one
#    chromatic hue, the app's orange. The skip link hides with a transform,
#    never a negative top, which leaves a visible bar when the link is taller.
CSS = (ROOT / gen.STYLESHEET).read_text(encoding="utf-8")
check(gen.STYLESHEET == "site.css", f"generator stylesheet is {gen.STYLESHEET!r}; styles.css belongs to the invite page")
check(gen.FONT == PINNED_FONT and (ROOT / PINNED_FONT).is_file(), f"generator font {gen.FONT!r} is not the pinned file {PINNED_FONT!r}")
check(PINNED_FONT in CSS, f"site.css: the @font-face does not load {PINNED_FONT}")
check(gen.OG_IMAGE == PINNED_OG_IMAGE, f"generator share card {gen.OG_IMAGE!r} is not {PINNED_OG_IMAGE!r}")
try:
    _png = (ROOT / PINNED_OG_IMAGE).read_bytes()
    check(_png[:8] == b"\x89PNG\r\n\x1a\n" and (int.from_bytes(_png[16:20], "big"), int.from_bytes(_png[20:24], "big")) == (1200, 630),
          f"{PINNED_OG_IMAGE}: not a 1200 by 630 PNG")
except OSError:
    failures.append(f"{PINNED_OG_IMAGE}: missing")


def css_vars(block: str) -> dict[str, str]:
    return {k: v.strip() for k, v in re.findall(r"--([\w-]+):\s*([^;]+);", block)}


def css_rule(selector: str) -> dict[str, str]:
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    return {k.strip(): v.strip() for k, v in re.findall(r"([\w-]+)\s*:\s*([^;]+);", m.group(1))} if m else {}


def css_color(value: str, env: dict[str, str]) -> str:
    for _ in range(5):
        m = re.fullmatch(r"var\(--([\w-]+)\)", value.strip())
        if not m:
            break
        value = env[m.group(1)]
    value = value.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", value):
        value = "#" + "".join(ch * 2 for ch in value[1:])
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"not a hex color: {value!r}")
    return value


def rgb(h: str) -> list[float]:
    return [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb(h)]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def apca(text: str, ground: str) -> float:
    """APCA-W3 0.0.98G-4g lightness contrast, as an absolute Lc value."""
    def y(h: str) -> float:
        r, g, b = rgb(h)
        v = 0.2126729 * r ** 2.4 + 0.7151522 * g ** 2.4 + 0.0721750 * b ** 2.4
        return v + (0.022 - v) ** 1.414 if v < 0.022 else v
    yt, yb = y(text), y(ground)
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:
        sapc = (yb ** 0.56 - yt ** 0.57) * 1.14
        return 0.0 if sapc < 0.1 else (sapc - 0.027) * 100
    sapc = (yb ** 0.65 - yt ** 0.62) * 1.14
    return 0.0 if sapc > -0.1 else -(sapc + 0.027) * 100


root_m = re.search(r"(?m)^:root\s*\{([^}]*)\}", CSS)
check(bool(root_m), "site.css: cannot find the :root block")
check(re.search(r"prefers-color-scheme\s*:\s*light", CSS) is None, "site.css: a light theme block; the site is dark only")
contrast_lines = []
if root_m:
    env = css_vars(root_m.group(1))
    check(re.search(r"(?m)^\s*color-scheme:\s*dark;", root_m.group(1)) is not None, "site.css: :root does not set color-scheme: dark")
    skip, skip_hover = css_rule(".skip"), css_rule(".skip:hover")
    check(skip.get("transform") == "translateY(-100%)" and not skip.get("top", "0").startswith("-"),
          f"site.css: .skip must hide with transform: translateY(-100%) and no negative top, has {skip}")
    store, hover = css_rule(".store"), css_rule(".store:hover")
    pairs = [(f"--{t} on --{b}", f"var(--{t})", f"var(--{b})") for t in ("ink", "body", "muted", "ember") for b in ("ground", "surface", "surface-2")]
    buttons = [("skip link", skip), ("skip link hover", skip_hover), ("store button", store), ("store button hover", hover)]
    pairs += [(name, rule.get("color", ""), rule.get("background", "")) for name, rule in buttons]
    apca_floor = {"--ember on --ground": 60, "--body on --ground": 75, "--ink on --ground": 90, "--muted on --ground": 45}
    apca_floor.update({name: 75 for name, _ in buttons})
    for token, want in PINNED_PALETTE.items():
        check(env.get(token, "").upper() == want, f"site.css: --{token} is {env.get(token)!r}, pinned {want} from the app")
    # One chromatic hue: any colour in the stylesheet with real chroma sits on
    # the app's orange. Near greys with the iOS cool tint have chroma under 0.12.
    flame_hue = colorsys.rgb_to_hls(*rgb(PINNED_PALETTE["flame"]))[0] * 360
    for m in re.finditer(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b|rgba?\(\s*(\d{1,3})[\s,]+(\d{1,3})[\s,]+(\d{1,3})", CSS):
        if m.group(1):
            h6 = m.group(1) if len(m.group(1)) == 6 else "".join(ch * 2 for ch in m.group(1))
            chans = rgb("#" + h6)
        else:
            chans = [int(m.group(k)) / 255 for k in (2, 3, 4)]
        if max(chans) - min(chans) <= 0.12:
            continue
        hue = colorsys.rgb_to_hls(*chans)[0] * 360
        off = min(abs(hue - flame_hue), 360 - abs(hue - flame_hue))
        check(off <= APP_HUE_TOLERANCE, f"site.css: {m.group(0)} has hue {hue:.1f}, {off:.1f} degrees off the app's orange ({flame_hue:.1f}); the page has one accent hue")
    worst, worst_apca = [], []
    for name, fg, bg in pairs:
        try:
            fg_hex, bg_hex = css_color(fg, env), css_color(bg, env)
        except (KeyError, ValueError) as e:
            failures.append(f"site.css: {name}: {e}")
            continue
        ratio = contrast(fg_hex, bg_hex)
        worst.append((ratio, name))
        check(ratio >= 4.5, f"site.css: {name} is {ratio:.2f}:1, below 4.5:1")
        if name in apca_floor:
            lc = apca(fg_hex, bg_hex)
            worst_apca.append((lc, name))
            check(lc >= apca_floor[name], f"site.css: {name} is APCA Lc {lc:.1f}, below {apca_floor[name]}")
    if worst:
        r, name = min(worst)
        contrast_lines.append(f"contrast: lowest {r:.2f}:1 ({name}) of {len(worst)} pairs")
    for lc, name in sorted(worst_apca):
        contrast_lines.append(f"apca: Lc {lc:.1f} {name} (floor {apca_floor[name]})")

# h. Prose hygiene.
DASHES = {0x2012, 0x2013, 0x2014, 0x2015, 0x2212}
PICTO_RANGES = [(0x1F000, 0x10FFFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF), (0x2300, 0x23FF), (0x2190, 0x21FF),
                (0xFE00, 0xFE0F), (0x200D, 0x200D), (0x20D0, 0x20FF), (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3297), (0x3299, 0x3299)]


def pictographic(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in PICTO_RANGES)


# The only list, stored rot13 so this file never spells the names it bans.
TOOL_NAMES = {codecs.decode(w, "rot13") for w in ("pynhqr", "pbqrk", "tcg", "naguebcvp", "bcranv")}
tool_rx = [(w, whole(w)) for w in sorted(TOOL_NAMES)]

hygiene_files = {
    "scripts/pages.json": (ROOT / "scripts/pages.json").read_text(encoding="utf-8"),
    "scripts/template.html": (ROOT / "scripts/template.html").read_text(encoding="utf-8"),
    "site.css": (ROOT / "site.css").read_text(encoding="utf-8"),
    "scripts/build-pages.py": GEN_PATH.read_text(encoding="utf-8"),
    "scripts/verify-pages.py": pathlib.Path(__file__).read_text(encoding="utf-8"),
    "vercel.json": (ROOT / "vercel.json").read_text(encoding="utf-8"),
    # The invite page's source, its stylesheet and the measurement module are
    # hand written; the share card source, the tests and the design notes
    # ship in the repository.
    "scripts/invite.html": (ROOT / "scripts" / "invite.html").read_text(encoding="utf-8"),
    "styles.css": (ROOT / "styles.css").read_text(encoding="utf-8"),
    "measure.js": MEASURE_TEXT,
    "scripts/og.html": (ROOT / "scripts" / "og.html").read_text(encoding="utf-8"),
}
for _test in sorted((ROOT / "scripts" / "tests").glob("*")):
    if _test.is_file() and _test.suffix in {".py", ".js", ".mjs"}:
        hygiene_files[str(_test.relative_to(ROOT))] = _test.read_text(encoding="utf-8")
for note in sorted((ROOT / "docs").rglob("*.md")):
    hygiene_files[str(note.relative_to(ROOT))] = note.read_text(encoding="utf-8")
for frag in sorted((ROOT / "scripts" / "policies").glob("*.html")):
    hygiene_files[str(frag.relative_to(ROOT))] = frag.read_text(encoding="utf-8")
hygiene_files.update(FRESH)
for name, text in hygiene_files.items():
    for lineno, line in enumerate(text.splitlines(), 1):
        for ch in line:
            cp = ord(ch)
            if cp in DASHES:
                failures.append(f"{name}:{lineno}: dash character U+{cp:04X}")
            elif pictographic(cp):
                failures.append(f"{name}:{lineno}: pictographic character U+{cp:04X}")
        for w, rx in tool_rx:
            if rx.search(line):
                failures.append(f"{name}:{lineno}: tool name '{w}'")


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)


for s in strings(gen.CONFIG):
    if " - " in s:
        failures.append(f"scripts/pages.json: spaced hyphen in {s[:80]!r}")

# i. Sitemap lists exactly the landing, the guides and the policy pages, each
#    dated by its own configured lastmod.
sitemap = FRESH["sitemap.xml"]
locs = [htmlmod.unescape(u) for u in re.findall(r"<loc>([^<]*)</loc>", sitemap)]
EXPECTED_URLS = [
    "https://habitflame.vishutdhar.com/",
    "https://habitflame.vishutdhar.com/accountability-partner-habit-tracker",
    "https://habitflame.vishutdhar.com/streak-tracker-app",
    "https://habitflame.vishutdhar.com/pomodoro-habit-app",
    "https://habitflame.vishutdhar.com/habit-app-for-couples",
    "https://habitflame.vishutdhar.com/daily-habit-tracker-with-reminders",
    "https://habitflame.vishutdhar.com/habitflame-vs-habitshare",
    "https://habitflame.vishutdhar.com/habit-tracker-with-friends",
    "https://habitflame.vishutdhar.com/new-year-habits-with-a-friend",
    "https://habitflame.vishutdhar.com/support",
    "https://habitflame.vishutdhar.com/privacy-policy",
    "https://habitflame.vishutdhar.com/terms-of-service",
]
for u in re.findall(r"<loc>([^<]*)</loc>", FRESH["sitemap.xml"]):
    check(htmlmod.unescape(u).startswith(PINNED_BASE_URL + "/"), f"sitemap.xml: {u} is not on {PINNED_BASE_URL}")
check(sorted(gen.sitemap_urls()) == sorted(EXPECTED_URLS), f"generator sitemap URLs differ from the pinned list: {sorted(set(gen.sitemap_urls()) ^ set(EXPECTED_URLS))}")
check(gen.POLICY_PAGES == ["support.html", "privacy-policy.html", "terms-of-service.html"], f"generator POLICY_PAGES is {gen.POLICY_PAGES}")
want_locs = EXPECTED_URLS
check(len(locs) == len(set(locs)), f"sitemap.xml: duplicate URLs {sorted({u for u in locs if locs.count(u) > 1})}")
check(set(locs) == set(want_locs), f"sitemap.xml: lists {sorted(set(locs) ^ set(want_locs))} unexpectedly or misses them")
check(len(locs) == 1 + len(PAGES) + len(gen.POLICY_PAGES), f"sitemap.xml: {len(locs)} URLs")
pairs = [(htmlmod.unescape(u), d) for u, d in re.findall(r"<loc>([^<]*)</loc>\s*<lastmod>([^<]*)</lastmod>", sitemap)]
check(len(pairs) == len(locs), f"sitemap.xml: {len(locs)} URLs but {len(pairs)} have a lastmod")
url_date = {f"{BASE}/": DATES["landing"]}
url_date.update({gen.page_url(p): DATES[p["slug"]] for p in PAGES})
url_date.update({gen.page_url(p): DATES[p["file"]] for p in POLICIES})
for u, d in pairs:
    check(iso_date(d), f"sitemap.xml: lastmod {d!r} for {u} is not a YYYY-MM-DD date")
    check(d == url_date.get(u), f"sitemap.xml: lastmod for {u} is {d}, configured {url_date.get(u)}")

# i2. Dates against the baseline, the first of origin/main, main or the
#     merge-base with HEAD's upstream that resolves. Read only git calls.
#     Without a baseline these checks are skipped, never failed.
#     a. lastmod must advance: a page whose content differs from the baseline
#        is dated strictly later than the baseline's configured date for it;
#        an identical page keeps the baseline's date.
#     b. Commit-date bound for policy pages: identical to the baseline means
#        dated no later than its last change there; changed means no earlier.
def git(*args: str) -> "bytes | None":
    try:
        r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True)
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def baseline_ref() -> "str | None":
    for ref in ("origin/main", "main"):
        if git("rev-parse", "--verify", "-q", ref + "^{commit}") is not None:
            return ref
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if upstream:
        base = git("merge-base", "HEAD", upstream.decode().strip())
        if base:
            return base.decode().strip()
    return None


BASELINE = baseline_ref()
_dirty = git("status", "--porcelain", "--", "scripts") or b""
EDIT_DATE = TODAY if _dirty.strip() else (git("log", "-1", "--format=%cd", "--date=short", "HEAD") or b"").decode().strip()
skip_lines: list[str] = []
if BASELINE is None:
    skip_lines.append("policy-date history check skipped: no baseline ref")
else:
    base_raw = git("show", f"{BASELINE}:scripts/pages.json")
    try:
        base_cfg = json.loads(base_raw) if base_raw else None
    except ValueError:
        base_cfg = None
    base_dates: dict[str, str] = {}
    if base_cfg:
        fallback = base_cfg.get("site", {}).get("lastmod")
        base_dates["index.html"] = base_cfg.get("landing", {}).get("lastmod") or fallback
        for bp in base_cfg.get("pages", []):
            base_dates[f"{bp['slug']}/index.html"] = bp.get("lastmod") or fallback
            base_dates[f"{bp['slug']}.html"] = bp.get("lastmod") or fallback
        for bp in base_cfg.get("policies", []):
            base_dates[bp.get("file")] = bp.get("lastmod") or fallback
        for name in POLICY_NAMES:
            base_dates.setdefault(name, (base_cfg.get("site", {}).get("policy_lastmod") or {}).get(name) or fallback)
    targets = [("index.html", DATES["landing"], FRESH["index.html"].encode("utf-8"))]
    targets += [(gen.page_file(p), DATES[p["slug"]], FRESH[gen.page_file(p)].encode("utf-8")) for p in PAGES]
    targets += [(name, DATES[name], FRESH[name].encode("utf-8")) for name in POLICY_NAMES]
    for rel_path, conf, here in targets:
        before = base_dates.get(rel_path)
        if not before or not iso_date(conf):
            continue  # new to the baseline's config: every configured date is new
        if here == git("show", f"{BASELINE}:{rel_path}"):
            check(conf == before, f"{rel_path}: unchanged from {BASELINE} but lastmod moved from {before} to {conf}")
        else:
            # A later change made on the same day the baseline was dated keeps
            # that date: the edit date is the HEAD commit's date, or today
            # while the change is uncommitted.
            check(conf > before or conf == before == EDIT_DATE,
                  f"{rel_path}: changed from {BASELINE} but lastmod {conf} is not later than {before}")
    for name in POLICY_NAMES:
        on_base = git("show", f"{BASELINE}:{name}")
        base_date = (git("log", "-1", "--format=%ad", "--date=short", BASELINE, "--", name) or b"").decode().strip()
        conf = DATES.get(name)
        if on_base is None or not base_date or not iso_date(conf):
            continue  # not on the baseline yet
        if FRESH[name].encode("utf-8") == on_base:
            check(conf <= base_date, f"{name}: unchanged from {BASELINE} (last changed {base_date}) but dated {conf}")
        else:
            check(conf >= base_date, f"{name}: changed from {BASELINE} but dated {conf}, before its change there on {base_date}")
for u in locs:
    rel = u[len(BASE) + 1:] if u.startswith(BASE + "/") else None
    if rel is None:
        failures.append(f"sitemap.xml: {u} is outside the site")
        continue
    f = ROOT / ("index.html" if rel == "" else rel + ".html")
    check(f.is_file() and not rel.endswith((".html", "/")), f"sitemap.xml: {u} does not resolve to a page Vercel serves without a redirect")
# j. The privacy policy (a hand written fragment, rendered into the template)
#    says what the app does.
# Visible markup only: the JSON-LD in the head could repeat a phrase the
# visible page lost.
POLICY = FRESH["privacy-policy.html"].split("<main", 1)[-1]


def visible_main(rel: str) -> tuple[str, list]:
    """The main element's visible text (scripts, styles and comments are not
    text) and its links, parsed rather than searched as markup."""
    main_node = first(parse(FRESH[rel]), lambda n: n.tag == "main")
    if main_node is None:
        return "", []
    def hidden(n) -> bool:
        return "hidden" in n.attrs or n.attrs.get("aria-hidden") == "true" or "display:none" in (n.attrs.get("style") or "").replace(" ", "")
    if hidden(main_node) or any(hidden(a) for a in main_node.ancestors()):
        return "", []
    links = [n.attrs.get("href", "") for n in main_node.walk()
             if n.tag == "a" and not hidden(n) and not any(hidden(a) for a in n.ancestors())]
    return norm(main_node.text(skip=hidden)), links


POLICY_TEXT, POLICY_LINKS = visible_main("privacy-policy.html")
for must in ("PostHog", "pairing service", "push notification", "Apple Health", "Screen recordings", "weekly count", "Nudges and reactions", SITE["contact_email"]):
    check(must in POLICY_TEXT, f"privacy-policy.html: missing {must!r} from the visible page")
# Facts the corrected policy states, each checked against the app and the
# relay migrations when it was written.
for must in ("Session replay is turned off", "in your private iCloud database", "one-way hash of the habit's identifier",
             "eligible for deletion 30 days later", "Share usage analytics", "when the app is started in the evening",
             "the same on your devices that share an iCloud account",
             "automatically through your iCloud account", "request counters for each IP address, pairing and device",
             "for a reaction the name of the habit you reacted to", "keeps a record of the invite used for the move with no end date",
             "Analytics never receives Health measurements", "the iOS keychain on this device only",
             "Once the pairing service receives the request", "while you are online",
             "a streak-at-risk alert for one habit that runs every day or on specific days",
             "Those recordings are deleted 30 days after they were made", "your IP address",
             "From version 4.5.3, you can turn analytics off", "Before it was turned off, PostHog could record sessions",
             "An invite nobody accepts is deleted the next time the pairing service runs its cleanup",
             "These counters are not deleted",
             "your IP address, which reaches PostHog with each request; PostHog is set to discard it, and no location is derived from it"):
    check(must in POLICY_TEXT, f"privacy-policy.html: missing {must!r} from the visible page")
# What measure.js sends, and what it never does, each checked against the
# module and its tests when it was written.
for must in ("This website is measured through PostHog", "Each click on an App Store link is counted with which link it was",
             "an address is sent without its query or fragment",
             "an invite page is sent as /invite, without the invite code or the name and identifier of the person who invited you",
             "The website sets no cookies and stores nothing in your browser's local storage",
             "a random value your browser keeps for the current tab and discards when the tab closes",
             "If your browser sends Global Privacy Control or Do Not Track, the website sends nothing at all",
             "This page is never measured"):
    check(must in POLICY_TEXT, f"privacy-policy.html: missing {must!r} from the visible page")
check(gen.POLICIES[1].get("deck") == "Last updated: November 2, 2026",
      f"privacy-policy.html: deck is {gen.POLICIES[1].get('deck')!r}; the website section is new on November 2, 2026")
# Sentences from the retired policies, false about what the app does: the
# first four from the old GitHub Pages policy, the rest from the old custom
# domain policy (partner activity relayed on every plan, Health data never
# leaving the device). No page on the site, the invite page included, may say
# them again.
RETIRED_POLICY_SENTENCES = (
    "We do not collect any personal information", "do not use analytics", "do not have servers",
    "does not integrate with any third-party analytics",
    "the names of shared habits, completion events, milestones, streak counts, nudges, reactions, and your display name are relayed",
    "It never leaves your device and is never sent to any server",
    "An anonymous identity key that represents your account without revealing who you are",
    # Retired from the first custom domain version of the truthful policy:
    # Health values sync through iCloud, replay is off, and the weekly count
    # carries one record per completion.
    "Health values stay on your device", "Session replay is turned on", "never individual habits",
    # Retired when 4.5.3 shipped the analytics switch, and for overstating
    # how the evening alert and the analytics identifier work.
    "There is currently no switch in the app to turn analytics off", "a random identifier for your installation",
    "one evening alert when a streak", "an evening streak-at-risk alert goes", "an evening warning when a streak",
    "once a day in the evening, a streak-at-risk alert",
    # Unshared habits still add to the weekly count, which shows each
    # person's total; widget completions are not sent to a partner.
    "is invisible to your partner", "Anything not shared is invisible", "Habits you do not share are never sent",
    "every habit you share and complete is sent", "each of your shared completions instantly",
    "Every shared completion as it happens",
    "A habit completed from a widget is not sent to your partner", "counts for your streak but is not sent",
    "so the message on Tuesday is not the message from Monday", "wording changes from day to day",
    "The wording varies from day to day", "keeps a small record of that code",
    "never a habit name.", "Weekly and monthly charts", "so a habit set to weekdays does not ring on Saturday.",
    "nothing your partner can see beyond what you chose to share.",
    "Analytics receives only the type of a habit", "and its record is removed 30 days after it expires",
    "marked as removed, and deleted 30 days later",
    "gets a different message each day", "it schedules a different message for each of the coming days",
    "Deleting the app removes the data stored on your device. It does not",
    "For every invite, the pairing service also keeps a permanent record",
    "either automatically through your iCloud account or with a code",
    "and phone numbers are removed from event details", "Premium is bought per person",
    "purchase per person", "on the side of whoever buys it", "Real-time partner updates are bought by",
    "monthly completion rates", "<p>When you remove a partner, the device records for that pairing",
    "the pairing service stores your display name, your device's push token",
    "the two of you are paired. If they do not have the app yet, the link takes them",
    "the link sends them to the App Store first",
    "your best day for each habit",
    "resets to zero and starts again with your next completion",
    "an evening streak-at-risk alert goes to your partner",
    "when a streak milestone is crossed", "an iPhone and iPad app only",
    # Retired when the analytics project stopped keeping IP addresses and
    # stopped deriving any location from them.
    "estimate your approximate location",
)
retired_scan = {rel: text for rel, text in FRESH.items() if rel.endswith(".html")}
for rel, text in retired_scan.items():
    flat = norm(re.sub(r"\s+", " ", htmlmod.unescape(text))).lower()
    for stale in RETIRED_POLICY_SENTENCES:
        check(stale.lower() not in flat, f"{rel}: still says {stale!r}")
push = re.search(r"<h2>Push notifications</h2>(.*?)<h2>", POLICY, re.S)
check(bool(push) and "have Premium and complete" in norm(re.sub(r"\s+", " ", push.group(1) if push else "")),
      "privacy-policy.html: the Push notifications section does not say 'have Premium and complete'")

# j2. The terms keep every section; an empty or shortened fragment fails.
TERMS_SECTIONS = ["Agreement to Terms", "Description of Service", "Accountability Partners", "User Responsibilities",
                  "Intellectual Property", "In-App Purchases", "Disclaimer of Warranties", "Limitation of Liability",
                  "Data Loss", "Modifications to Service", "Changes to Terms", "Governing Law", "Contact Us"]
terms_main = first(parse(FRESH["terms-of-service.html"]), lambda n: n.tag == "main")
terms_h2 = [n.text() for n in by_tag(terms_main, "h2")] if terms_main else []
check(terms_h2 == TERMS_SECTIONS, f"terms-of-service.html: sections are {terms_h2}")
terms_words = len(re.findall(r"\S*[A-Za-z0-9]\S*", terms_main.text())) if terms_main else 0
check(terms_words >= 400, f"terms-of-service.html: main has {terms_words} words, want at least 400")

# n. The support page does not tie iCloud sync to Premium.
SUPPORT = FRESH["support.html"].split("<main", 1)[-1]
SUPPORT_VISIBLE, SUPPORT_LINKS = visible_main("support.html")
check(f"mailto:{SITE['contact_email']}" in SUPPORT_LINKS, "support.html: no visible mailto link to the contact address")
for must in ("How do I add an accountability partner?", "I have an invite code. Where do I enter it?",
             "How do I restore my purchase?", "Restore Purchases",
             # InviteCodeValidator.codeLength and InviteLinkService's 7 day expiry.
             "the 6 character code", "An invite expires after 7 days",
             "Open the Partners tab and send an invite link", "choose Have a code and type",
             "the app shows your invite and they tap Accept"):
    check(must in SUPPORT_VISIBLE, f"support.html: missing {must!r} from the visible page")
# Every number on the support page is one of its known facts, and every day
# count is the 7 day invite expiry: InviteLinkService, InviteCodeValidator,
# and the 24 to 48 hour reply window.
for m in re.finditer(r"(?<![\w.])(\d+)(?:\s+(\w+))?", SUPPORT_VISIBLE):
    num, nxt = m.group(1), (m.group(2) or "").lower()
    check(num in {"6", "7", "24", "48"}, f"support.html: number {num} is not a known support fact")
    if nxt.startswith("day"):
        check(num == "7", f"support.html: '{num} {nxt}' is not the 7 day invite expiry")
# The Premium purchase has Family Sharing on; the couples guide says so.
COUPLES_TEXT = norm(first(parse(FRESH["habit-app-for-couples.html"]), lambda n: n.tag == "main").text())
for must in ("With Family Sharing, one purchase also unlocks Premium for the people in your Apple family",
             "Family Sharing lets one purchase unlock Premium for both of you"):
    check(must in COUPLES_TEXT, f"habit-app-for-couples.html: missing {must!r}")
# The landing's store note says what 4.6.0 changed on wide screens, in the
# words of its release notes ("Partners and Settings sit in a comfortable
# column on iPad and an unfolded iPhone Duo"): the readable column in
# AccountabilityPartnersView.swift and SettingsView.swift. It is the only
# Duo claim on the site, and the hero's store note shows it under the
# store button.
DUO_SENTENCE = "On iPad and an unfolded iPhone Duo, Partners and Settings sit in a comfortable column."
_hero_notes = [n.text() for n in parse(FRESH["index.html"]).walk() if "store-note" in n.classes]
check(_hero_notes == [f"On the App Store for iPhone and iPad. {DUO_SENTENCE}"],
      f"index.html: the hero store note is {_hero_notes}, want the App Store line and the 4.6.0 Duo sentence")
for rel in HTML_OUTPUTS:
    if rel != "index.html":
        check("Duo" not in FRESH[rel], f"{rel}: names the Duo; the landing's store note is the one place for it")
SUPPORT_TEXT = norm(htmlmod.unescape(re.sub(r"<[^>]+>", " ", SUPPORT)))
for false_sentence in ("With Premium, iCloud sync keeps your habits synchronized across all your devices automatically.",
                       "With Premium, iCloud sync keeps your habits in sync across all your iPhone and iPad devices.",
                       "Your streak will reset, but don't worry!"):
    check(false_sentence not in SUPPORT_TEXT, f"support.html: still says {false_sentence!r}")
for s in sentences(re.sub(r"\s+", " ", SUPPORT_TEXT)):
    if re.search(r"\biCloud\b", s) and re.search(r"\bPremium\b", s):
        failures.append(f"support.html: a sentence ties iCloud to Premium: {s!r}")
support_emails = emails_in(SUPPORT)
check(support_emails == {SITE["contact_email"]}, f"support.html: email addresses {sorted(support_emails)}")

policy_emails = emails_in(POLICY)
check(policy_emails == {SITE["contact_email"]}, f"privacy-policy.html: email addresses {sorted(policy_emails)}")

# The landing's screenshots. Which piece of the app stands beside each
# pairing step and each shown feature is pinned here with the row's own
# heading, outside pages.json, so an emptied, moved or reordered list cannot
# drop an image or set it beside another row's words. Every file an <img>
# names, in src or srcset, is a whole WebP file in assets/shots; the hero's
# srcset is exactly its two sizes and no other image has one; and the width
# and height attributes are the src file's real size, so the page reserves
# the right space before the image loads.
PINNED_SHOT_DIR = "/assets/shots/"
PINNED_HERO_SHOT = "partners-2026-11-09"
PINNED_STEP_PIECES = [("Send one invite link", "pair-connected-2026-11-09-840.webp"),
                      ("Check in as usual", "pair-completed-2026-11-09-840.webp"),
                      ("Hear back from them", "pair-nudge-2026-11-09-840.webp")]
PINNED_FEATURE_PIECES = [("Track any habit your way", "today-progress-2026-11-09-840.webp"),
                         ("Keep the streak alive", "celebration-card-2026-11-09-840.webp"),
                         ("See the whole year", "year-grid-2026-11-09-840.webp")]
PINNED_TEXT_FEATURES = ["Focus with a built-in timer", "Get reminders that change", "Glance from the home screen"]


def webp_size(path: "pathlib.Path") -> "tuple[int, int] | None":
    """Pixel size of a WebP file, or None when the file is not a whole one:
    the RIFF length must be the file's own, the first chunk must lie inside
    the file, and its header must carry the format's signature (lossy start
    code, lossless signature byte). Sizes are read as the container
    specification lays them out."""
    try:
        data = path.read_bytes()
    except (OSError, ValueError):
        return None
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        return None
    kind, size = data[12:16], int.from_bytes(data[16:20], "little")
    if 20 + size > len(data):
        return None
    body = data[20:20 + size]
    if kind == b"VP8 ":
        if len(body) < 10 or body[3:6] != b"\x9d\x01\x2a" or body[0] & 1:
            return None
        return (int.from_bytes(body[6:8], "little") & 0x3FFF, int.from_bytes(body[8:10], "little") & 0x3FFF)
    if kind == b"VP8L":
        if len(body) < 5 or body[0] != 0x2F:
            return None
        bits = int.from_bytes(body[1:5], "little")
        return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    if kind == b"VP8X":
        # An extended file is whole only when an image chunk follows the header
        if size != 10 or not any(tag in data[30:] for tag in (b"VP8 ", b"VP8L", b"ANMF")):
            return None
        return (int.from_bytes(body[4:7], "little") + 1, int.from_bytes(body[7:10], "little") + 1)
    return None


def shot_file(url: str) -> "pathlib.Path | None":
    prefix = PINNED_BASE_URL + PINNED_SHOT_DIR
    name = url[len(prefix):] if url.startswith(prefix) else ""
    return ROOT / "assets" / "shots" / name if re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.webp", name) else None


def under(node, cls: str) -> bool:
    """Whether an ancestor of the node (not the node itself) carries the class."""
    node = node.parent
    while node is not None:
        if cls in node.classes:
            return True
        node = node.parent
    return False


def shot_name(node) -> str:
    return (node.attrs.get("src") or "").rsplit("/", 1)[-1]


_landing_root = parse(FRESH["index.html"])
_all_imgs = [n for n in _landing_root.walk() if n.tag == "img"]
_shots = [n for n in _all_imgs if PINNED_SHOT_DIR in (n.attrs.get("src") or "") or PINNED_SHOT_DIR in (n.attrs.get("srcset") or "")]
for _n in _all_imgs:
    if _n not in _shots:
        check(not _n.attrs.get("srcset"), f"index.html: image {_n.attrs.get('src')!r} carries a srcset; only the hero screenshot has one")
        check(bool(re.search(r"\.(png|svg|webp)$", urlsplit(_n.attrs.get("src") or "").path)),
              f"index.html: image src {_n.attrs.get('src')!r} is not an image file")
_hero_set = (f"{PINNED_BASE_URL}{PINNED_SHOT_DIR}{PINNED_HERO_SHOT}-600.webp 600w, "
             f"{PINNED_BASE_URL}{PINNED_SHOT_DIR}{PINNED_HERO_SHOT}-900.webp 900w")
for _n in _shots:
    _src = _n.attrs.get("src") or ""
    _file = shot_file(_src)
    _real = webp_size(_file) if _file else None
    check(_real is not None, f"index.html: image {_src!r} is not a whole WebP file in assets/shots")
    if _real is not None:
        _attrs = (_n.attrs.get("width"), _n.attrs.get("height"))
        check(_attrs == (str(_real[0]), str(_real[1])),
              f"index.html: image {_src!r} is {_real[0]} by {_real[1]} but its attributes say {_attrs[0]} by {_attrs[1]}")
    _in_hero = under(_n, "hero-shot")
    check((_n.attrs.get("srcset") or "") == (_hero_set if _in_hero else ""),
          f"index.html: image {_src!r} has srcset {_n.attrs.get('srcset')!r}, want {(_hero_set if _in_hero else '')!r}")
    for _cand in [c.split() for c in (_n.attrs.get("srcset") or "").split(",") if c.strip()]:
        _cfile = shot_file(_cand[0])
        _creal = webp_size(_cfile) if _cfile else None
        check(_creal is not None, f"index.html: srcset candidate {_cand[0]!r} is not a whole WebP file in assets/shots")
        check(len(_cand) == 2 and _creal is not None and _cand[1] == f"{_creal[0]}w",
              f"index.html: srcset candidate {' '.join(_cand)!r} does not carry its file's real width")
        check(_creal is None or _real is None or abs(_creal[0] * _real[1] - _creal[1] * _real[0]) <= max(_creal[0], _real[0]),
              f"index.html: srcset candidate {_cand[0]!r} has another shape than its src")
    # Only the hero's lifted copy is decorative; every other screenshot is described
    _decorative = _in_hero and under(_n, "lift")
    check(bool((_n.attrs.get("alt") or "").strip()) != _decorative,
          f"index.html: image {_src!r}: the hero's lifted copy has an empty alt, every other screenshot has alt text")
    check(_n.attrs.get("aria-hidden") is None, f"index.html: image {_src!r} is hidden from assistive technology")


def piece_rows_of(cls: str) -> "list[tuple[str, list[str]]]":
    """(heading, image file names) for each row of the landing list with the class."""
    out = []
    for li in (n for n in _landing_root.walk() if n.tag == "li" and n.parent is not None and cls in n.parent.classes):
        heads = [n.text().strip() for n in li.walk() if n.tag == "h3"]
        out.append((" | ".join(heads), [shot_name(n) for n in li.walk() if n.tag == "img"]))
    return out


check(piece_rows_of("steps") == [(h, [f]) for h, f in PINNED_STEP_PIECES],
      f"index.html: the pairing steps are {piece_rows_of('steps')}, pinned {PINNED_STEP_PIECES}")
check(piece_rows_of("shown") == [(h, [f]) for h, f in PINNED_FEATURE_PIECES],
      f"index.html: the shown features are {piece_rows_of('shown')}, pinned {PINNED_FEATURE_PIECES}")
check(piece_rows_of("more") == [(h, []) for h in PINNED_TEXT_FEATURES],
      f"index.html: the text features are {piece_rows_of('more')}, pinned {PINNED_TEXT_FEATURES}")
_hero_imgs = [n for n in _shots if under(n, "hero-shot")]
check([shot_name(n) for n in _hero_imgs] == [f"{PINNED_HERO_SHOT}-600.webp"] * 2 and [under(n, "lift") for n in _hero_imgs] == [False, True],
      f"index.html: the hero shows {[shot_name(n) for n in _hero_imgs]}, want the screenshot and then its lifted copy of {PINNED_HERO_SHOT}")
check(len(_shots) == 8, f"index.html: {len(_shots)} screenshots, want the hero's two, three steps and three features")

# k. The inline link form in pages.json never reaches a page unrendered.
for rel, text in FRESH.items():
    for m in re.finditer(r"\[[^\[\]\n]+\]\([^)\s]*\)", text):
        failures.append(f"{rel}: inline link markup left unrendered: {m.group(0)!r}")

check(FRESH["robots.txt"] == f"User-agent: *\nAllow: /\nSitemap: {PINNED_BASE_URL}/sitemap.xml\n", "robots.txt: content changed")

# p. vercel.json keeps the routing every URL above depends on: clean URLs
#    without a trailing slash, the invite rewrite, the association file's
#    content type, and a year of caching for /assets (safe because published
#    assets never change in place, see q).
try:
    VERCEL = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
except (OSError, ValueError) as e:
    VERCEL = {}
    failures.append(f"vercel.json: does not parse: {e}")
check(sorted(VERCEL) == ["cleanUrls", "headers", "rewrites", "trailingSlash"],
      f"vercel.json: keys are {sorted(VERCEL)}; a new key such as outputDirectory can change what is deployed")
check(VERCEL.get("cleanUrls") is True, "vercel.json: cleanUrls is not true")
check(VERCEL.get("trailingSlash") is False, "vercel.json: trailingSlash is not false")
check({"source": "/invite/:code", "destination": "/invite"} in VERCEL.get("rewrites", []), "vercel.json: the /invite/:code rewrite is missing")
check(VERCEL.get("rewrites") == [{"source": "/invite/:code", "destination": "/invite"}],
      f"vercel.json: rewrites are {VERCEL.get('rewrites')}, want only the invite rewrite")
headers = {h.get("source"): {x.get("key", "").lower(): x.get("value") for x in h.get("headers", [])} for h in VERCEL.get("headers", [])}
check(headers.get("/.well-known/apple-app-site-association", {}).get("content-type") == "application/json",
      "vercel.json: the association file is not served as application/json")
check(headers == {"/.well-known/apple-app-site-association": {"content-type": "application/json"},
                  "/assets/(.*)": {"cache-control": "public, max-age=31536000, immutable"}},
      f"vercel.json: header rules are {headers}; an added rule such as X-Robots-Tag can block indexing")
check(VERCEL.get("headers") == [
    {"source": "/.well-known/apple-app-site-association", "headers": [{"key": "content-type", "value": "application/json"}]},
    {"source": "/assets/(.*)", "headers": [{"key": "cache-control", "value": "public, max-age=31536000, immutable"}]},
], "vercel.json: header rules differ from the pinned rules (a condition such as has or missing would make them conditional)")
asset_cache = headers.get("/assets/(.*)", {}).get("cache-control", "")
check(asset_cache == "public, max-age=31536000, immutable", f"vercel.json: /assets cache-control is {asset_cache!r}")
check(not any(src != "/assets/(.*)" and "cache-control" in hs for src, hs in headers.items()),
      "vercel.json: a long cache header outside /assets")

# q. The invite flow's files are present: the association file names the app
#    and the /invite/* path, and the invite page exists.
try:
    AASA = json.loads((ROOT / ".well-known" / "apple-app-site-association").read_text(encoding="utf-8"))
    details = AASA["applinks"]["details"]
    check(any("DABJS94K9F.com.vishutdhar.habitflame" in d.get("appIDs", []) and {"/": "/invite/*"} in d.get("components", [])
              for d in details), "apple-app-site-association: the app or the /invite/* component is missing")
except (OSError, ValueError, KeyError, TypeError) as e:
    failures.append(f"apple-app-site-association: {type(e).__name__}: {e}")
check((ROOT / "invite.html").is_file(), "invite.html: missing")
check((ROOT / "styles.css").is_file(), "styles.css: missing; the invite page uses it")
check("redirects" not in VERCEL, "vercel.json: redirects can move a page or the invite path; the site uses none")
for rd in VERCEL.get("redirects", []) + [r for r in VERCEL.get("rewrites", []) if r.get("source") != "/invite/:code"]:
    src = rd.get("source", "")
    check(not (src.startswith("/invite") or src.startswith("/.well-known") or src.startswith("/(") or src.startswith("/:")),
          f"vercel.json: {src!r} can capture the invite or association paths")
# The rendered page, which check a holds byte equal to the committed file, and
# its hand written source.
INVITE = FRESH.get("invite.html", "")
try:
    INVITE_SOURCE = (ROOT / "scripts" / "invite.html").read_text(encoding="utf-8")
except OSError:
    INVITE_SOURCE = ""
# The invite page's own flow: it reads the code from the path and builds the
# app deep link from it.
# The invite page is hand written in scripts/invite.html; the generator only
# fills in its App Store links. The source's bytes are pinned so a change to
# its code parsing or deep link is a deliberate edit here too; update the
# hash only after testing the invite flow on a device.
# The association file and the invite page's stylesheet are pinned the same
# way: Apple reads the components in order, so an added exclusion would stop
# invite links opening the app while every presence check still passed.
AASA_SHA256 = "338141d1c33ec3d86900cad72371a18e08a8ce2c274a7d66ed5b49514ef75968"
STYLES_SHA256 = "0e8a6071735c647d326f9cc3a9744ab098b389698eed339afa15ee50247de639"
for name, want in ((".well-known/apple-app-site-association", AASA_SHA256), ("styles.css", STYLES_SHA256)):
    here = ROOT / name
    check(here.is_file() and hashlib.sha256(here.read_bytes()).hexdigest() == want, f"{name}: changed; test the invite flow, then update its pinned hash")
# The invite flow lives in the page's one inline script element. Its bytes
# are pinned on their own as well, in the source and in the rendered page, so
# a change to the page's chrome (its palette, its header) can move
# INVITE_SOURCE_SHA256 while this hash proves the flow is untouched.
INVITE_SCRIPT_SHA256 = "37e4a895749b5380dac55cdaa7cd7351cd4f74d6bfadb9771dbcd663332745c0"
for _name, _text in (("scripts/invite.html", INVITE_SOURCE), ("invite.html", INVITE)):
    _invite_scripts = re.findall(r"<script>(.*?)</script>", _text, re.S)
    check(len(_invite_scripts) == 1 and hashlib.sha256(_invite_scripts[0].encode("utf-8")).hexdigest() == INVITE_SCRIPT_SHA256,
          f"{_name}: the invite script changed; test the invite flow on a device, then update INVITE_SCRIPT_SHA256")
# The invite page's stylesheet carries the same palette as site.css.
try:
    _styles_root = re.search(r"(?m)^:root\s*\{([^}]*)\}", (ROOT / "styles.css").read_text(encoding="utf-8"))
    _invite_env = css_vars(_styles_root.group(1)) if _styles_root else {}
    _site_env = css_vars(root_m.group(1)) if root_m else {}
    for _token in ("ground", "surface", "surface-2", "ink", "body", "muted", "line", "line-strong", "ember", "ember-hover", "on-ember"):
        check(_invite_env.get(_token) == _site_env.get(_token),
              f"styles.css: --{_token} is {_invite_env.get(_token)!r}, site.css has {_site_env.get(_token)!r}")
except OSError:
    pass
check(f'<meta name="theme-color" content="{PINNED_PALETTE["ground"]}">' in INVITE,
      f"invite.html: theme-color is not the ground {PINNED_PALETTE['ground']}")
INVITE_SOURCE_SHA256 = "cf18aa75b0d8ec26b1b2b8e9f856ffb59e605f5839e44deca3a8c2500f06e98d"
check(hashlib.sha256(INVITE_SOURCE.encode("utf-8")).hexdigest() == INVITE_SOURCE_SHA256,
      "scripts/invite.html: changed; test the invite flow, then update INVITE_SOURCE_SHA256")
for marker in ('window.location.pathname', '"habitflame://invite?code="', 'id="open-app-btn"', 'id="code-value"'):
    check(marker in INVITE, f"invite.html: missing {marker!r}")
# Its three App Store links (the download step, the fallback and the footer
# badge) all come from the campaign config, checked with every page's in s.
check(INVITE_SOURCE.count('href="{{app_store_url}}"') == 3 and "apps.apple.com" not in INVITE_SOURCE,
      "scripts/invite.html: the App Store links are not the three {{app_store_url}} placeholders")
for m in re.finditer(r'(?:href|src)="(/[^"#?]*)', INVITE):
    path_part = m.group(1).lstrip("/")
    target = ROOT / ("index.html" if path_part == "" else path_part)
    check(target.is_file() or (ROOT / (path_part + ".html")).is_file(), f"invite.html: {m.group(1)} does not resolve to a file")
for m in re.finditer(r'content="https://habitflame\.vishutdhar\.com(/[^"]+)"', INVITE):
    check((ROOT / m.group(1).lstrip("/")).is_file(), f"invite.html: {m.group(1)} does not resolve to a file")

# r. Published assets never change in place: /assets is cached for a year, so
#    a changed file needs a new name. Compared with the baseline ref; skipped
#    without one.
if BASELINE is not None:
    listed = git("ls-tree", "-r", "--name-only", BASELINE, "--", "assets")
    for name in (listed or b"").decode().splitlines():
        here = ROOT / name
        check(here.is_file(), f"{name}: a published asset was removed")
        if here.is_file():
            check(here.read_bytes() == git("show", f"{BASELINE}:{name}"), f"{name}: changed in place; publish a new file name instead")

# ---- Report ------------------------------------------------------------------
counts: dict[str, int] = {}
for value in DATES.values():
    counts[str(value)] = counts.get(str(value), 0) + 1
print("sitemap lastmod " + ", ".join(f"{d} ({n} entries)" for d, n in sorted(counts.items())))
for line in contrast_lines:
    print(line)
for name, n in word_counts:
    print(f"words  {n:5d}  {name}")
for line in skip_lines:
    print(line)
for note in notes:
    print(f"note   {note}")
if failures:
    for f in failures:
        print(f"FAIL   {f}")
    print(f"{len(failures)} failure(s)")
    sys.exit(1)
print(f"OK: {len(HTML_PAGES)} pages, {len(FRESH)} generated files, 0 failures")
