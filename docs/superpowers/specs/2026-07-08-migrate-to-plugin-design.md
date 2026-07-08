# `downbeat init --migrate-to-plugin` — design draft

> Status: DRAFT, not implemented. Scoped per relay request from `Claude-Cost-Optimazing`
> (2026-07-08), who is doing the equivalent for `claude-core-hooks`/`install.sh` in parallel.
> Revised after their full review (`d5159d102bb7`, 2026-07-08) — see "Review feedback
> incorporated" at the bottom for what changed and why.

## Problem

`downbeat init`'s hand-merge (`_register_hooks` in `init_cmd.py`) idempotently writes relay
hook registrations directly into `~/.claude/settings.json`. Since PR #4 (v0.4.0), a Claude Code
plugin (`.claude-plugin/` + `hooks/hooks.json`) exists as a second, preferred registration path.
`_is_plugin_enabled()` now makes `init` skip the hand-merge when the plugin is active — but a
user who ran `init` **before** ever installing the plugin still has the old hand-merged entries
sitting in `settings.json`. Once they install the plugin, both fire on every event
(`docs/plugin.md` currently documents this as a manual fix-up with an explicit WARNING — see
`decisions.md` row #15 correction). `--migrate-to-plugin` is the automated replacement for that
manual step.

## What already exists and is reusable

`_unregister_hooks()` (used today by `downbeat uninstall`) already implements the **drop-empty-
groups** logic correctly:
- removes a hook object from an entry's `hooks: [...]` list
- if that empties the list, drops the whole entry from the event's list
- if that empties the event's list, deletes the event key from `settings["hooks"]`
- never touches entries/hooks that don't match, so non-relay neighbours (e.g. a
  `cost-discipline` hook sharing the same `PostToolUse` entry) survive untouched

**What's unsafe about reusing it as-is for `--migrate-to-plugin`:** its match predicate is
`n in (h.get("command") or "")` — a **substring** check against `HOOK_NAMES = ("relay-inbox.py",
"relay-poll-offer.py")`. That's fine for `uninstall`, whose job is "remove everything downbeat
ever wrote, no matter the exact form" — but wrong for a migration that must remove *only* the
specific entries `_register_hooks` itself wrote, and leave alone anything else that happens to
contain the same filename substring (a third-party hook wrapping `relay-inbox.py` in a shell
one-liner, a differently-pathed copy from a previous `~/mama/claude-relay` install, etc.).

## Proposed design

**New matching primitive: exact command string, not substring.** `_register_hooks` writes each
hook's `command` as `str(hooks_dir / cmd_name)` — a fully deterministic absolute path given
`hooks_manifest.json`'s `(event, matcher, command)` triples. `--migrate-to-plugin` computes that
*exact* expected string per manifest entry and only removes a hook object whose `command` field
is byte-identical to it, scoped to the matching `(event, matcher)` slot. This makes migration the
precise inverse of registration — same manifest, same path-resolution function, opposite
direction — rather than a second, drift-prone definition of "what counts as a relay hook."

**Shared drop-empty-groups helper (not a re-implementation).** Peer review correctly flagged
that a standalone `_migrate_to_plugin` re-implementing drop-empty-groups with its own control
flow would be untested by the existing `_unregister_hooks` suite — a second definition that can
silently drift from the first. Fix: extract the group-pruning logic into one predicate-
parameterized helper, and have *both* callers use it:

```python
def _remove_matching_hooks(hooks: dict, match: Callable[[dict], bool]) -> list[str]:
    """Remove every hook object for which match(hook_obj) is True, dropping
    now-empty entries and now-empty event keys. Mutates `hooks` in place.
    Returns event labels for the removed hooks (dupes = one removal each)."""
    removed: list[str] = []
    for event in list(hooks.keys()):
        new_list = []
        for entry in hooks[event]:
            ehooks = entry.get("hooks", [])
            kept = [h for h in ehooks if not match(h)]
            removed.extend([event] * (len(ehooks) - len(kept)))
            if "hooks" in entry:
                if kept:
                    entry["hooks"] = kept
                    new_list.append(entry)
                # else: drop-empty-groups, entry level
            else:
                new_list.append(entry)
        if new_list:
            hooks[event] = new_list
        else:
            del hooks[event]           # drop-empty-groups, event level
    return removed
```

