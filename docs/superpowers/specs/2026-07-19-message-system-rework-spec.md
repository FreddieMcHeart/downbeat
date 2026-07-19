# Message-system rework (single source of truth, semantic states)

**Status:** design — exploration, NOT ready to implement; pending maintainer direction.
**Issue:** [#43](https://github.com/FreddieMcHeart/downbeat/issues/43) — "Message-system rework (single source of truth, semantic states)" (roadmap: Later, design-open tracking issue, milestone "Message-system rework")
**Prerequisites (design-open, do not start before):** [#40](https://github.com/FreddieMcHeart/downbeat/issues/40) "Stable peer identity, separate from display name", [#42](https://github.com/FreddieMcHeart/downbeat/issues/42) "Message-store schema versioning"
**Background:** `~/dev/claude-core-wiki/ideas/downbeat/cloud-relay-downbeat-inbox-rework.md` (living design note, read for history — this spec does not restate it)

This document is a problem analysis and a target-model sketch, not a build plan.
Issue #43 itself says "design is not yet settled ... sub-work will be split out as
the design firms up. Not ready-to-implement." Everything below should be read in
that spirit: it names the current implicit state machine precisely, sketches what
"done" could look like for each of the four goals, and lays out what has to happen
*before* any of this is buildable. Where a decision is genuinely open, it is
flagged as open rather than pre-decided.

## Context

downbeat's message store (`src/downbeat/core/store.py`) has no explicit,
persisted `state` field on a message. State is *computed*, twice, from a
handful of nullable timestamp/boolean fields on the `Message` dataclass, and
those same fields also determine which of four on-disk directories a
message's JSON file physically lives in. The directories are defined in
`src/downbeat/core/paths.py:9-13`:

```python
RELAY_DIR = Path(os.environ.get("CLAUDE_RELAY_DIR", str(Path.home() / ".claude" / "relay")))
INBOX_DIR = RELAY_DIR / "inbox"
PROCESSED_DIR = RELAY_DIR / "processed"
DELIVERED_DIR = RELAY_DIR / "delivered"
QUARANTINE_DIR = RELAY_DIR / "quarantine"
```

Each message is a file at `<dir>/<to_peer>/<msg_id>.json`. There is no fifth
"relayed" directory and no `state` column in any of these files — `state`
does not exist as a field on `Message` at all.

### The two independent implementations of the same state machine

`Message.state` (`src/downbeat/core/models.py:54-64`) is a computed property:

```python
@property
def state(self) -> MessageState:
    if self.quarantined_at is not None:
        return MessageState.QUARANTINED
    if self.archived:
        return MessageState.ARCHIVED
    if self.delivered_at is not None and self.delivery_ack_at is None:
        return MessageState.DELIVERED
    if self.read_at is not None:
        return MessageState.READ
    return MessageState.NEW
```

`_message_path` (`src/downbeat/core/store.py:283-292`) is a second function
that checks the *same four fields, in the same precedence order*, to decide
which directory a file belongs in:

```python
def _message_path(msg: Message) -> Path:
    if msg.quarantined_at is not None:
        base = paths.QUARANTINE_DIR
    elif msg.archived:
        base = paths.PROCESSED_DIR
    elif msg.delivered_at is not None and msg.delivery_ack_at is None:
        base = paths.DELIVERED_DIR
    else:
        base = paths.INBOX_DIR
    return base / msg.to_peer / f"{msg.id}.json"
```

These two functions agree today. Nothing enforces that they keep agreeing —
they are hand-synchronized, not derived from one shared source. Add a fifth
state, change one precedence check, or add a field that should gate a new
directory, and it is a silent two-file edit with no compiler or test forcing
both sides to move together. This is exactly what issue #43's second goal
("explicit semantic states ... rather than state inferred from which
directory a file sits in") is naming, and what the first goal ("single source
of truth ... so read/unread and processed can't disagree") is naming from the
consumer's side.

The `MessageState` enum itself (`models.py:21-26`) only has five values —
`NEW`, `READ`, `DELIVERED`, `QUARANTINED`, `ARCHIVED` — none of which are the
four states issue #43 actually asks for (`inbox → relayed → processed →
completed`). The current enum is a snapshot of *delivery* mechanics
(has it landed in the recipient's queue, has it been acked); the requested
enum is a snapshot of *conversational* mechanics (has the recipient dealt
with it). These are related but not the same axis, and today's code only
models the first axis explicitly.

### Every function that moves a message between directories

There is no single `transition(msg, event)` chokepoint. Nine different
`store.py` functions each independently read/write the same handful of
fields and independently write-then-unlink across directories:

| Function | file:line | Transition | Fields mutated |
|---|---|---|---|
| `send_message` | `store.py:330-351` | (new) → inbox | all defaults → `state == NEW` |
| `deliver_messages` | `store.py:354-384` | inbox → delivered | `delivered_at`, `delivered_to_session_id` |
| `mark_read` | `store.py:450-459` | no move, in place | `read_at` (no-op if `state != NEW`) |
| `ack_messages` | `store.py:387-413` | delivered → processed | `delivery_ack_at`, `archived` |
| `archive_messages` | `store.py:416-447` | inbox/delivered → processed | `archived` (+`delivery_ack_at` if was delivered) |
| `edit_message` | `store.py:462-479` | no move, in place | `body`/`subject`/`edited_at` (raises `MessageLocked` if `state != NEW`) |
| `reply_to` | `store.py:487-520` | archives original + inbox (new msg) | `archived`, `delivery_ack_at` on original; fresh `Message` for the reply |
| `reconcile` | `store.py:548-607` | delivered → inbox (requeue) OR delivered → quarantine | `delivered_at=None`/`redelivery_count+=1` OR `quarantined_at`/`quarantine_reason` |
| `requeue_quarantined` | `store.py:752-782` | quarantine → inbox | resets `quarantined_at`, `quarantine_reason`, `delivered_at`, `delivered_to_session_id`, `redelivery_count` |

Every mover follows the same write-then-unlink pattern (write the new file to
the destination directory, then `path.unlink()` the source) — `archive_messages`
even documents *why* that order matters at `store.py:431-435`, citing
`list_inbox`'s dedup-by-id `seen` set as the reason a reversed unlink-then-write
would produce a visible gap. That's a real, working safety property of the
current design worth preserving, not just an artifact of implicit-state sloppiness.

Two read-only functions are also part of the picture: `list_inbox`
(`store.py:523-545`) scans `INBOX_DIR` + `DELIVERED_DIR` always, adding
`PROCESSED_DIR` + `QUARANTINE_DIR` only under `include_archived=True`, and
`list_thread` (`store.py:829-841`) reconstructs two-party history by filtering
on the literal `from_peer`/`to_peer` strings baked into each message at
send-time — the exact mechanism issue #40 says breaks on peer rename.

### Directory location is (almost) never read as a signal — except once

Because `_message_path` deterministically recomputes the directory from the
same fields `Message.state` reads, directory-membership is not, today, an
*independent* source of truth in the strict sense — it is a redundant,
physically-real third encoding of the same four fields. One exception:
`find_message_by_id_prefix`'s `location_label` (`"inbox"`/`"delivered"`/
`"processed"`/`"quarantine"`) is set from which base directory the scan loop
is currently in, not derived from message fields — a second parallel,
directory-derived encoding used only for that one function's return value.
So the honest description of goal 1 is not "state currently lives in two
disagreeing places" (it doesn't disagree today) but "state is defined twice,
by convention, with no mechanism preventing the two definitions from
drifting apart as the schema grows" — which is precisely the kind of bug that
shows up only after a schema change, i.e. exactly where issue #42 (schema
versioning) becomes load-bearing.

## Target model per goal

Each of the four goals below is sketched independently. None of these
sketches is a final schema — they are starting shapes for a maintainer
conversation, written to be concrete enough to argue with.

### Goal 1 — single source of truth

Collapse the two independent implementations (`Message.state` property,
`_message_path`) into one. The shape of the fix is not in question — derive
`_message_path` from `Message.state` (or vice versa) instead of maintaining
parallel precedence chains — the open question is *whether the on-disk
directory should keep being the storage mechanism at all*, or whether
directory-as-storage should be replaced by a single message store (e.g. one
JSON-lines file per peer, or a SQLite file) with an explicit `state` column
and the four current directories demoted to a pure read-side/debugging view
(or removed). Directories are simple, `git`-diffable, and manually
inspectable/recoverable by hand (an operational property visible throughout
`store.py`'s "heals a hand-edited `sessions.json`" comments, e.g.
`store.py:230-235`) — that property should not be thrown away casually.

### Goal 2 — explicit semantic states (inbox → relayed → processed → completed)

The four states named in the issue are a *different axis* from the current
`MessageState` enum, and the two axes need to be reconciled, not merged
blindly:

- **inbox** — message exists, addressed to a peer, not yet delivered to a live
  session. Roughly today's `NEW` + "not yet delivered."
- **relayed** — delivered to a session (today's `DELIVERED`, i.e.
  `delivered_at is not None and delivery_ack_at is None`), or possibly
  delivered *and* read but not yet acted on (today's `READ` sits ambiguously
  between "relayed" and "processed" — read is not the same as acted-on).
- **processed** — the recipient has acted on it (replied, archived,
  explicitly acked). Roughly today's `ARCHIVED`.
- **completed** — not represented at all today. Issue #43 introduces a
  distinction between "the recipient dealt with it" (processed) and "the
  underlying task/thread this message was part of is finished" (completed) —
  this maps loosely onto the existing `kind` field's forward-looking
  `"backflow-ready"` / `"workflow-request"` / `"workflow-result"` values
  (`models.py:49-52`) and onto `broadcast_status`'s (`store.py:648-673`)
  ad hoc `replied`/`read`/`pending` per-target rollup, but neither of those
  is currently a state on the message itself.

### Goal 3 — layered separation of concerns (transport / relay / inbox / downbeat)

`store.py` today is one file doing all four jobs at once: physical
write/move/unlink (transport), routing by `to_peer`/`broadcast_id`/`in_reply_to`
(relay), a peer's personal view with `include_archived` filtering (inbox),
and TUI-facing conveniences the `tui/` layer builds on top of directly. A
layered target model would draw explicit seams:

- **Transport** — atomic write/move/unlink of a message record. No opinion on
  meaning. Candidate ownership: today's `_atomic_write_text`,
  `_message_path`, and the unlink-after-write pattern, generalized.
  `core/state.py` already reaches across this seam informally (per the
  comment at `store.py:255-260` describing it as reusing
  `_atomic_write_text` "same reuse pattern" as another module) — a real
  layering pass has to decide whether that's promoted to a shared primitive
  or left as an acceptable internal reuse.
- **Relay** — routing/addressing: `send_message`, broadcast fan-out,
  `reply_to`'s auto-ack-original-then-send-new two-step, `reconcile`'s
  requeue/quarantine policy. This is "where does a message go and when does
  it get retried or given up on."
- **Inbox** — a single peer's queue and its state transitions:
  `deliver_messages`, `mark_read`, `ack_messages`, `archive_messages`,
  `list_inbox`. This is "what does *this* peer see and what can they do to a
  message they own."
- **downbeat (UI + filters)** — `tui/` widgets/screens consuming the above
  through a read/command surface, plus CLI commands in
  `cli/commands/relay_cmds.py`. Should not itself know about directories,
  `_message_path`, or precedence-chain state derivation — it already mostly
  doesn't, but the wiki note (`cloud-relay-downbeat-inbox-rework.md`, per the
  "skills that call the CLI, not reinvent the filter" finding around PR #15)
  documents at least one case where a skill re-implemented store filtering
  logic in the wrong layer instead of calling `downbeat inbox --peer <me>`.

The open question here is not "should there be layers" but *where exactly
the transport/relay boundary sits* and whether it is worth a real module
split (`core/transport.py`, `core/relay.py`, `core/inbox.py`) versus staying
one file with clearer internal boundaries and doc comments. A premature
module split before goal 2's schema is settled risks a second migration on
top of the first.

### Goal 4 — lossless migration from the current on-disk layout

See "Migration strategy sketch" below — this goal is large enough, and
different enough in kind (it's an operational/data-safety concern, not a
design-shape concern), that it gets its own section rather than a short
paragraph here.

## Prerequisites & sequencing

Issue #43 should **not** start before #40 and #42 land. Both are already
tracked as narrower, independently-actionable issues under a different
milestone ("Peer identity & autonomy," vs #43's own "Message-system rework"
milestone) — that separation is not incidental, it reflects that they are
smaller, more concrete, and structurally *load-bearing* for #43:

- **#40 (stable peer identity, separate from display name) must land first**
  because `list_thread` (`store.py:829-841`) and every message's frozen
  `from_peer`/`to_peer` strings are exactly the mechanism goal 2's semantic
  states and goal 3's layering would be built on top of. If a peer rename can
  still silently orphan message history after the rework, the rework has
  built a cleaner state machine on top of a broken addressing layer — worse,
  a schema migration (goal 4) run before identity is stabilized risks baking
  the *current* fragile addressing assumption into a versioned, "migrated"
  format, making a later identity fix harder, not easier.
- **#42 (message-store schema versioning) must land first** because every
  target-model sketch above (a `state` field replacing the two computed
  functions, new semantic-state values, `completed` as a new value, any
  storage-mechanism change) *is itself* a schema change to the `Message`
  dataclass. Without a schema version field and a migration mechanism
  already in place and tested, goal 4 (lossless migration) has no
  infrastructure to run on top of — #43 would have to build ad hoc,
  one-off migration code for its own change, which is precisely the
  "manual, unscripted, no-error-protection... surgery" issue #42 exists to
  replace. Building #43's migration before #42 means throwing away #42's
  work, or duplicating it under time pressure inside a bigger issue.

Recommended order: **#40 → #42 → (design firms up here, this spec gets
revisited) → #43 sub-issues, smallest/lowest-risk first.**

## What decomposes into sub-issues

Issue #43 is explicitly a tracking issue, not a buildable unit — its own
body says sub-work will be split out. Candidate splits, once #40/#42 land
and the design actually firms up:

1. **Schema/state-field design** — collapse `Message.state` and
   `_message_path` into one derivation; decide the four-vs-five-state
   question from "Target model per goal 2" above. This is a pure design
   decision and should probably be its own spec before any code, since it's
   the one every other sub-issue depends on.
2. **Storage-mechanism decision** — directories-as-storage vs. a single
   store file vs. SQLite. Independent of (1) in principle but heavily
   informs migration cost (goal 4), so should be decided alongside it, not
   after.
3. **`completed` state + its relationship to `kind`/backflow/broadcast
   rollup** — this touches `broadcast_status` (`store.py:648-673`) and the
   Phase-3 `kind` values already anticipated in `models.py:49-52`; likely
   deserves its own issue since it's genuinely new behavior, not a rename of
   existing behavior.
4. **Layering/module split** (transport/relay/inbox) — a refactor issue,
   should follow (1)-(3) rather than lead them, since splitting modules
   around a state model that's about to change is wasted motion.
5. **Migration implementation** — depends on #42's versioning mechanism
   existing; see next section. Should be its own issue with its own
   acceptance criteria (no thread history dropped, verified against a real
   populated `~/.claude/relay/` directory, not a fixture).
6. **downbeat/TUI + skill-layer consumers updated to the new state names** —
   `tui/` widgets, `assets/hooks/relay-inbox.py`,
   `assets/hooks/relay-poll-offer.py`, `assets/commands/relay-monitor.md`,
   and any skill text that filters on `MessageState` values directly. This
   is mechanical once (1)-(3) are settled but easy to undercount — there are
   at least 8 consumer files identified during this spec's research (TUI
   widgets/screens, two hooks, one command, plus `core/watcher.py` and
   `core/state.py`), and each is a place old state semantics can leak
   through if not tracked explicitly.

## Migration strategy sketch

Not a plan — a sketch of the shape a plan would take, to be superseded by
#42's actual mechanism once it exists.

- **Baseline requirement**: every existing message file in
  `inbox/`, `delivered/`, `processed/`, `quarantine/` under a real
  `~/.claude/relay/` tree must end up addressable in the new model with its
  full history intact — this is issue #43's fourth goal verbatim, and
  matches the wiki note's own "no thread history dropped" framing.
  `Message.to_dict`/serialization already has a documented backward-compat
  property worth preserving as a design constraint: `models.py:1-3`'s module
  docstring states "backward-compatible JSON serialization (legacy messages
  missing the new fields still parse)" — any new field added by this rework
  should keep that property, not break it.
- **Depends on #42 for**: the version-tag-on-read/write mechanism. Without
  it, migration is a one-shot destructive rewrite with no rollback path and
  no way to distinguish "not yet migrated" from "migrated but old-shaped" if
  the migration is interrupted partway (a real risk — `store.py`'s existing
  "heals a hand-edited `sessions.json`" comments at `store.py:230-235` show
  the codebase already anticipates partially-corrupt on-disk state as a
  normal operating condition, not an edge case).
- **Verification approach** (per this org's own stated principle of
  verifying against the real artifact, not a stand-in): migration
  correctness should be checked by running it against a real, populated
  `~/.claude/relay/` directory (or a faithful copy of one) and diffing
  `list_thread`/`list_inbox` output before and after — not only against a
  synthetic fixture. The existing dual-implementation bug pattern (two
  functions independently agreeing today, silently able to drift) is exactly
  the kind of thing a fixture-only test suite would not catch, since a
  fixture is usually built to match what the code already does.
- **Rollback**: open question — is the old on-disk layout kept read-only
  as a fallback for some period, or is the migration considered one-way once
  run? Directories-as-storage's operational recoverability (grep-able,
  `git`-diffable, hand-editable) is a property worth deciding whether to
  keep even after a schema/storage change, precisely because it has already
  saved this codebase once (the "heals... instead of forwarding... damage"
  comments in `remove_peer`, `store.py:230-235`).

## Risks

- **Building goal 2/3 before #40/#42 land** bakes today's fragile
  addressing (string-frozen `from_peer`/`to_peer`) and unversioned schema
  into whatever new shape gets chosen, doubling migration work later.
- **Losing the write-then-unlink safety property** during a storage-mechanism
  change. `archive_messages`' documented ordering rationale
  (`store.py:431-435`) exists because of a specific `list_inbox` dedup
  interaction — any new storage mechanism needs an equivalent atomicity
  argument, not just "it's a database now so it's fine."
  Concurrent access from multiple sessions (a live design constraint of
  this whole project) makes this non-optional.
- **Under-scoping the consumer surface.** At least 8 files outside
  `core/store.py` read `Message.state` or directory membership directly
  (TUI widgets/screens, two hooks, one CLI command module, `watcher.py`,
  `state.py`). A migration that only touches `core/` and misses these will
  produce a codebase that "compiles" but silently disagrees with itself in
  the UI — the exact failure mode goal 1 exists to eliminate, reintroduced
  at a different layer.
- **Scope creep from the four-state model absorbing unrelated future work**
  (backflow/`kind`, workflow-request/result Phase-3 values already
  anticipated in `models.py:49-52`). These are real and related, but pulling
  them into #43 before the core state model is settled risks turning a
  "later, design-open" issue into an unbounded one.
- **Treating this spec's line-number citations as durable.** As with the
  house convention in the general-peer-tree spec, every `file:line`
  reference above should be re-verified at implementation time, not trusted
  as-is — `store.py` and `models.py` are both actively changing.

## Open decisions for the maintainer

1. **Is the four-state model (`inbox → relayed → processed → completed`)
   meant to *replace* `MessageState`, or sit alongside it as a second,
   independent axis?** This spec's reading is "replace, with `relayed`
   roughly absorbing today's `DELIVERED`+`READ`," but that's a judgment
   call, not a confirmed decision — `READ` genuinely straddles "relayed" and
   "processed" and could go either way.
2. **Does directory-as-storage survive this rework, or does the store move
   to a single file/SQLite?** This is probably the single highest-leverage
   decision in the whole rework — it changes the shape of goal 1, goal 3,
   and the entire migration strategy. Directories currently buy real,
   demonstrated recoverability (see the `remove_peer` healing comments);
   a database buys transactional consistency and removes the two-function
   duplication problem structurally. Worth deciding explicitly rather than
   defaulting to either.
3. **What exactly does `completed` mean, and does it belong on the message
   or on something above the message (a thread/task)?** Right now nothing
   in the codebase models a thread or task as a first-class object —
   `list_thread` reconstructs one on the fly by filtering two peers' history.
   If `completed` is a per-thread/task concept rather than a per-message
   one, goal 2 may need a data-model addition beyond just a new enum value.
4. **How much of goal 3's layering is a real module split vs. a
   documentation/boundary-discipline pass?** A full `transport.py`/
   `relay.py`/`inbox.py` split is a bigger, riskier change than clarifying
   boundaries within the existing `store.py`. Given #43 is explicitly
   "design not yet settled," it may be worth doing the smaller version first
   and revisiting the module split as a separate, later issue.
5. **Rollback/cutover strategy for goal 4** — one-way migration with a
   backup snapshot, or a dual-read period where both old and new formats are
   understood by the code simultaneously? The latter is safer but means
   carrying two implementations of state-derivation for a transition window,
   which cuts against goal 1's whole point.
6. **Sequencing confirmation** — this spec recommends #40 then #42 then
   #43's sub-issues. Is that maintainer-approved, or does the maintainer see
   a reason to interleave (e.g. start #42's versioning mechanism in parallel
   with #40 rather than strictly serially, since they touch different parts
   of `Message`)?
