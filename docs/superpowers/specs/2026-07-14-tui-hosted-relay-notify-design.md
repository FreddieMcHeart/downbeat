# TUI-hosted relay staleness notify (replaces standalone `downbeat watch`)

**Status:** approved, ready for implementation plan
**Branch:** `feat/tui-hosted-relay-notify` (from `origin/main`)
**Breaking change:** yes — removes the public `downbeat watch` CLI subcommand

## Context

This design closes a feasibility thread run this session (relay task
`e0c1e418427c` → `feature-dev:code-architect` analysis → several rounds of
correction with the parent session `Claude-Cost-Optimazing`). Full thread is
recorded in `ideas/downbeat/cloud-relay-downbeat-inbox-rework.md` in the wiki
(`~/dev/claude-core-wiki`). Summary of what's settled and out of scope here:

- **Core verdict (unchanged):** a genuine push/interrupt *into* an idle Claude
  Code session is not possible with current harness primitives
  (`ScheduleWakeup`/`Cron` only schedules a future turn of an already-resident
  session; there is no way to wake a fully-exited process). This design does
  **not** attempt that. It only pushes a native OS notification *to the human*,
  not into any session.
- **Rejected:** a standalone long-running daemon (`downbeat watch --notify` or
  similar) as a new process the human would need to start/supervise
  (singleton lock, reboot persistence). Explicitly ruled out by the human —
  see "Human's call" below.
- **Also rejected as its own deliverable:** keeping the standalone `downbeat
  watch` CLI command at all. The human doesn't want it as a user-facing
  feature; only the underlying `FsWatcher` primitive (`core/watcher.py`) is
  worth reusing, and it already has a resident consumer: the TUI
  (`tui/app.py`).
- **Deferred, not rejected:** a true standalone C-daemon remains a possible
  future follow-up for the coverage gap this design consciously accepts
  (headless recipient + non-Claude sender — see "Known limitations"). Tracked
  as a near-term wiki roadmap item, not built now.

## Human's call (2026-07-13/14, verbatim decisions)

1. Build the `watcher_active`-style dedup mechanism against double-fire (do
   not silently accept duplicate notifications).
2. Remove the standalone `downbeat watch` CLI component entirely — keep only
   what this design describes (`FsWatcher` reused inside the TUI + headless
   hook fallback).
3. The daemon question (a real standalone C-daemon) is raised later, not now
   — added to the wiki roadmap as a deferred near-term item.

## Architecture

No new process. Two independent triggers, **not** sharing code — see
"Implementation constraint" below:

```
TUI resident FsWatcher (tui/app.py, already running when TUI is open)
    → core/notify.py (subprocess: osascript / notify-send)

relay-poll-offer.py (PostToolUse hook on Bash send/reply, headless)
    → self-contained duplicate notify logic inline in the same hook file
```

### Implementation constraint: hooks cannot import the `downbeat` package

Verified directly: both existing hooks
(`src/downbeat/assets/hooks/relay-poll-offer.py`,
`.../relay-inbox.py`) are stdlib-only (`json`, `re`, `sys`, `tempfile`,
`traceback`, `datetime`, `pathlib` — no `downbeat.core` imports anywhere).
`hooks/hooks.json` invokes them by absolute path with a bare
`#!/usr/bin/env python3` shebang — confirmed `python3 -c "import downbeat"`
fails with `ModuleNotFoundError` on this machine's system Python, which is
what actually runs the hook (not the uv-tool venv the `downbeat` CLI itself
runs under). So `relay-poll-offer.py` **cannot** call
`core.notify.notify()`, `core.store.is_recipient_stale()`, or
`core.state.*` — those only work for code invoked through the installed
`downbeat` package (the TUI, via `downbeat tui`).

Consequence: the headless path re-implements the same **contract** (same
`sessions.json`/`tui_state.json` file paths and formats, same 10-minute
threshold constant, same notify mechanism) as a **second, independent,
stdlib-only implementation inside the hook file itself** — matching the
existing pattern where `relay-poll-offer.py` already duplicates its own
small state-file read/write helpers (`_load_state`/`_save_state` for
`loop_offer_state.json`) rather than importing anything. This is a
deliberate, acknowledged DRY violation forced by the hook's execution
environment, not an oversight — noted explicitly so nobody "fixes" it later
by adding an import that will silently break the hook (fails open, so the
whole feature would just stop firing with no visible error).

The hook's own `CLAUDE_RELAY_DIR` env var handling: the *existing* hook code
hardcodes `Path.home() / ".claude" / "relay"` for its own
`loop_offer_state.json` (pre-existing gap, not fixed here — out of scope).
The **new** staleness-notify code added by this design reads that same env
var (`os.environ.get("CLAUDE_RELAY_DIR")`, mirroring `core/paths.py`'s own
one-liner) so it's testable via the project's existing `relay_dir` pytest
fixture, without changing the old code path's behavior.

