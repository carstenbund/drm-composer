"""Scene model — the parsed, in-memory form of a screen-HTML document.

A Scene is a screen with ordered layers; each layer holds visual nodes
(box / text / img).  This is pure data: the parser builds it, the painter
consumes it.  Nothing here rasterizes or talks to drm_screen.
"""

from dataclasses import dataclass, field


@dataclass
class BoxNode:
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    color: str = "#000000ff"   # #rrggbb or #rrggbbaa


@dataclass
class TextNode:
    text: str
    x: int = 0
    y: int = 0
    size: int = 16
    color: str = "#ffffffff"


@dataclass
class ImageNode:
    src: str
    x: int = 0
    y: int = 0
    w: int | None = None       # None -> native size
    h: int | None = None
    fit: str = "fill"          # fill (stretch) | contain (letterbox) | cover (crop)


@dataclass
class ButtonNode:
    """An interactive region: compiled to its own interactive layer (hit_id=id)."""
    id: str
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    color: str = "#3060a0ff"        # button fill
    text_color: str = "#ffffffff"
    size: int = 28
    label: str = ""                  # character data inside <button>...</button>


@dataclass
class LayerNode:
    id: str
    z: int = 0
    visible: bool = True
    children: list = field(default_factory=list)   # Box/Text/Img/Button nodes


@dataclass
class Scene:
    width: int
    height: int
    layers: list = field(default_factory=list)      # LayerNode in document order