`_unregister_hooks` becomes a thin caller passing the existing substring predicate:
`match=lambda h: any(n in (h.get("command") or "") for n in names)`. `_migrate_to_plugin` passes
an exact-match predicate built from the manifest, scoped per `(event, matcher)`:

```python
def _migrate_to_plugin(manifest: dict, hooks_dir: Path, settings_path: Path,
                        backup_suffix: str) -> dict:
    """Remove exactly the hand-merged entries `_register_hooks` would have
    written for this manifest+hooks_dir, via _remove_matching_hooks. Returns
    {removed: [...], backup}. Raises SettingsParseError on malformed JSON —
    see "malformed settings.json" note below; caller must catch it."""
    settings, raw = _load_settings(settings_path)  # raises SettingsParseError
    if raw is None:                                  # on bad JSON; raw is None
        return {"removed": [], "backup": None}        # only for file-not-found
    expected = {
        (e["event"], e["matcher"]): str(hooks_dir / e["command"])
        for e in manifest["events"]
    }
    hooks = settings.get("hooks", {})

    def match(h: dict) -> bool:
        # Scope by (event, matcher) is implicit: _remove_matching_hooks already
        # iterates per-event, and matcher-scoping happens by only checking
        # commands present in slots this manifest actually targets — a hook
        # object's own command is either byte-identical to some manifest
        # entry's expected string or it isn't, regardless of which slot it's
        # physically sitting in, since exact-match already can't false-positive
        # across (event, matcher) pairs the way substring match could.
        return h.get("command") in expected.values()

    removed = _remove_matching_hooks(hooks, match)
    changed = bool(removed)
    backup = None
    if changed:
        backup = settings_path.with_name(f"settings.json.bak-{backup_suffix}")
        backup.write_text(raw)
        _atomic_write_json(settings_path, settings)
    return {"removed": removed, "backup": backup}
```

This reuses `_load_settings`/`_atomic_write_json` as-is, and now genuinely reuses drop-empty-
groups (not a parallel copy) via `_remove_matching_hooks`. `_unregister_hooks`'s own tests keep
covering that shared logic; `_migrate_to_plugin` only needs new tests for its match predicate
and the safety gate below.

**Malformed `settings.json`: migrate raises, it does not silently skip.** `_load_settings`
returns `raw=None` only when the file doesn't exist; it **raises `SettingsParseError`** on
invalid JSON (confirmed against current code — the earlier draft's comment describing this was
wrong, per review). `uninstall` swallows that case (`_unregister_hooks` catches
`json.JSONDecodeError` itself and no-ops rather than touching a malformed file). `migrate` should
**not** silently swallow it the same way: the CLI wiring must catch `SettingsParseError`
explicitly and mirror what `run_init` already does for the hand-merge path today — back up the
offending file, print an error, exit 1, touch nothing. Defensible (a migration silently no-oping
on unparsable settings would be a worse surprise than a loud failure), but it needs to be visible
in the CLI wiring, not left implicit.

**Exact-match is precision-over-recall by design — document this explicitly.** If a legacy
command string doesn't byte-match today's derivation (e.g. `$HOME` changed since the original
`init` run, a symlink got resolved differently, hand-editing), `--migrate-to-plugin` will
silently leave that entry in place rather than guess. Safe (nothing breaks, no double-fire risk
is *introduced* by migrate itself), but not a guaranteed-100%-clean result. `downbeat uninstall`'s
substring match remains the real fallback for a stubborn leftover; the CLI's summary output
should say so when `removed` is empty despite the plugin being enabled.

**Safety gate: refuse to run unless the plugin is actually active.** `--migrate-to-plugin` calls
`_is_plugin_enabled()` first; if `False`, print an error and exit 1 without touching
`settings.json`. Removing the legacy entries when the plugin *isn't* installed/enabled would
leave the user with no working hooks at all — the one failure mode migration must never cause.
Fails open-to-`False` on any `_is_plugin_enabled()` error (missing `claude` binary, bad JSON,
timeout) — same as today, no change needed there per review.

