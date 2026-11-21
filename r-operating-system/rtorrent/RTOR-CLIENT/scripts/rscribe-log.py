#!/usr/bin/env python3
"""Append one build turn to the shared RAGENT/ЯSYNC CRYPTOHIVEMIND (RSCRIBE) journal, same row shape as
SCOUT's scout-rscribe-log.py / RAgentJournal.record. Usage: rscribe-log.py <via> <user/prompt text> <reply/result text>"""
import json, os, re, sys, uuid, datetime
D = os.path.expanduser("~/R/ЯLAB/RCRYPTOFORGE/RKLOWD/SCROLLS/CRYPTOHIVEMIND/_inbox")
APP, SRC, DEV = "RTOR", "rtor-ghostchain-client", os.environ.get("RAGENT_HIVE_DEVICE", "neo")
SCRUB = [(re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1[redacted]"),
         (re.compile(r"(?i)((?:api[_-]?key|token|secret|password|passwd|storepass|keypass)\s*[:=]\s*)\S+"), r"\1[redacted]")]
SENS = re.compile(r"wallet|casket|seed|private|secret|token|passw|approv|mnemonic|\bkey", re.I)
def clean(s):
    for rx, rep in SCRUB: s = rx.sub(rep, s)
    return s[:4000]
via, user, reply = sys.argv[1], sys.argv[2], sys.argv[3]
ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds"); turn = str(uuid.uuid4())
rows = [{"t": ts, "role": "user", "app": APP, "source": SRC, "via": via, "text": clean(user), "recall": True, "turn": turn, "rid": turn + "-u", "dev": DEV},
        {"t": ts, "role": "assistant", "app": APP, "source": SRC, "via": via, "secs": 0.0,
         "text": "[sensitive turn: reply not stored]" if SENS.search(user + " " + reply) else clean(reply), "recall": True, "turn": turn, "rid": turn + "-a", "dev": DEV}]
os.makedirs(D, exist_ok=True); f = os.path.join(D, f"{APP}-{ts[:7]}.jsonl")
with open(f, "a") as h:
    for r in rows: h.write(json.dumps(r, ensure_ascii=False) + "\n")
    h.flush(); os.fsync(h.fileno())
print(f)
