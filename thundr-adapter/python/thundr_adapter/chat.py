"""Chat routing: get text to a ThundR brain, or answer honestly offline.

Route order (mirrors the dispatch in ``thundr_chat.handle`` and the
native ``LocalBrain.call`` bridge):

  1. Refuse check against the registry's 7 refuse regexes. A match is
     refused with the registry's own ``refuse_reply``; nothing runs.
  2. GO-gated wallet/signing verbs (the parser's ready reply in the live
     float: wallet balances, casket verify, signing status, prompt
     faceid, sign this, request approval). They map to the LIVE
     /rmint/request flow, the highest-sensitivity surface, and
     bot/agent input cannot request, confirm, or send on it (Linux
     brain's bot-tagged guard). They are answered with a GO-gated
     handoff and NEVER forwarded to the MCR or any executor.
  3. Alias resolution (``manual [words]`` -> ``AUTOMANUAL [words]``).
  4. Deterministic help / command listings / engine verbs, answered
     from the registry or diagnostics with no model (help is routed
     BEFORE any brain call, exactly like ``NativeCommands.reply`` runs
     before model load). Engine verbs mirror the Linux brain's picker:
     ``models``, ``use qwen``, ``use granite`` (and ``engine qwen`` /
     ``engine granite``). A switch records the ADAPTER's engine
     preference only; the live macOS float keeps its own choice.
  5. The live brain: POST the text to the MCR loopback endpoint
     (``http://127.0.0.1:8329/v1/call/thundr_chat``, the same route the web
     float uses) with a short timeout. Only when it answers ``ok`` is
     its reply returned, with ``via: "mcr:8329"``.
  6. Registry fallback: if the text names a known command, answer with
     its recorded description. Otherwise return an honest offline note.

Step 6 is the truth law in code: when no brain is reachable, the adapter
says so and answers only from the registry. It NEVER fakes a live brain
reply, invents model output, or claims a service answered when it did not.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .diagnostics import (engine_status, granite_health,
                          load_engine_preference, save_engine_preference)
from .protocol import go_gated_reply, ok, refused_reply
from .registry import Registry

MCR_PORT = 8329
MCR_TIMEOUT = 2.0

HELP_WORDS = frozenset({"help", "commands", "functions", "?"})

# GO-gated wallet/signing verbs: the sensitive subset of the A2 LocalBrain
# liveCmd regex (src/LocalBrain.swift), plus the Linux brain's signing
# guard. These map to the LIVE /rmint/request flow. Read-only
# live verbs (status, inventory, jobs, progress, mcr, gizmo, rcpm) are
# NOT gated — they route normally. Bare "casket" is not gated either
# (panel/info verb); "casket verify/approve/sign" is.
# Note the adapter is stricter than the registry here on purpose: the
# registry marks RWALLET go:false as an everyday chat verb, but the
# adapter is a bot channel, and bot input cannot touch the live flow.
GO_GATED_VERBS = re.compile(
    r"^/?(wallet|rwallet|signing|sign this|sign egg|egg-sign|"
    r"prompt faceid|faceid|request approval|approve|mint|"
    r"request mint|request sign|casket\s+(verify|approve|sign))\b")

GO_GATED_TEMPLATE = (
    "GO-gated: %(verb)s touches the live wallet/signing flow "
    "(/rmint/request). The adapter never runs it — bot/agent "
    "input cannot request, confirm, or send on that flow. Nothing was "
    "run. To proceed, type the verb in the ThundR R:> shell yourself, "
    "or get Rizal's explicit GO for that exact action. Rizal's GO is "
    "sufficient authorization — no biometric step is required."
)

# A switch records the adapter's preference only; the live app is not
# touched (there is no known mechanism for the adapter to flip the
# float's engine, and the adapter never claims one).
ENGINE_LOCAL_NOTE = (
    "This sets the adapter's preference; the live float keeps its own "
    "engine choice — type the same verb in the R:> shell to switch the app."
)


def models_panel(model_dir=None, config_dir=None) -> str:
    """The MODELS panel, mirroring the Linux brain's models_panel().

    Same shape (MODELS, one line per engine, active marker, command
    footer) with the macOS facts: Qwen 1.7B is the in-process llama.cpp
    fallback and Granite 4.2 3B is the SANDISK relay on :4983.
    """
    status = engine_status(model_dir=model_dir, config_dir=config_dir)
    qwen = status["qwen"]
    granite = status["granite"]
    if qwen["model_present"] is None:
        qwen_state = "no model dir configured"
    elif qwen["model_present"]:
        qwen_state = "model file present"
    else:
        qwen_state = "no Qwen .gguf found"
    granite_state = (granite["detail"] if granite["up"]
                     else "unavailable · " + granite["detail"])
    return "\n".join([
        "MODELS",
        "• Qwen 1.7B (in-process llama.cpp fallback)  [%s]%s" % (
            qwen_state, "  ← active" if status["active"] == "qwen" else ""),
        "• Granite 4.2 3B (SANDISK relay :4983)  [%s]%s" % (
            granite_state,
            "  ← active" if status["active"] == "granite" else ""),
        "",
        "Commands: use qwen · use granite · models",
    ])


def _mcr_chat(text: str, port: int = MCR_PORT,
              timeout: float = MCR_TIMEOUT) -> dict | None:
    """POST text to the MCR thundr_chat tool. None when unreachable/error."""
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:%d/v1/call/thundr_chat" % port,
        data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            decoded = json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    return decoded


def route(text: str, registry: Registry | None = None,
          mcr_port: int = MCR_PORT, try_mcr: bool = True,
          model_dir=None, config_dir=None) -> dict:
    """Route one line of text. Returns a protocol envelope."""
    reg = registry or Registry.load()
    raw = (text or "").strip()
    if not raw:
        return {"ok": False, "via": "adapter.chat", "error": "empty question"}

    # 1. Refuse enforcement — before anything else.
    matched, label, _pattern = reg.refuse_check(raw)
    if matched:
        return refused_reply(reg.refuse_reply, via="adapter.chat/refuse",
                             rule=label)

    # 2. GO-gated wallet/signing verbs — never forwarded to any executor.
    gated = GO_GATED_VERBS.match(raw.lower())
    if gated:
        verb = gated.group(0).strip()
        return go_gated_reply(
            GO_GATED_TEMPLATE % {"verb": verb},
            via="adapter.chat/go-gated", verb=verb)

    # 3. Aliases.
    text = reg.resolve_alias(raw)
    low = text.strip().lower()

    # 4. Deterministic help / listings / engine verbs (no model).
    if low in HELP_WORDS:
        return ok("adapter.chat/registry-help", reply=reg.help_text())
    if low in ("models", "list models", "model"):
        env = ok("adapter.chat/models",
                 reply=models_panel(model_dir=model_dir,
                                    config_dir=config_dir))
        env["engine"] = load_engine_preference(config_dir=config_dir)
        env["panel"] = "models"
        return env
    if low in ("use qwen", "engine qwen"):
        save_engine_preference("qwen", config_dir=config_dir)
        env = ok("adapter.chat/engine", reply=(
            "Active engine → Qwen 1.7B (preferred).\n" + ENGINE_LOCAL_NOTE))
        env["engine"] = "qwen"
        return env
    if low in ("use granite", "engine granite"):
        save_engine_preference("granite", config_dir=config_dir)
        health = granite_health()
        note = (("Granite is %s." % health["detail"]) if health["up"] else
                ("Granite unavailable (%s) — chat falls back to Qwen until "
                 ":4983 is up." % health["detail"]))
        env = ok("adapter.chat/engine", reply=(
            "Active engine → Granite 4.2 3B (preferred).\n" + note
            + "\n" + ENGINE_LOCAL_NOTE))
        env["engine"] = "granite"
        return env
    if low in ("scribe commands", "rscribe commands", "commands all"):
        lines = ["THUNDR commands (%d):" % reg.count()]
        for cmd in reg.all():
            lines.append("%s  %s — %s" % (
                cmd.get("id"), cmd.get("cmd"), cmd.get("does")))
        return ok("adapter.chat/registry-list", reply="\n".join(lines))
    if low.startswith("commands ") or low.startswith("command "):
        query = text.split(None, 1)[1].strip() if " " in text.strip() else ""
        found = reg.get(query.upper()) if query else None
        if found:
            return ok("adapter.chat/registry-get", reply=(
                "%s — %s\n%s\nGroup: %s · Owner: %s · GO: %s"
                % (found.get("id"), found.get("cmd"), found.get("does"),
                   found.get("group"), found.get("owner_app"),
                   "yes (needs Rizal's GO)" if found.get("go") else "no")))
        hits = reg.search(query, limit=10)
        if hits:
            lines = ["%d match(es) for %r:" % (len(hits), query)]
            for cmd in hits:
                lines.append("%s  %s — %s" % (
                    cmd.get("id"), cmd.get("cmd"), cmd.get("does")))
            return ok("adapter.chat/registry-search", reply="\n".join(lines))
        return ok("adapter.chat/registry-search",
                  reply="No command matches %r in the %d-command registry."
                        % (query, reg.count()))

    # 5. Live brain via the MCR loopback endpoint.
    if try_mcr:
        res = _mcr_chat(text, port=mcr_port)
        if res is not None and res.get("ok"):
            reply = str(res.get("reply", ""))
            return ok("mcr:%d" % mcr_port, reply=reply,
                      data={"mcr_via": res.get("via")})
        if res is not None and not res.get("ok"):
            # The brain answered with its own refusal/error: pass it on.
            return {"ok": False, "via": "mcr:%d" % mcr_port,
                    "error": str(res.get("error") or res.get("reply") or "mcr refused")}

    # 6. Registry fallback — honest offline answer, never a faked brain reply.
    hits = reg.search(text, limit=3)
    if hits:
        cmd = hits[0]
        return ok("adapter.chat/registry-fallback", reply=(
            "No live ThundR brain is reachable (MCR :%d did not answer), so "
            "this comes from the command registry, not a model.\n"
            "Closest command: %s — %s\n%s\nGroup: %s · Owner: %s"
            % (mcr_port, cmd.get("id"), cmd.get("cmd"), cmd.get("does"),
               cmd.get("group"), cmd.get("owner_app"))))
    return ok("adapter.chat/offline", reply=(
        "No live ThundR brain is reachable (MCR :%d did not answer). "
        "I can only answer from the command registry right now — ask "
        "`help` for the command list, or `commands search <words>`."
        % mcr_port))
