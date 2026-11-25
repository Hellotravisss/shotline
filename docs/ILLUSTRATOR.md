# The Illustrator route

shotline's own pipeline renders slides as HTML in headless Chrome. This is the second
route: build the slides in Adobe Illustrator with a script, on Apple's official device
bezels, and hand over editable `.ai` files. Use it when the person wants to edit the
set by hand later, or wants real Apple device frames instead of drawn ones. The method
(concept → capture → check → ship, `METHOD.md`) is the same; only compose changes.

```
tools/drive.py                capture by on-screen text (any device, any locale)
tools/illustrator/lib.jsx     slide helpers: text, device on bezel, pattern, export
tools/illustrator/example.jsx one slide, end to end
```

## 1. Before anything: three directions for slide 1

Build three different treatments of slide 1 only, put them side by side at thumbnail
size, give each an honest score, recommend one. Then build the set in the chosen
language. One slide is cheap to throw away; twenty are not. Typical trio:

- **The number** — one big, real result as the headline; the device below repeats it.
- **The document** — an illustration of the real-world thing the app replaces (a pay
  stub, a receipt, a form), with figures that add up, beside the device.
- **The callouts** — the device with short labels pointing at its rows from the margin.

The person will react to the example as much as the design: a figure that looks too low or
too ordinary for the audience ("$20 an hour looks too little") is a concept bug — recompute
with a better example and recapture, never edit the number.

## 2. Apple's rules for the bezels

From the App Store Marketing Guidelines, "Apple Product Images": use the bezels **as is**.
No reflections, shadows or highlights; no cropping, tilting or obstructing; nothing that
appears to enter or come out of the screen; no flipping. Use the latest devices.

So with Apple bezels: the device is upright and **whole** — no "device bleeding off the
bottom", no tilted phone (shotline's HTML `hero`/`tilted` layouts draw their own frames,
which is why they can). Callout lines stop at the device edge. Clip the *capture* to the
screen's rounded corners (your image, so allowed), never the bezel.

Bezels: developer.apple.com/design/resources → Product Bezels (`.dmg`, behind the Apple
Design Resources licence — someone has to accept it). The screen hole of the iPhone 17 Pro
and iPad Pro 13" PNGs equals the simulator screenshot size, so captures drop in at 1:1.

## 3. Capture with `tools/drive.py`

Find elements by their on-screen text instead of hard-coded coordinates, so one flow works
on iPhone and iPad and in every language (`tap "^(Next|Suivant)"`).

- `scrollto <label> <y>` brings a row to a height; swipes are slow (1.8 s) so they stop
  where they end. A fling overshoots and the loop never settles.
- `setfield` for inputs whose UI collapses at zero (a block shown only while
  "amount > 0"): clearing the field to type a new value hides the block mid-edit.
- iPad is not iPhone: results may sit beside the inputs, sheets may be half empty. Choose
  the iPad shot for what it shows, and check that it still proves the headline.
- Status bar stays at 9:41 from `shotline capture`'s override; check the first raw.

## 4. Look at every raw, in every locale, as a reviewer

This is where most of the real bugs turn up — in the app, not the slide:

- **Locale formatting.** A French screen showing `75.0 h`, `$7,000` or `30.5%` is an app
  bug (French: `75,0 h`, `7 000 $`, `30,5 %`). Fix the app, rebuild, recapture.
- **Stale years and hard-coded figures.** "2025 contribution room" in a 2026 build;
  a limit typed as a literal instead of read from the data.
- **Numbers that disagree with each other on the same screen** (a per-dollar rate beside a
  refund that implies a different rate). Don't put that screen in the store; open a fix.
- **Every headline figure is computed, not typed**: run the product's own engine for the
  example, write the inputs and outputs at the top of the build script, and check that the
  capture under the headline shows the same values.

## 5. Build with `tools/illustrator/lib.jsx`

ExtendScript traps the helpers already handle — keep them in mind when you add code:

- **Nested `?:` must be parenthesised.** `a === 'center' ? x : a === 'right' ? y : z`
  evaluates wrongly in ExtendScript ('center' took the 'right' branch). Silent; looks like
  a layout bug.
- **Point-text bounds are stale.** `geometricBounds` read right after styling a point-text
  frame are from before its last recompose. Measuring-then-centring lands half a width off.
  Use area text in a wide box and let paragraph justification align it (`S.text`).
- **Fonts must be installed for Illustrator** (`~/Library/Fonts`), then Illustrator
  restarted — check `app.textFonts.getByName(...)` before building. Quitting Illustrator
  closes documents: check `app.documents` for unsaved work first.
- **One `.ai` per locale × device, one artboard per slide**, exported with
  `shotlineExport` (Export for Screens, 1×, no transparency) → exact store sizes.
- Brand patterns go only where there is no text or number on top.

## 6. Check and ship

Make a contact sheet per locale × device (all slides at ~200–600 px wide) and judge it
there. Then the normal `ship` / `verify` from `METHOD.md`: the PNGs are ordinary store
screenshots. Keep `.ai` files out of git if they embed the captures (they are large); keep
the build script, the raws and the PNGs in.
