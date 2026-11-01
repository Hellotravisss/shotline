# The shotline method

Five stages, each with a gate. A stage is done when its gate passes, not when it looks
done. Most of these rules were learned by shipping a set, finding the problem in the
store, and pulling the version back out of review to fix it.

```
concept → capture → compose → check → ship
 copy      raw/      out/      gates    ASC + verify
```

---

## 1. Concept — decide what each slide sells before touching a simulator

**One idea per slide.** A slide that says two things says neither. Write the headline
first; if it needs "and", it is two slides.

**Sell the outcome, then show the proof.** The headline is what the user gets
("Where can your passport take you?"), the screenshot is the proof, the sub-line is
the mechanism. A headline that names a feature ("Explore screen") wastes the slide.

**The first three slides are the listing.** Search results show three; most people
never swipe. Put the strongest promise in slide 1, the most concrete number in
slide 2, the thing competitors don't have in slide 3.

**3–5 words per line, two lines.** Long lines shrink to fit and stop being readable
at thumbnail size. If auto-fit has to shrink a line, rewrite the line.

**Emphasise one word.** `*word*` in a headline gets the accent treatment. One per
headline; two emphases cancel out.

**Every claim must be true on the screenshot it sits on.** If the headline says
"43 countries", the screen under it shows 43. Numbers drift when data updates —
recapture, don't edit the number.

**Add a trust signal, and make it a fact.** "Every item links its official source",
"199 countries & territories", "Visa data refreshed monthly" — things a reviewer
could check. Never invent ratings, user counts or press quotes.

**Captions are search text.** Since 2025 Apple extracts screenshot captions and
indexes them. Use the words people search with, in every locale, written natively —
not translated.

**Hide-the-copy test.** Cover the screenshot and read only the headlines in order.
They should tell the story of the app on their own.

**Close with a wall, not another phone.** Five phone frames in a row is a "phone
parade"; the eye stops seeing them. The last slide lists what else the app does as
large type (`layout: "wall"`), or shows three screens at once (`"mosaic"`).

**Vary the layouts.** `hero` (copy top, device bleeding off the bottom),
`device-top` (device bleeding off the top, copy low), `tilted`, `wall`, `mosaic`.
Alternate so adjacent slides never share a silhouette.

---

## 2. Capture — real app, real data, reproducible

**Release build.** Debug and dev-client builds add overlays (dev menus, floating
buttons, yellow boxes). Build Release for the simulator once and keep it installed.

**Clean status bar.** `shotline capture` overrides it: 9:41, full signal, Wi-Fi,
battery **discharging** at 100 % — "charging" shows a bolt.

**Cold launch, then deep link.** Every shot terminates the app, launches it, then
opens a URL. A deep link to a route that is already on screen often doesn't reload
it; and a link opened while the app is frontmost skips iOS's "Open in …?" sheet.

**Seed state, don't click through it.** Typing into forms and spinning date pickers
is the flakiest part of any capture script. Write the state before launch instead:
`mergeJson` into the app's data container (React Native AsyncStorage lives in
`Library/Application Support/<bundle>/RCTAsyncLocalStorage_V1/manifest.json`) or
`defaults` for NSUserDefaults. App language set this way beats `-AppleLanguages`
when the app keeps its own language setting.

**Prefer deep links to taps; prefer taps to swipes.** Coordinates are in points and
differ per device, so `tap` accepts `{"iphone": [x,y], "ipad": [x,y]}`. Get them from
`axe describe-ui --udid <udid>`. Label taps work in-app; on system sheets use
coordinates.

**A tap is a press, not a point.** On the iOS 26 simulator a zero-length tap (down and up
in the same instant) is dropped after the first one, and the command still reports
success; once that happens the device ignores touches until it is rebooted. shotline sends
down → 80 ms → up for every coordinate tap. If a capture stops reacting, reboot the
simulator rather than adding waits.

