# De-slop rules

AI slop is output that shows no decision was made. The model reached for the most
common answer in its training data: the indigo gradient, Inter, the kicker above every
heading, "It's not just X, it's Y". A pattern only counts as slop when it is the default
nobody chose. The same element is fine if it was picked on purpose and you can say
why.

These rules are merged from the GitHub sources listed at the end. Rules that repeated
across sources appear once. Rules that only fit marketing mockups or one vendor's
tooling were dropped (see [Dropped](#dropped)). Rules marked **(page)** apply to landing
and marketing pages only. Everything else also applies to app screens like faðir's.

## Colour and surface

1. No purple-to-blue, purple-to-pink or cyan-on-dark gradients, and no stock framework
   swatches (Tailwind indigo-500, violet-600, slate-900). Mix the palette for the
   product, preferably in OKLCH.
2. No gradient text. Emphasis comes from size, weight or position.
3. No glow or wash. That means aurora or mesh blobs, blurred orbs, radial spotlights,
   and saturated zero-offset glow shadows. Use one flat ground. Show depth with
   lightness steps, a hairline, or a shadow that has an offset and a tight blur.
4. Never use pure `#000` or `#fff`. Tint neutrals slightly toward the anchor hue.
5. Every colour comes from a token. Five slightly different blues in one file means
   colours were invented inline.
6. Keep the accent to roughly 5% of any screen. Use one accent hue. When everything is
   loud, nothing is.
7. Status colours grow out of the palette. Avoid default rainbow candy and one-hue
   alert boxes (red border, red text, red 10% fill). Carry the state in a word first,
   then in colour.
8. Glass and `backdrop-blur` only where the effect means something, such as content
   scrolling under sticky chrome.
9. Dark mode is re-derived, not inverted:
   - In dark mode, raised surfaces are lighter than the canvas.
   - Shadows mostly give way to lightness steps.
   - The accent loses chroma and gains lightness.
   - The hue never moves between modes.
10. Avoid the "named looks" unless the brief asks for them:
    - cream paper with a high-contrast serif and a terracotta accent
    - an all-mono "tasteful terminal"
    - the "editorial dashboard": a serif greeting and serif numerals on an operational
      UI

## Type

11. Choose the typeface the way you would choose a logo. Inter, Roboto, Space Grotesk,
    Geist, Manrope, Plus Jakarta Sans, Poppins and bare system stacks are the training
    average. Landing on one after trying alternatives is a choice. Starting there is
    not.
12. Use three families at most: display, body, and one outlier.
13. Every heading is one weight, one style and one colour. Don't set one word in serif
    italic, a highlight or the accent colour.
14. No tracked-caps labels. Small text set uppercase and letter-spaced is the machine's
    favourite costume. Use the body face, one step smaller, in sentence case.
15. Use monospace only for code, measurements and figures. Never use it as a
    "technical" costume on labels.
16. Hierarchy needs real contrast: few sizes, at least 1.25× apart. Merge sizes that sit
    within a pixel or two of each other.
17. Running prose is 16px at 1.5 or more line height. Dense app chrome may sit at 14px.
    Running text never goes below 12px, and functional text never below 11px. Prose
    measure is 45–75ch.
18. Use `text-wrap: balance` on headings and `pretty` on copy. Never justify text.
19. Use tabular lining numerals on every number that is scanned or updates.

## Layout and components

20. Never put a card inside a card. Use one surface per region and group inside it
    with spacing, alignment and hairlines.
21. Don't give every row its own card. Lists separated by dividers read faster.
22. Avoid icon-in-a-tinted-square tiles and three equal icon-above-heading columns. An
    icon must carry meaning. Otherwise delete it. Never wash an icon's container in
    10% of the icon's own colour.
23. No eyebrows or kickers. Small text before a heading survives only if it carries a
    fact the reader would otherwise lack.
24. No ornamental `01 / 02 / 03` numbering. Number only real sequences.
25. No coloured side stripe (a border thicker than 1px on one side) on cards, rows or
    callouts.
26. Use one small radius scale. Nested radius = outer radius − gap, or don't round the
    inner box.
27. Put the border and the radius on the same box. Otherwise the stroke dies at the
    corners.
28. Separate with either an edge or an elevation, not both. Never cast a shadow larger
    than the thing that casts it.
29. Space by relationship. Keep related items tight and push groups apart, and give a
    heading more space above it than below it. Don't stamp one gap value everywhere.
30. Badges only for real status. Don't add "New", "Beta" or "Popular" pills to create
    fake buzz.
31. Status dots are small, flat and paired with a word. Use no halo and no endless
    pulse. If nothing is live behind the dot, remove it.
32. Avoid template punctuation:
    - `A · B · C` meta strings
    - arrows glued to labels ("Learn more →")
    - decorative dots in front of labels
33. No emoji or Unicode glyph standing in for an icon. Use one icon set with one
    stroke weight.
34. Theme the parts you didn't draw: text selection, caret, scrollbars, focus rings and
    underline offset.
35. Ship every state: hover, active, focus-visible, disabled, loading, empty and error.
    Show disabled through more than opacity alone. Focus rings appear instantly and
    reach 3:1 contrast.
36. No horizontal scroll at any width from 320px up. Buttons and primary nav labels
    never wrap.
37. Use a modal only when the task needs interruption or protected focus.
38. **(page)** No hero-plus-three-features-plus-CTA template. No invented stat rows,
    testimonials or logo walls. No hand-drawn browser chrome or device frames around a
    fake product: capture the real one.

## Motion

39. Motion explains something: an action was received, a state changed, or a thing
    moved or came from somewhere. Spend effort on one authored moment, not the same
    fade-and-rise on every section.
40. Never use `transition: all`. List only the properties that carry the change.
    Animate transform, opacity, clip-path or filter, never width, height, top, left or
    margins.
41. Hover is a surface shift on the container, with one signal per element. Avoid
    `scale(1.05)` lifts, tilting cards, images that zoom on hover, and hover effects on
    things you can't click.
42. Ease out exponentially. Don't use bounce or overshoot on UI state. Save springs for
    things that physically travel.
43. Timing:
    - 100–150ms for feedback
    - 150–300ms for state changes
    - 300–500ms for layout and views
    - exits faster than entrances
44. Content is visible by default. A failed script must never ship a blank page.
45. Every animation has a `prefers-reduced-motion` path that removes movement but keeps
    feedback. Non-essential loops stop when they are offscreen or the tab is hidden.
46. Spinners rotate around their own centre. Watch one full turn.
47. Don't toast what the user can already see. Toasts are for failures and effects that
    aren't visible.

## Numbers and charts

48. Pick the form from the data:
    - one value: a figure with a worded qualifier
    - a series over time: a line
    - parts of a whole: sorted bars
    - more than about seven categories: a table
49. Avoid pies, donuts and gauge walls.
50. One series argues in the accent. Context series are neutral. Labels and values
    never wear the series colour, so identify a series with a swatch beside its label.
51. Bars start at zero. Never use dual y-axes. If you truncate a line axis, say so.
52. Every metric has a window and a comparison. State what "good" means where up is
    bad.
53. Avoid decorative fake data viz: dot rows, unlabelled gauge ticks, sparklines and
    rings standing in for content.
54. The numbers also exist as text, so the chart can be used without a mouse.
55. Never invent a number. A precise figure without a source is decoration.

## UI copy

56. Use the product's own nouns. Controls name their action. Errors name the problem
    and the fix, never "Oops" or "Something went wrong".
57. Cut taglines, helper text and secondary labels. If a screen needs them to make
    sense, fix the layout.
58. Say each fact once, where it does work.
59. Avoid buzzwords: seamless, robust, empower, elevate, unlock, supercharge,
    effortless, next-generation, world-class.
60. Avoid a stock second action ("Learn more", "Get started") beside the real one.
61. Never fake success. A control that confirms something with no request behind it is
    a lie.

## Prose (docs, commit messages, chat)

62. Lead with the point.
63. Don't restate the question. Avoid filler openers ("Great question", "Let me break
    this down") and summary-stamp closers ("In conclusion", "Hope this helps").
64. State the positive claim. Avoid "It's not X, it's Y", "Not A. Not B. Just C."
    cadences, and arguing with nobody.
65. Avoid faux-insight setups ("Here's what most people miss"), colon reveals ("The
    best part: it learns."), and fake-profound one-line closers.
66. Avoid inflation: "pivotal", "testament", "plays a vital role", trailing
    "-ing, highlighting…" clauses, and weasel attribution ("experts agree"). Name the
    source or cut the claim.
67. Avoid the vocabulary list: delve, foster, leverage, utilize, tapestry, realm,
    multifaceted, meticulous, paramount, transformative, embark, harness.
68. Be concrete. "Cut deploy time from 40 minutes to 4" beats "improved efficiency". If
    a sentence could move unchanged to another product, it is filler.
69. Use "is" and "has" when they are clearer than "serves as" and "boasts". Repeat the
    right word rather than cycling synonyms.
70. Don't force triads or stacked fragments, and vary sentence openings. Use few em
    dashes: none in short copy.
71. Formatting follows content:
    - no bold sprinkled mid-sentence
    - no headings over two-sentence sections
    - no bullets where two sentences read better
    - no emoji in headings
72. Avoid chatbot residue and conditional offer menus ("If you want, I can also…").
    Take the next action or name it.

## Code

73. Comments say why, not what. Delete:
    - comments that restate the line or the signature
    - step-by-step narration
    - banner separators and end-of-block markers
    - empty labels ("Main logic")
    - vague TODOs
74. Keep comments that record an intent, a constraint, a workaround, an edge case, a
    security or performance trade-off, or a protocol rule. Use one line, or two when
    the second carries a new fact.
75. Fail visibly. Avoid broad catches, catch-and-fallback paths, speculative
    compatibility branches and repeated validation unless a real contract needs the
    recovery.
76. A test earns its place by protecting externally visible behaviour. A fallback that
    exists only because a test exercises it, and a test that exists only because of
    that fallback, can be deleted together.
77. Add no new dependency, wrapper or abstraction unless it removes more than it adds.

## Verify by looking

78. Run the real thing at the sizes it ships at, in both themes, and look at it. Most
    slop is visible in one glance at the render and invisible line by line: a dead
    corner, a wobbling spinner, a label that wraps.

## Dropped

Rules from the sources that were cut:

- **Rules for a vendor's tooling:** stamps, logs, linters and command menus.
- **Mockup-only rules:** "never show cents" and "abbreviate numbers over 10,000". A
  portfolio's exact lira values are the content.
- **Landing-page fold rules:** a hero at 92dvh, 120px between sections, 80 words per
  screen, the email-signup close.
- **"Prefer Unsplash photography":** it doesn't fit an app.
- **Duplicates.** Most rules above appeared in three or more sources.

## Sources

- [pbakaus/impeccable](https://github.com/pbakaus/impeccable): craft floor, animate, audit
- [Nutlope/hallmark](https://github.com/Nutlope/hallmark): gates, data viz, dark mode
- [yetone/kill-ai-slop](https://github.com/yetone/kill-ai-slop): 35-tell taxonomy
- [Gesso-Build/skills](https://github.com/Gesso-Build/skills): slop-guard catalogue
- [Trystan-SA/claude-design-system-prompt](https://github.com/Trystan-SA/claude-design-system-prompt): AI slop check
- [Ferousco-dev/anti-slop-design](https://github.com/Ferousco-dev/anti-slop-design): data visualisation, animation
- [miqdadbadjuber/anti-slop](https://github.com/miqdadbadjuber/anti-slop): UI, copywriting, code comments
- [blader/humanizer](https://github.com/blader/humanizer), [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop), [hexiecs/talk-normal](https://github.com/hexiecs/talk-normal): prose
- [MrZoyo/deslop-GPT](https://github.com/MrZoyo/deslop-GPT): test and fallback bloat
