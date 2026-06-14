# drm_composer

Stateless scene-to-screen-command compiler. Parses a declarative HTML-like
scene, rasterizes elements to **RGBA** bitmaps, and emits commands for
[`drm_screen`](../drm_screen).

Python package: `drm_composer`.

```
drm_composer  →  drm_screen  →  drm-display
 scene → cmds     layers →         frame →
 + RGBA bitmaps   composited       DRM/KMS
                  frame            pixels
```

- Parses `screen` / `layer` / `box` / `text` / `img` / `raw-buffer`
- Resolves layout (x, y, w, h, z, visibility)
- Rasterizes to RGBA bitmaps
- Translates layers into `drm_screen` commands

It holds **no** screen state, does **not** blend the final frame (that's
`drm_screen`'s compositor), and does **not** know DRM/KMS (that's `drm_display`).

See [outline.md](outline.md) for the design.