- **Recipient-TUI open** → notify fires from the TUI's own resident
  `FsWatcher.on_change` path. Recipient-side: the process that has the
  message already knows its own state directly, no inference needed. Zero
  new infrastructure — reuses the watcher instance the TUI already starts in
  `on_mount`.
- **Headless** (no TUI open) → fallback fires from the `relay-poll-offer.py`
  hook, sender-side (infers recipient state via `sessions.json`). Zero
  infrastructure, hook-adjacent cadence (only checked when *someone* sends a
  message, not on the actual event) — this is the accepted trade-off for not
  running a daemon.

## Components

### 1. `core/notify.py` (new)

```python
def notify(title: str, message: str) -> None
```

Detects OS via `sys.platform`. Shells out via `subprocess.run(..., timeout=3)`:
- macOS: `osascript -e 'display notification "<message>" with title "<title>"'`
- Linux: `notify-send <title> <message>`
- Any other platform, missing binary, or exception (e.g.
  `FileNotFoundError`, `TimeoutExpired`) → log a warning and return. Never
  raises. No new dependencies.

### 2. `core/store.py` (extend)

```python
def is_recipient_stale(peer_name: str, threshold_minutes: int = 10) -> bool
```

Reads `last_seen` via the existing `get_peer` / `sessions.json` path. Missing
peer (e.g. race with `unregister`) → `False` (don't notify for a peer that no
longer exists), never raises `PeerNotFound` into the caller.

Threshold is a hardcoded constant (`10` minutes) for this iteration — not
config/env-configurable. Revisit only if it proves wrong in practice.

The same constant is reused as the **cooldown window** for
`notify_last_sent` (see `core/state.py` below) — a recipient is "in
cooldown" if `now - notify_last_sent[peer] < 10 minutes`. One magic number,
not two independent ones to keep in sync.

### 3. `core/state.py` (extend `tui_state.json`)

Three new fields, alongside the existing `last_acting_as` / `last_active_peer`:

- `watcher_heartbeat_at: str | None` — global fact "a TUI is open right now."
  Written by the TUI on mount and refreshed on a periodic timer (~30s).
  Self-healing: if the TUI crashes without cleanup, the heartbeat simply goes
  stale on its own — no pidfile/lock needed.
- `notify_last_sent: dict[str, str]` — per-recipient cooldown timestamp
  (peer name → ISO timestamp of last notification sent for that peer),
  shared by both the TUI path and the hook path so cooldown is coherent
  regardless of which path fires.

Read/write goes through the existing `_atomic_write_text` helper already used
by `core/state.py`. A rare near-simultaneous write from both the TUI process
and a hook process can lose one of the two timestamp updates — acceptable
(worst case: one extra notification), not specially guarded against.

### 4. `tui/app.py` (extend)

- `on_mount`: start a heartbeat timer (`set_interval`) that refreshes
  `watcher_heartbeat_at` in `tui_state.json`.
- `_on_change` (currently fires on *any* filesystem event anywhere under
  `INBOX_DIR`/`PROCESSED_DIR`, with no information about which peer/message
  changed): for each registered peer, call `store.poll_new(peer,
  seen[peer])` using a per-instance `seen` dict on `RelayApp` (same pattern
  the old `cmd_watch`/`_watch_emit` used, just fanned out across every
  registered peer instead of one). For each genuinely new message: if
  `is_recipient_stale(recipient)` and the recipient isn't in cooldown per
  `notify_last_sent`, call `core.notify.notify(...)` and update
  `notify_last_sent[recipient]`.

### 5. `assets/hooks/relay-poll-offer.py` (extend, self-contained — see constraint above)

All of the following is added as new **private, stdlib-only functions
inside this file** — no imports from `downbeat.core`:

- `_relay_dir() -> Path`: `Path(os.environ.get("CLAUDE_RELAY_DIR", str(Path.home() / ".claude" / "relay")))`
  — mirrors `core/paths.py`'s `RELAY_DIR` one-liner, for test redirection.
- `_is_recipient_stale(peer_name, threshold_minutes=10) -> bool`: reads
  `_relay_dir() / "sessions.json"` directly (`json.loads`), looks up
  `peer_name`'s `last_seen`, compares via `datetime.fromisoformat` +
  `timedelta` against `datetime.now(UTC)`. Missing peer or missing/malformed
  `last_seen` → `False` (matches `core.store.is_recipient_stale`'s
  fail-quiet contract, independently).
