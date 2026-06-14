"""drm_composer — stateless scene-to-screen-command compiler.

Parses a constrained screen-HTML subset, rasterizes elements to RGBA bitmaps,
and emits drm_screen command batches.  Holds no screen state, never blends the
final frame, never touches DRM/KMS.
"""

from .scene import Scene, LayerNode, BoxNode, TextNode, ImageNode, ButtonNode
from .parser import parse_scene
from .painter import paint_scene
from .compositor import Compositor
from .actions import Action, parse_action, Dispatcher

from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("drm-composer")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "Scene", "LayerNode", "BoxNode", "TextNode", "ImageNode", "ButtonNode",
    "parse_scene", "paint_scene", "Compositor",
    "Action", "parse_action", "Dispatcher", "__version__",
]
