"""App Store campaign links, in both states of the provider token.

The generator adds Apple's campaign parameters to every App Store link only
when site.app_store_campaign.pt is set. These tests render the site with the
token empty and with a token set, and run the site gate on a copy of the
repository in each state, to show the gate pins both: once the token is set,
a page whose link lacks it fails; while it is empty, a page whose link
carries one fails.

  python3 -m unittest discover -s scripts/tests
"""
import pathlib
import re
import types
import unittest
from html.parser import HTMLParser
from urllib.parse import urlsplit

from gate_copy import GateCopy

ROOT = pathlib.Path(__file__).resolve().parents[2]
GEN_PATH = ROOT / "scripts" / "build-pages.py"
LISTING = "https://apps.apple.com/us/app/habit-flame-streak-tracker/id6756961710"
INVITE_LISTING = "https://apps.apple.com/app/id6756961710"
# A made up provider token; the real one is the owner's to read in App Store
# Connect.
TOKEN = "123456"
EXPECTED_CT = {
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


def load_generator(pt: "str | None" = None) -> types.ModuleType:
    """A fresh copy of the generator, as the gate loads it, with the provider
    token replaced when one is given."""
    gen = types.ModuleType("gen")
    gen.__file__ = str(GEN_PATH)
    exec(compile(GEN_PATH.read_text(encoding="utf-8"), gen.__file__, "exec"), gen.__dict__)
    if pt is not None:
        gen.CAMPAIGN["pt"] = pt
    return gen


class _StoreRefs(HTMLParser):
    """Every element whose href or src points at the store host, as
    (tag, attribute, decoded value)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value and urlsplit(value).hostname == "apps.apple.com":
                self.refs.append((tag, name, value))

    handle_startendtag = handle_starttag


def store_refs(text: str) -> list[tuple[str, str, str]]:
    parser = _StoreRefs()
    parser.feed(text)
    parser.close()
    return parser.refs


def html_outputs(files: dict[str, str]) -> dict[str, str]:
    return {rel: text for rel, text in files.items() if rel.endswith(".html")}


def listing_for(rel: str) -> str:
    return INVITE_LISTING if rel == "invite.html" else LISTING


class CampaignLinks(unittest.TestCase):
    def test_every_page_has_a_campaign_token(self):
        files = html_outputs(load_generator("").outputs())
        self.assertEqual(sorted(files), sorted(EXPECTED_CT))
        self.assertEqual(load_generator("").campaign_tokens(), EXPECTED_CT)
        for ct in EXPECTED_CT.values():
            self.assertLessEqual(len(ct), 30, f"{ct} is longer than Apple's 30 character limit")

    def test_an_empty_provider_token_leaves_every_link_the_bare_listing(self):
        for rel, text in html_outputs(load_generator("").outputs()).items():
            refs = store_refs(text)
            self.assertTrue(refs, f"{rel} has no App Store link")
            for tag, attr, value in refs:
                self.assertEqual((tag, attr, value), ("a", "href", listing_for(rel)), rel)
            self.assertNotIn("pt=", text, rel)
            self.assertNotIn("ct=site-", text, rel)

    def test_a_provider_token_reaches_every_link_with_the_page_ct(self):
        for rel, text in html_outputs(load_generator(TOKEN).outputs()).items():
            refs = store_refs(text)
            self.assertTrue(refs, f"{rel} has no App Store link")
            want = f"{listing_for(rel)}?pt={TOKEN}&ct={EXPECTED_CT[rel]}&mt=8"
            for tag, attr, value in refs:
                self.assertEqual((tag, attr, value), ("a", "href", want), rel)
            # In the markup the separators are escaped, as an attribute needs.
            raw = want.replace("&", "&amp;")
            self.assertEqual(text.count(f'href="{raw}"'), len(refs), rel)

    def test_the_token_changes_nothing_but_the_store_links(self):
        bare = load_generator("").outputs()
        tagged = load_generator(TOKEN).outputs()
        self.assertEqual(sorted(bare), sorted(tagged))
        for rel in bare:
            ct = EXPECTED_CT.get(rel, "")
            restored = tagged[rel].replace(f"?pt={TOKEN}&amp;ct={ct}&amp;mt=8", "")
            self.assertEqual(restored, bare[rel], rel)

    def test_structured_data_names_the_listing_and_never_a_campaign(self):
        for pt in ("", TOKEN):
            landing = load_generator(pt).outputs()["index.html"]
            ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', landing, re.S).group(1)
            self.assertIn(f'"url": "{LISTING}"', ld)
            self.assertNotIn("pt=", ld)

    def test_a_malformed_campaign_config_stops_the_build(self):
        cases = {
            "letters in the provider token": lambda g: g.CAMPAIGN.__setitem__("pt", "12a4"),
            "a number instead of a string": lambda g: g.CAMPAIGN.__setitem__("pt", 123456),
            "a ct over 30 characters": lambda g: g.LANDING.__setitem__("ct", "site-" + "x" * 26),
            "capitals in a ct": lambda g: g.PAGES[0].__setitem__("ct", "Site-Guide"),
            "a ct with a space": lambda g: g.POLICIES[0].__setitem__("ct", "site support"),
            "two pages with one ct": lambda g: g.PAGES[1].__setitem__("ct", g.PAGES[0]["ct"]),
            "a page without a ct": lambda g: g.PAGES[2].pop("ct"),
            "the invite page without a ct": lambda g: g.INVITE.pop("ct"),
        }
        for label, breaks in cases.items():
            with self.subTest(label):
                gen = load_generator(TOKEN)
                breaks(gen)
                with self.assertRaises((ValueError, KeyError)):
                    gen.outputs()


class GateInBothStates(GateCopy, unittest.TestCase):
    """The site gate, run on a copy of the repository, in each state of the
    provider token. The gate checks a fresh render and holds every committed
    page byte equal to it, so its link rules are shown failing on a copy
    whose generator was broken, and the byte rule on a page edited by hand."""

    def test_with_a_token_set_the_gate_passes(self):
        self.set_token(TOKEN)
        gate = self.build_and_gate()
        self.assertEqual(gate.returncode, 0, gate.stdout)

    def test_with_a_token_set_the_gate_fails_a_page_built_without_it(self):
        self.set_token(TOKEN)
        self.edit("scripts/build-pages.py", 'if not CAMPAIGN["pt"]:', 'if not CAMPAIGN["pt"] or ct == "site-support":')
        gate = self.build_and_gate()
        self.assertEqual(gate.returncode, 1)
        self.assertIn(f"support.html: App Store a '{LISTING}'", gate.stdout)

    def test_with_a_token_set_the_gate_fails_a_page_built_with_another_pages_ct(self):
        self.set_token(TOKEN)
        self.edit("scripts/build-pages.py", 'store_url(INVITE["ct"], INVITE["app_store_url"])',
                  'store_url("site-home", INVITE["app_store_url"])')
        gate = self.build_and_gate()
        self.assertEqual(gate.returncode, 1)
        self.assertIn(f"invite.html: App Store a '{INVITE_LISTING}?pt={TOKEN}&ct=site-home&mt=8'", gate.stdout)

    def test_with_the_token_empty_the_gate_passes(self):
        self.set_token("")
        gate = self.build_and_gate()
        self.assertEqual(gate.returncode, 0, gate.stdout)

    def test_with_the_token_empty_the_gate_fails_a_page_built_with_campaign_parameters(self):
        self.set_token("")
        self.edit("scripts/build-pages.py", 'if not CAMPAIGN["pt"]:', 'if not CAMPAIGN["pt"] and ct != "site-home":')
        gate = self.build_and_gate()
        self.assertEqual(gate.returncode, 1)
        self.assertIn(f"index.html: App Store a '{LISTING}?pt=&ct=site-home&mt=8'", gate.stdout)

    def test_the_gate_fails_a_store_url_written_anywhere_but_a_link(self):
        self.set_token(TOKEN)
        self.edit("scripts/template.html", "</main>", f"<p>{LISTING}</p>\n</main>")
        gate = self.build_and_gate()
        self.assertEqual(gate.returncode, 1)
        self.assertIn("streak-tracker-app.html: the store host appears", gate.stdout)

    def test_a_committed_page_edited_by_hand_fails_the_gate(self):
        self.set_token(TOKEN)
        self.assertEqual(self.build_and_gate().returncode, 0)
        tagged = f"?pt={TOKEN}&amp;ct=site-support&amp;mt=8"
        self.edit("support.html", f'href="{LISTING}{tagged}"', f'href="{LISTING}"')
        gate = self.run_script("verify-pages.py")
        self.assertEqual(gate.returncode, 1)
        self.assertIn("support.html: differs from a fresh render", gate.stdout)

if __name__ == "__main__":
    unittest.main()