**CLI wiring.** `downbeat init --migrate-to-plugin`:
1. Runs the existing `_is_plugin_enabled()` gate (hard-fail if not enabled).
2. Calls `_migrate_to_plugin(...)`, catching `SettingsParseError` explicitly (see above).
3. Prints a summary (`removed: [...]`, backup path), or `"nothing to migrate"` if the legacy
   entries were never there, or a note pointing at `downbeat uninstall` if `removed` came back
   empty but hand-merged entries plausibly still exist under a non-matching command string.
4. Does **not** also run the rest of `init`'s asset-install steps (skill/shim/hooks/commands
   installation) — those are plugin-irrelevant once the plugin owns hook registration, and
   re-running them would just be redundant work. `--migrate-to-plugin` is a standalone mode of
   `init`, not a modifier layered on top of a full init run.

**Orphaned files: leave them — scope boundary, not risk-aversion.** `--migrate-to-plugin`'s one
job is de-duplicating `settings.json`; file cleanup (`~/.claude/hooks/relay-*.py`,
`commands/relay-*.md`) is `uninstall`'s job already, and these aren't even inferred orphans — the
same `HOOK_NAMES`/manifest already names them precisely, so removing them would be easy to add.
The reason not to is scope, not uncertainty: migrate and uninstall should each do one thing.
Print one hint line on migrate's success output ("stale hook/command files can be removed with
`downbeat uninstall`") for discoverability. If file purge is ever wanted as part of migration
itself, make it an explicit opt-in `--purge-files` flag later, not a default side effect.

## `hooks_manifest.json` / `hooks/hooks.json` parity — new test, separate from migration itself

Peer review's most important structural finding: `_register_hooks` and `_migrate_to_plugin` both
derive from `hooks_manifest.json`, so they can't drift from *each other* — but nothing enforces
parity between `hooks_manifest.json` (hand-merge source of truth) and `hooks/hooks.json` (the
plugin's own source of truth). These are two independently hand-maintained files today; they
happen to agree (`UserPromptSubmit`/`SessionStart(startup|resume)`/`PostToolUse(Bash)`, same two
scripts), but nothing would catch it if a third relay hook binding were added to one and not the
other — exactly the class of bug the peer's own `claude-core` work just hit for real (a
`UserPromptSubmit` gap between their two lists). Add one test asserting both files enumerate the
same `(event, matcher, command-basename)` set — cheap, and it directly targets this failure mode.
Not part of `--migrate-to-plugin` itself, but should land in the same PR since it's the direct
mitigation for the risk migration's design surfaced.

## What this does NOT change

- `_unregister_hooks`'s own substring-based "remove everything downbeat-ish" semantics for
  `uninstall` are unchanged in behavior — only its internals now call the shared
  `_remove_matching_hooks` helper instead of doing its own loop.
- No change to `_register_hooks`, `_is_plugin_enabled`, or the plugin's own `hooks/hooks.json`.
- No change to `hooks_manifest.json`'s schema — `_migrate_to_plugin` reads it as-is.

## Review feedback incorporated (2026-07-08, from `Claude-Cost-Optimazing`/Opus review)

1. Confirmed **not** vulnerable to the manifest-drift bug in the migration logic itself (one
   manifest, one derivation, migrate is a re-traversal not a second list) — but the same bug
   class exists one layer up between `hooks_manifest.json` and `hooks/hooks.json`; added the
   parity-test section above as the direct mitigation.
2. "Reuse `_unregister_hooks` unchanged" was inaccurate — the original draft re-implemented
   drop-empty-groups with separate control flow, untested by the existing suite. Fixed by
   extracting `_remove_matching_hooks(hooks, match_fn)` as the one shared implementation.
3. Corrected the malformed-`settings.json` handling claim to match actual `_load_settings`
   behavior (raises `SettingsParseError` on bad JSON; `raw is None` is file-not-found only) and
   made the CLI's catch-and-report responsibility explicit instead of implicit.
4. Added the precision-over-recall note for exact-match, with `uninstall` named as the fallback.
5. Reframed "leave orphaned files" around scope boundary (migrate de-dupes settings, uninstall
   cleans files) rather than "riskier to infer" — same conclusion, more accurate reasoning — and
   added the hint-line + future-`--purge-files` suggestions.
6. Confirmed symmetric with claude-core's independent implementation (exact-match table,
   drop-empty-groups, backup-on-write, same orphaned-files lean) — no design changes needed on
   that front, just cross-validation.
