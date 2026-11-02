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

    def test_a_selection_sentence_in_the_terms_without_premium_fails(self):
        self.edit("scripts/policies/terms-of-service.html", "<h2>Accountability Partners</h2>\n",
                  "<h2>Accountability Partners</h2>\n<p>You decide which habits to share with each partner.</p>\n")
        self.assert_gate_fails_with("terms-of-service.html: habit selection is Premium only")


class CompletionsReachThePartnerFromTheAppToday(GateCopy, unittest.TestCase):
    """A partner hears about a completion at once only when it is made in the
    app for today: a widget completion or a backfilled day sends no alert
    (HabitCompletionEffects, WidgetIntents). A sentence saying a completion
    reaches the partner the moment it happens, instantly or as it happens
    says so."""

    def add_paragraph(self, text: str) -> None:
        self.edit("scripts/pages.json", '{"h2": "Pairing with several friends"},',
                  '{"h2": "Pairing with several friends"},\n        {"p": "' + text + '"},')

    def test_the_moment_without_the_qualification_fails(self):
        self.add_paragraph("With Premium, each shared habit you complete reaches your friends the moment you do it.")
        self.assert_gate_fails_with("habit-tracker-with-friends.html: a completion reaches the partner at once without 'in the app for today'")

    def test_instantly_without_the_qualification_fails(self):
        self.add_paragraph("With Premium, your completions arrive on their phone instantly.")
        self.assert_gate_fails_with("habit-tracker-with-friends.html: a completion reaches the partner at once without 'in the app for today'")

    def test_as_it_happens_without_the_qualification_fails(self):
        self.add_paragraph("With Premium, they see each shared completion as it happens.")
        self.assert_gate_fails_with("habit-tracker-with-friends.html: a completion reaches the partner at once without 'in the app for today'")

    def test_the_qualified_sentence_passes(self):
        self.add_paragraph("With Premium, each shared habit you complete in the app for today reaches your friends the moment you do it.")
        self.assert_gate_passes()


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



FRIENDS = '{"h2": "Pairing with several friends"},'
STREAKS = '{"h2": "How streaks are counted"},'
AGREE = '{"h2": "Where they agree"},'


def add_block(case, anchor: str, block: str) -> None:
    """Insert one content block after a heading in pages.json."""
    case.edit("scripts/pages.json", anchor, anchor + "\n        " + block + ",")


class HiddenArticleContents(GateCopy, unittest.TestCase):
    """A hidden wrapper inside the article hides the article; inline styles are
    read the way a browser reads them."""

    def body(self, html: str) -> None:
        HiddenGuides.hide(self, NEW_GUIDES[0], BODY_OPEN, html)

    def test_a_hidden_wrapper_inside_the_article_fails(self):
        self.body("f'<div class=\"article-body\">\\n<div hidden>\\n{blocks}\\n</div>\\n</div>\\n'")
        self.assert_gate_fails_with(f"{NEW_GUIDES[0]}.html: the article is hidden")

    def test_display_none_split_across_lines_fails(self):
        self.body("f'<div class=\"article-body\" style=\"display:\\nnone\">\\n{blocks}\\n</div>\\n'")
        self.assert_gate_fails_with(f"{NEW_GUIDES[0]}.html: the article is hidden")

    def test_a_later_display_block_wins_and_passes(self):
        self.body("f'<div class=\"article-body\" style=\"display:none;display:block\">\\n{blocks}\\n</div>\\n'")
        self.assert_gate_passes()


class InstantDeliveryWording(GateCopy, unittest.TestCase):
    """Every way of saying a completion reaches the partner at once needs the
    qualification; a sentence denying it does not."""

    WANT = "habit-tracker-with-friends.html: a completion reaches the partner at once without 'in the app for today'"

    def claim(self, text: str) -> None:
        add_block(self, FRIENDS, '{"p": "' + text + '"}')

    def test_right_away_fails(self):
        self.claim("With Premium, your partner sees each shared completion right away.")
        self.assert_gate_fails_with(self.WANT)

    def test_live_fails(self):
        self.claim("With Premium, your partner sees each shared completion live.")
        self.assert_gate_fails_with(self.WANT)

    def test_immediately_fails(self):
        self.claim("With Premium, your partner sees each shared completion immediately.")
        self.assert_gate_fails_with(self.WANT)

    def test_in_real_time_fails(self):
        self.claim("With Premium, your partner sees each shared completion in real time.")
        self.assert_gate_fails_with(self.WANT)

    def test_real_time_with_a_hyphen_fails(self):
        self.claim("With Premium, your partner gets real-time completions.")
        self.assert_gate_fails_with(self.WANT)

    def test_the_widget_denial_passes(self):
        self.claim("Completing a habit from a widget does not instantly notify your partner.")
        self.assert_gate_passes()


