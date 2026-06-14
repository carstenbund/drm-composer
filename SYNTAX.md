# drm_composer — screen-HTML syntax reference

`drm_composer` compiles a small, declarative **screen-HTML** subset into
`drm_screen` command batches. This document is the complete, authoritative list
of every element and attribute the parser actually understands, the exact value
formats each accepts, and the behaviour the painter gives them.

It is generated from the source — [`parser.py`](drm_composer/parser.py),
[`scene.py`](drm_composer/scene.py), and [`painter.py`](drm_composer/painter.py)
— not from the design outline. Where the outline promises more than the code
delivers, this reference describes the **code**. See [Not yet
implemented](#not-yet-implemented).

---

## At a glance

| Element | Where it may appear | Purpose | Self-closing? |
|---|---|---|---|
| [`<screen>`](#screen) | document root | Canvas size; the one required root element | no — wraps layers |
| [`<layer>`](#layer)  | inside `<screen>` | A named, z-ordered, full-screen RGBA plane | no — wraps nodes |
| [`<box>`](#box)    | inside `<layer>` | A filled rectangle | yes |
| [`<text>`](#text)   | inside `<layer>` | A line of text (content = element text) | no — needs a close tag |
| [`<img>`](#img)    | inside `<layer>` | A PNG/JPEG/etc. pasted from a file | yes |
| [`<button>`](#button) | inside `<layer>` | An interactive button — a click yields a `hit_id` (an action) | no — needs a close tag |
| [`<a>`](#a)      | inside `<layer>` | An interactive link — navigates (`hit_id` = `href:…`) | no — needs a close tag |

A minimal valid document:

```html
<screen width="800" height="480">
  <layer id="bg" z="0">
    <box x="0" y="0" w="800" h="480" color="#141e3c" />
  </layer>
</screen>
```

---

## Value formats (read this first)

These rules apply to **every** attribute below — they are enforced by the shared
parser helpers, so they behave identically on every element.

### Lengths — numbers, units, and percentages

Every numeric attribute (`x`, `y`, `w`, `h`, `z`, `size`, `width`, `height`) is
parsed the forgiving way HTML is: the **leading number is taken, any unit is
ignored**, and the result is rounded to an integer pixel. A trailing **`%`** on a
position/size (`x`/`y`/`w`/`h`) is resolved against the screen — width for
`x`/`w`, height for `y`/`h`.

- ✅ `x="20"`       → `20`
- ✅ `x="20px"`     → `20`  (unit ignored)
- ✅ `x="20.5"`     → `20`  (rounded to the nearest pixel)
- ✅ `size="1.5em"` → `2`
- ✅ `w="50%"`  on an 800-wide screen → `400`
- ✅ `h="100%"` on a 480-tall screen → `480`
- ⚪ `x="auto"`, `x=""`, or any value with no number → the attribute's **default**

**Nothing here raises** — a missing or unparseable value just uses the default.
`%` is only resolved for `x`/`y`/`w`/`h`; on `z`/`size`/`width`/`height` (which
have no screen reference) a `%` value is taken as the bare number.

### Booleans

`visible` is the only boolean. It is **false** when the value (case-insensitive,
trimmed) is one of:

```
false   0   no   hidden
```

Any other value — including `visible="true"`, `visible="yes"`, or
`visible="anything"` — is **true**. Omitting it defaults to **true**.

### Colors

`color` (and `text-color`) accept the **full CSS range** — parsing is delegated
to Pillow's `ImageColor`, so anything CSS understands works (case-insensitive):

| Form | Example | Notes |
|---|---|---|
| named              | `navy`, `rebeccapurple` | the full CSS color list, not just a handful |
| `#rgb`             | `#f0c`        | each digit doubled → `#ff00cc`, alpha `ff` |
| `#rgba`            | `#f0c8`       | 4-digit, with alpha |
| `#rrggbb`          | `#141e3c`     | alpha defaults to `ff` (opaque) |
| `#rrggbbaa`        | `#000000aa`   | explicit alpha — `aa` ≈ 67% opaque |
| `rgb()` / `rgba()` | `rgb(255,0,0)`, `rgba(0,0,0,128)` | components 0–255; rgba alpha is 0–255 |
| `hsl()`            | `hsl(120,100%,50%)` | also accepted |

An **unrecognized** color is treated as **transparent** `(0,0,0,0)` — ignored,
not an error — so a typo makes one element invisible instead of crashing the
whole scene. The `#` on hex is optional but conventional.

Alpha matters: it is the layer-local pixel alpha that `drm_screen` blends when
compositing. `#000000aa` gives you a translucent dark scrim; `#000000` (=`ff`)
is fully opaque.

### Coordinate system — absolute, per screen

**Every node's `x`/`y` is measured from the top-left of the whole screen, not
from its parent.** Each `<layer>` becomes a full-screen canvas the size of the
`<screen>`, and box/text/img are drawn into it at their absolute coordinates.
Y increases downward.

> ⚠️ **Nesting does not create relative positioning.** You may write
> `<box><text>…</text></box>`, and it parses without error — but the parser
> flattens *all* nodes into the layer regardless of nesting. The text is **not**
> offset by the box; its `x`/`y` are still screen-absolute. A box is a drawn
> rectangle, not a layout container. To put text "inside" a box, give the text
> coordinates that fall within the box's rectangle yourself.

---

## Elements

### `<screen>`

The root. There must be exactly one, and it must enclose everything. Parsing a
document with no `<screen>` raises `ValueError: no <screen> element found`.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `width`  | int | `1920` | Canvas width in pixels |
| `height` | int | `1080` | Canvas height in pixels |

The width/height define the size of **every** layer canvas the painter
allocates, so set them to match your real display.

```html
<screen width="800" height="480"> … </screen>
```

---

### `<layer>`

A named, independently z-ordered, full-screen plane. Must appear inside
`<screen>`; a `<layer>` elsewhere raises `ValueError: <layer> outside <screen>`.
Each `<layer>` compiles to a `CreateLayer` + a `PlaceRawBuffer` command.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `id`      | string | `layer{N}` (its index) | Layer name — used as the `drm_screen` layer key |
| `z`       | int  | `0`    | Stacking order; higher draws on top |
| `visible` | bool | `true` | Whether `drm_screen` shows the layer (see [Booleans](#booleans)) |

Notes:

- **Give every layer an explicit `id`.** Two layers with the same `id` (or two
  auto-generated ids that collide) map to the same `drm_screen` layer — the
  second `CreateLayer` will clash downstream.
- Layers are emitted in **document order**; `z` decides the actual paint order
  in `drm_screen`, independent of document order.
- An empty `<layer>` is legal — it produces a fully transparent plane.

```html
<layer id="status" z="10" visible="true"> … </layer>
```

---

### `<box>`

A filled rectangle. Must be inside a `<layer>` (else `ValueError: <box> outside
<layer>`). Self-closing.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `x`     | int    | `0`         | Left edge (screen-absolute) |
| `y`     | int    | `0`         | Top edge (screen-absolute) |
| `w`     | int    | `0`         | Width in pixels |
| `h`     | int    | `0`         | Height in pixels |
| `color` | string | `#000000ff` | Fill color (see [Colors](#colors)) |

The rectangle covers pixels `x … x+w-1` horizontally and `y … y+h-1` vertically
(i.e. `w`×`h` pixels exactly).

> ⚠️ **`w` and `h` default to `0`.** A box without explicit `w`/`h` is
> effectively invisible (a degenerate 0-area rectangle). Always set both.

```html
<box x="40" y="40" w="380" h="96" color="#000000aa" />
```

---

### `<text>`

A run of text. Must be inside a `<layer>` (else `ValueError: <text> outside
<layer>`). **Not self-closing** — the displayed string is the character data
between `<text>` and `</text>`, and it is `.strip()`-ed of surrounding
whitespace.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `x`     | int    | `0`         | Left edge of the text (screen-absolute) |
| `y`     | int    | `0`         | Top edge of the text (screen-absolute) |
| `size`  | int    | `16`        | Font size in points |
| `color` | string | `#ffffffff` | Text color (see [Colors](#colors)) |

Behaviour:

- The anchor is the **top-left** of the text box (PIL's default), so `y` is the
  top of the glyphs, not the baseline.
- The font is **DejaVu Sans** (`DejaVuSans.ttf`). If that font can't be found on
  the host, the painter falls back to PIL's built-in bitmap font — which is a
  **fixed size and ignores `size`**. Install DejaVu (e.g. `fonts-dejavu-core` on
  Debian/Raspberry Pi OS) for `size` to take effect.
- Use HTML entities for reserved characters: `&lt;` `&gt;` `&amp;`. Entities are
  decoded automatically (e.g. `-&gt;` renders as `->`).
- No word-wrapping, no multi-line layout — one drawn string. Embedded newlines
  in the content are passed straight to PIL.

```html
<text x="60" y="74" size="24" color="#ffffff">System ready</text>
```

---

### `<img>`

Pastes an image file, alpha-composited onto the layer. Must be inside a
`<layer>` (else `ValueError: <img> outside <layer>`). Self-closing.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `src` | string | **required** | Path to the image file |
| `x`   | int    | `0`            | Left edge (screen-absolute) |
| `y`   | int    | `0`            | Top edge (screen-absolute) |
| `w`   | int    | native width   | Target width — see resize rule below |
| `h`   | int    | native height  | Target height — see resize rule below |

Behaviour:

- **`src` is mandatory.** An `<img>` without `src` raises `KeyError: 'src'`.
- `src` is opened with Pillow, so any Pillow-supported format works (PNG, JPEG,
  BMP, GIF…). It is converted to RGBA, so PNG transparency is preserved.
- The path is resolved by the **process running the compositor**, relative to its
  current working directory — there is no asset root or URL support. Prefer
  absolute paths or paths you control.
- **Resize is all-or-nothing:** the image is scaled only when *both* `w` and `h`
  are given (and non-zero). If you set only one — or neither — the image is
  pasted at its **native size** and the lone dimension is ignored. There is no
  aspect-ratio preservation; the resize is an exact `w`×`h` stretch.

```html
<img src="/opt/kiosk/logo.png" x="240" y="20" w="64" h="64" />
```

---

### `<button>`

An interactive button. Must be inside a `<layer>` (else `ValueError: <button>
outside <layer>`). **Not self-closing** — the label is the character data between
`<button>` and `</button>`, `.strip()`-ed.

Unlike box/text/img (which are painted *into* their layer), a `<button>` becomes
its **own** interactive `drm_screen` layer, so `drm_screen.hit_test(x, y)` can
report which button a pointer is over.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `id`         | string | **required** | The button's `hit_id` (what `hit_test` returns) and its layer name |
| `x`          | int    | `0`          | Left edge (screen-absolute) |
| `y`          | int    | `0`          | Top edge (screen-absolute) |
| `w`          | int    | `0`          | Width in pixels |
| `h`          | int    | `0`          | Height in pixels |
| `color`      | string | `#3060a0ff`  | Fill color (see [Colors](#colors)) |
| `text-color` | string | `#ffffffff`  | Label color (note the hyphen) |
| `size`       | int    | `28`         | Label font size |

Behaviour:

- **`id` is mandatory.** A `<button>` without `id` raises `KeyError: 'id'`.
- Compiles to its own `CreateLayer(name=id, …, interactive=True, hit_id=id)` plus
  a `PlaceRawBuffer`, emitted at **z = the parent layer's z + 1000** so buttons
  sit above their layer's painted content.
- Rendered as a **rounded rectangle** (corner radius 12px) filled with `color`,
  the label centered in `text-color`.
- `w`/`h` default to `0` — set them, or the button is a zero-area (untappable)
  layer.
- `drm_screen` only reports the `hit_id`; the **app** decides what a hit means.

```html
<button id="ok" x="40" y="120" w="160" h="56" color="#2a7d4f">OK</button>
```

---

### `<a>`

A navigation link. Identical to `<button>` in every way **except** it carries an
`href` instead of an `id`, and its `hit_id` becomes `href:<href>`. It reuses the
exact same interactive-layer machinery — a link is a button whose action is
"navigate". This mirrors real HTML: `<a>` navigates, `<button>` performs an action.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `href`       | string | **required** | Navigation target; becomes `hit_id` `href:<href>` and the layer name |
| `x` `y` `w` `h` | int | `0` | Geometry — exactly as `<button>` |
| `color`      | string | `#3060a0ff`  | Fill color |
| `text-color` | string | `#ffffffff`  | Label color |
| `size`       | int    | `28`         | Label font size |

Behaviour:

- **`href` is mandatory.** An `<a>` without `href` raises `KeyError: 'href'`.
- Compiles exactly like a `<button>` (rounded rect + centered label, its own
  interactive layer at z+1000), with `hit_id = "href:" + href`.
- `drm_composer` does **not** interpret the href — it just hands the app a
  `hit_id` of `href:<href>`. The app maps it to a page (load a file, look up a
  page, …).

```html
<a href="settings.html" x="40" y="200" w="220" h="56">Settings</a>
```

---

## What a scene compiles to

Each `<layer>` produces exactly two `drm_screen` commands, in this order:

```python
CreateLayer(name=<id>, width=<screen w>, height=<screen h>, z=<z>, visible=<visible>)
PlaceRawBuffer(name=<id>, width=<screen w>, height=<screen h>, data=<RGBA bytes>)
```

`data` is the fully rasterized layer canvas: `width*height*4` bytes of
**RGBA8888** (boxes, text, and images already drawn in). `drm_screen` owns the
layer buffers, composites them by `z`, and pushes the result to `drm-display`.
The single RGBA→BGRA conversion happens downstream in `drm_screen`'s backend —
everything `drm_composer` emits is RGBA.

A `<button>` or `<a>` adds **two more** commands — its own interactive layer,
emitted right after its parent layer's pair:

```python
CreateLayer(name=<id | "href:"+href>, width=<w>, height=<h>, x=<x>, y=<y>,
            z=<layer z>+1000, interactive=True, hit_id=<id | "href:"+href>)
PlaceRawBuffer(name=…, width=<w>, height=<h>, data=<RGBA button bitmap>)
```

So the batch grows by two commands per interactive element. `drm_screen.hit_test`
walks the interactive layers top-down by `z` and returns the `hit_id` under a
point; the app routes it (e.g. an action id, or a `href:` link to a page).

You can inspect the batch without a display:

```python
from drm_composer import Compositor
# A target only needs a .submit(batch) method; use a stub to just see the batch.
class Stub:
    def submit(self, batch): self.batch = batch

c = Compositor(Stub())
batch = c.compile(SCENE_HTML)          # parse + paint, no side effects
for cmd in batch:
    print(type(cmd).__name__, getattr(cmd, "name", ""))
```

`Compositor.compile(html)` returns the batch with no side effects;
`Compositor.render_html(html)` compiles **and** hands the batch to the target's
`submit()`. See [`example/html_demo.py`](example/html_demo.py) for a full
headless end-to-end run.

---

## Complete example

```html
<screen width="800" height="480">

  <!-- z=0: opaque background fill -->
  <layer id="background" z="0">
    <box x="0" y="0" w="800" h="480" color="#141e3c" />
  </layer>

  <!-- z=10: translucent status panel with a label -->
  <layer id="status" z="10" visible="true">
    <box  x="40" y="40" w="380" h="96" color="#000000aa" />
    <text x="60" y="74" size="24" color="#ffffff">System ready</text>
  </layer>

  <!-- z=20: a logo and a footer hint -->
  <layer id="overlay" z="20">
    <img  src="logo.png" x="700" y="20" w="64" h="64" />
    <text x="60" y="430" size="18" color="#7fd0ff">drm_composer -&gt; drm_screen</text>
  </layer>

</screen>
```

---

## Errors at a glance

| Trigger | Exception |
|---|---|
| No `<screen>` in the document | `ValueError: no <screen> element found` |
| `<layer>` not inside `<screen>` | `ValueError: <layer> outside <screen>` |
| `<box>` / `<text>` / `<img>` / `<button>` / `<a>` not inside `<layer>` | `ValueError: <tag> outside <layer>` |
| `<img>` without `src` | `KeyError: 'src'` |
| `<button>` without `id` | `KeyError: 'id'` |
| `<a>` without `href` | `KeyError: 'href'` |
| `<img src="…">` pointing at a missing/unreadable file | `FileNotFoundError` / `PIL.UnidentifiedImageError` |

**Silently ignored (no error):**

- **Unknown elements** — any tag that isn't one of the seven above is dropped.
  This includes `<raw-buffer>` (see below).
- **Unknown attributes** — e.g. `opacity`, `id` on a `<box>`, `style`, classes.
  They are parsed but never read.
- **Bad lengths and colors** — a value with no number (`x="auto"`) falls back to
  the default; an unrecognized color renders transparent. Neither raises — see
  [Value formats](#value-formats-read-this-first).

---

## Not yet implemented

These appear in the design outline / README but are **not** in the current
parser. They are silently ignored if present — treat them as not supported until
a handler exists:

- **`<raw-buffer>`** — listed in the outline's "MVP element set", but there is no
  parser branch for it. Use the lower-level `drm_screen` `PlaceRawBuffer` command
  directly if you need to blit raw bytes.
- **Relative / nested layout** — boxes are not containers; all coordinates are
  screen-absolute (see [the coordinate note](#coordinate-system--absolute-per-screen)).
- **`style=` attributes, CSS rules, classes, font-family selection, text
  wrapping, image aspect-fit** — not parsed. (Lengths *do* now accept units and
  `%`, and colors accept the full CSS range — see
  [Value formats](#value-formats-read-this-first).)
- **`%` on `z` / `size` / screen `width` / `height`** — taken as the bare number,
  not resolved (there is no screen reference for those attributes).

If you add any of these, update this file alongside the parser so the reference
stays generated-from-code.
```

