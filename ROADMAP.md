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

## Recently shipped (through v0.14.8)

- **A history hit no longer lets a session take another's identity.** A resumed
  session used to repair itself whenever its id appeared in some peer's
  recorded history. But that history cannot tell *the same agent, resumed*
  apart from *a different agent that once held this name* — on disk they are
  the same thing — so once two live sessions had both held a name, each one's
  next command took the record back and reported the theft as a success. It
  ran six times on one record in production, five of them alternating, none of
  them an error, and it cost a code review credited to the wrong session and
  now unresolvable, the same task built twice, and a review delivered to the
  wrong author. A history hit is now *reported* — it names the peer, says
  plainly that a lead is not proof, and leaves the decision to a human. The
  resume-time check inverts with it: what used to be its reason for silence is
  now its strongest warning. (issue #88)
- **The changelog is written again.** `CHANGELOG.md` had not been touched since
  v0.3.0 — eleven releases absent from it — while every release job reported
  success. The generator was never broken: release notes rendered correctly the
  whole time and went only to GitHub. What broke was the *write*, and it broke
  silently, because the tool inserts each release after a marker that had gone
  missing, and finding no marker it does nothing and exits cleanly. The dry-run
  mode could not surface it either: it announces the write before attempting
  it, so the broken state looked healthy in exactly the check meant to catch
  it. Backfilled from tag history, and a post-release check now fails loudly
  when a release does not touch the file — after publishing, never blocking it.
  (issue #84)
- **A background session can identify itself.** Detection walks ancestor
  processes looking for `claude` and matched the process name as a path segment —
  a rule chosen deliberately, and correct for every shape that existed when it
  was written. Background workers wear a process *title* rather than a path, so
  the one ancestor holding the session marker was the only one being rejected,
  and `whoami`, `send`, `reply` and `inbox` all failed with "could not detect
  session id" — no name to pass, and no way to discover it. A background peer is
  the shape the relay exists to coordinate, so this was the more severe of the
  identity defects. (issue #75)
- **A stale identity announces itself at resume, not at the first send.** A
  resume that mints an unseen session id leaves no lineage to repair from, and
  the refusal used to surface only when a message was finally worth sending —
  everything up to that point looked healthy. A resume-only check now reports the
  stale binding and names the repair. It never rebinds: every available signal
  for *which* peer this is would be a guess, and a guess binds a session to the
  wrong identity. The check stays silent unless the evidence is unambiguous,
  because one that cries wolf gets turned off and then protects nothing.
  (issue #71, completing it)
- **A name collision can no longer re-home a peer behind your back.** The peer
  registry is keyed by name, and re-registering a known name used to be treated
  as "the same peer reattaching" — carrying its identity over while silently
  overwriting its parent. Someone who meant *a new child that happens to share a
  name* got a destructive move instead, with no warning: the peer vanished from
  one parent's view and appeared under another looking empty, while its history
  stayed on disk attributed to the old pairing. Registering with a parent that
  disagrees with the stored one is now refused, and the refusal says what is in
  the way — current parent, when it was registered, how many messages it holds —
  so the choice is visible before anything is written. Reattaching still works
  unchanged; a deliberate move goes through `peers set-parent`. (issue #70)
- **`last_seen` finally means what it says, and the write it made hot is
  locked.** The peers table's one liveness signal was a registration timestamp
  wearing a liveness name: the function that updates it existed and had no
  callers, so peers that had been sending and receiving all day read weeks
  stale — making live peers look dead. It now updates on the two events that
  mean a peer took part: sending, and draining its own inbox. That wiring turned
  a latent race live, since every such update rewrites the whole registry, so
  registry writes are now mutually excluded by a lock. Atomic writes were never
  enough on their own — they make the *write* indivisible, not the
  read-modify-write around it. (issue #72)
- **Identity survives a resume when the lineage is provable.** If the current
  session id is one a single peer previously held, that is recorded evidence
  rather than a guess, so the binding repairs itself instead of failing. Where
  the evidence is ambiguous — or absent — it still refuses rather than picking a
  winner, because binding a session to the wrong peer is worse than an error.
  This covers less than it sounds like: a resume that mints an entirely new
  session id leaves no trace to match on. That half is what the resume-time
  warning above exists for. (issue #71, in part)
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

Three issues are labelled **good first issue** — each is narrow in scope and
lands against an existing test suite.

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
- **Read a message from the CLI** ([#85](https://github.com/FreddieMcHeart/downbeat/issues/85)).
  `downbeat inbox` lists messages and nothing prints one — no `show`, no
  `--body`, no `--full`. Reading mail you have already listed means going around
  the CLI and parsing the store by hand, which requires knowing the on-disk
  layout and which of four directories a message currently sits in. It also
  blocks anything headless: a script or a background peer can enumerate its mail
  and cannot read it. The TUI renders bodies already, so the capability exists
  and is simply absent from the CLI. Worth deciding rather than assuming: that it
  searches all four directories and reports which one it found the message in
  (that directory *is* the state), and that reading does **not** set `read_at` —
  a debugging read that mutates state is a trap.

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
- **An error message that is safe to follow from wherever it is read.** When
  registering a name that is already taken, the refusal offers a way out —
  reattach the same peer by leaving the parent off. That is correct from the
  session that owns the record and destructive from any other, because
  `register` takes its subject from *the calling session* and dropping the
  parent skips the only check that fired. The remedy needs its precondition
  attached, and should not be offered at all to a caller that demonstrably
  isn't that session. Underneath sits the general rule worth encoding: a
  command that names its subject **implicitly** means different things in
  different windows, so it cannot be handed to a human in an error message the
  way one that takes its target as an **argument** can. The same fix should
  close the gap the guard only covers by accident — it refuses on a parent
  mismatch and merely happens to prevent a session takeover, which stops being
  true the moment that check is relaxed or routed around.
  ([#89](https://github.com/FreddieMcHeart/downbeat/issues/89))

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
- **How a session should *claim* an identity is still open.** The two acute
  failures underneath this are fixed — a background session can be identified
  now, and a resume that cannot repair itself says so at resume instead of at the
  first send. What remains is the design question they were symptoms of: a
  session's identity is currently *inferred*, by walking ancestor processes to a
  marker file and matching a session id against the registry. Inference has no
  ceiling on how many ways it can be wrong; each fix so far has closed one shape
  and left the mechanism intact. The alternative is for a session to **assert**
  who it is — a recorded claim written at registration, a handshake, or an
  explicit variable in the environment. Those do not cost the same and none is
  obviously right, which is why this stays a direction rather than a plan.
  ([#53](https://github.com/FreddieMcHeart/downbeat/issues/53))
- **Two parents, one child name.** A name like `Dev One` is a *role* someone
  plays in several trees, not a globally unique entity, and being pushed into
  `Dev One 2` is the storage model leaking into what things are called. But
  names are currently **addresses** — any peer reaches any other by name in one
  hop — so making them non-unique makes `send "Dev One"` ambiguous, which is why
  this is a design question rather than a change to a dictionary key. The clean
  resolution is probably to finish what stable identity started: let `peer_id`
  be the address and names be free-form labels, with message directories keyed
  by id (a store migration, which the schema ladder exists for). Scoping the key
  to `(parent, name)` is the tempting shortcut and the wrong one — parents can
  change, and keying identity on a *view* is the same category error `role`
  made before the tree was generalized.
  ([#73](https://github.com/FreddieMcHeart/downbeat/issues/73))
- **A way to let go of a name.** A session that finds it is holding an identity
  belonging to someone else cannot step aside. `register` only takes a claim,
  `rebind` repoints a record — which from a squatter means reassigning *another
  live session's* identity — and `peers rename` drags the message history along
  with the name, so freeing a record would carry off the displaced session's
  mail. The only remedy left is a human editing the registry by hand, which is
  what makes a collision *persist* rather than resolve: both sessions can see
  the problem and neither can stop taking part in it. The constraint that
  should be built in rather than left to good judgement — **releasing your own
  claim is the only identity operation a session may perform unilaterally;
  repointing someone else's record is not.** Open, and worth deciding rather
  than defaulting: what a record with no session bound to it should do when
  mail arrives.
  ([#90](https://github.com/FreddieMcHeart/downbeat/issues/90))
- **A way to say "received, nothing further" that the inbox believes.** A
  message can already declare it needs no answer — that is what `kind` is for,
  and `reconcile()` treats the terminal kinds as settled. What no part of the
  system does is *show* it that way: a status report keeps appearing in the
  inbox listing exactly like unanswered work, so the count stops meaning "work
  owed" and starts getting ignored. `ack` is the verb for this and it only
  reaches mail that has already been delivered, so the messages most in need of
  clearing — sitting in a peer whose per-turn drain has not run — are the ones
  it cannot touch. What remains is replying, which puts a fresh task in the
  sender's inbox and restarts the exchange the status kind existed to end. The
  likely shape is a listing that separates *owed* from *unread but not owed*,
  which needs no decision about when to clear anything; auto-acking at delivery
  is the tempting alternative and answers the wrong question, since it archives
  a report before it has been read. Same disease as the unread badge above,
  from a different cause, and much cheaper to cure.
  ([#93](https://github.com/FreddieMcHeart/downbeat/issues/93))
- **One home for registry writes, and one for delivery.** Two places where the
  same operation exists twice. Half the registry's mutators take the lock added
  with the liveness fix and half do not, and since the lock is advisory an
  unlocked writer doesn't merely go unprotected — it defeats the protection on
  the locked side too
  ([#78](https://github.com/FreddieMcHeart/downbeat/issues/78)). Separately,
  the per-turn hook that actually delivers mail reimplements draining instead of
  calling the store's, so the store's version runs only when a human types
  `downbeat drain`. That divergence already silently halved a shipped fix, and
  it duplicates invariants — crash-safe write ordering, delivery stamping — that
  should have exactly one definition
  ([#79](https://github.com/FreddieMcHeart/downbeat/issues/79)). Same principle
  as *"skills call the CLI; they don't reimplement it"*, one layer down.

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
  hop-by-hop forwarding. The cost of this, worth stating plainly: it makes the
  *name* an address, which is why non-unique names are a design question and not
  a small change.
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
