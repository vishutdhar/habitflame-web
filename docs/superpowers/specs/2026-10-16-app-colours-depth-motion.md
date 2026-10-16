# HabitFlame landing, pass 2: the app's colours, depth and motion

Date: 2026-10-16. Owner, after seeing the rebuilt page live: "can we match the colors
of the app in the landing page and add some 3d stuff to them? also some animations?"

This pass changes three things on the page merged in #11 and leaves everything else
from the first design plan (2026-10-16-landing-rebuild-design.md) in force: the
proportions token set, rows and hairlines, one typeface, the copy, the footer, the
pricing row, the accessibility floor.

## 1. Palette

### Which scheme

The app is dark first and does not follow the system. A new install has no settings
record, and MainTabView.swift returns `.dark` for that case; UserSettings.swift stores
`appearanceModeRaw = "dark"` by default; the only appearance control in Settings is a
"Dark Mode" toggle (SettingsView.swift), which flips between dark and light and never
offers "system". Every store screenshot is the dark appearance.

So the page is dark only, declared with `color-scheme: dark`, and does not answer
`prefers-color-scheme: light`. A visitor whose phone is set to light still opens the app
to a black screen, so a light page would show them an app they will not see. The light
appearance is a choice the user makes inside the app, which a web page cannot read.

### Tokens and where each comes from

Sampled values were read pixel by pixel from the shipped screenshots: the Partners shot
on the page (assets/shots/partners-2026-10-16-900.webp) and the June 2026 store set in
the app repository (Screenshots/2026-06-04-v3.6/iphone).

| Token        | Value                    | Source in the app |
|--------------|--------------------------|-------------------|
| ground       | #000000                  | iOS systemBackground in dark. Sampled #000000 behind every screen in the Partners, Today and streak shots. |
| surface      | #1C1C1E                  | iOS secondarySystemBackground and systemGray6 in dark: the grouped cards on Partners and Today (sampled #1C1C1E) and the empty day cell in YearGridView.swift. |
| surface-2    | #2C2C2E                  | iOS systemGray5 in dark: the open check circle in HabitRowView.swift, the unscheduled day cell in YearGridView.swift, the focus timer track in PomodoroView.swift. Used for the device bezel. |
| ink          | #FFFFFF                  | iOS label in dark: every title and row label in the screenshots. Headings and the price row. |
| body         | #D3D3DC                  | iOS secondaryLabel's base colour, rgb(235, 235, 245), at 0.9 over the ground. The app's own secondaryLabel (0.6, #8D8D93) measures Lc 41, too faint for running text, so the page keeps its cool grey and raises its strength. |
| muted        | #A2A2A9                  | The same base at 0.69. Fine print only: the store note, the footer. |
| line         | rgba(84, 84, 88, 0.65)   | iOS separator in dark. It renders #373739 on the ground; sampled #3D3C3F between the Partners rows. |
| line-strong  | rgba(235, 235, 245, 0.3) | iOS tertiaryLabel in dark. Outline of the share button and the header store link. |
| flame        | #E67E00                  | Color.themeOrange (ColorHelpers.swift), the tint of the whole tab view (MainTabView.swift `.tint(.themeOrange)`) and the selected tab colour, with 140 uses in the sources. Sampled #E77E00 on Jordan's avatar and #E67F00 on the Edit button. |
| ember        | #FFBD6C                  | themeOrange at its own HSL hue (33 degrees) and full saturation, lifted to 71% lightness: the lightest step that carries black ink at APCA Lc 75. |
| ember-hover  | #FFCA8A                  | The same hue at 77% lightness. |

The page uses one chromatic colour, the app's orange, in two strengths. themeOrange
itself (flame) cannot carry text on black: as text it measures Lc 47.7, and neither black
(Lc 49.9) nor white (Lc 59.4) reaches Lc 75 on it as a button. So:

- flame, the literal #E67E00, paints marks that carry no text: the streak cells in the
  hero's back plane, at the same four strengths YearGridView.swift uses.
- ember, the same hue lifted, is the text and button tone: the App Store button, the
  ring around the partner's reaction, its label and the keyboard focus ring.

