# Stable peer identity, separate from display name

**Status:** decided (2026-07-21) — **Option B shipped**, Option A is the accepted
target architecture, deferred until #42 (message-store schema versioning) lands.
Maintainer chose "B now + schedule A later" per the fork in "Open decisions" below;
the rename operation is resumable (idempotent per-file), not fully transactional.
**Issue:** [#40 — Stable peer identity, separate from display name](https://github.com/FreddieMcHeart/downbeat/issues/40)
**Related:** [#42 — Message-store schema versioning](https://github.com/FreddieMcHeart/downbeat/issues/42) (dependency for a clean Option A migration, see below)

This spec presents two implementation options for #40, with honest trade-offs,
and a recommendation. It does **not** commit the codebase to either option —
see "Open decisions for the maintainer" at the bottom.

## Context

A peer's display `name` is the *only* identifier downbeat has ever used for a
peer, and it is baked into three places at once:

1. **The sessions registry key.** `sessions.json` is a `dict[name, Peer-dict]`
   — `register_peer` writes `sessions[name] = peer.to_dict()`
   (`src/downbeat/core/store.py:156`), and every other mutator (`set_parent`
   at `store.py:174`, `touch_peer` at `store.py:248`, `rebind_session` at
   `store.py:696-705`) reads/writes the same `sessions[name]` entry. There is
   no field in `Peer` that identifies "this same peer, even if renamed" —
   `name` *is* the primary key.

2. **Every message's `from`/`to`.** `Message.from_peer`/`Message.to_peer` are
   plain strings, and `send_message` stamps them directly from the caller's
   name argument (`store.py:337-347`). Once written, a message file never
   gets touched again to reflect a later rename — messages are otherwise
   append/transition-only (`_write_message`, `store.py:314-316`).

3. **The on-disk directory layout.** `_message_path` (`store.py:283-292`)
   computes `base / msg.to_peer / f"{msg.id}.json"` where `base` is one of
   `paths.INBOX_DIR`, `DELIVERED_DIR`, `PROCESSED_DIR`, `QUARANTINE_DIR`
   (`src/downbeat/core/paths.py:10-13`). So a peer's messages don't just
   *reference* its name, they live in a directory literally named after it —
   `inbox/<peer-name>/`, `delivered/<peer-name>/`, etc. `deliver_messages`
   (`store.py:358-361`), `list_inbox` (`store.py:533-534`),
   `list_quarantined` (`store.py:741`), and `requeue_quarantined`
   (`store.py:756-774`) all derive their working directory the same way:
   `<BASE_DIR> / peer_name`.

4. **Peer *groups*.** `groups.json` (`src/downbeat/core/groups.py`) stores
   `dict[group_name, list[member_peer_name]]` — `save_group` (`groups.py:24-27`)
   persists member names as plain strings too, a fourth surface that a rename
   must account for, distinct from the three the issue names explicitly.

The break, exactly as issue #40 describes it: `list_thread` reconstructs a
conversation by comparing each message's **stored, historical** sender name
against the counterpart's **current, live** name:

```python
# store.py:829-841
def list_thread(peer_a: str, peer_b: str,
                include_archived: bool = True) -> list[Message]:
    """Return all messages between peer_a and peer_b (either direction),
    sorted oldest to newest. Used by the chat view."""
    out: list[Message] = []
    seen: set[str] = set()
    for owner, sender in ((peer_a, peer_b), (peer_b, peer_a)):
        for m in list_inbox(owner, include_archived=include_archived):
            if m.from_peer == sender and m.id not in seen:
                out.append(m)
                seen.add(m.id)
    out.sort(key=lambda m: m.created_at)
    return out
```

`peer_a`/`peer_b` are whatever the TUI currently calls the two peers —
i.e. their *current* names. `m.from_peer` is whatever the sender was called
*at send time*. The moment a peer is renamed, every message it sent before
the rename has `from_peer == <old name>`, the `sender` argument passed into
`list_thread` is `<new name>`, the `==` comparison at `store.py:837` fails
silently, and that message drops out of the thread — no error, no
quarantine, just a hole in history. The same stale-name problem applies to
`_message_path` at read time: `deliver_messages`/`list_inbox`/etc. look in
`<BASE_DIR>/<current-name>/`, but any message filed under the old
directory name is invisible until moved.

Today's only recovery is exactly what the issue says: hand-editing every
`from`/`to` field and physically moving every message file across
`inbox/`, `delivered/`, `processed/`, `quarantine/` — on the order of ~100
files for an active peer — plus fixing up `groups.json` membership and the
`sessions.json` key by hand. There is no tooling for this today; `downbeat`
has no `rename` verb at all (confirmed: no `rename` in
`src/downbeat/cli/commands/relay_cmds.py` or `src/downbeat/cli/__main__.py`).

### Does `Peer.session_id` already solve this?

The issue asks this explicitly, and it's worth being precise about why the
answer is **no**. `Peer` already carries a `session_id: str`
(`src/downbeat/core/models.py:122`) that looks, at a glance, like exactly the
kind of rename-proof key #40 wants. It isn't, for a reason that's load-bearing
for the rest of this spec: `session_id` is the *volatile* field, and `name`
is the *stable* one, in the exact opposite direction from what #40 needs.

`rebind_session` (`store.py:676-712`) exists specifically to change a peer's
`session_id` while holding `name` fixed — that's its whole purpose: the same
logical peer restarts its Claude Code process (new PID, new Claude session
id) and reattaches under its *existing, unchanged* name:

```python
# store.py:696-706
entry = sessions[name]
old_sid = entry.get("session_id")
history = list(entry.get("session_id_history", []))
if old_sid and old_sid != new_session_id and old_sid not in history:
    history.append(old_sid)
entry["session_id"] = new_session_id
entry["session_id_history"] = history
entry["last_rebind_at"] = now_iso()
entry["last_seen"] = now_iso()
sessions[name] = entry
```

So today: `name` is expected to be constant across the peer's lifetime and
`session_id` is expected to churn (every rebind appends the old value to
`session_id_history` and moves on). Using `session_id` as the stable
message-addressing key would mean every rebind — a routine, frequent event,
not a rare one like a rename — silently breaks thread continuity in exactly
the way #40 is trying to fix, just on a shorter cycle. `session_id` answers
"which OS process is this peer running as right now," not "which enduring
peer is this." It does not suffice. A stable key needs a field that is
*never* reassigned by any existing store operation — neither `register_peer`
re-registration, nor `rebind_session`, nor (today) any rename — and no
existing `Peer` field has that property. `session_id_history` is close in
spirit (an append-only log) but logs the wrong thing for this purpose.

## Options

### Option A — dedicated stable identity key, name becomes a pure alias

Add a new immutable field to `Peer`, e.g. `peer_id: str` (a `uuid.uuid4().hex`
like `models.new_id()` already produces for messages/broadcasts,
`models.py:17-18`), generated once at first `register_peer` and never
reassigned by any later mutation (rename, rebind, or re-register). `name`
becomes a mutable display alias resolved to `peer_id` at every entry point.
Messages store `from_peer_id`/`to_peer_id` (or repurpose `from_peer`/`to_peer`
to hold the id and add separate display fields — see "Data-model sketch"
below for the concrete shape). Directory layout keys on `peer_id`, not name.

**What this actually touches**, concretely, beyond `models.py`/`store.py`:

- `sessions.json`: either re-key the top-level dict from `name` → `peer_id`
  (breaking every `sessions[name]` lookup in `store.py` — six call sites
  listed under Context above) or keep it name-keyed and add `peer_id` as a
  field inside each entry (smaller diff, but then "look up a peer by stable
  id" needs a linear scan or a second name→id index — `sessions.json` today
  has no secondary index of any kind).
- Every message file, past and present: `from`/`to` currently hold names
  (`Message.to_dict`, `models.py:69-70`); Option A means the *meaning* of
  those two fields changes for every message ever written, which is exactly
  the kind of on-disk format change issue #42 exists to make migratable
  cleanly (see "Dependency on #42" below) — without it, Option A has no
  principled way to tell an old-format message (fields are names) from a
  new-format one (fields are ids) except heuristics.
  file naming/moving: every message currently under
  `inbox/<name>/<id>.json` needs a directory move to `inbox/<peer_id>/<id>.json`.
- `groups.json` membership lists (`groups.py:24-27`) — currently names,
  would need the same id-vs-alias resolution.
- Every TUI file that reads `Message.from_peer`/`to_peer` and treats it as a
  human-readable label to render directly — `screens/chat.py`,
  `screens/quarantine.py`, `screens/message_detail.py`,
  `widgets/find_message.py`, `widgets/composer.py`, `widgets/chat_stream.py`,
  `widgets/inbox_list.py`, `widgets/message_view.py` (all confirmed via grep
  to reference `from_peer`/`to_peer`) would need a name-*lookup* step
  (`peer_id → current display name`) inserted before rendering, since the
  field itself would no longer be display-ready.
- CLI/TUI arguments that currently take a peer *name* (`--peer`, `--parent`,
  `set-parent <child_name> <parent_name>`, group membership) would need to
  keep accepting names for human ergonomics while resolving to `peer_id`
  internally — a name→id resolver becomes a new, permanent piece of surface
  area, and it has to handle "no peer with this name" and, once renames
  exist, "this name used to belong to a different peer_id" (name reuse after
  a rename) as explicit, tested cases.

**Trade-offs.** This is the architecturally correct answer — identity and
display name become genuinely orthogonal, which is exactly what #40 asks
for, and it's a strict category improvement (rebind already proved the
project believes "peer" should be independent of any one mutable
attribute — this generalizes that same idea to `name`). But it is a large,
invasive change: it touches the on-disk message schema (every message file,
past and present), the sessions.json key/index shape, `groups.json`, and
every TUI/CLI surface that currently treats `from_peer`/`to_peer`/`--peer`
as a human name. It is not safely executable without #42's schema
versioning (below) — doing it without a version marker means writing a
migration with no reliable way to detect "have I already migrated this
file," which is a well-known way to double-migrate or silently skip files
on a partial/interrupted run.

### Option B — atomic `downbeat peers rename` command

Keep `name` as the only identifier (no new field, no schema change). Add a
transactional CLI command that, given `old_name new_name`, rewrites every
on-disk reference to `old_name` to `new_name` as a single all-or-nothing
operation:

- every message file's `from`/`to` field, across all four state directories
  (`inbox/`, `delivered/`, `processed/`, `quarantine/`) — matching the same
  four bases `_find_message_path` already iterates
  (`store.py:305-311`);
- the physical directory rename: `<BASE>/<old_name>/` → `<BASE>/<new_name>/`,
  for each of the four bases (a plain `os.replace` per base is sufficient
  when both dirs are on the same filesystem — the store already commits to
  `os.replace`-based atomicity elsewhere, see `_atomic_write_text`,
  `store.py:29-38`);
- the `sessions.json` entry: pop `sessions[old_name]`, reinsert under
  `sessions[new_name]` with `name` updated inside the value too (the value's
  own `name` field and the dict key must never disagree — `_load_sessions`
  already treats the dict key as authoritative and backfills `name` from it
  for legacy entries, `store.py:56-58`);
- every peer's `parent` pointer that equals `old_name` — every other peer in
  `sessions.json` whose `parent == old_name` needs repointing to
  `new_name`, or its children silently detach (this is the same
  "dangling-pointer" failure mode `remove_peer`'s docstring already warns
  about at `store.py:213-224`, just triggered by rename instead of removal);
- `groups.json` membership lists containing `old_name` (`groups.py`).

**Making it atomic in practice**: since this is a filesystem tree, not a
database, "all-or-nothing" has to be built, not assumed. The established
pattern in this codebase is stage-then-commit via `os.replace`
(`_atomic_write_text`, `store.py:29-38`) — extend that shape: write every
modified message file to a temp path first, build the full list of
(source, dest) directory/file moves, and only start `os.replace`-ing once
every write has succeeded, in an order that never leaves both an
`old_name` and a `new_name` directory holding live (non-duplicate) message
state simultaneously. A crash mid-rename should be recoverable — at minimum
detectable — not silently half-migrated; see "Migration" below for the
concrete recovery shape.

**Trade-offs.** Smaller: no `Peer` field added, no message schema change, no
#42 dependency, no id-vs-name resolution layer to add across every TUI file.
It directly satisfies the acceptance criteria in #40 ("renaming a peer
preserves full thread history with no manual file surgery"). But identity
stays fundamentally string-based — a rename is still, structurally, "reissue
this peer's key, then chase down every place the old key was copied," which
is O(files touched) per rename and re-derives the same file/dir-touching
logic issue #40 is trying to retire, just wrapped in one command instead of
done by hand. It doesn't change the fact that `name` is simultaneously the
identity key *and* the thing users want to be free to change — it makes
that combination safe, not gone. Every future feature that wants "the same
logical peer across a rename" (audit log, cross-referencing, external
integration) still has to either re-run the migration idea or accept
string identity's limits. It also doesn't touch the `session_id`-vs-`name`
volatility mismatch described above; it only fixes the `name`-changes case, not any structural ambiguity about what "identity" means for a peer.