class SelectionClaimsAndAdvice(GateCopy, unittest.TestCase):
    """Premium has to qualify the choice, not be denied by it; free claims
    fail; the competitor's own sentences and plain planning advice pass."""

    WANT = "habit selection is Premium only"

    def test_without_premium_is_not_a_qualification(self):
        add_block(self, FRIENDS, '{"p": "Free users can choose which habits to share without Premium."}')
        self.assert_gate_fails_with(f"habit-tracker-with-friends.html: {self.WANT}")

    def test_without_premium_alone_is_not_a_qualification(self):
        add_block(self, FRIENDS, '{"p": "You can choose which habits each friend follows without Premium."}')
        self.assert_gate_fails_with(f"habit-tracker-with-friends.html: {self.WANT}")

    def test_a_free_claim_fails_even_beside_premium(self):
        add_block(self, FRIENDS, '{"p": "Free users can choose which habits to share, just like Premium users."}')
        self.assert_gate_fails_with(f"habit-tracker-with-friends.html: {self.WANT}")

    def test_choose_the_habits_to_share_fails(self):
        add_block(self, FRIENDS, '{"p": "Choose the habits to share with each friend."}')
        self.assert_gate_fails_with(f"habit-tracker-with-friends.html: {self.WANT}")

    def test_a_comparison_sentence_naming_both_apps_is_not_exempt(self):
        add_block(self, AGREE, '{"p": "HabitShare and HabitFlame both let you choose which habits each friend follows."}')
        self.assert_gate_fails_with(f"habitflame-vs-habitshare.html: {self.WANT}")

    def test_planning_advice_passes(self):
        add_block(self, FRIENDS, '{"p": "Choose which habits you want to build before opening the app."}')
        self.assert_gate_passes()

    def test_an_explicit_free_denial_passes(self):
        add_block(self, FRIENDS, '{"p": "On the free version you cannot choose which habits to share."}')
        self.assert_gate_passes()


class WeeklyTargetMilestones(GateCopy, unittest.TestCase):
    """A weekly target's streak moves a week at a time (WeeklyStreakCalculator)
    and a milestone is celebrated only when the streak lands on it exactly,
    so copy may not promise a weekly target every milestone."""

    def test_promising_a_weekly_target_the_same_milestones_fails(self):
        add_block(self, STREAKS, '{"p": "A weekly target reaches the same milestones, just later."}')
        self.assert_gate_fails_with("streak-tracker-app.html: a weekly target is promised milestones it can step past")


class MilestonePlanWording(GateCopy, unittest.TestCase):
    """Week by week milestone promises in any wording need a daily
    qualification; equivalent qualifications and negated promises pass."""

    WANT = "streak-tracker-app.html: a week by week milestone plan without the daily qualification"

    def test_in_the_second_week_fails(self):
        add_block(self, STREAKS, '{"p": "In the second week you reach the 14 day milestone."}')
        self.assert_gate_fails_with(self.WANT)

    def test_after_two_weeks_fails(self):
        add_block(self, STREAKS, '{"p": "After two weeks you reach the 14 day milestone."}')
        self.assert_gate_fails_with(self.WANT)

    def test_assumes_a_daily_habit_qualifies(self):
        add_block(self, STREAKS, '{"p": "This plan assumes a daily habit. In the second week you reach the 14 day milestone."}')
        self.assert_gate_passes()

    def test_scheduled_days_only_qualifies(self):
        add_block(self, STREAKS, '{"p": "The streak counts scheduled days only. After two weeks you reach the 14 day milestone."}')
        self.assert_gate_passes()

    def test_a_negated_promise_passes(self):
        add_block(self, STREAKS, '{"p": "The 14 day milestone need not arrive in week two."}')
        self.assert_gate_passes()


class MeasureModuleStrings(GateCopy, unittest.TestCase):
    """measure.js prose is read as JavaScript would produce it: template
    interpolations are code, and escapes are decoded."""

    def code(self, line: str) -> None:
        self.edit("measure.js", "const MOBILE_BELOW = 768;", "const MOBILE_BELOW = 768;\n" + line)

    def test_subtraction_inside_an_interpolation_passes(self):
        self.code("const NOTE = `${769 - 1}`;")
        self.assert_gate_passes()

    def test_a_spaced_hyphen_in_template_text_fails(self):
        self.code("const NOTE = `views - ${769} clicks`;")
        self.assert_gate_fails_with("measure.js: spaced hyphen")

    def test_a_unicode_escaped_banned_word_fails(self):
        self.code("const NOTE = 'guaran\\u0074eed';")
        self.assert_gate_fails_with("measure.js: banned phrase 'guaranteed'")

    def test_a_braced_unicode_escape_is_decoded(self):
        self.code("const NOTE = 'guaran\\u{74}eed';")
        self.assert_gate_fails_with("measure.js: banned phrase 'guaranteed'")

    def test_a_hex_escaped_banned_word_fails(self):
        self.code("const NOTE = 'chall\\x65nge';")
        self.assert_gate_fails_with("measure.js: banned phrase 'challenge'")

if __name__ == "__main__":
    unittest.main()