The second chromatic colour the brief allows was considered and left out. The app's
green (iOS systemGreen #30D158, Color.success #34C759; sampled #31D259 on "All done!")
marks completion, and the page has no completion state of its own to mark. It still
shows inside the screenshots, where the app put it.

### Contrast (APCA Lc, text on ground)

| Pair                         | Lc    | Floor |
|------------------------------|-------|-------|
| ink on ground                | 107.9 | 90    |
| body on ground               | 80.3  | 75    |
| ember on ground              | 74.4  | 60    |
| black on the ember button    | 75.3  | 75    |
| black on the hover button    | 80.7  | 75    |
| muted on ground (fine print) | 52.2  | 45    |

scripts/verify-pages.py checks every one of these, and a pinned palette check holds
ground, surface and flame to the app's values.

### Accent coverage

The accent sits on the store button, the ring and its label, and, at no more than 0.3
strength, the done days in the back plane. No section band, background fill or heading
is orange. Measured on the captures, counting pixels on the orange hue: "bright" is the
accent as a reader sees it (a channel above 75%), "all tones" adds the dim grid cells.

| Screen                     | Bright accent | All tones |
|----------------------------|---------------|-----------|
| 1440 by 900, top           | 1.2%          | 3.3%      |
| 1920 by 1080, top          | 0.8%          | 2.1%      |
| 390 by 844, top            | 4.3%          | 5.9%      |
| 390 by 844, hero in view   | 4.4%          | 8.1%      |

On a phone the store button alone is about 4% of the screen, as it was in the first
pass; the grid adds no bright accent there (4.37% with it hidden), only the dim cells.

## 2. Depth: the hero as one scene

Built with CSS perspective and transform-style: preserve-3d only. No canvas, no library,
no new images: every plane is markup, the screenshot, or a crop of that same screenshot.

```
            ......:::::::::::......  back plane: the app's year grid, a band per
            ......::::+-------------+ habit, 180px behind
            ..::......|  Partners   |
            ::::......|  [Jordan  ] |  subject: the phone, turned toward the copy
 Jordan reacted to ==[[ Jordan sent ]] foreground: the reaction row, lifted 44px
 your Morning Run.    |  [  slot   ] | out of its slot, with the ember ring
            ::::::::::|  Evening Run|
            ::::::::::|  Journaling |
 -----------::::::::::+-------------+-- the hero hairline: every plane stands on it
```

### The three planes

1. Back plane: a quiet grid of streak marks taken from the app's own year grid
   (YearGridView.swift), laid out the way the app lays it out: a column per week,
   oldest on the left, and a row per day, Monday at the top. One band per habit, and
   the three habits are the partner's from the screenshot: Journaling ending on an 11
   day streak, Evening Run on a 20 day streak, Morning Run on a long one. 20 weeks span
   the column, with cells and gaps in the ratio of the app's 12pt cell and 3pt gap. The
   day states are the app's: the empty cell in systemGray6 (#1C1C1E), done days in
   themeOrange at the app's four steps, days before the habit existed and future days
   fainter, and a label coloured stroke on today. The strengths keep the app's
   proportions but are scaled down, as something far behind would be: the strongest
   done day sits at 0.3, so the grid reads as texture and never competes with the copy.
   The scatter before each streak comes from a fixed seed, so every build renders the
   same bytes. Wide screens show three bands; below 1200px, where the label moves above
   the phone, the last two. The plane sits 180px behind the phone.

   A first build set the grid out as a seven column calendar spanning the column. At
   that size every day became a 50px tile, and even dimmed the streak read as solid
   orange blocks beside the headline. The app's own layout, at the app's own scale,
   reads as the year grid it is.
2. Subject plane: the real Partners screenshot in its device frame, turned toward the copy
   and leaning back, standing on the hairline.
3. Foreground plane: Jordan's reaction row, "Jordan sent a flame for Morning Run", cut
   from the same screenshot at its exact pixel bounds (x 41 to 859, y 575 to 716 of the
   900 by 1211 image) and lifted toward the reader. Where it came from, the screen shows
   an empty recessed slot, so the row reads as taken out of the list, not copied.
   The card's shadow falls into that slot and onto the rows below it.

### One shared contact point

The perspective origin and every transform origin sit on the hero's bottom hairline, and
the scene is clipped there. The phone and the grid both stand on that line, and the
lifted card's shadow lands in its own slot on the screen, so the three planes read as one
object on one floor rather than three floating layers.

### The one 3D treatment

The partner's reaction rises out of the screen. On load the phone rises out of the
hairline into a turned pose (18 degrees about the vertical, 8 degrees leaning back), then
the reaction row lifts out of its slot toward the reader and the ember ring settles round
it. As the reader scrolls through the hero the phone straightens to 4 degrees and 1
degree, the card lifts a further 16px and the grid sinks 28px, so the planes separate at
different rates. Every in between pose is a complete, legible frame: the card never
leaves the slot's outline and the ring never leaves the card.

On a desktop with a fine pointer, moving the pointer tilts the whole scene up to 6
degrees about the vertical and 4 about the horizontal, eased each frame and with transform
only, so the grid shifts behind the phone and the card shifts in front of it. Touch
screens get the scroll pose only.

The label "Jordan reacted to your Morning Run." stays in flat page space so it is always
crisp. On wide screens it sits left of the phone on a plate of ground colour, and the
leader line belongs to the lifted card: it runs from the ring under the plate, so it stays
joined to the label whatever the pose. Below 1200px the label sits above the phone with
no leader line.

Shadows: light comes from the upper right. The phone casts an offset, blurred shadow to
its lower left onto the grid; the card casts one down into its slot. No glow, no zero
offset shadow, no gradient text.

## 3. Motion score

| Section  | Moment                    | Trigger                               | What moves                                                                 | Duration |
|----------|---------------------------|---------------------------------------|----------------------------------------------------------------------------|----------|
| Hero     | Grid settles              | page load                             | back plane comes forward 90px from deeper in, from transparent             | 0 to 900 ms |
| Hero     | Phone rises               | page load                             | phone rises out of the hairline into its turned pose                       | 100 to 1100 ms |
| Hero     | Reaction lifts            | page load                             | the row lifts out of its slot; the ring scales in; the label fades in      | 850 to 1450 ms |
| Hero     | Copy appears              | page load                             | headline, lede, buttons and note: opacity and a 12px rise, 80 ms apart      | 450 to 1200 ms |
| Hero     | Phone straightens         | scroll through the hero               | phone turn 18 to 4 degrees, lean 8 to 1; card lift 44 to 60px; grid sinks 28px | follows scroll |
| Hero     | Scene tilt                | pointer move, fine pointers only      | the whole scene, at most 6 degrees, eased                                   | follows pointer |
| Pairing  | Rows wipe in              | the list above the bottom eighth, once | each step's hairline draws left to right, then its text uncovers along it   | 500 ms each, 140 ms apart |
| Features | Today screenshot squares up | the shot above the bottom eighth, once | the phone turns from 16 degrees and leans from 10 to flat                   | 1000 ms |
| Pricing  | Price arrives             | the row above the bottom eighth, once | the row comes in, "$9.99" rises from behind its own baseline, then the terms fade in | 200 ms, 700 ms, then 400 ms |
| Buttons  | Hover and press           | hover, press                          | a 1px lift on hover, scale 0.98 on press                                    | 160 ms |

Guides, questions and the closing call to action have no entrance: they are reading
material, and the brief asks for a few moments, not one per section. Links do not
animate. Nothing is pinned, there is no scroll cue, no counter, no overlay, no grain.

Transform, opacity and clip-path only; no transition: all. The section reveals use an
IntersectionObserver that adds a class once, when the block's top rises above the bottom
eighth of the screen. Their hidden states only apply after the script has added a motion
class to the root, so without the script every section shows in its final state. A block
waiting for its reveal is hidden whole, never in part: the price row is not shown as
"Premium is ," with the number still below its line.

## 4. Reduced motion

With prefers-reduced-motion: reduce, every animation and transition is off and the
script stops before it adds the motion class or any listener. The scene is fixed at its
final pose: the phone turned 4 degrees and leaning 1, the reaction lifted 60px with its
shadow, ring and label, the grid behind. The depth stays visible through occlusion and
the shadows; nothing moves.

## 5. Budget

- One inline script for the scene and the reveals, under 3 KB unminified. It reads layout
  only on load and resize (cached rects), uses passive listeners and requestAnimationFrame,
  and stops its frame loop when the tilt has settled.
- Layers: the grid, the phone and the card are promoted with will-change: transform; no
  full screen layer, no filter, no blend mode.
- No layout shift from motion: every moving thing animates transform, opacity or
  clip-path, and the scene's headroom is padding inside a negative margin, so it adds no
  height to the hero.
- The cut out row is a second img with the same src, srcset and sizes as the screenshot,
  so it resolves to the same file and costs no request.
