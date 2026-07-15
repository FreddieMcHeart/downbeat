# General peer tree (decouple `role` from structure)

**Status:** approved, ready for implementation plan
**Branch:** `feat/general-peer-tree` (from `origin/main`, tip `3033b20` / v0.8.0)

## Context

downbeat's peer registry (`Peer` in `core/models.py`) today enforces a
strict two-tier parent/child structure: a peer with `role=="parent"` can
have any number of children but can never itself have a parent; a peer with
`role=="child"` has exactly one parent and can never itself have children.
The human wants to go from this to a general tree, confirmed via a diagram
(published as an artifact during design): a root with two children, one of
which (`Child-A`) is *itself* a parent for its own children — an interior
node, structurally both a child and a parent at once — with an explicit
requirement that depth is not capped now and may grow further later.

This spec is the result of a three-stage design process:
1. An Opus exploration (no code touched) surveyed the current codebase and
   proposed three options (A: decouple `role` from structure, keep the
   TUI's 2-level viewport; B: full recursive tree UI; C: hard depth cap),
   recommending A.
2. The human confirmed the topology matches Option A's data model exactly
   (via the diagram) and explicitly rejected a hard depth cap.
3. The parent session (`Claude-Cost-Optimazing`) reviewed the resulting
   design (relay thread `8644391e554b` → `27c1d6c7e7a9`) and corrected two
   things the first pass under-addressed: the depth-cap question resolves
   to **no cap** (bounded traversal is the real safety property, not a cap
   — see "Cycle prevention" below), and a new concept — **interior-node
   autonomy** — needs an explicit invariant, since `role`'s third meaning
   (the `/relay-monitor` autonomy default) is exactly where the old
   two-tier assumption was hiding.

## `role`'s three meanings today (why this needs to be explicit)

`role` currently does three independent jobs, conflated onto one field:

1. **Structural gate** (`core/store.py`) — `_resolve_parent` rejects any
   `--parent` target whose `role != "parent"`; `set_parent` requires the
   peer being repointed to have `role=="child"` and the target to have
   `role=="parent"`.
2. **TUI acting-as filter** — only `role=="parent"` peers are selectable as
   `acting_as` across ~5 files (`screens/chat.py`, `screens/peers.py`,
   `screens/main.py`, `widgets/peer_list.py`, `widgets/switch_acting_as.py`).
3. **`/relay-monitor` autonomy default** — `child` auto-executes arriving
   tasks; `parent` surfaces-and-asks (`assets/commands/relay-monitor.md`,
   `skill/SKILL.md`, and a Fable-model nudge in `assets/hooks/relay-inbox.py`).

This design removes meaning #1 entirely, repoints meaning #2 (see "TUI
changes" below), and — this is the part the parent's review added — makes
meaning #3 an **explicit, orthogonal-to-structure invariant** rather than
letting it silently keep deriving from tree position.

## Data model

`Peer` (`core/models.py`) is **unchanged** as a dataclass — no new fields,
no renamed fields. `role: str` keeps the literal `"parent"`/`"child"`
strings (renaming was considered and rejected: it would touch
`relay-monitor.md`, `SKILL.md`, `relay-inbox.py`, and every
`role=="parent"` TUI comparison for zero functional gain). `parent: str |
None` is the existing adjacency pointer, unchanged in shape.

Add a one-line comment directly on the `role` field in the `Peer`
dataclass stating its new, narrowed meaning:

```python
role: str   # "parent" | "child" — the /relay-monitor autonomy DEFAULT only
            # (auto-execute vs surface-and-ask). NOT structural position:
            # a peer can be role="child" and still have its own children:
            # gaining/losing children never changes this field. See
            # docs/superpowers/specs/2026-07-15-general-peer-tree-design.md.
```

This is the single most important documentation change in this spec — per
the parent's review, it's "the only place the two-tier assumption can
silently survive the refactor" if left unstated.

### Invariant: autonomy is orthogonal to structure

**A peer's `role` never changes as a side effect of gaining or losing
children.** When a peer acquires its first child (becomes an interior
node), its own autonomy behavior (how it handles its *own* inbox) stays
exactly what it was explicitly set to at registration. The human sets
`role` consciously per peer; nothing in `register_peer`/`set_parent`
touches an existing peer's `role`. This is stated explicitly here (not left
implicit) because a tree makes "child" peers that are also structural
parents commonplace — the old model never had to make this call, since a
node could never be both.

