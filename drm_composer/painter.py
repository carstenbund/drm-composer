"""Painter — Scene -> RGBA layer bitmaps -> drm_screen command batch.

Each layer becomes its own full-screen RGBA canvas; box/text/img nodes are drawn
into it at their coordinates.  The output is a list of drm_screen command records
(the stable contract) — this module never blends the final screen and never
touches DRM.

Channel order is RGBA throughout; the single RGBA->BGRA conversion happens far
downstream in drm_screen's backend.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageColor

from drm_screen.commands import CreateLayer, PlaceRawBuffer

from .scene import Scene, BoxNode, TextNode, ImageNode, ButtonNode

# Buttons sit above their layer's painted content (but well below the pointer).
_BUTTON_Z_OFFSET = 1000


def _rgba(color: str) -> tuple[int, int, int, int]:
    """Parse a CSS color -> (r, g, b, a), the forgiving HTML way.

    Delegates to Pillow's ImageColor, so the full CSS range works: named colors
    (`red`, `navy`, `rebeccapurple`, …), `#rgb` / `#rgba` / `#rrggbb` /
    `#rrggbbaa`, and `rgb()` / `rgba()` / `hsl()`.  An unrecognized value is
    treated as transparent (ignored) rather than raising.
    """
    try:
        c = ImageColor.getrgb(color.strip())
    except (ValueError, AttributeError):
        return (0, 0, 0, 0)
    return c if len(c) == 4 else c + (255,)


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def paint_scene(scene: Scene) -> list:
    """Compile a Scene into a drm_screen command batch."""
    W, H = scene.width, scene.height
    batch = []

    for layer in scene.layers:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        for node in layer.children:
            if isinstance(node, BoxNode):
                draw.rectangle(
                    [node.x, node.y, node.x + node.w - 1, node.y + node.h - 1],
                    fill=_rgba(node.color),
                )
            elif isinstance(node, TextNode):
                draw.text((node.x, node.y), node.text,
                          fill=_rgba(node.color), font=_font(node.size))
            elif isinstance(node, ImageNode):
                _paste_image(canvas, node)
            # ButtonNode is NOT painted here — it becomes its own interactive layer

        rgba = np.asarray(canvas, dtype=np.uint8)
        batch.append(CreateLayer(layer.id, W, H, z=layer.z, visible=layer.visible))
        batch.append(PlaceRawBuffer(
            name=layer.id, width=W, height=H,
            data=np.ascontiguousarray(rgba).tobytes(),
        ))

        # Each <button> -> its own interactive layer (hit_id = id).
        for node in layer.children:
            if isinstance(node, ButtonNode):
                batch.extend(_paint_button(node, layer.z))

    return batch


def _button_bitmap(node: ButtonNode) -> np.ndarray:
    img = Image.new("RGBA", (node.w, node.h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, node.w - 1, node.h - 1], radius=12,
                        fill=_rgba(node.color))
    if node.label:
        f = _font(node.size)
        tw = d.textlength(node.label, font=f)
        d.text(((node.w - tw) / 2, (node.h - node.size) / 2 - 2),
               node.label, fill=_rgba(node.text_color), font=f)
    return np.asarray(img, dtype=np.uint8)


def _paint_button(node: ButtonNode, layer_z: int) -> list:
    rgba = _button_bitmap(node)
    return [
        CreateLayer(node.id, node.w, node.h, x=node.x, y=node.y,
                    z=layer_z + _BUTTON_Z_OFFSET, interactive=True, hit_id=node.id),
        PlaceRawBuffer(name=node.id, width=node.w, height=node.h,
                       data=np.ascontiguousarray(rgba).tobytes()),
    ]


def _paste_image(canvas: Image.Image, node: ImageNode):
    img = Image.open(node.src).convert("RGBA")
    if node.w and node.h:
        img = img.resize((node.w, node.h))
    canvas.alpha_composite(img, (node.x, node.y))
