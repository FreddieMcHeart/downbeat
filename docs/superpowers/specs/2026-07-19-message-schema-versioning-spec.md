# Message-store schema versioning

**Status:** design — recommendation, pending maintainer decision
**Issue:** [#42 Message-store schema versioning](https://github.com/FreddieMcHeart/downbeat/issues/42)
**Branch:** none yet — this is analysis, not an approved plan (see "Stance" below)
**Tip at time of writing:** `c459e49` (`main`, v0.10.4)

## Stance

This document analyzes the problem and recommends one option. It does not
commit downbeat to a design the way the peer-tree spec
(`2026-07-15-general-peer-tree-design.md`) does — that one carries **Status:
approved, ready for implementation plan**; this one does not, on purpose. Open
questions are called out explicitly in "Open decisions for the maintainer" at
the end, and none of the code changes described here should be implemented
until those are resolved.

## Context

Message JSON files carry no schema version field today. Every message on disk
is just whatever shape `Message.to_dict()` happened to produce at write time,
and there is nothing in the file itself that says which shape that was. Issue
#42 names the consequence directly: "the manual rename surgery in the
peer-identity issue is a symptom of this" — issue #40 documents a real
instance of exactly that problem, where a peer rename requires "manually
rewriting `from`/`to` across ~100 files in
`inbox/delivered/processed/quarantine/*/*.json`" by hand, because there is no
mechanism to apply a structural transform to existing files as part of a
schema change.

### The existing tolerance (the seam this design exploits)

`Message.from_dict` (`src/downbeat/core/models.py:91-112`) already tolerates
files missing fields that were added after those files were written:

```python
@classmethod
def from_dict(cls, d: dict) -> Message:
    return cls(
        id=d["id"],
        from_peer=d["from"],
        to_peer=d["to"],
        subject=d.get("subject", ""),
        body=d.get("body", ""),
        created_at=d.get("created_at") or d.get("ts") or "",
        read_at=d.get("read_at"),
        edited_at=d.get("edited_at"),
        broadcast_id=d.get("broadcast_id"),
        archived=d.get("archived", False),
        delivered_at=d.get("delivered_at"),
        delivered_to_session_id=d.get("delivered_to_session_id"),
        redelivery_count=d.get("redelivery_count", 0),
        delivery_ack_at=d.get("delivery_ack_at"),
        in_reply_to=d.get("in_reply_to"),
        quarantined_at=d.get("quarantined_at"),
        quarantine_reason=d.get("quarantine_reason"),
        kind=d.get("kind", "task"),
    )
```

Only `id`, `from`, and `to` are hard-required (`d["id"]`, `d["from"]`,
`d["to"]` — a `KeyError` on any of those is caught by `_read_message_at` and
re-raised as `StoreCorrupt`, see below). Every field added since the original
shape — the whole "Phase 0 schema additions" and "Phase 2 schema additions"
blocks in the `Message` dataclass (`models.py:41-52`) — uses `.get()` with a
default. This is *already* a de facto additive-field migration mechanism; it
has silently carried the store through at least two rounds of schema growth
(`created_at` even falls back to a legacy `ts` key at `d.get("created_at") or
d.get("ts") or ""`, which is a rename tolerated the same way). What it cannot
do is a **structural** change — renaming a key, changing a value's meaning
(e.g. re-keying `from`/`to` from a display name to a stable identity, per
issue #40), or dropping/splitting a field. Those need code that runs once per
file, on a known "this file predates version N" condition — and today there
is no such condition to test, because there is no version.

### The choke points

Every message read and write in the store funnels through two single
functions:

```python
def _write_message(msg: Message) -> None:
    path = _message_path(msg)
    _atomic_write_text(path, msg.to_json())


def _read_message_at(path: Path) -> Message:
    try:
        return Message.from_json(path.read_text())
    except (json.JSONDecodeError, KeyError) as e:
        raise StoreCorrupt(f"{path} is not a valid message: {e}") from e
```

(`src/downbeat/core/store.py:314-323`) Every store function that touches a
message file goes through one or the other: `get_message`, `deliver_messages`,
`list_inbox`, `list_thread`, `ack_messages`, `archive_messages`, `mark_read`,
`edit_message`, `reply_to`, `reconcile`, `list_quarantined`,
`requeue_quarantined`, `_scan_all_messages` (feeding `broadcast_status`), and
`find_message_by_id_prefix` all call `_read_message_at` (directly or via
`get_message`); every path that persists a message (`send_message`,
`deliver_messages`, `ack_messages`, `archive_messages`, `mark_read`,
`edit_message`, `reply_to`, `reconcile`, `requeue_quarantined`) calls
`_write_message` or the equivalent `_atomic_write_text(path, msg.to_json())`
inline. `list_inbox` (`store.py:523-545`) and `list_thread`
(`store.py:829-841`) are two of the highest-traffic read paths — `list_thread`
in particular is what issue #40 identifies as the code that breaks on stale
identity — and both are just callers of `_read_message_at` via a `glob()`
loop; neither has any per-file version awareness today. This concentration is
the whole reason a versioning scheme is tractable here: there are exactly two
places to hook a migration, not one per call site.

## Options

### Option A (recommended) — in-file `schema_version` int + upgrade-on-read migration ladder

Add an integer field to the message JSON, `"schema_version": N`, defaulted to
the current version on write. On read, `_read_message_at` checks the stored
version against `CURRENT_SCHEMA_VERSION`; if it's older, it runs the file's
dict through an ordered chain of small migration functions
(`_migrate_v0_to_v1`, `_migrate_v1_to_v2`, …) before constructing the
`Message`. Each migration function takes and returns a plain `dict`, so it can
apply structural changes (`.pop()`, `.get()` with a rename, restructuring
nested values) that `from_dict`'s field-level `.get()` defaults cannot express.
On the next write of that message (any of the mutating store calls above), the
now-current-version dict gets persisted, so the file self-heals in place —
"upgrade on read, stamp on write," matching the acceptance criteria in #42
verbatim ("A documented, tested migration mechanism upgrades older files on
read/write").

This is the natural extension of the tolerance `from_dict` already has: rather
than every field individually guessing its own default forever, the version
number tells you *exactly* which migrations to run, and the migration ladder
is where structural (not just additive) transforms live. It directly enables
issue #40's stable-identity fix: option (a) in #40 ("give each peer a
`session_id`/UUID that never changes... Messages reference the stable key")
is exactly a structural transform of `from`/`to` — re-keying from a
mutable display name to a stable identifier — that a bare `.get()` default
cannot express, but a `_migrate_vN_to_vN+1(d: dict) -> dict` function can,
because it runs once, deterministically, keyed off the file's own recorded
version, with full access to whatever mapping table the identity migration
needs.

**Where the registry lives:** a small ordered list/dict in `core/models.py`,
next to `Message` (the migrations operate on `Message`'s wire format, so they
belong beside the dataclass that owns it, not in `store.py` which only calls
`from_dict`/`to_dict`) — e.g.:

```python
CURRENT_SCHEMA_VERSION = 1

_MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    0: _migrate_v0_to_v1,
    # 1: _migrate_v1_to_v2,   # add here when v2 ships
}
```

`Message.from_dict` applies the ladder before constructing the dataclass:
read `d.get("schema_version", 0)`, then `while v < CURRENT_SCHEMA_VERSION:
d = _MIGRATIONS[v](d); v += 1`. `Message.to_dict` always stamps
`"schema_version": CURRENT_SCHEMA_VERSION`. This keeps `_read_message_at` and
`_write_message` in `store.py` completely unchanged — they already just call
`Message.from_json`/`msg.to_json()`, so the migration ladder is invisible to
the two choke points identified above; it lives entirely inside the model
layer, which is the right layer since it's a wire-format concern.

**Testing:** each migration function gets a direct unit test — construct a
"v0-shaped" dict by hand (the current shape minus `schema_version`, per the
bootstrap rule below), run it through `_migrate_v0_to_v1`, assert the result.
Plus two integration-level tests against the real choke points (see
"Testing" section below): a round-trip test and an old-file-upgrade test.

**How v0 (unversioned) bootstraps to v1:** every message file that exists on
disk today has no `schema_version` key at all. That absence *is* the v0
marker — `d.get("schema_version", 0)` reads exactly the files this codebase
has been writing all along as version 0, with no separate backfill pass
needed. `_migrate_v0_to_v1` for the first ship of this feature is therefore
close to a no-op in content (there's no structural change bundled with the
versioning feature itself) — its job is just to prove the ladder mechanism
works end-to-end on a real pre-existing file shape, so the harder structural
migrations (e.g. issue #40's identity rekey, whenever it ships) land on
already-proven infrastructure rather than untested infrastructure and a
data-model change at the same time.

### Option B — alternatives considered and rejected

- **Versioned directories or filenames** (e.g. `inbox/v1/<peer>/<id>.json`, or
  `<id>.v1.json`). Rejected: every one of the ~15 call sites listed under "The
  choke points" above constructs paths via `_message_path`/`_find_message_in`/
  glob patterns over `inbox/ delivered/ processed/ quarantine/`; a version
  segment in the path multiplies every one of those glob patterns and
  `_find_message_in`'s directory walk by the number of live versions, and
  requires *every* call site to know about version directories forever, not
  just the two functions that already gate every read/write. It also doesn't
  actually solve the problem: a v1 *directory* still doesn't tell you how to
  transform a v1 file into a v2 shape — you'd still need an in-file version
  or a parallel migration ladder, so this option pays the path-fragmentation
  cost for no corresponding win over Option A.
- **No in-file version, detect shape by field presence** (i.e. keep doing what
  `from_dict`'s `.get()` defaults already do, forever). Rejected: this is
  exactly the status quo issue #42 is filed against. It works for adding
  optional fields but cannot express a structural change like a rename or a
  value re-keying (the `from`/`to` display-name → stable-id transform issue
  #40 needs) without ambiguity — `.get("old_key") or .get("new_key")`-style
  guessing breaks down as soon as two schema generations could plausibly both
  have populated the same key with different meanings, and there's no way to
  stamp the file as "already migrated" so the guess-and-fallback code can ever
  be retired.
- **A one-shot batch migration script (`downbeat migrate`) instead of
  upgrade-on-read.** Rejected as the *sole* mechanism (a `--migrate` CLI
  entry point is fine as a convenience layered on top of upgrade-on-read, not
  a replacement for it): message files live across four directories
  (`inbox/ delivered/ processed/ quarantine/`) and the store's own docstring
  states "Read operations tolerate missing files and return empty
  containers" as a design principle (`store.py:3-4`) — a batch script the
  human must remember to run reintroduces exactly the kind of manual,
  easy-to-forget operational step issue #42 is trying to eliminate, and
  quarantined/archived files that a user never actively touches again would
  simply never get migrated. Upgrade-on-read guarantees every file gets
  current the moment anything reads it, with no separate step to forget.

## Recommendation

**Option A** — in-file `schema_version: int`, migration ladder registered in
`core/models.py`, applied inside `Message.from_dict` (equivalently reachable
from `_read_message_at`, since that's the only place `from_json` is called on
disk-sourced text), stamped to `CURRENT_SCHEMA_VERSION` on every `to_dict`.
Rationale: it's the direct generalization of the tolerance mechanism the
codebase already trusts (`from_dict`'s `.get()` defaults), it requires zero
changes to `store.py`'s two choke points or any of their ~15 callers, it
gives a real backfill-free bootstrap from every existing unversioned file
(v0 by absence), and it is the concrete prerequisite issue #40's stable-identity
fix needs — without a version field and a ladder, that fix has no clean way to
express "rewrite `from`/`to` for files written before the rekey" other than
the ad hoc file surgery #42 was filed to stop.

## Data-model / store changes

**`core/models.py`:**
- Add `CURRENT_SCHEMA_VERSION = 1` module constant.
- Add `schema_version: int = CURRENT_SCHEMA_VERSION` field to the `Message`
  dataclass (placed after the existing "Phase 2 schema additions" block,
  labeled as its own "Phase 3" comment block matching the existing
  `# --- Phase 0 schema additions ---` / `# --- Phase 2 schema additions
  ---` convention already in the file).
- `to_dict`: add `"schema_version": self.schema_version` to the emitted dict.
- `from_dict`: before constructing the `Message`, read
  `stored_version = d.get("schema_version", 0)`, run the migration ladder
  (`while stored_version < CURRENT_SCHEMA_VERSION: d =
  _MIGRATIONS[stored_version](d); stored_version += 1`), then build the
  dataclass from the migrated `d` exactly as today. Because the ladder
  mutates the dict before any `d.get(...)` field extraction runs, no
  individual field-extraction line needs to change — the migration functions
  are the only place that needs to know about the old shape.
- Add `_migrate_v0_to_v1(d: dict) -> dict` (v0 = "no `schema_version` key
  present" = every file on disk today). Its actual body depends on whether
  v1 bundles any structural change at ship time — if not, it can be exactly
  `return d` (all current fields already have `.get()` defaults, so nothing
  needs rewriting); if a structural change is intentionally bundled with this
  feature, it goes here.
- Add the `_MIGRATIONS` registry dict as shown in Option A above.

**`core/store.py`:** no changes required to `_read_message_at`,
`_write_message`, `list_inbox`, or `list_thread` — they call
`Message.from_json`/`.to_json()`/`.to_dict()`, which is where the migration
now lives. This is the point of putting the ladder in the model layer rather
than the store layer.

**`core/errors.py`:** no new error type is strictly required — a migration
function raising lets the existing `except (json.JSONDecodeError, KeyError)`
in `_read_message_at` either catch it (if it raises `KeyError`) or propagate
uncaught (anything else). Recommend migrations raise `KeyError` on
unrecoverable shape mismatches so they fold into the existing
`StoreCorrupt` path with no new catch site — consistent with how
`CycleDetected` was deliberately made a subclass of `InvalidParent` in the
peer-tree spec specifically to avoid new wiring at call sites.

## Testing

Following the pattern in `tests/test_models.py` (direct dataclass
round-trips) and `tests/test_store_messages.py` (choke-point-level tests):

- **Migration-ladder unit tests** (`tests/test_models.py`): construct a
  hand-built v0 dict (current shape, no `schema_version` key — i.e. exactly
  what `Message(...).to_dict()` produces today, minus the new field), call
  `Message.from_dict`, assert `.schema_version == CURRENT_SCHEMA_VERSION` and
  every other field matches expectations. One test per migration function as
  the ladder grows.
- **Round-trip test**: `Message(...).to_dict()` → `Message.from_dict(d)` →
  assert equality with the original (extending the dataclass `frozen=True`
  equality downbeat already relies on) — proves stamping-on-write and
  reading-back-current-version is lossless, the base case the ladder must
  never break.
- **Old-file-upgrade test** (the one #42's acceptance criteria call for
  explicitly — "A documented, tested migration mechanism upgrades older files
  on read/write"): write a **real v0 JSON file** to a temp `inbox/<peer>/`
  directory (no `schema_version` key, matching what today's `send_message`
  actually produces on `main` before this change), call `_read_message_at`
  on it directly — the real choke point, not a mock — and assert (a) it
  parses without raising `StoreCorrupt`, (b) the returned `Message` has
  `schema_version == CURRENT_SCHEMA_VERSION`, (c) all pre-existing fields
  survived unchanged. Then feed that message through `_write_message` and
  re-read the file from disk with a raw `json.loads` (not through the model)
  to assert the persisted JSON now carries `"schema_version":
  CURRENT_SCHEMA_VERSION` — proving the self-heal-on-write half of the
  mechanism, not just the tolerant-read half. This mirrors the project's
  "verify against the real artifact" convention: read the real file the real
  choke point reads, not a constructed `Message` object that never touches
  `from_json`.
- **Regression coverage for existing corrupt-file handling**: confirm a
  genuinely malformed file (missing `id`/`from`/`to`, or invalid JSON) still
  raises `StoreCorrupt` after this change — the migration ladder must not
  swallow or mask the existing corruption detection in `_read_message_at`.

## Migration

**Existing data**: no batch/backfill step needed. Every message file on disk
today (across `inbox/ delivered/ processed/ quarantine/`) is a valid v0 input
by construction — it has no `schema_version` key, which is precisely the v0
condition `d.get("schema_version", 0)` detects. The first read of each file
through `_read_message_at` (via any of the ~15 existing call sites) upgrades
it in memory; the next write of that same message (`mark_read`, `deliver_messages`,
`ack_messages`, etc.) persists the upgraded shape. Messages that are never
read or written again (e.g. old `processed/` archives nobody revisits) simply
stay v0 on disk indefinitely, which is safe — they still parse correctly
via the ladder every time something *does* read them (e.g. `broadcast_status`'s
`_scan_all_messages`, or a future audit tool) — but is worth naming
explicitly as a known, accepted gap rather than assuming full backfill; see
"Open decisions" below for whether an explicit `downbeat migrate` convenience
command is wanted on top of this.

**Behavior**: none of the current store functions' return shapes or call
signatures change. `schema_version` is not exposed anywhere the TUI or CLI
currently render message fields, so no UI change is implied by this spec.

## Relationship to issue #40 (peer identity)

This spec is explicitly a **prerequisite/enabler**, not a fix, for issue #40.
#40's option (a) — a stable identity key separate from display name, with
messages referencing the stable key instead of a mutable name — requires
rewriting `from`/`to` in every historical message file the moment the rekey
ships. Today that rewrite has no home: `from_dict`'s additive `.get()`
tolerance cannot express "if this file predates the identity rekey, replace
`from`/`to` with the stable-id equivalent looked up from a rename-history
table," because there is no per-file signal for "predates." With the ladder
in place, that becomes `_migrate_v1_to_v2` (or whichever version number is
current when #40 lands): a normal addition to `_MIGRATIONS`, tested the same
way as every other rung, running through the same two choke points, with no
new call-site wiring. This spec does not attempt to design that migration's
content (the identity-key scheme itself is #40's open design question, e.g.
whether the stable key is a UUID or the existing `session_id`) — it only
establishes the ladder #40 will need to land its fix without hand-editing
~100 files again.

## Open decisions for the maintainer

1. **Does v1 bundle any structural change**, or does it ship as a pure
   plumbing release (`_migrate_v0_to_v1` is `return d`, just proving the
   mechanism)? Recommendation in this doc assumes plumbing-only, deferring
   #40's actual rekey to a later version bump — confirm that's the intended
   sequencing (versioning lands first, cleanly, as its own PR; identity rekey
   follows as a separate, later change).
2. **Is a `downbeat migrate` (or `downbeat store migrate`) CLI convenience
   command wanted**, to force-touch every file across all four directories
   and eagerly upgrade them, for operators who want a fully-current store on
   disk rather than relying on lazy upgrade-on-read/write? This spec treats
   it as optional and out of scope, since upgrade-on-read already satisfies
   #42's acceptance criteria without it, but it's a reasonable follow-up if
   the maintainer wants an explicit "flush" story (e.g. before a backup, or
   before deprecating a migration rung).
3. **How long do old migration rungs stay in the ladder?** Once v0 files are
   believed to be fully flushed out of production instances, `_migrate_v0_to_v1`
   could theoretically be dropped, raising `StoreCorrupt` on a stray v0 file
   instead of silently upgrading it forever. Not addressed here — flag for a
   future decision once there's real-world signal on how long v0 files
   linger (quarantine/processed files with no further activity could persist
   indefinitely, per "Migration" above).
4. **Error type for unrecoverable migrations**: this spec recommends reusing
   `StoreCorrupt` via `KeyError` rather than adding a new exception class.
   Confirm that's preferred over a dedicated `SchemaMigrationError`
   (which would need its own catch site(s), unlike the `CycleDetected`
   pattern this spec otherwise follows).