- `_notify(title, message) -> None`: same subprocess logic as
  `core/notify.py`'s `notify()` (`osascript`/`notify-send` by
  `sys.platform`, `timeout=3`, fail-open on any exception) — a private
  duplicate, not a shared import.
- `_read_tui_state() -> dict` / `_write_tui_state(data: dict) -> None`:
  reads/writes `_relay_dir() / "tui_state.json"` as a whole dict, same
  load-mutate-save shape as this file's existing `_load_state`/`_save_state`
  for `loop_offer_state.json`. The hook only ever **reads**
  `watcher_heartbeat_at` (never writes it — only the TUI writes that key)
  and only **writes** `notify_last_sent[peer]` (read-modify-write,
  preserving every other key already in the file, including
  `watcher_heartbeat_at` and `last_acting_as`/`last_active_peer` written by
  the TUI).

After the existing `send`/`reply` regex match (unchanged): determine the
recipient. This differs by verb, since only `send`'s command line actually
contains the recipient name:
- `send <to> <subject> <body>` — `to_peer` is the first positional argument
  after `send`. Parse via `shlex.split(command)`, taking the token after the
  matched `send` (handles quoted subjects/bodies containing spaces).
- `reply <msg_id> <body>` — the command line has no recipient at all; the
  recipient is the *original sender* of the message being replied to. Parse
  `msg_id` the same way (first positional after `reply`), then resolve it to
  a peer name by reading the message file directly off disk (glob
  `_relay_dir() / "{inbox,delivered,processed}" / "*" / f"{msg_id}.json"`,
  read `from_peer`) — a minimal, read-only, stdlib-only lookup, not a call
  into `core.store`. If no matching file is found (message already moved
  somewhere the glob doesn't cover, or genuinely absent), skip the
  staleness-notify silently; this is a best-effort nudge, not a guaranteed
  delivery path.

If `_is_recipient_stale(to_peer)` **and** `watcher_heartbeat_at` from
`_read_tui_state()` is not fresh (TUI not open — avoids double-firing with
the TUI path) **and** the recipient isn't in cooldown per
`notify_last_sent` → call `_notify(...)` and update
`notify_last_sent[to_peer]` via `_write_tui_state`.

This is **independent of** the existing once-per-session `/loop`-offer gate
(`hinted_at` in `loop_offer_state.json`) — that gate is about the `/loop`
polling *offer*, a separate feature. The staleness-notify fires every time a
send/reply targets a peer that is currently stale (subject to the
per-recipient cooldown above), not once per session.

## Data flow (headless case, worked example)

1. Human runs `downbeat send Claude-Relay "subject" "body"` from a Claude
   Code session.
2. `PostToolUse` fires `relay-poll-offer.py` with the Bash command in its
   payload.
3. Hook matches the `send` regex (unchanged), parses `to_peer = "Claude-Relay"`.
4. Hook reads `sessions.json` → `Claude-Relay.last_seen` → stale (>10min)?
5. Hook reads `tui_state.json` → `watcher_heartbeat_at` → stale/absent (no
   TUI open)?
6. Hook reads `tui_state.json` → `notify_last_sent["Claude-Relay"]` → outside
   cooldown?
7. If all three hold → `core.notify.notify("downbeat", "New message for
   Claude-Relay")`, update `notify_last_sent["Claude-Relay"]`.
8. Existing `/loop`-offer hint logic (unchanged) still runs independently on
   its own once-per-session gate.

## Error handling

- `core/notify.py`'s `notify()` fails open (see above) — never raises into
  its one caller (the TUI).
- `relay-poll-offer.py` already wraps `main()` in `try/except` with
  `sys.exit(0)` on any exception (never blocks the Bash tool). The new
  staleness logic (`_is_recipient_stale`/`_notify`/`_read_tui_state`/
  `_write_tui_state`) sits inside that same envelope — no new failure
  contract, and its own `_notify` fails open independently of
  `core/notify.py`'s (see "Implementation constraint" above — they're two
  separate functions, not one shared import).
- `tui/app.py`'s `_on_change` staleness/notify logic wraps in `try/except`
  matching the existing pattern used elsewhere in `on_mount` (e.g. the
  rebind-notification block already does this) — a notify failure must never
  crash the TUI.
- `core.store.is_recipient_stale` never raises `PeerNotFound` — returns
  `False` instead. The hook's independent `_is_recipient_stale` matches this
  contract by construction (a missing key in a `dict.get()` chain, not an
  exception path).

## Testing

- `tests/test_notify.py` (new): `core.notify.notify()` — mock
  `subprocess.run`; assert correct binary selected per `sys.platform`
  (`osascript` vs `notify-send`); assert fail-open on
  `FileNotFoundError`/`TimeoutExpired`/unknown platform.
