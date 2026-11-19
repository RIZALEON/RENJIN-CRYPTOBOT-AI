# ThundR Plugin Adapter

## Decide when to use the adapter

- Use the adapter when the user asks about ThundR health, engines, commands, the chain, the wallet roster, repairs, or updates.

- Use it when a bot or AI needs to talk to ThundR, since the adapter is the one route with the refuse rules and GO gating built in.

- Do not use it for RENJIN core work, since that lives in the RENJIN project space and has its own tools.

## Drive it through the CLI

- Run commands from `~/workspace/thundr-adapter` with `PYTHONPATH=python python3 -m thundr_adapter` followed by the subcommand.

- Start with `hello` to confirm the adapter answers, then `chat "help" --no-mcr` for the command list.

- Check engines with `diagnostics`, optionally with `--model-dir` for the GGUF inventory and `--chain-port` for the RGHOSTCHAIN daemon.

- Route one line of text with `chat "<text>"`, adding `--no-mcr` when the live brain is not wanted or not reachable.

- Inspect the parts catalog with `analyze components`, a ЯID with `analyze rid --rid <ЯID>`, and the chain read layer with `analyze rtrackr-feed`.

- Propose a repair with `repair-propose` and check for updates with `update-check`, then stop and show the plan to the user.

- Start the loopback server with `serve` only when another bot or AI needs HTTP access, and tell the user the port and the token file path.

## Read the answers honestly

- Read the `via` field first, since it names the route that answered.

- Treat a registry fallback or offline note as exactly that, and never present it as a live brain reply.

- Report a service as up only when the adapter probed it and it answered, and report everything else as unreachable.

- Name the source and timestamp on every RTRACKR or snapshot value, since baked data goes stale and is never a live balance.

- Report a registered-but-unsealed row as registered, never as minted.

## Stay inside the safety rules

- Never ask the adapter to sign, seal, enroll, mint, send, swap, or transfer, since it refuses all seven even with GO.

- Route wallet and signing verbs to the user instead, since they need the owner's explicit GO for the exact action. His command is sufficient authorization — no biometric step is required.

- Never run a repair or update apply without the user's explicit GO for the exact plan, and apply by reference with the plan id and nonce the proposal returned.

- Never call a chain submit, register, or ingest endpoint, since the adapter is read-only against the chain.

- Treat the wallet as watch-only and read roster, snapshot, and pool state only.

- Keep the grounding files under `grounding/` untouched, and never push the adapter tree to a repo without being asked.

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
