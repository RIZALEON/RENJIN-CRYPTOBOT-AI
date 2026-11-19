"""ThundR command registry access for the adapter.

Loads the canonical THUNDR-CORE registry (``thundr-commands.json``, schema
``thundr.core.commands.v1``) and enforces its refuse rules at the adapter
layer for every agent, so no caller can bypass them by talking to ThundR
through a different route.

Resolution order for the registry file:
  1. ``$THUNDR_CORE/thundr-commands.json`` (explicit override)
  2. The canonical Mac path
     ``~/R/ЯLAB/RCRYPTOFORGE/cryptoapp/ThundR/THUNDR-CORE/thundr-commands.json``
  3. The bundled snapshot shipped in this package (``data/``)

The loader prefers the canonical registry whenever it is present; the
snapshot exists so the adapter works offline on machines without the
ThundR tree (like this VM). ``Registry.source`` always says which file
was loaded, and ``content_sha256()`` uses the gen-thundr-core
normalisation (sorted keys, compact separators, ``generated``/``build``
keys excluded) so stamps compare cleanly against ``thundr-build.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

SCHEMA = "thundr.core.commands.v1"

# Canonical Mac location of the THUNDR-CORE registry (hosts.json root
# ~/R/ЯLAB/RCRYPTOFORGE, workspace cryptoapp/ThundR/THUNDR-CORE/).
CANONICAL_RELATIVE = Path("R/ЯLAB/RCRYPTOFORGE/cryptoapp/ThundR/THUNDR-CORE/thundr-commands.json")

PACKAGE_DIR = Path(__file__).resolve().parent
BUNDLED_SNAPSHOT = PACKAGE_DIR / "data" / "thundr-commands.json"


def canonical_path() -> Path:
    """The canonical Mac registry path (may not exist on this machine)."""
    return Path.home() / CANONICAL_RELATIVE


def resolve_registry_path(explicit: str | os.PathLike | None = None) -> Path:
    """Resolve the registry file in the documented order. Raises FileNotFoundError."""
    candidates = []
    if explicit is not None:
        candidates.append(Path(explicit))
    env = os.environ.get("THUNDR_CORE")
    if env:
        candidates.append(Path(env) / "thundr-commands.json")
    candidates.append(canonical_path())
    candidates.append(BUNDLED_SNAPSHOT)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "thundr-commands.json not found in THUNDR_CORE, the canonical Mac "
        "path, or the bundled snapshot"
    )


def content_stamp(data: dict) -> str:
    """sha256 of the normalised registry JSON (gen-thundr-core.py pattern).

    Drops the ``generated`` and ``build`` keys, then dumps with sorted
    keys and compact separators. A stamp only changes when content changes,
    which is how ``thundr-build.json`` decides whether to bump the build.
    """
    trimmed = {k: v for k, v in data.items() if k not in ("generated", "build")}
    blob = json.dumps(trimmed, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Registry:
    """A loaded thundr-commands.json with query + refuse enforcement."""

    def __init__(self, data: dict, source: Path):
        if data.get("schema") != SCHEMA:
            raise ValueError("not a %s registry: %r" % (SCHEMA, data.get("schema")))
        self.data = data
        self.source = Path(source)
        self._commands = {c["id"]: c for c in data.get("commands", [])}
        self._refuse = [
            (re.compile(pattern), label)
            for pattern, label in data.get("refuse", [])
        ]
        self._aliases = [
            (re.compile(pattern), replacement)
            for pattern, replacement, _label in data.get("aliases", [])
        ]

    @classmethod
    def load(cls, explicit: str | os.PathLike | None = None) -> "Registry":
        """Load from the resolution order. Prefers canonical when present."""
        path = resolve_registry_path(explicit)
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh), path)

    # -- identity -----------------------------------------------------
    @property
    def version(self) -> str:
        return str(self.data.get("version", "?"))

    @property
    def name(self) -> str:
        return str(self.data.get("name", "?"))

    @property
    def source_info(self) -> dict:
        return dict(self.data.get("source", {}))

    def stamp(self) -> str:
        return content_stamp(self.data)

    # -- rules --------------------------------------------------------
    @property
    def rules(self) -> dict:
        return dict(self.data.get("rules", {}))

    @property
    def refuse_reply(self) -> str:
        return str(self.rules.get("refuse_reply", "Refused."))

    @property
    def hosts(self) -> list:
        return list(self.data.get("hosts", []))

    @property
    def groups(self) -> dict:
        return dict(self.data.get("groups", {}))

    @property
    def models(self) -> dict:
        return dict(self.data.get("models", {}))

    @property
    def panels(self) -> dict:
        return dict(self.data.get("panels", {}))

    @property
    def local_commands(self) -> list:
        return list(self.data.get("local_commands", []))

    # -- refuse enforcement -------------------------------------------
    def refuse_check(self, text: str) -> tuple[bool, str | None, str | None]:
        """Check text against the registry's refuse regexes.

        Returns (matched, label, pattern). Matching is case-insensitive:
        the registry patterns are lowercase and ThundR normalises input
        the same way (thundr_chat.py lowers every line; NativeCommands
        lowercases in normalize()).
        """
        lowered = (text or "").strip().lower()
        for pattern, label in self._refuse:
            if pattern.search(lowered):
                return True, label, pattern.pattern
        return False, None, None

    def is_refused(self, text: str) -> bool:
        matched, _, _ = self.refuse_check(text)
        return matched

    def refuse_patterns(self) -> list:
        """The [pattern, label] refuse rules, for inspection and tests."""
        return [[p.pattern, label] for p, label in self._refuse]

    # -- aliases ------------------------------------------------------
    def resolve_alias(self, text: str) -> str:
        """Apply registry aliases (e.g. ``manual [words]`` -> ``AUTOMANUAL [words]``).

        The alias label in the registry (``manual [words] -> AUTOMANUAL
        [words]``) keeps the captured words; a bare ``subn`` would drop
        them, so the captured group is re-appended when present.
        """
        stripped = (text or "").strip()
        for pattern, replacement in self._aliases:
            match = pattern.match(stripped)
            if match:
                out = replacement
                if match.lastindex and match.group(1):
                    out += " " + match.group(1)
                return out
        return text

    # -- queries ------------------------------------------------------
    def count(self) -> int:
        return len(self._commands)

    def get(self, command_id: str) -> dict | None:
        return self._commands.get(command_id)

    def all(self) -> list:
        return list(self.data.get("commands", []))

    def by_group(self, group: str) -> list:
        want = group.strip().lower()
        return [c for c in self.all()
                if want in str(c.get("group", "")).lower()
                or want == str(c.get("group", "")).lower()]

    def by_host(self, host: str) -> list:
        """Commands with any availability on ``host`` (registry hosts map)."""
        return [c for c in self.all()
                if host in (c.get("hosts") or {})]

    def go_commands(self) -> list:
        """Commands flagged go=true (need Rizal's GO to run)."""
        return [c for c in self.all() if c.get("go")]

    def search(self, text: str, limit: int = 20) -> list:
        """Token search over id/cmd/does/group/owner_app, ranked by field.

        Every word in the query must appear in a command; a field holding
        all the words scores higher, and words split across fields count
        as a weak match. ``open app`` therefore finds ``open <App>``.
        """
        tokens = [t for t in (text or "").strip().lower().split() if t]
        if not tokens:
            return []
        ranked = []
        for cmd in self.all():
            if len(tokens) == 1 and tokens[0] == str(cmd.get("id", "")).lower():
                ranked.append((100, cmd))
                continue
            fields = {
                "cmd": str(cmd.get("cmd", "")).lower(),
                "does": str(cmd.get("does", "")).lower(),
                "group": str(cmd.get("group", "")).lower(),
                "owner_app": str(cmd.get("owner_app", "")).lower(),
            }
            if not all(tok in " ".join(fields.values()) for tok in tokens):
                continue
            if all(tok in fields["cmd"] for tok in tokens):
                score = 50
            elif all(tok in fields["does"] for tok in tokens):
                score = 30
            elif all(tok in fields["group"] for tok in tokens):
                score = 20
            elif all(tok in fields["owner_app"] for tok in tokens):
                score = 10
            else:
                score = 5
            ranked.append((score, cmd))
        ranked.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
        return [cmd for _, cmd in ranked[:limit]]

    def help_text(self) -> str:
        """Deterministic help generated from this registry (no model needed)."""
        groups: dict[str, int] = {}
        for cmd in self.all():
            groups[str(cmd.get("group", "?"))] = groups.get(str(cmd.get("group", "?")), 0) + 1
        lines = [
            "THUNDR commands: %d known · registry %s (source: %s)"
            % (self.count(), self.version, self.source.name),
            "Groups:",
        ]
        for name in sorted(groups):
            lines.append("  %s — %d" % (name, groups[name]))
        lines.append("Ask `commands <id>` for one command, or `commands search <words>`.")
        lines.append("GO commands (%d) need Rizal's GO. Refused patterns are never run."
                     % len(self.go_commands()))
        return "\n".join(lines)
