# downbeat roadmap

downbeat is a local relay + TUI for handing work between parallel Claude Code
sessions on one machine. This roadmap is **directional, not dated** — it says
what we're likely to build next and in roughly what order of confidence, not
when. Committed, actionable work lives in
[GitHub issues](https://github.com/FreddieMcHeart/downbeat/issues); this file is
the map above them.

Horizons are ordered by confidence, not calendar:

- **Now** — open and ready to pick up.
- **Next** — planned, shape is clear, not yet started.
- **Later** — direction we intend to take; design still open.
- **Exploring** — plausible, deliberately deferred until there's a real need.

---

## Recently shipped (through v0.11.1)

- **Atomic peer rename.** `downbeat peers rename <old> <new>` migrates a peer's
  full on-disk identity in one shot — `from`/`to` across every message, all four
  per-peer directories, `sessions.json` (key + parent pointers), and group
  membership — so renaming is no longer a data-corrupting operation. Resumable
  via an in-progress marker; validates names against path traversal. (v0.11.0,
  hardened in v0.11.1 — issue #40 Option B.)
- **Honest relay CLI for background sessions.** When a session can't
  auto-identify, the error now names the flag the subcommand actually accepts
  (`--peer`, not a hardcoded `--from`), `whoami` gained a `--peer` override, and
  `ack` explains why a message couldn't be acked instead of failing silently.
  (v0.10.8)
- **Clipboard that works on Terminal.app + honest dependency floors.** The TUI
  copies via OSC 52 **and** the local clipboard (⌘C / `c` / `y` all work now),
  and a `min-versions` CI job exercises the declared dependency floors so they
  can't silently drift below what the code needs. (v0.10.5 / v0.10.6)
- **Honest UTC logs + keyboard-navigable message finder.** Log timestamps are now
  real UTC (the trailing `Z` was previously local time wearing a UTC label), and
  the find-message modal hands keyboard focus from the search box to the results
  so a match can be picked without the mouse. (v0.10.4)
- **General peer tree.** Any peer can be both a child and a parent — arbitrary
  depth in the data model, with a bounded cycle check. `role` no longer gates
  structure; it only sets the relay-monitor autonomy default.
- **One-command updates.** `/downbeat:update` moves *both* artifacts (the plugin
  and the `downbeat` CLI), a `SessionStart` hook warns when the two versions
  drift, and `--version` reports provenance so an editable install can't lie
  about what code is actually running.
- **TUI-hosted relay notifications.** Native OS notification when a peer has idle
  mail, fired from the TUI's resident file-watcher when it's open and from a
  send/reply hook when it isn't, with heartbeat arbitration against double-fire.
- **Reliability wave.** Fixed a family of "state on disk vs. what's rendered
  diverge silently" bugs — empty-thread-on-tab-switch, peer removal orphaning
  its children, a message-archival write/unlink race, and inbox/tab desync.

See [CHANGELOG.md](CHANGELOG.md) for the full, versioned release history.

---

## Now — open, ready to pick up

Nothing open right now — the two good-first-issues (#30, #31) shipped in v0.10.4.
The **Next** items below are the strongest near-term candidates; if you'd like to
take one, opening an issue (or a PR) is the way in — see
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## Next — planned, shape is clear

- **Stable peer identity, separate from display name.** _Option B shipped:_
  `downbeat peers rename` now migrates a peer's full history atomically
  (messages, directories, parent pointers, groups), so renaming is no longer a
  data-corrupting operation. What remains is _Option A_ — a stable identity key
  (UUID) with the name as a pure display alias, so no code path ever compares a
  stored historical name against a live one. Option A rewrites what every
  message's `from`/`to` field *means*, so it's gated on message-store schema
  versioning (below) landing first.
- **Per-peer autonomy control.** A peer's relay-monitor autonomy (auto-execute
  vs. surface-and-ask) is fixed at registration by `role` and can't be changed
  afterward. Now that any node can be both a parent and a child, autonomy no
  longer follows from tree position — it's a value the human should set
  consciously per peer. Expose it: view and change a peer's autonomy after
  registration, independent of its structure.
- **Message-store hardening.** Schema versioning on message files, so future
  format changes are migratable instead of manual.

---

## Later — direction set, design open

**The message-system rework** — one coherent redesign of how sessions exchange
mail:

- **A single source of truth** for cross-session messages, so "read/unread" and
  "processed" state can't disagree between channels.
- **Explicit semantic states** — inbox → relayed → processed → completed — rather
  than state inferred from which directory a file happens to sit in.
- **Layered separation of concerns**: transport (physical delivery) · relay
  (routing between sessions) · inbox (a peer's personal queue) · downbeat (the UI
  and filters on top).
- **Lossless migration** from the current on-disk layout, with no thread history
  dropped.

Alongside it, two narrower directions:

- **Kind-aware message reconciliation.** `reconcile()` today re-queues and
  eventually quarantines any unacked message purely by age — including status
  reports and closing replies that were absorbed the moment they arrived and
  have no natural ack path. They churn through redeliveries and pile into
  quarantine (a real backlog we've had to hand-clear). Teach reconcile the
  difference: auto-ack terminal messages, re-queue only genuine tasks. A focused
  precursor to — or part of — the rework above.
- **Copy anywhere in the TUI.** The copy affordance (`c` id / `y` body) lives
  only on the message-detail screen, and mouse-selection copy (drag-select +
  `Ctrl+C`) isn't surfaced anywhere. Extend copy to the chat and peers views and
  make the selection-copy path discoverable.

---

## Exploring — plausible, deferred on purpose

- **Standalone watcher daemon.** A long-lived file-watcher process would close the
  one coverage gap the current notify design accepts — a headless recipient whose
  sender isn't a Claude session. Deferred because it adds a real lifecycle
  (supervise, single-instance lock, reboot-persistence); revisit when that gap is
  actually felt.
- **Multi-level tree UI.** The data model already supports arbitrary depth; the
  TUI deliberately renders two levels at a time and navigates deeper by
  re-rooting. A genuine nested tree view is a larger TUI change, worth it only
  once someone runs trees deep enough to need it.
- **New message kinds** — `workflow-request` / `workflow-result` — for structured
  hand-offs beyond free-form relay messages.
- **Cross-user / cross-machine relay.** Today's model assumes one human with many
  tabs. Going cross-user needs an explicit owner/account on each peer and changes
  the notification story; a deliberate topology jump, not an increment.

---

## Principles carried across all of the above

- **Identity is data, not a display alias** — until a stable key exists, treat any
  rename as a migration.
- **Every tree traversal is bounded** — a visited-set/iteration cap on every
  `.parent` walk, not just the cycle check, so corrupt on-disk data can't hang a
  read.
- **Verify against the real artifact, not its test double** — drive the real
  binary / real TUI / real store; a check that fakes what it's checking passes for
  the wrong reason.
- **Skills call the CLI; they don't reimplement it** — any filtering logic
  duplicated into skill text will drift from the store at the next change.

---

## Contributing

New contributors: with the good-first-issues shipped, the **Next** section holds
the strongest near-term candidates — open an issue or PR to claim one. See
[CONTRIBUTING.md](CONTRIBUTING.md) for setup, and please check open issues **and**
PRs before starting so effort isn't duplicated.
