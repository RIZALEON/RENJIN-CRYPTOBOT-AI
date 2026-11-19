"""Plugin manifests: load, verify, register. Never execute in v0.1.

A plugin is a JSON manifest plus one entry file. The manifest names the
plugin, its version, the capabilities it offers, and the SHA-256 of its
entry file. The adapter verifies the entry file (exact bytes + SHA-256,
no symlinks — the ``ModelSelect`` child() pattern) and registers its
capabilities. It does NOT import or execute plugin code in v0.1: loading
foreign code is a future GO-gated step, and this module says so plainly
instead of pretending otherwise.

Manifest format (``<name>.tpa-plugin.json``)::

    {
      "schema": "tpa.plugin.v1",
      "name": "example-plugin",
      "version": "0.1.0",
      "description": "What the plugin does, in one sentence.",
      "entry": "example.py",
      "sha256": "<64 hex chars of the entry file>",
      "capabilities": [
        {"name": "example.echo", "method": "adapter.chat",
         "description": "Echoes text through the adapter."}
      ]
    }

``entry`` must be a plain file name directly inside the plugin directory:
no separators, no ``..``, no hidden names, not a symlink.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

SCHEMA = "tpa.plugin.v1"
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class PluginError(ValueError):
    """Manifest or verification failure."""


def _safe_child(plugin_dir: Path, name: str) -> Path:
    """A plain file name directly inside dir (ModelSelect.child pattern)."""
    if (not isinstance(name, str) or not name or "/" in name or "\\" in name
            or name.startswith(".") or name == ".."):
        raise PluginError("unsafe plugin entry name: %r" % (name,))
    target = plugin_dir / name
    if target.is_symlink():
        raise PluginError("symlinked plugin entry refused: %r" % (name,))
    if not target.is_file():
        raise PluginError("plugin entry missing: %r" % (name,))
    if target.resolve().parent != plugin_dir.resolve():
        raise PluginError("plugin entry escapes its directory: %r" % (name,))
    return target


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: str | os.PathLike) -> dict:
    """Parse and validate a plugin manifest. Returns the manifest dict."""
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PluginError("unreadable plugin manifest %s: %s" % (target, exc)) from exc
    if not isinstance(data, dict):
        raise PluginError("plugin manifest must be a JSON object: %s" % target)
    if data.get("schema") != SCHEMA:
        raise PluginError("not a %s manifest: %r" % (SCHEMA, data.get("schema")))
    for field in ("name", "version", "entry", "sha256"):
        if not data.get(field):
            raise PluginError("plugin manifest missing %r: %s" % (field, target))
    if not _SHA256_HEX.match(str(data["sha256"])):
        raise PluginError("plugin manifest sha256 must be 64 hex chars: %s" % target)
    capabilities = data.get("capabilities", [])
    if not isinstance(capabilities, list):
        raise PluginError("plugin capabilities must be a list: %s" % target)
    for cap in capabilities:
        if not isinstance(cap, dict) or not cap.get("name"):
            raise PluginError("each capability needs a name: %s" % target)
    data["_manifest_path"] = str(target)
    return data


def verify(manifest: dict, plugin_dir: str | os.PathLike | None = None) -> dict:
    """Verify a manifest's entry file: present, regular, exact SHA-256.

    Returns ``{"ok": bool, "file": ..., "bytes": ..., "sha256": ...}``
    with a ``reason`` on failure. Never imports or executes the file.
    """
    base = Path(plugin_dir) if plugin_dir is not None else Path(
        manifest.get("_manifest_path", ".")).parent
    try:
        entry = _safe_child(base, manifest["entry"])
    except PluginError as exc:
        return {"ok": False, "file": manifest.get("entry"), "reason": str(exc)}
    digest = _sha256_file(entry)
    if digest != manifest["sha256"]:
        return {"ok": False, "file": manifest["entry"],
                "bytes": entry.stat().st_size, "sha256": digest,
                "reason": "sha256 mismatch (manifest expects %s)" % manifest["sha256"]}
    return {"ok": True, "file": manifest["entry"],
            "bytes": entry.stat().st_size, "sha256": digest,
            "reason": "exact identity verified"}


class CapabilityRegistry:
    """Registered plugin capabilities (name -> plugin + method + description).

    Registration is data only. No plugin code runs through this registry
    in v0.1.
    """

    def __init__(self):
        self._caps: dict[str, dict] = {}

    def register(self, manifest: dict, plugin_dir=None) -> dict:
        """Verify a manifest and register its capabilities. Returns a report."""
        check = verify(manifest, plugin_dir)
        report = {"plugin": manifest.get("name"), "version": manifest.get("version"),
                  "verified": check["ok"], "registered": [], "skipped": []}
        if not check["ok"]:
            report["reason"] = check.get("reason")
            return report
        for cap in manifest.get("capabilities", []):
            name = cap["name"]
            if name in self._caps:
                report["skipped"].append(
                    {"name": name, "reason": "already registered by %s"
                     % self._caps[name]["plugin"]})
                continue
            self._caps[name] = {
                "plugin": manifest["name"],
                "version": manifest.get("version"),
                "method": cap.get("method"),
                "description": cap.get("description", ""),
            }
            report["registered"].append(name)
        return report

    def list_capabilities(self) -> dict:
        return dict(self._caps)

    def get(self, name: str) -> dict | None:
        return self._caps.get(name)
