"""Actions — the composer↔host interface for interactive hits.

`drm_screen.hit_test(x, y)` returns an **opaque `hit_id` string**; it knows
nothing about what the string means.  `drm_composer` *generates* those ids (from
`<a>`, `<button>`, `<input>`, …), so it owns their grammar — and this module is
that grammar, kept pure: no Pillow, no display, no execution.  It only parses a
`hit_id` into a structured :class:`Action` and routes it to host-supplied
callables.  **The host is the sole executor.**

Wire grammar — ``kind:payload``; ``set`` carries ``key=value``; a bare id with no
recognized prefix maps to ``action`` (so it is routable, never a crash):

    href:settings.html   -> Action("navigate", target="settings.html")
    cmd:reboot           -> Action("command",  target="reboot")
    play:/media/clip.mp4 -> Action("play",     target="/media/clip.mp4")
    set:brightness=80    -> Action("set",      target="brightness", value="80")
    quit                 -> Action("action",   target="quit")

Routing is **allowlist-by-registration**: the host registers only the commands,
setting keys, and actions it permits; anything unregistered is a silent no-op
(optionally logged).  Nothing the host did not opt into can ever fire — a stale
or hostile scene cannot trigger it.
"""

from dataclasses import dataclass

# hit_id prefixes -> Action.kind.  The order is irrelevant; lookup is exact on
# the text before the first ':'.
_PREFIXES = {
    "href": "navigate",
    "cmd": "command",
    "play": "play",
    "set": "set",
}


@dataclass(frozen=True)
class Action:
    """A parsed interactive intent.  Pure data — carries no behaviour.

    kind    one of: navigate | command | play | set | action
    target  page / command name / media src / setting key / bare id
    value   the new value (``set`` only; ``None`` otherwise)
    raw     the original hit_id, for logging and unknown kinds
    """
    kind: str
    target: str
    value: str | None = None
    raw: str = ""


def parse_action(hit_id: str) -> Action:
    """Parse a raw ``hit_id`` into an :class:`Action`.  Total — never raises.

    An empty/None id, or one whose prefix is not recognized, becomes an
    ``action`` carrying the whole string as ``target`` (bare ids like ``quit``
    and ``back`` route this way, preserving the pre-actions app contract).
    """
    raw = hit_id or ""
    prefix, sep, payload = raw.partition(":")
    kind = _PREFIXES.get(prefix) if sep else None
    if kind is None:
        # No recognized prefix -> a bare action id (quit, back, …).
        return Action(kind="action", target=raw, raw=raw)
    if kind == "set":
        key, eq, value = payload.partition("=")
        return Action(kind="set", target=key, value=(value if eq else None), raw=raw)
    return Action(kind=kind, target=payload, raw=raw)


class Dispatcher:
    """Routes :class:`Action`s to host-registered callables.  Executes nothing
    itself — it only calls what the host registered.

    Registration *is* the allowlist: an unregistered ``command`` / ``set`` key /
    ``action`` is a silent no-op (logged via ``logger`` if supplied).  ``navigate``
    and ``play`` take a single handler each; ``command`` / ``set`` / ``action``
    are keyed, so only named entries the host opted into can fire.

        d = Dispatcher()
        d.on_navigate(app.goto)
        d.on_command("reboot", do_reboot)      # cmd:reboot allowed; others ignored
        d.on_play(launch_mpv)
        d.on_set("brightness", set_brightness)
        d.dispatch(parse_action(service.hit_test(x, y)))
    """

    def __init__(self, logger=None):
        self._navigate = None
        self._play = None
        self._commands: dict[str, callable] = {}
        self._sets: dict[str, callable] = {}
        self._actions: dict[str, callable] = {}
        self._log = logger

    # ── registration ───────────────────────────────────────────────────────────

    def on_navigate(self, fn):
        """Handler for ``href:`` hits — called as ``fn(target)``."""
        self._navigate = fn
        return self

    def on_play(self, fn):
        """Handler for ``play:`` hits — called as ``fn(target)`` (the media src)."""
        self._play = fn
        return self

    def on_command(self, name, fn):
        """Allow ``cmd:<name>`` — called as ``fn()``."""
        self._commands[name] = fn
        return self

    def on_set(self, key, fn):
        """Allow ``set:<key>=<value>`` — called as ``fn(value)``."""
        self._sets[key] = fn
        return self

    def on_action(self, name, fn):
        """Allow a bare action id (``quit``, ``back``, …) — called as ``fn()``."""
        self._actions[name] = fn
        return self

    # ── dispatch ─────────────────────────────────────────────────────────────────

    def dispatch(self, action: "Action | str | None") -> bool:
        """Route an Action (or a raw hit_id, or None) to its handler.

        Returns True if a registered handler ran, False otherwise (unknown /
        unregistered / no hit).  Never raises on an unhandled action.
        """
        if action is None:
            return False
        if isinstance(action, str):
            action = parse_action(action)

        if action.kind == "navigate":
            return self._call(self._navigate, action, action.target)
        if action.kind == "play":
            return self._call(self._play, action, action.target)
        if action.kind == "command":
            return self._call(self._commands.get(action.target), action)
        if action.kind == "set":
            return self._call(self._sets.get(action.target), action, action.value)
        if action.kind == "action":
            return self._call(self._actions.get(action.target), action)
        return self._deny(action)

    # ── internals ──────────────────────────────────────────────────────────────

    def _call(self, fn, action, *args) -> bool:
        if fn is None:
            return self._deny(action)
        fn(*args)
        return True

    def _deny(self, action) -> bool:
        if self._log is not None:
            self._log.info("drm_composer: no handler for hit_id %r", action.raw)
        return False
