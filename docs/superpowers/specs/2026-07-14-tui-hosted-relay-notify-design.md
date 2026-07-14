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

No new process. Two independent triggers converge on one shared notify
helper:

```
TUI resident FsWatcher (tui/app.py, already running when TUI is open) ──┐
                                                                          ├──► core/notify.py
relay-poll-offer.py (PostToolUse hook on Bash send/reply, headless) ────┘      (subprocess: osascript / notify-send)
```

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

### 5. `assets/hooks/relay-poll-offer.py` (extend)

After the existing `send`/`reply` regex match (unchanged): determine the
recipient. This differs by verb, since only `send`'s command line actually
contains the recipient name:
- `send <to> <subject> <body>` — `to_peer` is the first positional argument
  after `send`. Parse via `shlex.split(command)`, taking the token after the
  matched `send` (handles quoted subjects/bodies containing spaces).
- `reply <msg_id> <body>` — the command line has no recipient at all; the
  recipient is the *original sender* of the message being replied to. Parse
  `msg_id` the same way (first positional after `reply`), then look it up
  via the store (the message's `from_peer`) to get the actual recipient.
  If the lookup fails (message not found — already archived/moved by the
  time the hook runs), skip the staleness-notify silently; this is a
  best-effort nudge, not a guaranteed delivery path.

If
`is_recipient_stale(to_peer)` **and** `watcher_heartbeat_at` is not fresh
(TUI not open — avoids double-firing with the TUI path) **and** the
recipient isn't in cooldown → call `core.notify.notify(...)` directly from
the hook process (not via the `PushNotification` tool — the hook is a plain
subprocess and can shell out itself) and update `notify_last_sent`.

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

- `core/notify.py` fails open (see above) — never raises into either caller.
- `relay-poll-offer.py` already wraps `main()` in `try/except` with
  `sys.exit(0)` on any exception (never blocks the Bash tool). The new
  staleness logic sits inside that same envelope — no new failure contract.
- `tui/app.py`'s `_on_change` staleness/notify logic wraps in `try/except`
  matching the existing pattern used elsewhere in `on_mount` (e.g. the
  rebind-notification block already does this) — a notify failure must never
  crash the TUI.
- `is_recipient_stale` never raises `PeerNotFound` — returns `False` instead.

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
- `assets/hooks/relay-poll-offer.py` — extend whatever existing hook test
  coverage exists (confirm at implementation time) with: stale+no-TUI →
  notify; stale+TUI-heartbeat-live → skip (avoid double-fire); not-stale →
  skip; in-cooldown → skip; recipient resolution for `send` (parsed directly
  from command) vs `reply` (looked up via the original message's
  `from_peer`, including the not-found-message case → skip silently).
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
