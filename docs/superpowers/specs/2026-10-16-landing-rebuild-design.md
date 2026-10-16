# HabitFlame landing rebuild: design plan

Date: 2026-10-16. Site: https://habitflame.vishutdhar.com/ (Vercel project habitflame-web).

## Subject, audience, job

- Subject: an iPhone habit tracker built around one accountability partner. You pair
  with one person through an invite link; with Premium each shared habit you complete
  in the app reaches their phone as it happens, and either of you can react or nudge.
- Audience: people who have dropped habits before and know they keep promises to other
  people better than to themselves. Couples, friends, siblings, training buddies. Adults
  on iPhone, mostly 20 to 45, who would never install something that looks like a toy.
- Primary job: an App Store tap, or sending the page to the one person you would pair
  with. Both actions sit in the hero and again at the end.

## Tokens

| Name         | Hex                       | Role                                              |
|--------------|---------------------------|---------------------------------------------------|
| ground       | #07080B                   | page ground                                       |
| surface      | #0F1116 / #15181F         | header bar, device bezel, quiet fills             |
| ink          | #E6E8EB                   | headings, the price row                           |
| body         | #CDD0D4                   | running text                                      |
| muted        | #9BA1A8                   | fine print only (captions, footer, store note)   |
| line         | rgba(255,255,255,0.11)    | every hairline                                    |
| ember        | #FFBE5C                   | the one accent: primary button, the annotation    |

The ember is sampled from the app icon. The icon's ground is a red orange (hue 5 to 15)
and its flame averages #FCB24D (hue 35). A true orange cannot carry dark ink at APCA Lc 75,
so the accent is the icon's flame tone lifted to #FFBE5C (hue 36): ember text on ground
measures Lc 74.4 and ground ink on an ember button Lc 75.3. The hover tone is a lighter
step of the same hue, #FFCB7A.

## Type

One family: Bricolage Grotesque, self hosted as one variable woff2 subset to Latin with
two axes kept, weight 400 to 700 and optical size 12 to 96. With font-optical-sizing on,
the 16px body draws the calm 12pt cut and the 56px headline draws the display cut with
its ink traps and lively joins. That split is the reason for this face: a grotesque that
reads like a person at headline size and like plain text at body size suits an app about
one human keeping another honest. Weights: 400 for text, 700 for headings and the price.
No second family, no mono, no all caps.

Scale (from the shared brief): body 16 to 17 at lh 1.55, lede 18 to 20 at 1.45, h2 28 to
40 at 1.12, h1 34 to 56 at 1.06, price row at h1 size. Measures: body 30em, lede 28em,
h1 12em.

## Layout

Centred column, 1120px max, fluid gutter 20 to 32px, 8px rhythm, every block left
aligned. Text to media is 7 to 5 in the hero and again in the features section, so the
two screenshots sit on the same vertical line.

```
+------------------------------------------------------------------------------+
| [icon] HabitFlame                               Guides   Support  [App Store]|
+------------------------------------------------------------------------------+
|                                                   .--------------.           |
| Habits stick when                                 | 9:41         |           |
| someone is watching.                              | Partners     |           |
|                                                   | (J) Jordan   |           |
| Pair with one person. With Premium, each   [ember |=Jordan sent==|=ring]     |
| shared habit ... Premium is $9.99, paid    chip]  | Evening Run  |           |
| once, no subscription.                            | Journaling   |           |
|                                                   | hit 10 days  |           |
| [Download on the App Store] [Send this page]      |              |           |
| For iPhone and iPad.                              |              |           |
+----------------------------------------------- phone sits on this hairline --+
| How pairing works            1  Send one invite link            .........    |
|                              2  Check in as usual               .........    |
|                              3  They answer                     .........    |
+------------------------------------------------------------------------------+
| The rest of a good habit app                                                 |
| Track any habit your way   ......................     .--------------.       |
| ------------------------------------------------      | Today        |       |
| Keep the streak alive      ......................     | (real shot,  |       |
| ------------------------------------------------      |  sticky)     |       |
| See the whole year ...                                '--------------'       |
+------------------------------------------------------------------------------+
| What it costs                                                                |
| $9.99 paid once, no subscription.          <- set at h1 size, ink not ember  |
| Free     The free version includes up to 5 habits ...                        |
| Premium  Premium adds unlimited habits ...                                   |
+------------------------------------------------------------------------------+
| Guides (rows: title, one line)                                               |
| Questions (rows: question left, answer right)                                |
| Start with one habit and one person.  [Download on the App Store] [Send]     |
+------------------------------------------------------------------------------+
| Support  Privacy  Terms  support@freedom-terminal.com   [App Store badge]    |
| A Freedom Terminal product                       (c) 2026 HabitFlame         |
+------------------------------------------------------------------------------+
```

