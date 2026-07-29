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

## Recently shipped (through v0.14.1)

- **Stable peer identity.** A peer now carries a `peer_id` assigned once and
  never reassigned — not by rename, not by rebind, not by re-registration —
  while `name` becomes a display alias. Messages carry both: `from`/`to` keep
  the name *at send time* (real history, and what the TUI renders), while
  `from_peer_id`/`to_peer_id` carry identity, and `list_thread` compares those.
  A rename can no longer punch a hole in a conversation, and neither can a
  message the rename sweep failed to reach. Legacy peers get a **deterministic**
  id derived from their name, so two sessions loading the registry concurrently
  can never mint competing identities for the same peer. A message whose sender
  is no longer registered stays unresolved rather than being given an invented
  identity — the name comparison still carries it. (issue #40, Option A)
- **Message-store schema versioning.** Every message file now records a
  `schema_version`, and `Message.from_dict` runs a migration ladder before
  reading any field — so a future structural change (a key renamed, a value's
  meaning changed) is a registered rung with a test, not hand-editing files
  across four directories. Files written before versioning existed are v0 by
  the absence of the key, so there is no backfill: they upgrade on read and
  self-heal on the next write. `downbeat migrate [--dry-run]` is the eager
  flush for archives nothing reads again. A file from a *newer* downbeat is
  refused rather than silently rewritten, since reading it would drop fields
  this build does not know. v1 ships the mechanism only — no data change — so
  the first real migration lands on proven plumbing. (issue #42)
- **Kind-aware reconciliation.** `reconcile()` no longer redelivers mail that
  carries no work back. A message is *terminal* when its `kind` is terminal
  (`backflow-ready`, `status`) or it carries an `in_reply_to` — the original
  sender absorbed it on arrival and has no ack path. Terminal messages are
  auto-acked into `processed/` instead of churning through redeliveries into
  quarantine; genuine tasks still requeue and quarantine exactly as before. The
  delivery window still governs, so an awake recipient keeps its normal chance
  to ack. `downbeat reconcile` reports the new outcome as `auto_acked=N`.
  (issue #47)
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

Two issues are labelled **good first issue** — both are narrow in scope and
land against an existing test suite.

- **Group writes during a rename** ([#56](https://github.com/FreddieMcHeart/downbeat/issues/56)).
  `_rename_in_groups` (`core/store.py`) rewrites `groups.json` once for *every*
  group the peer belongs to, so a peer in five groups means five full rewrites
  of the same file — five windows in which an interrupted rename leaves it
  half-updated. Collect the membership edits and write once. One function, with
  the rename path already covered in `tests/test_store_rename.py`.
- **Copy beyond the detail screen** ([#48](https://github.com/FreddieMcHeart/downbeat/issues/48)).
  `c` (copy id) and `y` (copy body) exist only on the message-detail screen, and
  nothing anywhere hints that a mouse drag plus `Ctrl+C` copies a selection.
  Extend the bindings to the chat and peers views and surface the
  selection-copy path. The clipboard mechanics are already factored out
  (`tui/widgets/clipboard.py`, tested in `tests/test_tui_clipboard.py`), so this
  is wiring bindings into more screens rather than new plumbing.

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, and please comment on the
issue before starting so effort isn't duplicated.

---

## Next — planned, shape is clear

- **Per-peer autonomy control.** A peer's relay-monitor autonomy (auto-execute
  vs. surface-and-ask) is fixed at registration by `role` and can't be changed
  afterward. Now that any node can be both a parent and a child, autonomy no
  longer follows from tree position — it's a value the human should set
  consciously per peer. Expose it: view and change a peer's autonomy after
  registration, independent of its structure.
  ([#41](https://github.com/FreddieMcHeart/downbeat/issues/41))
- **Cross-branch send from the TUI.** Routing is already flat — any peer can
  `downbeat send` to any other by name, regardless of tree position — but the
  TUI only surfaces the current group's peers, so a message to a far branch
  gets hand-forwarded hop-by-hop through a common ancestor instead. That chain
  is fragile: every intermediary has to wake, pick up, and consciously forward.
  Add a "send to any peer" action — a fuzzy picker over all registered peers —
  so reaching a distant branch is one step, not a relay chain.
  ([#60](https://github.com/FreddieMcHeart/downbeat/issues/60))
- **First-class message forwarding.** Forwarding a received message today means
  hand-copying its body into a fresh send. Add `downbeat forward <msg_id>
  <target>` that re-sends the original verbatim — preserving the source
  `from`/subject/body and adding a "forwarded by" trail — so passing an ask
  along is lossless and attributed instead of a manual paste.
  ([#61](https://github.com/FreddieMcHeart/downbeat/issues/61))

---

## Later — direction set, design open

**The message-system rework**
([#43](https://github.com/FreddieMcHeart/downbeat/issues/43)) — one coherent
redesign of how sessions exchange mail:

- **A single source of truth** for cross-session messages, so "read/unread" and
  "processed" state can't disagree between channels.
- **Explicit semantic states** — inbox → relayed → processed → completed — rather
  than state inferred from which directory a file happens to sit in.
- **Layered separation of concerns**: transport (physical delivery) · relay
  (routing between sessions) · inbox (a peer's personal queue) · downbeat (the UI
  and filters on top).
- **Lossless migration** from the current on-disk layout, with no thread history
  dropped.

Alongside it, a few narrower directions:

- **Idle-peer inbox controls + an honest unread badge.** A background peer that
  isn't taking prompts never drains its own inbox — pickup is per-turn, not
  event-driven — so `new` messages pile up behind a `●N` badge that reads as
  "unread" when it actually means "undelivered, recipient idle". Two moves: (a)
  a **CLI** bulk-ack — the TUI already has one (`c` on the inbox tab: confirmed,
  recoverable, and role-aware, since clearing a *child*'s inbox can bury
  unstarted tasks), but nothing scripted or headless can do it without reaching
  into the store; (b) an honest badge — the substantial half, and a bigger
  question than filtering terminal noise. `state == "new"` requires **both** no
  `delivered_at` **and** no `read_at`, so the badge collapses two unrelated
  facts and either moves it: it overstates work owed by counting terminal
  replies, and it understates to *zero* because opening a message in the TUI
  sets `read_at` — a human scrolling clears the badge while the recipient
  session has received nothing. Measured on a live store: `delivered` was `no`
  for every message a peer had ever been sent, and three genuine four-day-old
  tasks went `●3` → `●0` from scrolling alone. So the question is which fact the
  badge is *for* — what a human has seen, or what the recipient has actually
  received. Kind-aware reconciliation (shipped) does **not** help: `reconcile()`
  scans `delivered/` only, and an idle peer's mail never leaves `inbox/` for it
  to find — #47 stopped churn at a *live* recipient, this is an *idle* one.
  ([#62](https://github.com/FreddieMcHeart/downbeat/issues/62))
- **Peer identity for a background session.** A session that didn't register
  itself has to guess which peer it is, and the guess keys off `session_id` —
  which changes when a session is resumed or re-launched, so the match silently
  fails and the CLI falls back to "can't auto-identify, pass `--peer`". Stable
  `peer_id` (shipped) gives the *peer* a durable key but doesn't tell a running
  session which peer it is; the binding between a live session and a peer is
  still the open question. Design deferred until the shape of that binding is
  clear — a recorded claim, a handshake, or an explicit env var are all
  plausible and they don't cost the same.
  ([#53](https://github.com/FreddieMcHeart/downbeat/issues/53))

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

- **Identity is data, not a display alias** — a peer's `peer_id` is assigned once
  and never reassigned; `name` is what a human reads. Compare on the id, render
  the name, and never let a rename become a data migration again.
- **Every tree traversal is bounded** — a visited-set/iteration cap on every
  `.parent` walk, not just the cycle check, so corrupt on-disk data can't hang a
  read.
- **Routing is flat; the tree is a view** — any peer can address any peer
  directly by name. The parent/child tree only groups the TUI and sets autonomy
  defaults; it is not a delivery topology, so a cross-branch message never needs
  hop-by-hop forwarding.
- **Verify against the real artifact, not its test double** — drive the real
  binary / real TUI / real store; a check that fakes what it's checking passes for
  the wrong reason.
- **Skills call the CLI; they don't reimplement it** — any filtering logic
  duplicated into skill text will drift from the store at the next change.

---

## Contributing

New contributors: start with the two **Now** items — both are labelled *good
first issue*, touch one file, and land against an existing test suite. Past
those, the **Next** section holds the strongest near-term candidates, and #41
and #61 carry *help wanted*. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
and please check open issues **and** PRs before starting so effort isn't
duplicated.
