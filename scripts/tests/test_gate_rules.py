"""Gate rules shown failing on a broken copy of the repository.

Each test breaks one thing the site must never ship, in a fresh copy:
a guide hidden from readers, habit selection offered without Premium,
structured data that drifts from its pinned wording, a week by week
milestone plan without its daily qualification, and a measure.js with a
banned phrase, a spaced hyphen or a syntax error. The gate must fail each
with its own message, and pass the site as it is.

  python3 -m unittest discover -s scripts/tests
"""
import unittest

from gate_copy import GateCopy

GUIDE_OPEN = "'<div class=\"guide\">\\n'"
HEAD_OPEN = "'<header class=\"article-head\">\\n'"
BODY_OPEN = "f'<div class=\"article-body\">\\n{blocks}\\n</div>\\n'"
NEW_GUIDES = ("habit-tracker-with-friends", "new-year-habits-with-a-friend")


class HiddenGuides(GateCopy, unittest.TestCase):
    """Every generated page's h1, article and store button are visible."""

    def hide(self, slug: str, old: str, new: str) -> None:
        """Swap one of article_main's adjacent string literals for a choice
        between it and the hidden form, joined to its neighbours with +, so
        only the one guide renders hidden."""
        before = "" if old == GUIDE_OPEN else "+ "
        self.edit("scripts/build-pages.py", old, f"{before}({new} if page['slug'] == {slug!r} else {old}) +")
        built = self.run_script("build-pages.py")
        self.assertEqual(built.returncode, 0, f"the mutation must still build: {built.stderr}")

    def test_the_site_as_it_is_passes(self):
        self.assert_gate_passes()

    def wrapped_in_hidden(self, slug: str) -> None:
        self.hide(slug, GUIDE_OPEN, "'<div class=\"guide\" hidden>\\n'")
        self.assert_gate_fails_with(f"{slug}.html: the h1 is hidden", f"{slug}.html: the article is hidden",
                                    f"{slug}.html: the App Store button is hidden")

    def header_under_aria_hidden(self, slug: str) -> None:
        self.hide(slug, HEAD_OPEN, "'<header class=\"article-head\" aria-hidden=\"true\">\\n'")
        self.assert_gate_fails_with(f"{slug}.html: the h1 is hidden", f"{slug}.html: the App Store button is hidden")

    def body_set_to_display_none(self, slug: str) -> None:
        self.hide(slug, BODY_OPEN, "f'<div class=\"article-body\" style=\"display: none\">\\n{blocks}\\n</div>\\n'")
        self.assert_gate_fails_with(f"{slug}.html: the article is hidden")

    def test_the_friends_guide_wrapped_in_a_hidden_element_fails(self):
        self.wrapped_in_hidden(NEW_GUIDES[0])

    def test_the_new_year_guide_wrapped_in_a_hidden_element_fails(self):
        self.wrapped_in_hidden(NEW_GUIDES[1])

    def test_the_friends_guide_header_under_aria_hidden_fails(self):
        self.header_under_aria_hidden(NEW_GUIDES[0])

    def test_the_new_year_guide_header_under_aria_hidden_fails(self):
        self.header_under_aria_hidden(NEW_GUIDES[1])

    def test_the_friends_guide_body_set_to_display_none_fails(self):
        self.body_set_to_display_none(NEW_GUIDES[0])

    def test_the_new_year_guide_body_set_to_display_none_fails(self):
        self.body_set_to_display_none(NEW_GUIDES[1])