- `tests/test_store_messages.py` (extend): `is_recipient_stale` — fresh
  `last_seen`, stale `last_seen`, missing peer. Also **migrate in** the 4
  pure `poll_new` tests currently in `tests/test_watch.py` (tests 1-4:
  first-call, second-call-empty, incremental, excludes-non-new-states) —
  unchanged, they're already fully isolated from the watcher/CLI layer.
- `tests/test_tui_notify.py` (new): mock `store.poll_new` /
  `is_recipient_stale` / `core.notify.notify`; assert `_on_change` notifies
  only when the recipient is stale and not in cooldown, and does not
  notify otherwise.
- `tests/test_relay_poll_offer_hook.py` (new — no test coverage exists for
  this hook today besides manifest-parity). Since the hook has no `__init__.py`/
  package context and its filename has a hyphen (`relay-poll-offer.py`,
  not importable via a normal `import` statement), load it per-test via
  `importlib.util.spec_from_file_location("relay_poll_offer", path)` +
  `spec.loader.exec_module(module)`, then call the loaded module's private
  functions directly (`module._is_recipient_stale(...)`,
  `module._notify(...)`, `module.main()` with a monkeypatched `sys.stdin`).
  Set `CLAUDE_RELAY_DIR` via `monkeypatch.setenv` (reusing the project's
  `relay_dir` fixture works here too, since the new hook code reads that
  same env var) before loading the module, so `_relay_dir()` resolves into
  `tmp_path`, never touching the real `~/.claude/relay/`. Cases: stale+no-TUI
  → notify; stale+TUI-heartbeat-live → skip (avoid double-fire); not-stale →
  skip; in-cooldown → skip; recipient resolution for `send` (parsed directly
  from the command string) vs `reply` (resolved via the on-disk message
  file's `from_peer`, including the not-found-message case → skip silently).
- `tests/test_watch.py` — **deleted entirely** after the 4 pure-`poll_new`
  tests are migrated out (the rest test `cmd_watch`/`_watch_emit`, which no
  longer exist).

## Removal scope: standalone `downbeat watch`

Delete:
- `src/downbeat/cli/commands/relay_cmds.py` — `cmd_watch()`, `_watch_emit()`;
  remove now-unused `threading` and `watcher as watcher_mod` imports
  (`datetime`/`UTC`/`timedelta` stay — used elsewhere in the file, e.g.
  `gc-stale`)
- `src/downbeat/cli/__main__.py` — the `sp_watch` subcommand registration

Edit (remove watch references, note the replacement mechanism):
- `README.md` — remove the "Always-on inbox watch" section (cost table,
  watch-vs-`/relay-monitor` comparison table); add a short new section
  describing the automatic staleness-notify (TUI-hosted + headless fallback)
- `src/downbeat/skill/SKILL.md` — remove "Registration + always-on watch";
  note that notification is now automatic, no manual step
- `examples/parent-child-handoff/README.md` — remove the `downbeat watch
  --peer demo-child` line
- `src/downbeat/assets/commands/relay-monitor.md` — in "Notes", replace the
  `downbeat watch` mention (command no longer exists) with a pointer to the
  new automatic mechanism

Do **not** touch:
- `docs/decisions.md` — the existing entry about the `FsWatcher.stop()`
  deadlock is about the underlying class, not the CLI wrapper; stays as
  historical record.
- `CHANGELOG.md` — generated by `python-semantic-release` from conventional
  commits, never hand-edited.

Keep unchanged:
- `src/downbeat/core/watcher.py` (`FsWatcher`/`PollWatcher`) — the reused
  primitive, not touched structurally.

## Versioning

Commit as `feat!: remove standalone downbeat-watch CLI, replace with
automatic staleness notify` with a `BREAKING CHANGE:` footer describing that
`downbeat watch` no longer exists as a subcommand;
`python-semantic-release` will pick this up as a major bump automatically —
no manual version editing.

## Known limitations (accepted, not blockers)

- **Headless recipient + non-Claude sender** (e.g. a plain script calling
  `downbeat send` directly, not through a Claude Code session with the hook
  wired up): neither path fires. This is the conscious price of not running
  a daemon — deferred to the wiki roadmap as a possible future C-daemon
  follow-up, not solved here.
- **Rename-staleness cosmetic gap**: if a peer is renamed mid-flight, the
  notify text may show a stale display name momentarily — same caveat
  already noted for the earlier C-lite sketch, doesn't change with this
  design.
- **Near-simultaneous TUI+hook write to `tui_state.json`**: can lose one of
  two timestamp updates in a race; worst case is one extra notification, not
  file corruption (whole-file atomic write). Not specially guarded against.
