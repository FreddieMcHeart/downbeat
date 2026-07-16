---
description: Update downbeat — both the plugin and the downbeat CLI/TUI — in one step
argument-hint: (no arguments)
---

Update downbeat. There are **two** artifacts and they update separately; this
command does both so the user doesn't have to know that.

Why two: a Claude Code plugin cannot ship a terminal command. Plugin `bin/` is
on the *Bash tool's* PATH, not the user's shell, and there is no install-time
hook — so `claude plugin update` moves the plugin's hooks/commands/skills and
cannot touch the `downbeat` CLI. Don't try to work around this; just do both.

## 1. Report what's installed now

```bash
downbeat --version 2>&1 || echo "downbeat CLI: not on PATH"
claude plugin list --json 2>/dev/null | python3 -c "import json,sys;d=json.load(sys.stdin);print(next((f\"plugin: {p.get('version')}\" for p in (d if isinstance(d,list) else d.get('plugins',[])) if 'downbeat' in str(p.get('id',p.get('name','')))), 'plugin: not installed'))" 2>/dev/null || true
```

**If `--version` reports an editable install** (the output says `editable → <path>`),
STOP and tell the user rather than upgrading. An editable install runs code
live from that working tree — `uv tool upgrade` would silently replace their
development setup with a release. Report the path and ask whether they want to
switch to a release install; that's their call, not yours.

## 2. Update the plugin

```bash
claude plugin update downbeat@downbeat
```

## 3. Update the CLI

```bash
uv tool upgrade downbeat
```

If downbeat isn't a uv tool yet (`uv tool upgrade` errors, or step 1 said it's
not on PATH), install it:

```bash
uv tool install downbeat
```

If `uv` itself is missing, say so and point at https://docs.astral.sh/uv/ —
don't silently fall back to `pip install --user` or similar, which is how
people end up with two downbeats on PATH and no idea which one runs.

## 4. Confirm both moved

```bash
downbeat --version
```

Report the before/after for **both** artifacts. If the two versions still
disagree after this, say so plainly — that's a real problem worth surfacing,
not something to paper over.

## 5. Tell them to restart the TUI

A running TUI holds the code it loaded at launch. If they have `downbeat tui`
open, it is still running the old version until they quit and relaunch. Say
this explicitly — it is the single most common reason an update "didn't work".
