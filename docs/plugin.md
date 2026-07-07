# Claude Code plugin

downbeat ships as a native [Claude Code plugin](https://docs.claude.com/en/docs/claude-code/plugins)
(`.claude-plugin/plugin.json` + `hooks/hooks.json`, at the repo root) — an
**optional**, Claude-Code-only fast path alongside `downbeat init`'s
existing hand-merge into `settings.json`. It doesn't replace `init`: downbeat
is a general local message bus, not a Claude-Code-only tool, so `init`'s
settings.json hand-merge remains the baseline path that works everywhere.

## Install

```
claude plugin install downbeat
```

(exact source — marketplace, git, or local path — depends on how you've
registered downbeat as a plugin source; see Claude Code's own plugin docs).

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

There's no automated migration yet (`downbeat init --migrate-to-plugin` is
planned but not built — see the project's decisions log). Until then, fix it
manually:

1. Open `~/.claude/settings.json`.
2. Under `hooks`, find the `UserPromptSubmit`, `SessionStart`
   (`startup|resume`), and `PostToolUse` (`Bash`) entries whose `command`
   points at `<home>/.claude/hooks/relay-inbox.py` or
   `relay-poll-offer.py`.
3. Remove those specific hook objects (leave any other hooks in the same
   entry — e.g. a `cost-discipline.py` entry sharing the same event/matcher
   — untouched).
4. If removing them empties out an entry's `hooks` list, delete the whole
   entry.

`downbeat init --force` does **not** do this for you — it only re-verifies
the hand-merge path, which is exactly what you're trying to stop using.