## Store changes (`core/store.py`)

- **`_resolve_parent`** (currently rejects `target.get("role") != "parent"`
  at what's line 75 as of this spec's writing): remove that rejection. Any
  existing, registered peer is a valid `--parent` target. Re-verify the
  exact current line number/text at implementation time — re-read the file
  fresh rather than trusting this spec's line numbers, matching this
  project's established convention for exact-match old_string/new_string
  edits.
- **`register_peer`**: currently resolves a parent `if role == "child"`
  only (line 107 as of writing) — a `role=="parent"` peer's `parent` is
  force-set to `None`. Change to resolve a parent whenever one is given or
  inferable, regardless of `role`.
- **`set_parent`**: currently requires the peer being repointed to have
  `role=="child"` (line ~128) and the target to have `role=="parent"` (line
  ~131). Remove both checks.
- **New: cycle prevention.** A single helper, called from both
  `_resolve_parent` and `set_parent` (so neither write path can bypass it):
  before accepting `parent=P` for peer `N`, walk upward from `P` following
  `.parent` pointers in the loaded `sessions` dict, accumulating a
  **visited set** (not a bare counter — the set is what lets the error
  message list the actual offending chain, and is also the natural
  building block for "bounded traversal" as a general property, not just
  this one check). If the walk reaches `N`, reject. Self-parent
  (`parent == name`) is the degenerate 1-cycle — reject explicitly with its
  own clear message rather than letting it fall through the general walk.
  Bound the walk by `len(sessions)` iterations so a pre-existing corrupt
  cycle already on disk (e.g. from hand-edited `sessions.json`) can't hang
  it — this is defense against corrupt *existing* data, not a design
  constraint on new writes.
- **New error**: `CycleDetected(InvalidParent)` in `core/errors.py`, e.g.
  `"--parent 'A' would create a cycle: A → B → N → A"`. Because it
  subclasses the existing `InvalidParent`, the two current catch sites
  (`cli/commands/relay_cmds.py:cmd_register`,
  `tui/widgets/add_peer_modal.py:submit`) need **no new wiring** — they
  already print/surface `InvalidParent`'s message.

### Why no depth cap

The parent's review corrected the original draft here. A depth cap was
originally floated as a "cheap safety net" alongside the cycle check. It's
unnecessary and actively worse than the alternative:

- The cycle-prevention walk plus the single-parent-per-node invariant
  already make the peer graph a forest — a path from any node to the root
  cannot exceed the total peer count without revisiting a node, which the
  cycle check already forbids. Depth is therefore *already* bounded by
  `len(sessions)`, with no separate cap needed for correctness.
- A cap re-introduces exactly the restriction the human rejected, just at
  a higher, arbitrary number. A future legitimately-deep tree would
  silently trip it, and someone would have to go find and raise the
  constant.
- The actual safety property a cap would be trying to buy — protecting
  code that walks the tree from blowing up on corrupt/adversarial data —
  is bought correctly by making **every** `.parent`-pointer traversal
  bounded (visited-set, iterative, not naive unbounded recursion), not by
  capping depth at write time. A write-time cap doesn't protect a
  hypothetical future read-time traversal against data that's already on
  disk (e.g. hand-edited). Bounded traversal is the standing invariant this
  spec adopts for the cycle-check now, and must be adopted by any future
  traversal added to this codebase (e.g. a hypothetical future recursive
  `descendants_of()` — not built in this pass, since nothing in scope needs
  it, but if it's ever added, it must reuse the same bounded-walk
  discipline).

## TUI changes

