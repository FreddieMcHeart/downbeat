# Claude Code plugin

downbeat ships as a native [Claude Code plugin](https://docs.claude.com/en/docs/claude-code/plugins)
(`.claude-plugin/plugin.json` + `hooks/hooks.json`, at the repo root) — an
**optional**, Claude-Code-only fast path alongside `downbeat init`'s
existing hand-merge into `settings.json`. It doesn't replace `init`: downbeat
is a general local message bus, not a Claude-Code-only tool, so `init`'s
settings.json hand-merge remains the baseline path that works everywhere.

## Install

Two commands, nothing to fill in — copy, paste, run:

```bash
claude plugin marketplace add FreddieMcHeart/downbeat
claude plugin install downbeat@downbeat
```

No local clone needed: the first command points Claude Code at this GitHub
repo (it shallow-clones the marketplace manifest under
`~/.claude/plugins/marketplaces/`), the second installs the plugin from that
source. Then start a new Claude Code session (or restart your current one)
so the hooks actually load.

**Verify it worked:**

```bash
claude plugin list --json | grep -A2 '"id": "downbeat@downbeat"'
```

Should show `"enabled": true`.

If you're working from a local clone instead (e.g. testing an unmerged
branch, or you keep the repo checked out anyway), point at the path instead
of the GitHub shorthand:

```bash
claude plugin marketplace add /path/to/your/downbeat/checkout
claude plugin install downbeat@downbeat
```

(the `name@marketplace` form on the install command disambiguates if you
ever have another plugin also named `downbeat` registered from a different
marketplace).

## How coexistence works

`downbeat init` checks whether the `downbeat` plugin is installed **and**
enabled (`claude plugin list --json`) before hand-merging hooks into
`settings.json`:

- **Plugin enabled, no prior `init` run:** hand-merge is skipped entirely —
  the plugin's own `hooks/hooks.json` is natively loaded by Claude Code, so
  there's nothing for `init` to add.
- **Plugin enabled, `init` was already run before you installed the
  plugin:** `init` prints an explicit **WARNING** about double-firing (both
  the old hand-merged entries in `settings.json` *and* the plugin's own
  hooks would fire on every event) instead of silently doing nothing.
- **Plugin not detected** (not installed, or the `claude` CLI itself isn't
  on `PATH`): `init` falls back to today's hand-merge, unchanged.

The check fails open — any error running `claude plugin list --json`
(missing binary, timeout, bad JSON) is treated as "plugin not detected", so
a broken or absent Claude Code CLI never blocks `init`'s fallback path.

## If you get the double-fire warning

Run:

```
downbeat init --migrate-to-plugin
```

This removes exactly the hand-merged entries the original `init` run wrote —
matched by exact command string against `hooks_manifest.json`, so any other
hook sharing the same event/matcher (e.g. `cost-discipline.py`) is left
untouched — and backs up `settings.json` first. It refuses to run unless the
plugin is actually installed and enabled, so it can never leave you with no
working relay hooks.

If a legacy entry doesn't get removed (e.g. its command string no longer
byte-matches today's derivation — `$HOME` changed, a symlink resolved
differently), the command tells you and points at `downbeat uninstall` as
the substring-based fallback.

`--migrate-to-plugin` is a standalone mode of `init` — it does not also
re-run the rest of `init` (skill/shim/hooks/commands installation), since
those are plugin-irrelevant once the plugin owns hook registration.
`downbeat init --force` does **not** do this for you — it only re-verifies
the hand-merge path, which is exactly what you're trying to stop using.
