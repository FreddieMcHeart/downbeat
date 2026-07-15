# General peer tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple `Peer.role` from tree structure so any registered peer can be both a child and a parent (a general tree instead of a strict two-tier hierarchy), with cycle prevention and no artificial depth cap.

**Architecture:** Remove the `role`-based structural gate from three `core/store.py` functions, add a bounded cycle-check shared by both write paths, add one new `store.acting_as_candidates()` helper consumed by every TUI acting-as picker, and delete two files (`tui/screens/main.py`, `tui/widgets/peer_list.py`) that were already dead code, confirmed unreferenced outside each other during planning.

**Tech Stack:** Python 3.11+, `core/store.py`'s existing patterns (no new dependencies), Textual (existing TUI framework), pytest + pytest-asyncio (existing test stack).

**Spec:** `docs/superpowers/specs/2026-07-15-general-peer-tree-design.md` — read it first if anything below is ambiguous; this plan implements it task-by-task.

## Global Constraints

- **No depth cap.** Cycle-prevention (a bounded, visited-chain walk) plus the single-parent-per-node invariant already make the peer graph a forest — a path can't exceed the total peer count without revisiting a node, which the cycle check forbids. Do not add a maximum-depth check anywhere in this plan.
- **`role` keeps its literal `"parent"`/`"child"` strings** — do not rename the field or its values anywhere. Only its *meaning* narrows (autonomy default only, not structural position).
- **Autonomy is orthogonal to structure.** No code in this plan may change an existing peer's `role` as a side effect of it gaining or losing children. `register_peer`/`set_parent` only ever touch the `parent` field, never `role`, for an *existing* peer.
- **The acting-as eligibility filter is a union, not a replacement:** `role == "parent" OR has_children(peer)`. Never simplify this to `has_children` alone — that breaks top-down tree setup (a childless fresh parent must stay selectable) and silently changes selectability for existing zero-child `role=="parent"` peers.
- **Cycle detection must produce the offending chain in its error message**, not just reject silently — build it from the same walk that detects the cycle, don't do a second pass.
- Branch: `feat/general-peer-tree` (already created from `origin/main` at tip `3033b20` / v0.8.0 — confirm you're on it before Task 1; `git status --short` should be clean, `git log --oneline -1` should show the spec-doc commit `8dd765c` as the tip).

---

### Task 1: `core/store.py` — remove structural gate, add cycle prevention, add `acting_as_candidates()`

**Files:**
- Modify: `src/downbeat/core/errors.py`
- Modify: `src/downbeat/core/models.py`
- Modify: `src/downbeat/core/store.py`
- Modify: `src/downbeat/cli/__main__.py`
- Test: `tests/test_store_peers.py` (extend, and repurpose 3 existing tests)

**Interfaces:**
- Produces: `CycleDetected(InvalidParent)` (new, in `core/errors.py`); `store.acting_as_candidates() -> list[Peer]` (new). Consumed by Task 2 and Task 3.
- `store._resolve_parent`, `store.register_peer`, `store.set_parent` keep their existing public signatures — only their internal validation logic changes.

- [ ] **Step 1: Add `CycleDetected` to `core/errors.py`**

In `src/downbeat/core/errors.py`, find this exact block:

```python
class InvalidParent(RelayError):
    """Raised when --parent names a peer that doesn't exist or isn't role=parent."""
```

Replace it with:

```python
class InvalidParent(RelayError):
    """Raised when --parent names a peer that doesn't exist, or the
    assignment would be invalid for another reason (see CycleDetected)."""


class CycleDetected(InvalidParent):
    """Raised when a --parent assignment would create a cycle in the peer
    tree (including self-parenting, the degenerate 1-cycle). Subclasses
    InvalidParent so existing catch sites (cli/commands/relay_cmds.py,
    tui/widgets/add_peer_modal.py) need no new wiring."""
```

- [ ] **Step 2: Add the `role` field's narrowed-meaning comment to `core/models.py`**

In `src/downbeat/core/models.py`, find this exact block:

```python
@dataclass
class Peer:
    name: str
    session_id: str
    cwd: str
    role: str   # "parent" | "child"
    registered_at: str
    last_seen: str
```

Replace it with:

```python
@dataclass
class Peer:
    name: str
    session_id: str
    cwd: str
    role: str   # "parent" | "child" -- the /relay-monitor autonomy DEFAULT
                # only (auto-execute vs surface-and-ask). NOT structural
                # position: a peer can be role="child" and still have its
                # own children -- gaining/losing children never changes
                # this field. See docs/superpowers/specs/
                # 2026-07-15-general-peer-tree-design.md.
    registered_at: str
    last_seen: str
```

- [ ] **Step 3: Write the failing tests for the store.py changes**

First, in `tests/test_store_peers.py`, find these three exact existing tests and replace them (they currently assert the OLD structural-gate behavior; under this change the same setup must succeed instead of raising):

Find:

```python
def test_register_child_explicit_parent_wrong_role_raises(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="other-child", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent")
    with pytest.raises(InvalidParent):
        store.register_peer(name="child", session_id="s-3", cwd="/tmp", role="child",
                            parent="other-child")
```

Replace with:

```python
def test_register_child_explicit_parent_can_be_a_child_peer(relay_dir):
    """A role=child peer is now a valid --parent target -- it becomes an
    interior node (structurally both a child and a parent)."""
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="other-child", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent")
    grandchild = store.register_peer(name="child", session_id="s-3", cwd="/tmp",
                                     role="child", parent="other-child")
    assert grandchild.parent == "other-child"
```

Find:

```python
def test_set_parent_target_not_a_parent_raises(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="other-child", session_id="s-3", cwd="/tmp", role="child",
                        parent="parent")
    with pytest.raises(InvalidParent):
        store.set_parent("child", "other-child")
```

Replace with:

```python
def test_set_parent_target_can_be_a_child_peer(relay_dir):
    """Repointing a peer's parent to another role=child peer is now valid --
    the target becomes an interior node."""
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="other-child", session_id="s-3", cwd="/tmp", role="child",
                        parent="parent")
    updated = store.set_parent("child", "other-child")
    assert updated.parent == "other-child"
```

Find:

```python
def test_set_parent_on_a_parent_peer_raises(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-2", session_id="s-2", cwd="/tmp", role="parent")
    with pytest.raises(InvalidParent):
        store.set_parent("parent", "parent-2")
```

Replace with:

```python
def test_set_parent_on_a_parent_peer_is_now_valid(relay_dir):
    """A role=parent peer can now also have its own parent -- role is no
    longer a structural gate."""
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-2", session_id="s-2", cwd="/tmp", role="parent")
    updated = store.set_parent("parent", "parent-2")
    assert updated.parent == "parent-2"
```

Then append these new tests to the end of `tests/test_store_peers.py`:

```python
def test_set_parent_direct_two_node_cycle_raises(relay_dir):
    from downbeat.core.errors import CycleDetected
    store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="B", session_id="s-2", cwd="/tmp", role="child", parent="A")
    with pytest.raises(CycleDetected):
        store.set_parent("A", "B")


def test_set_parent_self_parent_raises(relay_dir):
    from downbeat.core.errors import CycleDetected
    store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent")
    with pytest.raises(CycleDetected):
        store.set_parent("A", "A")


def test_set_parent_multi_hop_cycle_raises(relay_dir):
    from downbeat.core.errors import CycleDetected
    store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="B", session_id="s-2", cwd="/tmp", role="child", parent="A")
    store.register_peer(name="C", session_id="s-3", cwd="/tmp", role="child", parent="B")
    with pytest.raises(CycleDetected):
        store.set_parent("A", "C")


def test_set_parent_cycle_error_message_lists_the_chain(relay_dir):
    from downbeat.core.errors import CycleDetected
    store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="B", session_id="s-2", cwd="/tmp", role="child", parent="A")
    store.register_peer(name="C", session_id="s-3", cwd="/tmp", role="child", parent="B")
    with pytest.raises(CycleDetected) as exc_info:
        store.set_parent("A", "C")
    message = str(exc_info.value)
    assert "A" in message
    assert "B" in message
    assert "C" in message


def test_set_parent_valid_deep_chain_accepted(relay_dir):
    store.register_peer(name="L1", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="L2", session_id="s-2", cwd="/tmp", role="child", parent="L1")
    store.register_peer(name="L3", session_id="s-3", cwd="/tmp", role="child", parent="L2")
    store.register_peer(name="L4", session_id="s-4", cwd="/tmp", role="child", parent="L3")
    store.register_peer(name="L5", session_id="s-5", cwd="/tmp", role="child", parent="L4")
    assert store.get_peer("L5").parent == "L4"
    assert store.get_peer("L1").parent is None


def test_autonomy_role_unchanged_when_gaining_children(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s-2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s-3", cwd="/tmp", role="child",
                        parent="Child-A")
    # Child-A just gained its own child -- its own role/autonomy must not
    # have changed as a side effect.
    assert store.get_peer("Child-A").role == "child"


def test_acting_as_candidates_excludes_pure_leaf(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Leaf", session_id="s-2", cwd="/tmp", role="child",
                        parent="Root")
    names = {p.name for p in store.acting_as_candidates()}
    assert "Leaf" not in names


def test_acting_as_candidates_includes_childless_parent_role(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    names = {p.name for p in store.acting_as_candidates()}
    assert names == {"Root"}


def test_acting_as_candidates_includes_interior_child_role_node(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s-2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s-3", cwd="/tmp", role="child",
                        parent="Child-A")
    names = {p.name for p in store.acting_as_candidates()}
    assert names == {"Root", "Child-A"}


def test_acting_as_candidates_no_duplicate_for_parent_role_with_children(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Child", session_id="s-2", cwd="/tmp", role="child",
                        parent="Root")
    candidates = store.acting_as_candidates()
    names = [p.name for p in candidates]
    assert names.count("Root") == 1
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd ~/mama/downbeat && pytest tests/test_store_peers.py -v`
Expected: the 3 repurposed tests FAIL (old code still raises `InvalidParent` where the new test expects success), the cycle-detection tests FAIL with `AttributeError: module 'downbeat.core.errors' has no attribute 'CycleDetected'`, the `acting_as_candidates` tests FAIL with `AttributeError: module 'downbeat.core.store' has no attribute 'acting_as_candidates'`.

- [ ] **Step 5: Update the import block in `core/store.py`**

Find this exact block:

```python
from . import paths
from .errors import (
    AmbiguousParent,
    InvalidParent,
    MessageLocked,
    MessageNotFound,
    PeerNotFound,
    StoreCorrupt,
)
from .models import Broadcast, Message, MessageState, Peer, new_id, now_iso
```

Replace it with:

```python
from . import paths
from .errors import (
    AmbiguousParent,
    CycleDetected,
    InvalidParent,
    MessageLocked,
    MessageNotFound,
    PeerNotFound,
    StoreCorrupt,
)
from .models import Broadcast, Message, MessageState, Peer, new_id, now_iso
```

- [ ] **Step 6: Replace `_resolve_parent`, `register_peer`, and `set_parent`**

Find this exact block (the three functions plus their existing docstrings/bodies, verbatim as they exist today):

```python
def _resolve_parent(name: str, sessions: dict[str, dict], existing: dict | None,
                     parent: str | None) -> str | None:
    """Resolve the `parent` a role=child peer should be stored with.

    Explicit --parent always wins (validated: must exist, must be role=parent).
    Otherwise reuse the peer's already-stored parent (rebind case). Otherwise
    auto-default only if exactly one role=parent peer exists — ambiguity or
    absence is a hard error, never a silent guess."""
    if parent is not None:
        target = sessions.get(parent)
        if target is None or target.get("role") != "parent":
            raise InvalidParent(f"--parent {parent!r} is not a registered role=parent peer")
        return parent
    if existing and existing.get("parent"):
        return existing["parent"]
    parent_names = sorted(
        n for n, d in sessions.items() if d.get("role") == "parent" and n != name
    )
    if len(parent_names) == 1:
        return parent_names[0]
    if not parent_names:
        raise InvalidParent(
            f"no role=parent peer exists yet to pair {name!r} with — "
            "register the parent first, or pass --parent explicitly"
        )
    raise AmbiguousParent(
        f"multiple parent peers exist ({', '.join(parent_names)}) — "
        f"pass --parent explicitly to disambiguate {name!r}"
    )


def register_peer(name: str, session_id: str, cwd: str, role: str,
                  claude_pid: int | None = None,
                  claude_pid_start: str | None = None,
                  parent: str | None = None) -> Peer:
    sessions = _load_sessions()
    existing = sessions.get(name)
    registered_at = existing["registered_at"] if existing else now_iso()
    history = list(existing.get("session_id_history", [])) if existing else []
    if existing and existing.get("session_id") and existing["session_id"] != session_id:
        if existing["session_id"] not in history:
            history.append(existing["session_id"])
    resolved_parent = _resolve_parent(name, sessions, existing, parent) if role == "child" else None
    peer = Peer(
        name=name, session_id=session_id, cwd=cwd, role=role,
        registered_at=registered_at, last_seen=now_iso(),
        claude_pid=claude_pid,
        claude_pid_start=claude_pid_start,
        session_id_history=history,
        parent=resolved_parent,
    )
    sessions[name] = peer.to_dict()
    _save_sessions(sessions)
    _log.info("register peer=%s session=%s role=%s parent=%s claude_pid=%s",
              name, session_id, role, resolved_parent, claude_pid)
    return peer


def set_parent(name: str, parent: str) -> Peer:
    """Backfill/repoint an existing role=child peer's parent without full re-register."""
    sessions = _load_sessions()
    if name not in sessions:
        raise PeerNotFound(name)
    if sessions[name].get("role") != "child":
        raise InvalidParent(f"{name!r} is not a role=child peer")
    target = sessions.get(parent)
    if target is None or target.get("role") != "parent":
        raise InvalidParent(f"{parent!r} is not a registered role=parent peer")
    sessions[name]["parent"] = parent
    _save_sessions(sessions)
    return Peer.from_dict(sessions[name])
```

Replace it with:

```python
def _check_no_cycle(name: str, parent: str, sessions: dict[str, dict]) -> None:
    """Walk upward from `parent` following .parent pointers; raise
    CycleDetected if the walk reaches `name` (would create a cycle) or if
    parent==name outright (self-parent, the degenerate 1-cycle). Bounded by
    len(sessions) iterations so a pre-existing corrupt cycle already on disk
    (e.g. from a hand-edited sessions.json) can't hang this walk -- that's
    defense against corrupt existing data, not a depth limit on new writes;
    see "Why no depth cap" in docs/superpowers/specs/
    2026-07-15-general-peer-tree-design.md."""
    if parent == name:
        raise CycleDetected(f"{name!r} cannot be its own parent")
    chain = [name, parent]
    current = parent
    for _ in range(len(sessions)):
        next_parent = sessions.get(current, {}).get("parent")
        if next_parent is None:
            return
        chain.append(next_parent)
        if next_parent == name:
            raise CycleDetected(
                f"setting {name!r}'s parent to {parent!r} would create a "
                f"cycle: {' → '.join(chain)}"
            )
        current = next_parent


def _resolve_parent(name: str, sessions: dict[str, dict], existing: dict | None,
                     parent: str | None) -> str | None:
    """Resolve the `parent` a peer should be stored with.

    Explicit --parent always wins (validated: must exist, must not create a
    cycle). Any registered peer is a valid target regardless of role --
    role is no longer a structural gate, see docs/superpowers/specs/
    2026-07-15-general-peer-tree-design.md. Otherwise reuse the peer's
    already-stored parent (rebind case -- no new edge introduced, skip the
    cycle check). Otherwise auto-default only if exactly one role=parent
    peer exists — ambiguity or absence is a hard error, never a silent
    guess. Auto-default stays scoped to role=parent peers specifically (the
    common single-coordinator convenience); it does NOT expand to "any
    peer with no other candidates," since that would silently guess a
    non-obvious interior node as often as not."""
    if parent is not None:
        target = sessions.get(parent)
        if target is None:
            raise InvalidParent(f"--parent {parent!r} is not a registered peer")
        _check_no_cycle(name, parent, sessions)
        return parent
    if existing and existing.get("parent"):
        return existing["parent"]
    parent_names = sorted(
        n for n, d in sessions.items() if d.get("role") == "parent" and n != name
    )
    if len(parent_names) == 1:
        _check_no_cycle(name, parent_names[0], sessions)
        return parent_names[0]
    if not parent_names:
        raise InvalidParent(
            f"no role=parent peer exists yet to pair {name!r} with — "
            "register the parent first, or pass --parent explicitly"
        )
    raise AmbiguousParent(
        f"multiple parent peers exist ({', '.join(parent_names)}) — "
        f"pass --parent explicitly to disambiguate {name!r}"
    )


def register_peer(name: str, session_id: str, cwd: str, role: str,
                  claude_pid: int | None = None,
                  claude_pid_start: str | None = None,
                  parent: str | None = None) -> Peer:
    sessions = _load_sessions()
    existing = sessions.get(name)
    registered_at = existing["registered_at"] if existing else now_iso()
    history = list(existing.get("session_id_history", [])) if existing else []
    if existing and existing.get("session_id") and existing["session_id"] != session_id:
        if existing["session_id"] not in history:
            history.append(existing["session_id"])
    resolved_parent = (
        _resolve_parent(name, sessions, existing, parent)
        if role == "child" or parent is not None
        else None
    )
    peer = Peer(
        name=name, session_id=session_id, cwd=cwd, role=role,
        registered_at=registered_at, last_seen=now_iso(),
        claude_pid=claude_pid,
        claude_pid_start=claude_pid_start,
        session_id_history=history,
        parent=resolved_parent,
    )
    sessions[name] = peer.to_dict()
    _save_sessions(sessions)
    _log.info("register peer=%s session=%s role=%s parent=%s claude_pid=%s",
              name, session_id, role, resolved_parent, claude_pid)
    return peer


def set_parent(name: str, parent: str) -> Peer:
    """Repoint an existing peer's parent. Any registered peer is a valid
    target regardless of role -- role is no longer a structural gate, see
    docs/superpowers/specs/2026-07-15-general-peer-tree-design.md."""
    sessions = _load_sessions()
    if name not in sessions:
        raise PeerNotFound(name)
    target = sessions.get(parent)
    if target is None:
        raise InvalidParent(f"{parent!r} is not a registered peer")
    _check_no_cycle(name, parent, sessions)
    sessions[name]["parent"] = parent
    _save_sessions(sessions)
    return Peer.from_dict(sessions[name])
```

- [ ] **Step 7: Add `acting_as_candidates()` after `children_of`**

Find this exact block:

```python
def children_of(parent_name: str) -> list[Peer]:
    """All peers 'related' to acting_as parent_name for TUI display purposes:
    the parent itself plus every child explicitly paired with it. Replaces the
    old name-prefix-string inference (_related_prefix)."""
    return [
        p for p in list_peers()
        if p.name == parent_name or p.parent == parent_name
    ]


def list_peers() -> list[Peer]:
    return [Peer.from_dict(d) for d in _load_sessions().values()]
```

Replace it with:

```python
def children_of(parent_name: str) -> list[Peer]:
    """All peers 'related' to acting_as parent_name for TUI display purposes:
    the parent itself plus every child explicitly paired with it. Replaces the
    old name-prefix-string inference (_related_prefix)."""
    return [
        p for p in list_peers()
        if p.name == parent_name or p.parent == parent_name
    ]


def acting_as_candidates() -> list[Peer]:
    """Peers eligible to be selected as `acting_as`: either explicitly
    role="parent" (even with zero children yet -- needed so a freshly
    registered parent can be acted-as to add its first child), or any peer
    that has at least one child (an interior node in the tree, regardless
    of its own role/autonomy setting). Union, not either alone -- see
    docs/superpowers/specs/2026-07-15-general-peer-tree-design.md."""
    peers = list_peers()
    parent_names = {p.parent for p in peers if p.parent is not None}
    return [p for p in peers if p.role == "parent" or p.name in parent_names]


def list_peers() -> list[Peer]:
    return [Peer.from_dict(d) for d in _load_sessions().values()]
```

- [ ] **Step 8: Update the `--parent` CLI help text in `cli/__main__.py`**

Find this exact block:

```python
    sp_reg.add_argument("--parent", default=None,
                        help="name of the role=parent peer this child is joining "
                             "(required for --role child unless exactly one parent "
                             "peer is currently registered)")
```

Replace it with:

```python
    sp_reg.add_argument("--parent", default=None,
                        help="name of the peer this session is joining as a child "
                             "(required for --role child unless exactly one "
                             "role=parent peer is currently registered)")
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `pytest tests/test_store_peers.py -v`
Expected: PASS (all tests, including the 3 repurposed and the 12 new ones)

- [ ] **Step 10: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: PASS — no other test in the suite depends on the old structural-gate behavior (confirmed at planning time by reading `tests/test_store_peers.py` in full).

- [ ] **Step 11: Commit**

```bash
cd ~/mama/downbeat
git add src/downbeat/core/errors.py src/downbeat/core/models.py src/downbeat/core/store.py src/downbeat/cli/__main__.py tests/test_store_peers.py
git commit -m "feat: decouple role from tree structure, add cycle prevention"
```

---

### Task 2: TUI acting-as pickers — `chat.py` and `switch_acting_as.py`

**Files:**
- Modify: `src/downbeat/tui/screens/chat.py`
- Modify: `src/downbeat/tui/widgets/switch_acting_as.py`
- Test: `tests/test_tui_chat.py` (extend)

**Interfaces:**
- Consumes: `store.acting_as_candidates() -> list[Peer]` (Task 1).

**Note on scope:** `tui/widgets/peer_list.py` was confirmed at planning time to be referenced ONLY by `tui/screens/main.py` (dead code, deleted in Task 4) — it is not used by `chat.py` or anywhere else live. It does **not** need the union-filter fix; it's deleted whole in Task 4 instead.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tui_chat.py` (the file already imports `pytest` and `RelayApp` at the top):

```python
@pytest.mark.asyncio
async def test_acting_as_candidates_include_interior_child_node(relay_dir):
    """_populate_acting_as's candidate set includes a role=child peer that
    itself has children (an interior node), not just role=parent peers."""
    from downbeat.core import store
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s3", cwd="/tmp", role="child",
                        parent="Child-A")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        screen.acting_as = "Child-A"
        screen._populate_acting_as()
        assert screen.acting_as == "Child-A"


@pytest.mark.asyncio
async def test_switch_acting_as_modal_includes_interior_child_node(relay_dir):
    """A role=child peer that has its own children (an interior node) must
    be selectable as acting_as too -- not just role=parent peers."""
    from downbeat.core import store
    from downbeat.tui.widgets.switch_acting_as import SwitchActingAsModal
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s3", cwd="/tmp", role="child",
                        parent="Child-A")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        modal = SwitchActingAsModal(current="Root")
        app.push_screen(modal)
        await pilot.pause()
        assert set(modal._parents) == {"Root", "Child-A"}


@pytest.mark.asyncio
async def test_find_message_switches_acting_as_to_interior_child_node(relay_dir):
    """find_message's acting-as-target check must accept a role=child peer
    that has its own children as a valid switch target, not just
    role=parent peers. Drives the real modal flow (types the message id,
    presses Enter) rather than re-deriving the target expression inline --
    a test that only recomputes the same formula and compares it to itself
    would never fail if the actual chat.py logic were wrong."""
    from downbeat.core import store
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s3", cwd="/tmp", role="child",
                        parent="Child-A")
    msg = store.send_message(from_peer="Child-A-1", to_peer="Child-A",
                             subject="s", body="b")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        screen.acting_as = "Root"
        screen.action_find_message()
        await pilot.pause()
        modal = app.screen
        modal._input.value = msg.id
        modal._refresh_results(msg.id)
        await pilot.pause()
        modal._table.move_cursor(row=0)
        await pilot.press("enter")
        await pilot.pause()
        assert screen.acting_as == "Child-A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tui_chat.py -k "interior_child_node" -v`
Expected: the first two FAIL — `test_acting_as_candidates_include_interior_child_node` fails because `screen.acting_as` gets reset away from `"Child-A"` (old code only recognizes `role=="parent"`); `test_switch_acting_as_modal_includes_interior_child_node` fails because `modal._parents == ["Root"]` only. `test_find_message_switches_acting_as_to_interior_child_node` fails because `chat.py`'s `after(msg)` closure still checks `role=="parent"` and Child-A doesn't qualify, so `screen.acting_as` stays `"Root"` instead of switching to `"Child-A"`.

- [ ] **Step 3: Update `chat.py`'s `_populate_acting_as` and `find_message`**

Find this exact block:

```python
    def _populate_acting_as(self) -> None:
        parents = [p for p in store.list_peers() if p.role == "parent"]
        parent_names = {p.name for p in parents}
        # Prefer persisted last-acting-as if still valid
        if self.acting_as is None or self.acting_as not in parent_names:
            last = state.get_last_acting_as()
            if last in parent_names:
                self.acting_as = last
            else:
                self.acting_as = parents[0].name if parents else None
```

Replace it with:

```python
    def _populate_acting_as(self) -> None:
        candidates = store.acting_as_candidates()
        candidate_names = {p.name for p in candidates}
        # Prefer persisted last-acting-as if still valid
        if self.acting_as is None or self.acting_as not in candidate_names:
            last = state.get_last_acting_as()
            if last in candidate_names:
                self.acting_as = last
            else:
                self.acting_as = candidates[0].name if candidates else None
```

Then, in the same file, find this exact block:

```python
        async def after(msg):
            if msg is None:
                return
            # Switch acting-as and tab if needed
            peers = {p.name: p for p in store.list_peers()}
            is_parent = msg.to_peer in peers and peers[msg.to_peer].role == "parent"
            target_acting = msg.to_peer if is_parent else msg.from_peer
            other = msg.from_peer if target_acting == msg.to_peer else msg.to_peer
            if target_acting in peers and peers[target_acting].role == "parent":
                self.acting_as = target_acting
                await self._populate_tabs()
                self.active_peer = other
                tabs = self.query_one("#peer-tabs", PeerTabs)
                if other in self._group_members():
                    tabs.active = f"tab-{tabs._safe_id(other)}"
                self._refresh_thread()
        self.app.push_screen(FindMessageModal(), after)
```

Replace it with:

```python
        async def after(msg):
            if msg is None:
                return
            # Switch acting-as and tab if needed
            candidate_names = {p.name for p in store.acting_as_candidates()}
            target_acting = msg.to_peer if msg.to_peer in candidate_names else msg.from_peer
            other = msg.from_peer if target_acting == msg.to_peer else msg.to_peer
            if target_acting in candidate_names:
                self.acting_as = target_acting
                await self._populate_tabs()
                self.active_peer = other
                tabs = self.query_one("#peer-tabs", PeerTabs)
                if other in self._group_members():
                    tabs.active = f"tab-{tabs._safe_id(other)}"
                self._refresh_thread()
        self.app.push_screen(FindMessageModal(), after)
```

- [ ] **Step 4: Update `switch_acting_as.py`'s `on_mount`**

Find this exact block:

```python
    def on_mount(self) -> None:
        self._parents = [p.name for p in store.list_peers() if p.role == "parent"]
```

Replace it with:

```python
    def on_mount(self) -> None:
        self._parents = [p.name for p in store.acting_as_candidates()]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_tui_chat.py -v`
Expected: PASS (all tests in the file, including the 3 new ones and every pre-existing test — in particular `test_chat_screen_auto_picks_first_parent_as_acting_as` and `test_switch_acting_as_modal_lists_parents` must still pass unchanged, since a pure `role=="parent"` peer is still included by the union)

- [ ] **Step 6: Run the broader TUI test suite to check for regressions**

Run: `pytest tests/test_tui_chat.py tests/test_tui_smoke.py tests/test_tui_peer_admin.py -v`
Expected: PASS (all tests)

- [ ] **Step 7: Commit**

```bash
git add src/downbeat/tui/screens/chat.py src/downbeat/tui/widgets/switch_acting_as.py tests/test_tui_chat.py
git commit -m "feat: TUI acting-as pickers recognize interior tree nodes"
```

---

### Task 3: `screens/peers.py` — group/sort by the same union eligibility

**Files:**
- Modify: `src/downbeat/tui/screens/peers.py`
- Test: `tests/test_tui_peer_admin.py` (extend)

**Interfaces:**
- Consumes: `store.acting_as_candidates() -> list[Peer]` (Task 1).

**Note on scope resolved at planning time:** the spec left open whether this screen's grouping is scoped to one `acting_as` or shows all peers system-wide. Confirmed by reading the live code: `PeersScreen` displays `sorted(store.list_peers(), key=sort_key)` — every registered peer, unscoped. The union-filter fix below applies directly, with one accepted consequence documented inline: an interior node (a peer that is both someone's child and someone else's parent) becomes its **own** group header rather than nesting under its own parent's group, since this screen is a flat single-level grouping, not a recursive tree — consistent with Option A's "2-level viewport, navigate deeper by re-rooting acting_as" design (see the spec's "Known limitations" section).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tui_peer_admin.py` (the file already imports `pytest`, `RelayApp`, and has the `#peers-table` row-reading pattern in `test_peers_screen_groups_by_explicit_parent` — follow that exact pattern):

