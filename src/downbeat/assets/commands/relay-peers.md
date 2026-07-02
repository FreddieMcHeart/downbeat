---
description: List registered relay peer sessions and their liveness
argument-hint: (no arguments)
---

List all registered relay sessions. Run:

```
~/.claude/relay/relay.py peers
```

Liveness column meaning:
- `live` — the peer's JSONL transcript was modified within the last 10 minutes
- `idle(Ns)` — peer hasn't written to its transcript for N seconds
- `gone` — JSONL no longer exists (the session was deleted/cleaned)

If you suspect stale entries, run `~/.claude/relay/relay.py gc-stale` to prune.
