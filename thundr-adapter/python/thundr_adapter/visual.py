"""Visual integrations: float/orb/panel state queries (read-only).

Reports what the visual surfaces look like from the files on disk:
which float/scout hosts exist in hosts.json and whether their pages are
present, where thundr-orb.js lives, and which Apple panels the registry
declares. Nothing here opens a window, moves the orb, or takes a
screenshot. The shot hook is documented, never executed: screenshots
need a human GO (they capture the user's screen).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ORB_FILENAME = "thundr-orb.js"
FLOAT_FILENAME = "float.html"

# The live macOS float window, described from Rizal's screenshot of the
# running RTHUNDR app (2026-11-19 13:33 MST,
# grounding/thundr-float-live-2026-11-19.png). This is the visual
# integration target for adapter.visual: the adapter reports this layout
# and the float/scout host states; it never opens, moves, types into, or
# screenshots the window.
FLOAT_LAYOUT = {
    "source": "screenshot of the live RTHUNDR float, 2026-11-19 13:33 MST",
    "app": "RTHUNDR (menu-bar app, THUNDR-CRYPTOBOT Xcode workspace)",
    "window": ("floating panel over other apps; purple border, "
               "green corner brackets"),
    "avatar": ("ThundR imp above the window with a 'ThundR · awake' label "
               "and a lightning bolt"),
    "header": ("green text: '⚡ THUNDR · RDOS · SANDISK GRANITE 4.2 3B · "
               "127.0.0.1:4983' + SANDISK tag; red ✕ close button top-right"),
    "shell": ("R:> input row, green border, quick commands 'models · "
              "use qwen · use granite · …' + green SEND button"),
    "status_bar": "'Qwen 1.7B · UP' pill, 'idle', level bar, 'q:0', clock",
    "reply_area": ("dark body; parser replies carry a green "
                   "'via parser' attribution"),
    "ready_reply": ("ThundR ready. Try: wallet balances · casket verify · "
                    "signing status · prompt faceid · sign this <dir> · "
                    "request approval <what>"),
}

# Where thundr-orb.js is known to live, relative to the ThundR root
# (~/R/ЯLAB/RCRYPTOFORGE), from the project analysis.
ORB_KNOWN_PATHS = (
    "cryptoapp/ThundR/RTHUNDR-IOS/www/thundr-orb.js",
    "cryptoapp/ThundR/THUNDR-FLOAT/web/thundr-orb.js",
    "APPS/RDRAGON-ANDROID-20261112-vc36/src/web/skills/rthundr-1.2.0/www/thundr-orb.js",
    "APPS/RDRAGON-LINUX-UBPORTS-20261112-vc35/stage-payload/web/skills/rthundr-1.2.0/www/thundr-orb.js",
)


def float_state(hosts_path=None, root=None) -> dict:
    """Float/scout host states from hosts.json + presence on disk.

    Reuses :func:`analyze.host_check` for the wired/missing accounting and
    adds the float-vs-scout split. When the ThundR root is absent (this
    VM), every host reports ``present: false`` honestly.
    """
    from .analyze import host_check
    from .registry import canonical_path

    if hosts_path is None:
        default = canonical_path().parent / "hosts.json"
        hosts_path = default if default.is_file() else None
    if hosts_path is None:
        return {"exists": False,
                "error": "hosts.json not found (no ThundR tree on this machine)",
                "hosts": []}
    checked = host_check(hosts_path, root=root)
    floats = [h for h in checked.get("hosts", [])
              if h.get("path", "").endswith("float.html")]
    scouts = [h for h in checked.get("hosts", [])
              if h.get("path", "").endswith("scout.html")]
    checked["float_hosts"] = len(floats)
    checked["scout_hosts"] = len(scouts)
    checked["floats_present"] = sum(1 for h in floats if h.get("present"))
    checked["scouts_present"] = sum(1 for h in scouts if h.get("present"))
    return checked


def orb_state(root=None) -> dict:
    """Where thundr-orb.js exists under the ThundR root (if any)."""
    base = Path(root) if root is not None else Path.home() / "R/ЯLAB/RCRYPTOFORGE"
    found = []
    missing = []
    for rel in ORB_KNOWN_PATHS:
        target = base / rel
        (found if target.is_file() else missing).append(rel)
    return {"root": str(base), "root_exists": base.exists(),
            "found": found, "missing": missing,
            "note": "thundr-orb.js is the float UI orb (67,809 bytes in the "
                    "1.2.0 bundles). Presence on disk only; liveness needs "
                    "the running host."}


def panel_state(registry=None) -> dict:
    """Apple panels declared in the registry (profile / ghostmachine)."""
    from .registry import Registry

    reg = registry or Registry.load()
    panels = reg.panels.get("apple", {})
    return {"panels": panels,
            "note": str(panels.get("note", "")),
            "source": str(reg.source)}


def float_window() -> dict:
    """The live macOS float window layout (from the 2026-11-19 screenshot).

    A static description of the visual integration target, not a live
    read: the adapter cannot see the running window from here. The
    layout is reported so bots and UIs know what the float is and where
    the R:> shell, engine header, and status bar live.
    """
    return dict(FLOAT_LAYOUT)


def shot_hook() -> dict:
    """The documented screenshot hook. Never executed by the adapter.

    On Linux, ``shot.py`` (in the 1.2.0-l1 source) drives screenshots
    under Xvfb; on macOS the equivalent is a human-run screencapture.
    Screenshots capture the user's screen, so the adapter only describes
    the hook and refuses to run it. A future GO-gated step may execute it
    with Rizal's explicit approval for a named window.
    """
    return {
        "hook": "shot",
        "executed": False,
        "linux": "extracts/linux-src/shot.py (Xvfb; see src-linux README-LINUX.md)",
        "macos": "screencapture (human-run; never executed by the adapter)",
        "note": ("Screenshots capture the user's screen and need an explicit "
                 "GO naming the window. This adapter documents the hook only."),
    }


def run(registry=None, hosts_path=None, root=None) -> dict:
    """Combined visual report: floats, orb, panels, shot hook."""
    return {
        "float": float_state(hosts_path=hosts_path, root=root),
        "float_window": float_window(),
        "orb": orb_state(root=root),
        "panels": panel_state(registry=registry),
        "shot": shot_hook(),
    }