```python
@pytest.mark.asyncio
async def test_peers_screen_interior_node_groups_under_itself(relay_dir):
    """An interior node (child of one peer, parent of its own) becomes its
    own group header -- this screen is a 2-level viewport per peer, not a
    recursive tree, so Child-A shows as a group root with its own child
    rather than nesting under Root's group."""
    from downbeat.core import store
    from downbeat.tui.screens.peers import PeersScreen
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s3", cwd="/tmp", role="child",
                        parent="Child-A")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(PeersScreen())
        await pilot.pause()
        table = app.screen.query_one("#peers-table")
        names: list[str] = []
        for row_idx in range(table.row_count):
            row = table.get_row_at(row_idx)
            name = row[0].strip() if row[0] else ""
            if name:
                names.append(name)
        # Group keys sort alphabetically: "Child-A" < "Root". Within the
        # "Child-A" group: Child-A itself (rank 0, group header) then
        # Child-A-1 (rank 1). Root has no children here, so it's a
        # single-row group on its own.
        assert names == ["Child-A", "Child-A-1", "Root"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tui_peer_admin.py -k interior_node_groups -v`
Expected: FAIL — old code's `group_key`/`sort_key` put `Child-A` in group `"Root"` (since `Child-A.role == "child"`), so the actual row order groups `Root`+`Child-A` together and `Child-A-1` separately under group `"Child-A"`, not matching the expected `["Child-A", "Child-A-1", "Root"]`.