### Dependency on #42 (message-store schema versioning)

Issue #42 exists because "the manual rename surgery in the peer-identity
issue is a symptom of" the deeper problem: `Message` files carry no schema
version (`Message.to_dict`/`from_dict`, `models.py:66-116`, has no
`schema_version` field; tolerance today is purely `.get(key, default)`
duck-typing, not a versioned migration). That matters differently for each
option:

- **Option A** cannot be migrated cleanly without it. Reinterpreting
  `from`/`to` from "peer name" to "peer id" is a breaking change to what
  those fields *mean*, applied to every message file ever written. Without
  a version marker, a migration script has no reliable way to tell "this
  file already has id-valued `from`/`to`" from "this file still has
  name-valued `from`/`to`" — especially once a peer is renamed and its old
  name could coincidentally look like a valid id-shaped string, or vice
  versa. #42's "every message file records a schema version" acceptance
  criterion is close to a hard prerequisite for Option A being safe to ship
  as an automatic, non-interactive migration.
- **Option B** does not strictly need #42 — it doesn't change what the
  `from`/`to` fields *mean* (they're still names before and after,
  just a different name), so there's no ambiguity a schema version would
  resolve. It only needs its own rename operation to be atomic (see above),
  which is a narrower, self-contained guarantee.

This asymmetry — A structurally depends on #42, B does not — is itself a
data point for sequencing, independent of which option is otherwise
preferred (see Recommendation).

