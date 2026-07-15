# Claude Code plugin

downbeat ships as a native [Claude Code plugin](https://docs.claude.com/en/docs/claude-code/plugins)
(`.claude-plugin/plugin.json` + `hooks/hooks.json`, at the repo root) — an
**optional**, Claude-Code-only fast path alongside `downbeat init`'s
existing hand-merge into `settings.json`. It doesn't replace `init`: downbeat
is a general local message bus, not a Claude-Code-only tool, so `init`'s
settings.json hand-merge remains the baseline path that works everywhere.

## Updating: use `/downbeat:update`, not `claude plugin update` alone

**`claude plugin update` does not update the `downbeat` CLI.** It moves the
plugin only. This surprises everyone exactly once, so it's worth being blunt
about why.

A Claude Code plugin cannot ship a terminal command. Plugin `bin/` puts
executables on the **Bash tool's** PATH — reachable when Claude shells out
inside a session, invisible to a terminal you open yourself. There is also no
install-time hook: the hook event list has no `PluginInstall`/`PluginUpdate`,
so nothing can run at update time to go fetch the CLI. Those are properties of
the plugin system, not gaps in this project.

So downbeat is two artifacts with two update paths, and the plugin can only
move one of them:

| artifact | what it is | updated by |
|---|---|---|
| plugin | hooks, slash commands, skills | `claude plugin update downbeat@downbeat` |
| CLI / TUI | the `downbeat` command | `uv tool upgrade downbeat` |

Run **`/downbeat:update`** and forget the table — it does both and reports what
moved.

Two things guard the gap for when you forget:

- The plugin's `SessionStart` hook compares your CLI's version against the
  plugin's and speaks up if they've drifted. It stays quiet when they agree,
  and quiet on editable installs — there the version is stamped at install
  time while the code is read live from a working tree, so a mismatch is
  expected and means nothing.
- `downbeat --version` reports *where the code came from*, not just a number:

  ```
  downbeat 0.9.2
  downbeat 0.9.2 (editable → /path/to/checkout; this number is from install
                  time, the code is whatever is checked out there now)
  ```

  That second form matters. A bug once got filed against the version
  `--version` printed while the code actually running was several releases
  ahead; the mismatch sent the investigation the wrong way twice.

**A running TUI holds the code it loaded at launch.** After any update, quit
and relaunch `downbeat tui` — otherwise you are still on the old one, and no
amount of updating will show it.

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