- [ ] **Step 3: Update `group_key`/`sort_key` in `peers.py`**

Find this exact block:

```python
        def group_key(peer):
            # Group by the real parent-child pairing (Peer.parent), not a
            # name-prefix guess. Parents group under their own name; a child
            # with no parent set yet (pre-migration peer) sorts to the bottom.
            if peer.role == "parent":
                return peer.name
            return peer.parent or "~ungrouped"

        def sort_key(peer):
            return (
                group_key(peer),
                0 if peer.role == "parent" else 1,
                peer.name,
            )

        sorted_peers = sorted(store.list_peers(), key=sort_key)
```

Replace it with:

```python
        candidate_names = {p.name for p in store.acting_as_candidates()}

        def group_key(peer):
            # Group by the real parent-child pairing (Peer.parent), not a
            # name-prefix guess. Peers eligible to act as a group header
            # (role="parent", or any peer with children of its own) group
            # under their own name; everyone else groups under their
            # explicit parent, or "~ungrouped" if that's unset. An interior
            # node (child of one peer, parent of others) becomes its OWN
            # group header here rather than nesting under its own parent's
            # group -- this screen is intentionally a 2-level viewport per
            # peer, not a recursive tree; see docs/superpowers/specs/
            # 2026-07-15-general-peer-tree-design.md.
            if peer.name in candidate_names:
                return peer.name
            return peer.parent or "~ungrouped"

        def sort_key(peer):
            return (
                group_key(peer),
                0 if peer.name in candidate_names else 1,
                peer.name,
            )

        sorted_peers = sorted(store.list_peers(), key=sort_key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tui_peer_admin.py -k interior_node_groups -v`
