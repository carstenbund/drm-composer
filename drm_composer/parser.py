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

`<button>` and `<a>` both compile to interactive layers (a click yields a
hit_id): a button's hit_id is its `id`; a link's is `href:<href>`.  Text content
is the character data inside the element.  Built on stdlib html.parser — no
external dependency.
"""

from html.parser import HTMLParser

from .scene import Scene, LayerNode, BoxNode, TextNode, ImageNode, ButtonNode


def _int(attrs, key, default=None):
    v = attrs.get(key)
    return int(v) if v is not None else default


def _bool(attrs, key, default=True):
    v = attrs.get(key)
    if v is None:
        return default
    return v.strip().lower() not in ("false", "0", "no", "hidden")


class _SceneParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scene: Scene | None = None
        self._layer: LayerNode | None = None
        self._text: TextNode | None = None     # open <text> collecting char data
        self._button: ButtonNode | None = None  # open <button> collecting its label

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "screen":
            self.scene = Scene(width=_int(a, "width", 1920),
                               height=_int(a, "height", 1080))
        elif tag == "layer":
            self._require_scene(tag)
            self._layer = LayerNode(
                id=a.get("id") or f"layer{len(self.scene.layers)}",
                z=_int(a, "z", 0),
                visible=_bool(a, "visible", True),
            )
            self.scene.layers.append(self._layer)
        elif tag == "box":
            self._require_layer(tag)
            self._layer.children.append(BoxNode(
                x=_int(a, "x", 0), y=_int(a, "y", 0),
                w=_int(a, "w", 0), h=_int(a, "h", 0),
                color=a.get("color", "#000000ff"),
            ))
        elif tag == "img":
            self._require_layer(tag)
            self._layer.children.append(ImageNode(
                src=a["src"],
                x=_int(a, "x", 0), y=_int(a, "y", 0),
                w=_int(a, "w", None), h=_int(a, "h", None),
            ))
        elif tag == "text":
            self._require_layer(tag)
            self._text = TextNode(
                text="",
                x=_int(a, "x", 0), y=_int(a, "y", 0),
                size=_int(a, "size", 16),
                color=a.get("color", "#ffffffff"),
            )
            self._layer.children.append(self._text)
        elif tag in ("button", "a"):
            self._require_layer(tag)
            # <a href="X"> is a navigation link — it reuses the button machinery,
            # with hit_id "href:X" so the app routes it to a page. <button id="X">
            # is an action (the app chooses what id means).
            hit_id = ("href:" + a["href"]) if tag == "a" else a["id"]
            self._button = ButtonNode(
                id=hit_id,
                x=_int(a, "x", 0), y=_int(a, "y", 0),
                w=_int(a, "w", 0), h=_int(a, "h", 0),
                color=a.get("color", "#3060a0ff"),
                text_color=a.get("text-color", "#ffffffff"),
                size=_int(a, "size", 28),
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