At 390px everything stacks: text, then the hero shot at 60% of the screen width, still
standing on its hairline; the feature screenshot drops below the rows.

## The one memorable element

The partner moment. The hero object is the real Partners tab from the app: Jordan's
card, then Jordan's flame for your Morning Run, then Jordan's own check ins with their
streaks. The shot is cropped at the bottom and stands on the hero's bottom hairline like
a phone held up out of the page. On load it rises once out of that line, and then a thin
ember ring settles around the one row that matters, "Jordan sent a flame for Morning
Run", with a small ember label beside it in page type: "Jordan saw your run." The
headline names the idea, the screenshot proves it, the ring points at the proof. That
is the only accent area of any size and the only motion on the page; prefers reduced
motion shows the settled state with no movement.

Everything else is quiet: rows and hairlines, ink and body grey, no cards, no glow, no
icons beside feature names, no flame drawings.

## Review against the defaults, and what changed

Checked the plan against the generic defaults (cream plus serif plus terracotta; near
black plus one acid accent; broadsheet hairlines everywhere; the SaaS card kit; template
chrome) and against the current page.

1. Near black plus one bright accent is the second default, and the brief fixes the
   ground at #07080B. The difference has to come from the accent and the type. The
   accent is not a stock acid or vermilion: it is the icon's own flame tone, and it is
   used in exactly two places (the primary button and the annotation), so the page
   reads as ink on near black with one warm point of light. Changed: dropped the
   earlier idea of ember links and ember headings; links are ink with an underline.
2. Broadsheet hairlines everywhere was the risk of "rows and hairlines". Changed: a
   hairline appears only where it separates two items of the same kind (feature rows,
   tiers, guides, questions) or where the hero shot stands. Sections are separated by
   space, not by a rule on every section top as the current page does.
3. The current page leads with a drawn ledger of flame shaped cells with a glow and a
   staggered animation. It is invented UI, it reads as decoration, and the brief bans
   flame illustrations and glow. Changed: replaced by the real partner screenshot.
4. The current page set its h1 at 64px weight 800 in Plus Jakarta Sans from Google
   Fonts, and its section heads in 800. Changed: one self hosted family, headings at
   700, h1 capped at 56px, no runtime font request.
5. Template chrome check: no eyebrows above headings, no tracked caps, no middle dot
   meta strings, no arrows on links, no mono for the invite code. The only numbers used
   as markers are the three pairing steps, which are a real sequence.
6. The current pricing block is a rounded card with the price buried mid sentence.
   Changed: the price is a row set at h1 size in ink, the one place the page states
   "paid once, no subscription" apart from the hero lede.
7. Template check on the hero: a big number with a small label and a gradient accent
   was considered for the price and rejected; the price row is a sentence, not a stat.

## Constraints from the repo

- Every page, the landing included, is generated by scripts/build-pages.py from
  scripts/pages.json and scripts/template.html, and scripts/verify-pages.py checks the
  copy against facts pinned from the app (numbers, Premium only features, banned and
  retired phrases, partner visibility wording). The landing copy is written to pass
  those checks, and the checker gains APCA checks for the brief's two contrast rules.
- Published files under /assets are cached for a year and never change in place, so the
  new font, screenshots, icons and share card are new files.
- invite.html keeps its script byte for byte; only its markup chrome and its stylesheet
  (styles.css) change, and their pinned hashes move with that change.

## Changes after the screenshot critique

The plan above was built, captured at 1920, 1440 and 390 wide, and changed where the
captures showed a problem. The wireframe stays as the starting point; this section is
what shipped.

1. Split rows (title left, text right) left a dead band under every short title, and
   the FAQ hairlines broke across the column gap. Every text section now uses a left
   rail instead: the heading and intro sit in the 5 part column and stay in view while
   the list scrolls, and the rows stack title over text in the 7 part column, so each
   hairline runs unbroken.

   ```
   How pairing works        1  Send one invite link
   Choose the one person       .............................
                            -------------------------------------
                            2  Check in as usual
   ```

2. The Today screenshot moved from the right column into the rail, under "Everything
   else a habit needs", so the section follows the same rail as the others while the
   hero keeps the only shot on the right. It is its own grid item: under the heading on
   wide screens, after the six rows on a phone, so the rows come first there.
3. The price row read "Premium is $9.99, paid / once, no subscription." Changed: it breaks
   after the price, with "paid once, no subscription." on its own line in body ink at
   weight 400, still at h1 size.
4. The leader line from the callout to the ring was a separate draw animation that a
   full page capture dropped. It now fades in with the callout text.
5. At 390 the header nav wrapped and collided with the brand, and the skip link's
   fractional height left a one pixel ember line at the top. The header drops Guides
   below 480px and Support below 400px (both stay in the footer), and the skip link has a
   whole pixel height so its translateY(-100%) hides it fully.
6. Gaps of 12px became 16px to keep the 8px rhythm.