## Recommendation

Ship **Option B now**, and treat **Option A as the target architecture**,
sequenced after #42 lands.

Reasoning: #40's acceptance criteria ("renaming a peer preserves full thread
history with no manual file surgery," "no code path compares a stored
historical sender name against a live name") are both fully satisfiable by
Option B alone — it doesn't require the message schema to change shape, so
it doesn't require #42 first, and it's a self-contained, testable, atomic
operation with a blast radius the codebase already has patterns for
(`_atomic_write_text`'s stage-then-`os.replace` shape). Option A is the
architecturally cleaner end state — it's the only option that makes
"identity" and "display name" genuinely orthogonal rather than "renaming is
now a safe, expensive operation instead of an unsafe one" — but it is a
larger migration whose safe execution is gated on #42 landing first, and
building it before #42 means either blocking on that issue or accepting the
double-migration/partial-migration risk described above. Landing B first
also does not throw away work: `peers rename`'s file-touching logic
(enumerate every reference to a peer across 4 message-state dirs +
sessions.json + groups.json) is close to a superset of what Option A's
one-time migration script needs to do internally, just keyed on `peer_id`
generation additionally once that field exists.

## Data-model sketch

Only in scope if/when Option A is chosen; sketched here so the maintainer
can evaluate the shape of the larger change, not as something to build now.

```python
@dataclass
class Peer:
    peer_id: str        # NEW — uuid4().hex, assigned once at first
                         # register_peer, NEVER reassigned by rename,
                         # rebind, or re-register. The stable key.
    name: str            # display alias; mutable via `peers rename`.
    session_id: str       # unchanged meaning: current OS-process
                         # attachment, volatile across rebinds (see
                         # "Does Peer.session_id already solve this?").
    ...                  # remaining fields unchanged
```

```python
@dataclass(frozen=True)
class Message:
    ...
    from_peer: str        # becomes peer_id, not display name
    to_peer: str          # becomes peer_id, not display name
    schema_version: int = 2   # NEW, from #42 — required to distinguish
                               # id-valued fields (v2+) from name-valued
                               # legacy fields (v1, implicit/unversioned)
```

Rendering code (TUI) resolves `peer_id → current display name` via a single
shared lookup (e.g. `store.get_peer_name(peer_id)` backed by an
in-memory name→id / id→name index built once per `list_peers()` call,
analogous to how `acting_as_candidates()` already builds a derived set
over `list_peers()` at `store.py:189-198`) rather than each of the eight
TUI call sites rolling its own resolution.

## Store / CLI changes

**Option B, concretely** — new functions in `core/store.py`, following the
existing four-base-directory iteration pattern used by
`_find_message_path`/`_scan_all_messages` (`store.py:305-311`,
`store.py:631-645`):

```python
def rename_peer(old_name: str, new_name: str) -> Peer:
    """Atomically rename a peer: rewrites from/to on every message file
    across inbox/delivered/processed/quarantine, moves each of the four
    per-peer directories, repoints sessions.json (key + parent pointers),
    and updates groups.json membership. All-or-nothing: either every
    reference is updated or none are."""
```

- Validate first, before any write: `new_name` must not already be a
  registered peer (collision) and must be a non-empty, otherwise-valid name
  by whatever constraints `register_peer` already enforces on names today
  (currently none explicit beyond non-empty dict key — worth confirming/
  tightening as part of this work, since `sessions.json` is dict-keyed on
  name and a collision would silently overwrite).
- Reuse the existing atomic-write primitive (`_atomic_write_text`,
  `store.py:29-38`) per file, and stage full success before committing any
  directory move, per the "Making it atomic in practice" note under Option
  B above.
- New CLI subcommand modeled directly on the existing `peers set-parent`
  pattern (`src/downbeat/cli/__main__.py:93-103`,
  `relay_cmds.py:cmd_peers`, dispatched via `args.peers_action`):

  ```python
  sp_peers_rename = sp_peers_sub.add_parser(
      "rename",
      help="rename a peer, atomically migrating all message history and directories",
      parents=[debug_parent])
  sp_peers_rename.add_argument("old_name")
  sp_peers_rename.add_argument("new_name")
  ```

  `cmd_peers` gains an `elif args.peers_action == "rename":` branch calling
  `store.rename_peer(args.old_name, args.new_name)`, catching a new
  `PeerNotFound`/`PeerNameCollision`-style error the same way the existing
  `set-parent` branch catches `PeerNotFound, InvalidParent`
  (`relay_cmds.py:122-129`).
- New error class in `core/errors.py`, alongside the existing
  `PeerNotFound`/`InvalidParent` family: `PeerNameCollision(RelayError)` for
  "new_name already registered."

## Testing

Mirrors the structure of the existing peer/store test suite
(`tests/test_store_peers.py`, `tests/test_rebind.py`), plus a rename-specific
file:

- **Happy path**: register peer A, send several messages both directions
  with another peer B (mix of inbox/delivered/processed/quarantine states —
  reuse the quarantine/reconcile helpers already exercised in
  `tests/test_store_quarantine.py`), call `rename_peer("A", "A2")`, then
  assert `list_thread("A2", "B")` returns the full pre-rename history with
  no gaps — this is the direct regression test for the `list_thread` bug
  quoted under Context.
- **Directory migration**: assert no files remain under any of
  `inbox/A/`, `delivered/A/`, `processed/A/`, `quarantine/A/` after
  rename, and the same message IDs exist under `.../A2/`.
- **Parent-pointer repointing**: register a child peer C with
  `parent="A"`, rename A→A2, assert `get_peer("C").parent == "A2"` (the
  dangling-pointer case `remove_peer`'s docstring already flags for a
  different operation, `store.py:213-224` — same failure shape, different
  trigger).
- **Group membership**: create a group containing "A" via
  `groups.save_group`, rename A→A2, assert the group's member list contains
  "A2" not "A".
- **Collision rejection**: attempt `rename_peer("A", "B")` where B is
  already registered; assert it raises before touching any file (verify via
  mtimes/inode or a before/after file listing diff, not just the return
  value).
- **Atomicity under simulated failure**: inject a failure partway through
  the file-rewrite loop (e.g. monkeypatch one message write to raise) and
  assert the on-disk state is unchanged from before the call — either fully
  rolled back or, if full rollback isn't implemented, that the operation is
  safely re-runnable/resumable (see "Migration" below) and never leaves a
  state where the same message id exists validly under both the old and
  new peer directories.
- **CLI wiring**: a `test_cli.py`-style subprocess/argparse test that
  `downbeat peers rename old new` dispatches to `cmd_peers` and exits 0/1
  correctly, matching the existing coverage pattern for `set-parent`.

## Migration

**For Option B (recommended, do now)**: no migration of *existing* data is
needed — `rename_peer` is a new operation applied going forward; peers that
are never renamed are entirely unaffected, and nothing about existing
message files or `sessions.json` shape changes. The only new operational
concern is crash-safety of the rename operation itself: document (in the
command's own help text or a `docs/` note) what state a user finds their
relay dir in if `peers rename` is interrupted mid-run (e.g. process killed),
and what recovery command to run — at minimum, `rename_peer` should be
safely re-runnable with the same `(old_name, new_name)` pair if the first
attempt didn't finish (idempotent per-file: skip a file already correctly
written under the new name/location rather than erroring).

**For Option A (deferred, gated on #42)**: this is where real data migration
lives — every existing message file's `from`/`to` needs reinterpreting from
name to id, every `sessions.json` entry needs a `peer_id` backfilled, and
`groups.json` needs no change in shape (member lists can stay name-based if
groups are treated as a display-layer concept, or migrate to id-based for
consistency — an open question in its own right, not resolved by this
spec). This migration is exactly the shape #42 is meant to make safe: read
old-format (unversioned) messages, write them back at the new
`schema_version` with `from`/`to` reinterpreted, in a way that's detectable
and resumable. Not designed in detail here — it is explicitly out of scope
until #42 lands and the maintainer decides to proceed with Option A.

## Open decisions for the maintainer

1. **A vs. B vs. both-sequenced.** This spec recommends B now / A later,
   gated on #42. The maintainer may instead prefer A directly (accepting
   the #42 dependency up front and delaying #40's fix until both land), or
   B only (accepting that identity stays string-based indefinitely and
   declining to schedule A at all).
2. **If B ships**: should `rename_peer` support true rollback on partial
   failure, or is "safely re-runnable/resumable" (finish the job on a second
   invocation) an acceptable substitute? True rollback is more work; the
   codebase's existing atomicity primitive (`_atomic_write_text`) is
   per-file, not multi-file-transactional, so true rollback across the full
   file set is new machinery, not a reuse of an existing pattern.
3. **If B ships**: what, if anything, constrains a valid peer name beyond
   "non-empty and not already registered"? `sessions.json` being dict-keyed
   on name means any accepted string becomes a directory name too
   (`inbox/<name>/`) — worth deciding whether to validate against filesystem-
   unsafe characters at rename time (and, ideally, at `register_peer` time
   too, as a related but separate hardening).
4. **If A is scheduled**: does `groups.json` migrate to id-based membership
   in the same pass, or stay name-based as a deliberately separate,
   display-layer concept? Sketched as an open question above, not decided
   by this spec.
5. **Timing relative to #42**: should #42's schema-version field be added
   opportunistically now (a small, low-risk addition to `Message`) even
   before Option A is scheduled, purely so any *future* on-disk format
   change — not just this one — doesn't face the same "no version marker"
   problem? This spec's position is that #42 is a prerequisite for Option A
   specifically, but the maintainer may see independent value in landing it
   sooner regardless of A/B sequencing.
