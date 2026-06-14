"""Parser — screen-HTML subset -> Scene tree.

Constrained, declarative markup.  Supported elements:

    <screen width="800" height="480">
      <layer id="status" z="10" visible="true">
        <box    x="20" y="20" w="300" h="80" color="#000000cc" />
        <text   x="40" y="56" size="22" color="#ffffff">Ready</text>
        <img    src="logo.png" x="240" y="20" w="64" h="64" />
        <button id="ok" x="40" y="120" w="120" h="48">OK</button>
        <a href="next.html" x="200" y="120" w="120" h="48">Next</a>
      </layer>
    </screen>

Values are parsed the forgiving way HTML is: lengths tolerate units and accept
percentages of the screen (`x="50%"`, `w="20px"`); colors accept the full CSS
range (names, `#rgb`/`#rgba`/`#rrggbb`/`#rrggbbaa`, `rgb()`, `rgba()`).  A missing
or unparseable value falls back to the element default rather than raising.

`<button>` and `<a>` both compile to interactive layers (a click yields a
hit_id): a button's hit_id is its `id`; a link's is `href:<href>`.  Built on
stdlib html.parser — no external dependency.
"""

import re

from html.parser import HTMLParser

from .scene import Scene, LayerNode, BoxNode, TextNode, ImageNode, ButtonNode

_NUM = re.compile(r"[-+]?\d*\.?\d+")


def _num(s: str):
    """First number in a string, or None — '20px' -> 20.0, 'auto' -> None."""
    m = _NUM.search(s)
    return float(m.group()) if m else None


def _length(value, default, ref=None):
    """HTML-style length -> int pixels.

    Takes the leading number and ignores any trailing unit ('px', 'em', …);
    a trailing '%' is resolved against `ref` (a screen dimension) when given.
    Missing or unparseable -> `default` (never raises).
    """
    if value is None:
        return default
    s = value.strip().lower()
    if not s:
        return default
    if s.endswith("%"):
        n = _num(s[:-1])
        if n is None:
            return default
        return int(round(n / 100.0 * ref)) if ref is not None else int(round(n))
    n = _num(s)
    return default if n is None else int(round(n))


def _bool(attrs, key, default=True):
    v = attrs.get(key)
    if v is None:
        return default
    return v.strip().lower() not in ("false", "0", "no", "hidden")


def _fullscreen(attrs):
    """img `fullscreen` mode: '' (off) | 'toggle' | 'always'.

    Bare `fullscreen` (or `="toggle"`, `="true"`, `="on"`) -> 'toggle' (tap to
    expand). `="always"` -> drawn fullscreen from the source. `="false"`/`"0"`/
    `"no"`/`"off"` or absent -> '' (off)."""
    if "fullscreen" not in attrs:
        return ""
    v = attrs["fullscreen"]
    if v is None:                       # bare attribute
        return "toggle"
    v = v.strip().lower()
    if v in ("false", "0", "no", "off"):
        return ""
    return "always" if v == "always" else "toggle"


class _SceneParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scene: Scene | None = None
        self._layer: LayerNode | None = None
        self._text: TextNode | None = None     # open <text> collecting char data
        self._button: ButtonNode | None = None  # open <button>/<a> collecting label

    # length helpers: x/w resolve % against screen width, y/h against height
    def _w(self, a, key, default=0):
        return _length(a.get(key), default, self.scene.width)

    def _h(self, a, key, default=0):
        return _length(a.get(key), default, self.scene.height)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "screen":
            self.scene = Scene(width=_length(a.get("width"), 1920),
                               height=_length(a.get("height"), 1080))
        elif tag == "layer":
            self._require_scene(tag)
            self._layer = LayerNode(
                id=a.get("id") or f"layer{len(self.scene.layers)}",
                z=_length(a.get("z"), 0),
                visible=_bool(a, "visible", True),
            )
            self.scene.layers.append(self._layer)
        elif tag == "box":
            self._require_layer(tag)
            self._layer.children.append(BoxNode(
                x=self._w(a, "x"), y=self._h(a, "y"),
                w=self._w(a, "w"), h=self._h(a, "h"),
                color=a.get("color", "#000000ff"),
            ))
        elif tag == "img":
            self._require_layer(tag)
            self._layer.children.append(ImageNode(
                src=a["src"],
                x=self._w(a, "x"), y=self._h(a, "y"),
                w=self._w(a, "w", None), h=self._h(a, "h", None),
                fit=a.get("fit", "fill").strip().lower(),
                fullscreen=_fullscreen(a),
            ))
        elif tag == "text":
            self._require_layer(tag)
            self._text = TextNode(
                text="",
                x=self._w(a, "x"), y=self._h(a, "y"),
                size=_length(a.get("size"), 16),
                color=a.get("color", "#ffffffff"),
            )
            self._layer.children.append(self._text)
        elif tag in ("button", "a"):
            self._require_layer(tag)
            # All three reuse the same interactive-layer machinery; only the
            # hit_id prefix differs (the host routes on it):
            #   <a href="X">            -> href:X   (navigate)
            #   <button action="X">     -> cmd:X    (run an allowlisted command)
            #   <button id="X">         -> X        (bare action, e.g. quit/back)
            if tag == "a":
                hit_id = "href:" + a["href"]
            elif "action" in a:
                hit_id = "cmd:" + a["action"]
            else:
                hit_id = a["id"]
            self._button = ButtonNode(
                id=hit_id,
                x=self._w(a, "x"), y=self._h(a, "y"),
                w=self._w(a, "w"), h=self._h(a, "h"),
                color=a.get("color", "#3060a0ff"),
                text_color=a.get("text-color", "#ffffffff"),
                size=_length(a.get("size"), 28),
            )
            self._layer.children.append(self._button)

    def handle_data(self, data):
        if self._text is not None:
            self._text.text += data
        elif self._button is not None:
            self._button.label += data

    def handle_endtag(self, tag):
        if tag == "text" and self._text is not None:
            self._text.text = self._text.text.strip()
            self._text = None
        elif tag in ("button", "a") and self._button is not None:
            self._button.label = self._button.label.strip()
            self._button = None
        elif tag == "layer":
            self._layer = None

    # ── guards ────────────────────────────────────────────────────────────────

    def _require_scene(self, tag):
        if self.scene is None:
            raise ValueError(f"<{tag}> outside <screen>")

    def _require_layer(self, tag):
        if self._layer is None:
            raise ValueError(f"<{tag}> outside <layer>")


def parse_scene(html: str) -> Scene:
    p = _SceneParser()
    p.feed(html)
    p.close()
    if p.scene is None:
        raise ValueError("no <screen> element found")
    return p.scene