Expected: PASS

- [ ] **Step 5: Run the full peers-screen test suite to check for regressions**

Run: `pytest tests/test_tui_peer_admin.py -v`
Expected: PASS (all tests, including `test_peers_screen_groups_by_explicit_parent`, which uses only `role=="parent"` peers as group headers — still correct under the union since those peers qualify via `role` alone)

- [ ] **Step 6: Commit**

```bash
git add src/downbeat/tui/screens/peers.py tests/test_tui_peer_admin.py
git commit -m "feat: peers screen groups interior tree nodes as their own header"
```

---

### Task 4: Delete dead code — `screens/main.py` and `widgets/peer_list.py`

**Files:**
- Delete: `src/downbeat/tui/screens/main.py`
- Delete: `src/downbeat/tui/widgets/peer_list.py`
- Modify: `tests/test_tui_peers.py` (remove the 4 skip-marked tests that exercise the deleted `PeerList` widget; keep the one live test)

**Interfaces:** none (removes unreferenced code; nothing in this codebase imports either deleted file outside of each other, confirmed by `grep -rln "MainScreen" tests/ src/` and `grep -rln "PeerList" src/downbeat/tui/` at planning time — both come back empty except the two files being deleted and `app.py`'s comment referencing `ChatScreen` as the replacement).

- [ ] **Step 1: Confirm no other code references these files (defense against drift since planning)**

Run:
```bash
cd ~/mama/downbeat
grep -rn "MainScreen" src/ tests/
grep -rn "PeerList\b" src/ tests/
```
Expected: `MainScreen` appears only in `src/downbeat/tui/screens/main.py` itself and as a comment in `src/downbeat/tui/screens/chat.py` (`"""Chat-style main screen. Replaces the three-pane MainScreen."""` — a comment, not a reference, safe to leave). `PeerList` appears only in `src/downbeat/tui/screens/main.py` and `src/downbeat/tui/widgets/peer_list.py` itself. If either grep turns up an additional live reference not accounted for here, STOP and report NEEDS_CONTEXT rather than deleting — something changed since planning.

- [ ] **Step 2: Remove the 4 skip-marked `PeerList` tests from `tests/test_tui_peers.py`**

Find this exact block (spans from the file's imports through the end of the 4th skip-marked test, right before the still-live `test_group_members_uses_explicit_parent_not_name_shape`):

```python
import pytest

from downbeat.tui.app import RelayApp


@pytest.mark.skip(reason="three-pane view replaced by chat view")
@pytest.mark.asyncio
async def test_peer_list_shows_registered_peers(relay_dir):
    from downbeat.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        peer_widget = app.screen.query_one("PeerList")
        # List shows all peers (parent + children).
        # "parent" has no "-" so prefix is empty → fallback: all peers shown.
        names = [item.peer_name for item in peer_widget.items]
        assert "child" in names
        assert "parent" in names


@pytest.mark.skip(reason="three-pane view replaced by chat view")
@pytest.mark.asyncio
async def test_peer_list_acting_as_default_first_parent(relay_dir):
    from downbeat.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        peer_widget = app.screen.query_one("PeerList")
        assert peer_widget.acting_as == "parent"


@pytest.mark.skip(reason="three-pane view replaced by chat view")
@pytest.mark.asyncio
async def test_peer_list_unread_count(relay_dir):
    from downbeat.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="parent", to_peer="child", subject="x", body="y")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        peer_widget = app.screen.query_one("PeerList")
        peer_widget.refresh_from_store()
        await pilot.pause()
        child_row = next(i for i in peer_widget.items if i.peer_name == "child")
        assert child_row.unread == 1


@pytest.mark.skip(reason="three-pane view replaced by chat view")
@pytest.mark.asyncio
async def test_dropdown_lists_only_parents(relay_dir):
    from downbeat.core import store
    store.register_peer(name="P1", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="P2", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="C1", session_id="s3", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True):
        peer_widget = app.screen.query_one("PeerList")
        peer_widget.refresh_from_store()
        # acting_as must be one of the parents, not the child
        assert peer_widget.acting_as in {"P1", "P2"}


@pytest.mark.skip(reason="three-pane view replaced by chat view")
@pytest.mark.asyncio
async def test_list_shows_all_related_peers_including_parent(relay_dir):
    from downbeat.core import store
    store.register_peer(name="PLAT-3113-master", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-child", session_id="s2", cwd="/tmp", role="child")
    store.register_peer(name="PLAT-3113-slave", session_id="s3", cwd="/tmp", role="child")
    store.register_peer(name="other-child", session_id="s4", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True):
        peer_widget = app.screen.query_one("PeerList")
        peer_widget.refresh_from_store()
        names = [item.peer_name for item in peer_widget.items]
        assert set(names) == {"PLAT-3113-master", "PLAT-3113-child", "PLAT-3113-slave"}
        assert "other-child" not in names
```

Replace it with:

```python
import pytest

from downbeat.tui.app import RelayApp
```

(This leaves the file's remaining content — the `test_group_members_uses_explicit_parent_not_name_shape` test, which tests `ChatScreen`, not `PeerList` — untouched below this point.)

- [ ] **Step 3: Delete the two dead files**

```bash
git rm src/downbeat/tui/screens/main.py src/downbeat/tui/widgets/peer_list.py
```

- [ ] **Step 4: Run the full test suite to confirm the deletion is clean**

Run: `pytest -v`
Expected: PASS — zero collection errors (nothing imports the deleted modules), zero references to `MainScreen`/`PeerList` remain anywhere except the harmless comment in `chat.py`.

- [ ] **Step 5: Run ruff to catch any lint issue from the deletion**

Run: `ruff check src/downbeat/tui/ tests/test_tui_peers.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete dead MainScreen/PeerList (superseded by ChatScreen)"
```

---

### Task 5: Full verification and PR

**Files:** none (verification only).

- [ ] **Step 1: Run the complete test suite**

Run: `cd ~/mama/downbeat && pytest -v`
Expected: PASS, zero failures, zero errors. Note the total test count for the PR description.

- [ ] **Step 2: Run ruff across the whole repo**

Run: `ruff check .`
Expected: no errors.

- [ ] **Step 3: Confirm the branch's commit log tells a clean story**

Run: `git log --oneline origin/main..HEAD`
Expected: the spec-doc commit (`8dd765c`), then one `feat:` commit per Task 1-3, then the `refactor:` dead-code-deletion commit (Task 4) — 5 commits total, no `fixup`/`wip` noise.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feat/general-peer-tree
gh pr create --title "feat: general peer tree (decouple role from structure)" --body "$(cat <<'EOF'
## Summary
- Removes the strict two-tier parent/child restriction: any registered peer can now be both a child and a parent (a general tree), with no artificial depth cap.
- `role` narrows to meaning ONE thing only: the `/relay-monitor` autonomy default (auto-execute vs surface-and-ask). It no longer gates tree structure.
- New invariant, stated explicitly in code and the spec: autonomy is orthogonal to structure -- a peer's `role` never changes as a side effect of gaining or losing children.
- Cycle prevention: a bounded, visited-chain walk shared by `register_peer` and `set_parent`, raising `CycleDetected(InvalidParent)` (existing catch sites need no new wiring). No depth cap -- the cycle check plus the single-parent invariant already bound depth by peer count.
- New `store.acting_as_candidates()` (`role=="parent" OR has_children`) is the single source of truth for "which peers can be acted-as," consumed by every TUI picker (`chat.py`, `switch_acting_as.py`, `peers.py`'s grouping).
- Deleted two dead files found during planning: `tui/screens/main.py` (superseded by `ChatScreen`, never pushed anywhere reachable) and `tui/widgets/peer_list.py` (referenced only by the dead `main.py`).
- Full design rationale, including why the human explicitly rejected a depth cap and the parent-session architectural review that shaped this: `docs/superpowers/specs/2026-07-15-general-peer-tree-design.md`.

## Test plan
- [x] `pytest -v` -- full suite green
- [x] `ruff check .` -- clean
- [ ] Manual: register a `role=parent` Root, a `role=child` Child-A under it, then a `role=child` Child-A-1 under Child-A. Confirm `downbeat tui` lets you switch acting-as to Child-A (not just Root) and see Child-A-1 as its tab.
- [ ] Manual: attempt `downbeat peers set-parent Root Child-A-1` (or equivalent) and confirm it's rejected with a `CycleDetected` message listing the chain.
EOF
)"
```

- [ ] **Step 5: Report the PR URL back to the human** — this plan's execution ends here; merging is a separate, explicit human decision (matches this session's established pattern for PR #13/#15/#17).

---

## Self-Review

**Spec coverage:** every section of the spec maps to a task — "Data model" + "Store changes" + "Cycle prevention"/"Why no depth cap" → Task 1; "TUI changes" (chat.py, switch_acting_as.py, peer_list.py) → Task 2 (peer_list.py redirected to Task 4 once confirmed dead, a real finding from re-reading live code, not a spec gap); "TUI changes" (peers.py) → Task 3; "Migration" (data: none needed, nothing to do; behavior: covered by the union filter in Tasks 1-3) → no separate task needed, correctly folded into the filter fix itself. "Known limitations" section is explicitly deferred, no task needed.

**Placeholder scan:** no TBD/TODO; every step has complete, runnable code or an exact command with an expected result. The one place a plan-time decision superseded the spec's own hedge ("verify against current code" for peers.py's scoping, and for whether peer_list.py needs the union fix at all) is resolved concretely in Task 2's "Note on scope" and Task 3's "Note on scope resolved at planning time" — both state what was found and why, not deferred further.

**Type consistency:** `store.acting_as_candidates() -> list[Peer]` (Task 1) is called identically in Task 2 (`chat.py`, `switch_acting_as.py`) and Task 3 (`peers.py`) — same zero-argument call, same iteration pattern (`{p.name for p in store.acting_as_candidates()}` or `[p.name for p in store.acting_as_candidates()]` depending on whether a set or list is needed at that call site). `CycleDetected` (Task 1, subclasses `InvalidParent`) is never separately imported by Task 2/3/4's TUI code, since neither `chat.py` nor `switch_acting_as.py` nor `peers.py` call `set_parent`/`register_peer` directly in a way that constructs a new tree edge in this plan's scope -- the existing `AddPeerModal`/`cmd_register` catch sites (unchanged, not touched by any task here) already catch it via the existing `(AmbiguousParent, InvalidParent)` tuples.