**Swipe slowly.** A 3-second drag stops where it ends; a flick keeps scrolling after
the screenshot is taken. `{"swipe": [[x1,y1],[x2,y2]], "duration": 3}`.

**Real data only.** Screens show what the shipping app shows for a real query. No
mocked numbers, no lorem ipsum, no "John Appleseed" with a fake 5-star review.

**Look at every raw.** Capture is where content bugs surface: an English paragraph
inside the Chinese UI, half-width punctuation in CJK text, a truncated label. Fix
the app or pick a different example — don't paper over it in compose.

**iPad needs iPad captures.** A phone screenshot in an iPad frame is rejected (and
looks wrong). If the app's iPad layout is a stretched phone layout, that shows — the
fix is in the app.

**Raws belong in git.** They are expensive and often impossible to reproduce (data
changes, accounts expire). `out/` is cheap; it can be rebuilt from raws + config.

---

## 3. Compose — copy and layout in one JSON, rendered by a browser

Slides are HTML rendered by headless Chrome at exact store size, so type is real type
(kerning, CJK fonts, emoji) and layout is CSS. Copy lives in `shotline.json`, per
locale. The template reports back after layout: which lines it had to shrink and
whether anything overflows.

**CJK typesetting.** Full-width punctuation (，。？：) in Chinese/Japanese copy; a
space between CJK and Latin/digits (`免签 43 国`, `申根 90/180 天`). Type full-width
characters directly or as `，`-style escapes — never let an editor turn them
into ASCII. Tracking: slightly positive for CJK, slightly negative for Latin display
type; the themes set both.

**Themes are a starting point.** `brutal` (flat saturated ground, hard offset
shadows) and `editorial` (paper, serif display). Override any token under `theme`.
Match the app's own visual language — the listing should look like the product.

---

## 4. Check — gates before anything leaves the machine

`shotline check` fails on:

- **size** — not exactly the store resolution for the device;
- **overflow** — copy outside the canvas, or copy leaving too little room for the device.

It warns on:

- **shrunk** — auto-fit had to shrink a headline line. Treat it as a copy bug.
- **alpha** — accepted by App Store Connect, but flatten if a reviewer complains.

It writes `out/sheet-<locale>-<device>.png`: every slide at ~200 px wide, the size of a
search result. **Look at the sheet, not the full-size files.** If a headline is not
legible on the sheet, it does not work.

---

## 5. Ship — upload, then prove it arrived

**Screenshots are locked during review.** If the version is waiting for review,
`ship --cancel-review` pulls it (state becomes `DEVELOPER_REJECTED`) so the sets can
be replaced. That resets your place in the review queue — decide on purpose.

**Replace whole sets.** `ship` deletes each target set and uploads it fresh, in
order. Partial edits leave stale slides behind.

**Verify every set.** Each upload call can return 200 while the asset later fails
processing, and processing can take minutes. `ship` re-reads every locale × device
set and requires the exact file names, in order, all `COMPLETE`. `verify` does the
same on demand. A set still processing when `ship` exits shows up here — re-run
`verify` until it passes.

**Submit only after verify passes.** `shotline submit` refuses otherwise. Submitting
is outward-facing; it is its own command.

**Credentials stay in the environment.** `ASC_KEY_ID`, `ASC_ISSUER_ID`,
`ASC_KEY_PATH`. Nothing secret goes in `shotline.json`.

---

## Credits

The concept rules build on two open-source skills, then on what broke when we
shipped:

- [ParthJadhav/app-store-screenshots](https://github.com/ParthJadhav/app-store-screenshots) — one idea per headline, short lines, varied layouts, the closer slide, the thumbnail test.
- [framara/app-store-screenshots-skill](https://github.com/framara/app-store-screenshots-skill) (Scrnsht Studio) — value proposition from research, sell the outcome, hide-the-copy test, a true trust signal on every panel, verify after upload.
- [cameroncooke/AXe](https://github.com/cameroncooke/AXe) drives taps and swipes in the simulator.