class HabitSelectionNeedsPremium(GateCopy, unittest.TestCase):
    """Choosing which habits each partner follows is a Premium feature
    (PartnerReachability.showsPushOptions is hasPro && isReachable)."""

    def test_a_selection_sentence_without_premium_fails(self):
        self.edit("scripts/pages.json", '{"h2": "Pairing with several friends"},',
                  '{"h2": "Pairing with several friends"},\n        {"p": "You can choose which habits each friend follows."},')
        self.assert_gate_fails_with("habit-tracker-with-friends.html: habit selection is Premium only")

    def test_premium_in_a_later_sentence_of_the_paragraph_is_too_late(self):
        self.edit("scripts/pages.json", '{"h2": "Pairing with several friends"},',
                  '{"h2": "Pairing with several friends"},\n        {"p": "You can choose which habits each friend follows. '
                  'Premium adds real-time partner updates."},')
        self.assert_gate_fails_with("habit-tracker-with-friends.html: habit selection is Premium only")

    def test_share_all_habits_without_premium_fails(self):
        self.edit("scripts/pages.json", '{"h2": "Pairing with several friends"},',
                  '{"h2": "Pairing with several friends"},\n        {"p": "Turn off Share All Habits to pick the ones you want."},')
        self.assert_gate_fails_with("habit-tracker-with-friends.html: habit selection is Premium only")

    def test_a_table_row_offering_selection_under_free_fails(self):
        self.edit("scripts/pages.json", '["Habits", "5", "Unlimited"],',
                  '["Habits", "5", "Unlimited"],\n            ["Choose habits per partner", "Included", "Included"],')
        self.assert_gate_fails_with("table row 'Choose habits per partner' offers habit selection under Free")


class StructuredDataWording(GateCopy, unittest.TestCase):
    """The app's structured data descriptions are pinned in the gate, so a
    change to pages.json alone cannot move them."""

    def test_a_changed_app_description_fails(self):
        self.edit("scripts/pages.json", '"app_description": "', '"app_description": "Track anything. ')
        self.assert_gate_fails_with("index.html: SoftwareApplication description is not the pinned text")

    def test_a_changed_premium_description_fails(self):
        self.edit("scripts/pages.json", '"premium_description": "', '"premium_description": "Everything, ')
        self.assert_gate_fails_with("index.html: Premium offer description is not the pinned text")


class WeekByWeekMilestones(GateCopy, unittest.TestCase):
    """Milestones reached by calendar week hold only for a habit done every
    day; streaks count scheduled days."""

    def test_a_week_plan_without_the_daily_qualification_fails(self):
        self.edit("scripts/pages.json", '{"h2": "How streaks are counted"},',
                  '{"h2": "How streaks are counted"},\n        {"ul": ["Week two: the 14 day milestone comes at the end of it."]},')
        self.assert_gate_fails_with("streak-tracker-app.html: a week by week milestone plan without the daily qualification")


class MeasureModuleHygiene(GateCopy, unittest.TestCase):
    """measure.js is deployed with the pages and held to the same copy rules
    in its comments and strings, and it must parse."""

    def test_a_banned_phrase_in_a_comment_fails(self):
        self.edit("measure.js", "// Site measurement:", "// Results guaranteed.\n// Site measurement:")
        self.assert_gate_fails_with("measure.js: banned phrase 'guaranteed'")

    def test_a_banned_phrase_in_a_string_fails(self):
        self.edit("measure.js", "const MOBILE_BELOW = 768;", "const MOBILE_BELOW = 768;\nconst NOTE = 'join the challenge';")
        self.assert_gate_fails_with("measure.js: banned phrase 'challenge'")

    def test_a_spaced_hyphen_in_a_comment_fails(self):
        self.edit("measure.js", "// Site measurement:", "// Page views - and clicks.\n// Site measurement:")
        self.assert_gate_fails_with("measure.js: spaced hyphen")

    def test_a_spaced_hyphen_in_a_string_fails(self):
        self.edit("measure.js", "const MOBILE_BELOW = 768;", "const MOBILE_BELOW = 768;\nconst NOTE = 'views - clicks';")
        self.assert_gate_fails_with("measure.js: spaced hyphen")

    def test_subtraction_in_code_is_not_a_spaced_hyphen(self):
        self.edit("measure.js", "const MOBILE_BELOW = 768;", "const MOBILE_BELOW = 769 - 1;")
        self.assert_gate_passes()

    def test_invalid_javascript_fails(self):
        self.edit("measure.js", "const MOBILE_BELOW = 768;", "const MOBILE_BELOW = 768;\nconst = ;")
        self.assert_gate_fails_with("measure.js: does not parse")


if __name__ == "__main__":
    unittest.main()