Every place that currently filters "is this peer eligible to be
`acting_as`" on `role=="parent"` alone must become a **union**: `role ==
"parent" OR has_children(peer)`, where `has_children` is computed as `{p.parent
for p in store.list_peers()} - {None}` (i.e. "does at least one other peer
point at this one"). This is a union, not a replacement, because a pure
`has_children`-only filter breaks two real cases the parent's review
caught:

1. A freshly-registered peer with `role=="parent"` but zero children yet
   would be unselectable as `acting_as` — you couldn't act-as it to add its
   *first* child, breaking top-down tree setup.
2. An existing `role=="parent"` peer with zero children (a real, valid
   state today — plenty of parents may have no children registered yet)
   would silently disappear from the acting-as list on upgrade to this
   model. This means the earlier "migration: none needed" framing was
   correct for *data loading* but incomplete for *acting-as selectability*
   — this spec corrects that: selectability changes for zero-child
   `role=="parent"` peers unless the filter is the union, not the
   replacement.

Files needing this change (re-verify exact current line numbers at
implementation time, same as always):
- `tui/screens/chat.py` — `_populate_acting_as`, and the acting-as-target
  check inside `find_message`.
- `tui/widgets/peer_list.py` — the acting-as candidate list and its
  dropdown.
- `tui/widgets/switch_acting_as.py` — its parent-only candidate list.
- `tui/screens/peers.py` — `group_key`/`sort_key` currently key off
  `role=="parent"` for grouping/sorting; at implementation time, read the
  current code fresh to determine whether the same union applies directly,
  or whether this screen's grouping is already scoped inside one
  `acting_as`'s world (in which case a different, scoped adjustment may be
  correct instead of a blind copy of the union filter — do not assume,
  verify against the actual current implementation).
- `tui/screens/main.py` — has a `role=="parent"` check inside
  `find_message`, but this screen is the legacy three-pane view already
  marked `@pytest.mark.skip(reason="three-pane view replaced by chat
  view")` in `tests/test_tui_smoke.py`. At implementation time, confirm
  whether this screen is still reachable from any live code path. If it's
  dead (never pushed anywhere reachable), delete it rather than leave it
  holding stale two-tier logic next to the corrected version — silently
  inconsistent dead code is worse than no code. If it's still reachable
  for some reason, apply the same union fix.

## Error handling

`CycleDetected` requires no new catch sites (see "Store changes" above) —
it's caught wherever `InvalidParent` already is. No other new failure
surface is introduced; `_resolve_parent`/`set_parent`/`register_peer` keep
their existing behavior for every non-cycle case.

## Testing

- **Cycle detection** (`core/store.py`): direct 2-node cycle (A→B, then
  B→A rejected), self-parent (A→A rejected, explicit distinct message),
  multi-hop cycle (A→B→C, then C→A rejected, chain listed in the error), a
  *valid* deep non-cyclic chain (e.g. 5+ levels) is accepted without
  tripping any cap.
- **Structural gate removal**: `_resolve_parent`/`set_parent` no longer
  reject a `role=="child"` peer as a valid `--parent` target;
  `register_peer` resolves a parent regardless of the registering peer's
  `role`.
- **Autonomy orthogonality**: register a peer with `role=="child"`, give it
  a child via `set_parent`, assert its own `role` is still `"child"`
  afterward (not auto-flipped to `"parent"`).
- **TUI acting-as union filter**, all four combinations: pure leaf
  (`role=="child"`, no children) → excluded; `role=="parent"` with zero
  children → included (via `role`, not `has_children`); interior node with
  `role=="child"` and one or more children → included (via `has_children`,
  not `role`); interior node with `role=="parent"` and children → included
  (either condition alone would include it — confirm no double-counting in
  whatever data structure the filter builds, e.g. a set/dict keyed by
  name, not a list that could append the same peer twice).

## Migration

**Data**: none needed — `Peer.from_dict` already tolerates missing fields
via `.get()` defaults, so every existing `sessions.json` entry loads as a
valid degenerate case of the new model (old `role=="parent"` peers keep
`parent=None`; old `role=="child"` peers keep their single parent).

**Behavior**: the one real change is TUI acting-as selectability for
zero-child `role=="parent"` peers, corrected by using the union filter (not
`has_children` alone) — see "TUI changes" above. With the union filter in
place, there is no selectability regression either.

## Known limitations / deferred (not built in this pass)

- **No recursive tree UI** (Option B, explicitly deferred). The TUI stays
  a 2-level viewport; a user navigates deeper by re-rooting `acting_as`.
  Revisit only if a concrete depth-3+ *simultaneous-view* workflow is
  named — none exists today in the product's own docs (`SKILL.md`'s model
  is a two-role handoff).
- **No `descendants_of()` / recursive tree-walk helper** is added — nothing
  in this pass's scope needs one. If a future task adds one, it must reuse
  the bounded-visited-set-walk discipline established here for the
  cycle-check, not a naive unbounded recursion.
- **`screens/peers.py`'s exact grouping/sorting fix** is intentionally left
  as "verify against current code at implementation time" rather than
  specified in detail here, since its current scoping (system-wide vs.
  scoped-to-one-`acting_as`) needs to be re-confirmed by reading the live
  file, not assumed from this spec's earlier exploration pass.
