# drm_composer — roadmap: easy syntax wins

Grounded in the current pipeline: parser ([`parser.py`](drm_composer/parser.py)) →
dataclass nodes ([`scene.py`](drm_composer/scene.py)) → per-layer PIL `ImageDraw`
([`painter.py`](drm_composer/painter.py)) → `drm_screen` command batch.

"Easy" = doable in one shot with PIL features already imported, reusing the
existing helpers (`_length`, `_bool`, `_rgba`, `_font`, `textlength`,
`rounded_rectangle`). Anything needing a frame clock (animation, video) is
deliberately **out of scope** — see [Deferred](#deferred-needs-runtime-support).

Keep [`SYNTAX.md`](SYNTAX.md) generated-from-code: update it alongside each change,
and add round-trip tests in the style of `test_html_compat`.

## Status

- ✅ **composer↔host action interface** (`drm_composer.actions`) — `Action`,
  `parse_action`, `Dispatcher`; allowlist-by-registration; `page_demo.py` ported;
  10 headless tests green. See [Tier 3](#the-composer--host-interface--drm_composeractions-done).
- ⬜ Everything else below (Tier 1–3 tags, display handoff) is open.

---

## Tier 1 — near-free (new attrs / shape tags in the existing paint loop)

### `<box>` styling
- [ ] `radius="12"` → use `draw.rounded_rectangle` when set (already used for buttons)
- [ ] `border-color` + `border-width` → PIL `outline=` / `width=` args
- [ ] Factor a shared fill+border+radius helper used by both `<box>` and `<button>`

### New shape tags (one `ImageDraw` call each)
- [ ] `<line x1 y1 x2 y2 color width>` → `draw.line`
- [ ] `<ellipse>` / `<circle>` → `draw.ellipse`

### `<text>` improvements
- [ ] `align="center|right"` → reuse the `textlength` math from the button label path
- [ ] `bold` / `italic` (or `font-weight`) → load `DejaVuSans-Bold.ttf` /
      `-Oblique.ttf`; give `_font()` a variant argument (falls back to regular)
- [ ] `wrap` + `w="…"` → stdlib `textwrap` + `draw.multiline_text`
      (removes the "no word-wrapping" limitation noted in SYNTAX.md)

### `<img>` polish
- [ ] `fit="contain|cover"` → aspect-preserving resize (currently exact stretch only)
- [ ] `opacity="0.5"` → scale the alpha channel before `alpha_composite`

---

## Tier 2 — small, self-contained

### Document chrome (fits the "unknown tags are silently ignored" model)
- [ ] `<html>` / `<head>` / `<body>` → accept as transparent pass-through wrappers
      (parser must not error; layout is already flat — near-zero cost)
- [ ] `background="#141e3c"` on `<screen>` (or `<body>`) → auto-emit a low-z
      full-screen fill layer, replacing the boilerplate background `<box>`

### `<style>` — minimal stylesheet (defaults only, NOT cascading CSS)
- [ ] Tag- and id-level **default** resolution: `text { color:#fff; size:24 }`,
      `#title { color:cyan }`. Implement as a pass over nodes after parse,
      before paint. Scope to a documented handful of props (color, size,
      font weight/style, align) — explicitly not full CSS, same as how
      lengths/colors document their forgiving subset.

### Video poster stand-in (the easy 90% without playback)
- [ ] `<video poster="…">` → render the poster image as a static `<img>`,
      optional centered "play" glyph overlay. Gives the *appearance* of video
      for kiosk/status screens with Tier-1 effort.
- [ ] Note: a static/animated GIF already renders **frame 0** today via
      `Image.open(...).convert("RGBA")` — document this.

---

## Tier 3 — kiosk interactivity (the `hit_id` model, not new rendering)

The unifying idea: `drm_composer` **never executes anything**. Like `<a>` today
(which emits `hit_id` `href:<page>`), these tags just carry an **intent string**;
the **host app** owns the handlers and is the **sole executor**.

Proposed `hit_id` namespace:

| Tag | `hit_id` | Host action |
|---|---|---|
| `<a href="x">` *(exists)* | `href:x` | navigate to page |
| `<button action="reboot">` | `cmd:reboot` | run an **allowlisted** command |
| `<video src="clip.mp4" launch>` | `play:clip.mp4` | release display, exec mpv/vlc fullscreen |
| `<input ... key="brightness">` | `set:brightness=<v>` | update a setting (host owns the value) |

### The composer ↔ host interface — `drm_composer.actions` *(DONE)*

Layering: `drm_screen.hit_test()` returns an **opaque `hit_id` string** (it stays
mechanical, no semantics). `drm_composer` owns the grammar it generates, so the
**parser lives in a new pure module `drm_composer/actions.py`** (no Pillow, no
display — testable headless). The **host executes**.

Wire grammar — `kind:payload`, `set` carries `key=value`; a bare id (no prefix)
maps to `action` for backward-compat with existing apps (`quit`, `back`):

| `hit_id` | parsed `Action` |
|---|---|
| `href:settings.html` | `Action("navigate", target="settings.html")` |
| `cmd:reboot` | `Action("command", target="reboot")` |
| `play:/media/clip.mp4` | `Action("play", target="/media/clip.mp4")` |
| `set:brightness=80` | `Action("set", target="brightness", value="80")` |
| `quit` | `Action("action", target="quit")` |

- [x] `Action` frozen dataclass: `kind`, `target`, `value: str|None`, `raw: str`.
- [x] `parse_action(hit_id) -> Action` — **total, never raises**; unknown prefix →
      `kind="action"` carrying the bare id (so it's routable, not a crash).
- [x] `Dispatcher` — host registers concrete bindings; routing only, executes
      nothing itself:
      `on_navigate(fn)`, `on_command(name, fn)`, `on_play(fn)`,
      `on_set(key, fn)`, `on_action(name, fn)`.
- [x] **Allowlist by registration**: an unregistered `command` / `set` key /
      `action` is a **silent no-op** (with an optional `logger`). Nothing the host
      didn't opt into can ever fire — a stale or hostile scene can't trigger it.
- [x] Replace the `startswith("href:")` / `=="quit"` ladder in
      [`integration/page_demo.py`](../integration/page_demo.py) with
      `dispatch(parse_action(hit))` as the reference consumer.
- [x] Headless unit tests for the grammar (every row above + malformed input) —
      `integration/test_actions.py` (10 tests).

> Note: the `cmd:` / `play:` / `set:` *emitters* (`<button action>`, `<video
> launch>`, `<input>`) are not parsed yet — the interface that *consumes* them is
> ready and tested, so those tags can be added incrementally against a stable
> contract.

### Display handoff for `play:` — needs a `drm_screen` capability
- [ ] `drm_screen` must expose **release / reacquire** of the display (drop DRM
      master + stop the render loop, then reclaim) so an external fullscreen
      player (mpv/vlc) can own the screen and hand it back on exit. The `on_play`
      handler: release → `exec` player and wait → reacquire → re-render current
      page. **Dependency for `<video launch>`; track in drm_screen.**

### Launch commands — actions (#3)
- [ ] `<button action="…">` → `hit_id` `cmd:<action>`, reusing the exact `<a>`
      machinery in `parser.py` (`hit_id = "cmd:" + a["action"]`). No painter change.
- [ ] Document the host-side allowlist contract: composer carries intent only;
      host must validate `cmd:` against a fixed set before exec.

### Full-app video handoff via mpv/vlc (#4)
- [ ] `<video src="…" launch>` → `hit_id` `play:<src>`. The host suspends the
      compositor and execs mpv/vlc fullscreen, resuming on exit. This sidesteps
      in-compositor decoding entirely (that stays Deferred below) — playback is a
      separate full-app takeover, not a composited layer.

### Auto-advance — `<meta http-equiv="refresh">` (#1)
- [ ] Parse `<meta http-equiv="refresh" content="5; url=next.html">` into
      scene-level metadata (`Scene.refresh = (seconds, url)`).
- [ ] Host loop honors it: after N seconds with no interaction, navigate to `url`
      (or reload if no url). Needs a one-shot timer in the host — **nothing in
      `drm_screen`**.

### Settings input — `<input>` (non-text types first) (#2)
- [ ] `<input type="checkbox|toggle|range|select|stepper" key="…" value="…">`
      → interactive layer(s) like `<button>`, emitting `set:<key>=<value>`.
- [ ] Host owns the current value and re-renders to reflect it (composer is
      stateless). Render: checkbox/toggle = box + glyph; range = track + thumb;
      select/stepper = labeled value with +/- or prev/next hit regions.
- [ ] **Text input deferred** — needs an on-screen keyboard; group with video below.

### Image sequence / slideshow (#5)
- [ ] Slow **slideshow** (seconds per frame) is feasible host-driven *now*:
      `<slideshow>` / `<img frames="a.png,b.png,c.png" interval="3">` → host swaps
      the layer buffer on a timer (pre-rasterized frames, cheap re-submit).
- [ ] Smooth **animation** (many fps) → still needs the `drm_screen`
      frame-update path; see Deferred.

---

## Deferred — needs runtime support (NOT in this roadmap)

The current pipeline is **single-shot**: `paint_scene` emits one `PlaceRawBuffer`
per layer and returns. There is no frame clock and no cheap repeated
layer-update path in `drm_screen`. These require new subsystems, not tags:

- **Animated GIF playback** — needs a scheduler that re-rasterizes + re-submits a
  layer at the GIF's frame delays, plus `drm_screen` support for repeated
  single-layer buffer updates.
- **`<video>` in-compositor playback** — the above plus a decoder (ffmpeg / PyAV)
  and A/V sync. (The `<video launch>` mpv/vlc handoff in Tier 3 avoids this.)
- **Smooth image-sequence animation** (high fps) — same frame-update dependency;
  the slow slideshow variant in Tier 3 does **not** need it.
- **Text `<input>`** — needs an on-screen keyboard widget + focus/IME handling.

Revisit once `drm_screen` grows a frame-update path.
