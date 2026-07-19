# Per-peer autonomy control (change autonomy after registration)

**Status:** design — recommendation, pending maintainer decision. Tracks
[issue #41](https://github.com/FreddieMcHeart/downbeat/issues/41) ("Per-peer
autonomy control (change autonomy after registration)"), milestone "Peer
identity & autonomy". This spec analyzes the options and recommends one; it
does not commit to a design — see "Open decisions for the maintainer" below.

## Context

A peer's `/relay-monitor` autonomy — auto-execute vs. surface-and-ask — is
set once, at `downbeat register` time, via the `--role` flag, and there is
no path to change it afterward.

`Peer.role` (`src/downbeat/core/models.py:124-129`) already documents this
narrowed meaning, added by the general peer tree spec
(`docs/superpowers/specs/2026-07-15-general-peer-tree-design.md`):

```python
role: str   # "parent" | "child" -- the /relay-monitor autonomy DEFAULT
            # only (auto-execute vs surface-and-ask). NOT structural
            # position: a peer can be role="child" and still have its
            # own children -- gaining/losing children never changes
            # this field. See docs/superpowers/specs/
            # 2026-07-15-general-peer-tree-design.md.
```

`role` is written in exactly two places, and neither is a "change autonomy"
path:

- **`register_peer`** (`src/downbeat/core/store.py:132-160`) takes `role` as
  a required positional argument and stores it verbatim on every call —
  including a re-register of an existing peer (`existing = sessions.get(name)`
  at line 137), which *would* let a repeat `downbeat register <name> --role
  parent` silently flip an existing peer's autonomy as a side effect of an
  unrelated re-registration. That's a footgun, not a supported "change
  autonomy" command.
- **`set_parent`** (`src/downbeat/core/store.py:163-176`) only ever touches
  `sessions[name]["parent"]`; it never reads or writes `role`. This is the
  intended enforcement of the orthogonality invariant for the *structural*
  path — but it also means `set_parent` offers no autonomy-change capability
  at all, by design.

The CLI (`src/downbeat/cli/__main__.py:37-192`) confirms there is no
autonomy-change surface: subcommands are `register`, `send`, `reply`,
`inbox`, `peers` (with only a `set-parent` sub-action,
`__main__.py:97-103`), `gc-stale`, `gc-markers`, `rebind`, `quarantine`,
`whoami`, `tui`, `drain`, `ack`, `reconcile`, `init`, `uninstall`. `rebind`
explicitly preserves role (`--role/cwd unchanged`, `__main__.py:116`); no
subcommand sets it.

The TUI's only role-setting surface is `AddPeerModal`
(`src/downbeat/tui/widgets/add_peer_modal.py`), which drives a first-time
`store.register_peer(..., role=role, ...)` call (line 80) — registration,
not editing. `PeersScreen` (`src/downbeat/tui/screens/peers.py`) displays
`p.role` as a table column (line 83) and has bindings for add/remove/gc/
rebind (`BINDINGS`, lines 15-23) but none for changing role.

### Why this now matters (post-#18)

Before the general peer tree (#18), `role` and tree position were
1:1 — a `role=="parent"` peer was always a root, a `role=="child"` peer
was always a leaf — so autonomy incidentally tracked structure and the gap
was invisible. Post-#18, `store.acting_as_candidates()`
(`store.py:189-198`) and `PeersScreen._refresh`'s `group_key`
(`screens/peers.py:45-58`) both explicitly treat "is this an interior node"
and "is `role=="parent"`" as independent, unioned conditions — the codebase
already assumes any peer can be both a parent and a child. Autonomy, by
contrast, is still frozen at whatever `--role` was passed at registration,
with no way to reconsider it once the peer's place in the tree — or its
job — changes.

### Invariant: autonomy is orthogonal to structure (restated, must survive this change)

**A peer's `role` must never change as a side effect of gaining or losing
children, or of being repointed via `set_parent`.** This spec's whole job is
to add an *explicit, conscious* path to change `role` — it must not
reintroduce an *implicit* one. Concretely: `set_parent` must continue to
touch only the `parent` field; nothing added by this spec should live in
`set_parent`, `_resolve_parent`, `register_peer`'s parent-resolution branch,
or `remove_peer`'s grandparent-promotion path. This is the same invariant
the 2026-07-15 spec established and tested (its "Autonomy orthogonality"
test case, `2026-07-15-general-peer-tree-design.md` line ~219); this spec
extends the test matrix (see "Testing" below) rather than replacing it.

## Options

### Option A — minimal: keep `role`, add an explicit setter

Add `store.set_role(name: str, role: str) -> Peer`, a `downbeat peers
set-role <name> <parent|child>` CLI subcommand (siblings with the existing
`peers set-parent`), and a TUI keybinding on `PeersScreen` (e.g. `r`) that
opens a small confirm/select modal and calls the same store function. The
field stays named `role`, keeps its two literal values, and keeps living on
`Peer` unchanged in shape.

```python
def set_role(name: str, role: str) -> Peer:
    """Change an existing peer's /relay-monitor autonomy default.
    Structural-only: never touches `parent`. See docs/superpowers/specs/
    2026-07-19-per-peer-autonomy-spec.md."""
    sessions = _load_sessions()
    if name not in sessions:
        raise PeerNotFound(name)
    if role not in ("parent", "child"):
        raise InvalidRole(f"role must be 'parent' or 'child', got {role!r}")
    sessions[name]["role"] = role
    _save_sessions(sessions)
    return Peer.from_dict(sessions[name])
```

CLI wiring mirrors the existing `peers set-parent` sub-action
(`__main__.py:97-103`, `relay_cmds.py cmd_peers` lines 122-130): a new
`peers_action == "set-role"` branch calling `store.set_role`, catching a new
`InvalidRole(RelayError)` the same way `set-parent` catches
`PeerNotFound`/`InvalidParent`.

**Trade-offs:**
- Smallest possible diff: one store function, one CLI branch, one TUI
  binding + tiny modal (or an inline `Select` reusing `AddPeerModal`'s
  pattern). No changes to `Peer`'s shape, `relay-monitor.md`, `SKILL.md`, or
  `relay-inbox.py`'s `role` reads (`assets/hooks/relay-inbox.py:130-132,254-257`).
- Ships the acceptance criteria in #41 directly and literally ("a CLI path
  … e.g. `downbeat peers set-role`").
- Leaves the underlying naming problem unresolved: `role` is a field whose
  *name* still suggests "structural position" (a plausible reading for
  anyone who hasn't read the 2026-07-15 spec's field comment) while its
  *only remaining meaning* is an autonomy default. The field comment is the
  only thing preventing a future contributor from re-conflating the two —
  same risk the 2026-07-15 spec flagged for the comment itself ("the only
  place the two-tier assumption can silently survive the refactor").
- `register_peer`'s re-register footgun (an unrelated re-registration
  silently changing `role`) stays unaddressed unless bundled in — see "Data
  model / CLI / TUI changes" below, where it's folded into Option A anyway
  since it's cheap and directly adjacent.

### Option B — clarifying refactor: rename `role` → `autonomy`

Rename the field itself: `Peer.autonomy: str` (values `"auto"` /
`"ask"`, or keep `"parent"`/`"child"` string values under the new field name
— a separate sub-decision), remove `role` entirely, and thread the rename
through every read site: `core/store.py` (`_resolve_parent`'s
`role=="parent"` filter is unaffected — that check is about the auto-default
*pairing* convenience, but it currently keys off the *same* field, so it
would need to migrate too, or be re-justified as intentionally staying on
the old field for a different reason), `acting_as_candidates()`
(`store.py:189-198`), every `p.role` in the TUI (`screens/peers.py:31,79,83`,
`add_peer_modal.py`), `relay-monitor.md`, `skill/SKILL.md`
(`whoami`'s `<name> <role>` output format), and `relay-inbox.py`'s
`model_nudge_line`/`sessions.get(name, {}).get("role")`
(`assets/hooks/relay-inbox.py:130,254`).

**Trade-offs:**
- Fixes the naming problem at the root: a field called `autonomy` cannot be
  mistaken for a structural concept, which is exactly the ambiguity Option A
  leaves standing. This is the more honest long-term shape, and it's the
  kind of clarifying rename the 2026-07-15 spec itself *considered and
  rejected* for the same reason it would be needed now ("renaming was
  considered and rejected: it would touch `relay-monitor.md`, `SKILL.md`,
  `relay-inbox.py`, and every `role=="parent"` TUI comparison for zero
  functional gain" — at that time, because the rename bought nothing beyond
  what the field comment already documented). Issue #41 is arguably the
  first time the rename buys something concrete: a setter command whose
  name (`set-role` vs. `set-autonomy`) will otherwise permanently encode the
  ambiguity into the CLI's public surface.
- Backward compatibility: `Peer.from_dict` (`models.py:147-161`) uses
  `.get()` with defaults, so a rename needs a compat read (`d.get("autonomy",
  d.get("role", "child"))`) to load pre-existing `sessions.json` files
  without a migration script, and `to_dict()`/`asdict()` would start
  serializing the new key name going forward — meaning any external tooling
  or saved fixtures reading raw `sessions.json` for `"role"` breaks silently
  unless a transition period double-writes both keys, or a one-time
  migration pass rewrites `sessions.json` in place.
  `assets/hooks/relay-inbox.py` is Jinja/shell-adjacent hook code shipped as
  an *asset* installed into users' `~/.claude/hooks/` — a rename there is a
  breaking change to an interface that isn't versioned alongside the Python
  package the way `store.py` is, so stale installed hooks would read
  `"role"` from a `sessions.json` that no longer writes it, silently
  degrading the Fable-model nudge (`relay-inbox.py:130-132`) rather than
  erroring.
  `SKILL.md`'s `whoami --json` output shape (`{"name": ..., "role": ...}`,
  `SKILL.md:75`) is documented, human/agent-facing API; renaming its key
  changes a contract that other Claude Code sessions' prompts (the
  `relay-monitor.md` role-branch logic) may already parse by that name.
- Bigger surface, bigger review, and — per the 2026-07-15 spec's own
  prior rejection of this exact rename — no functional payoff beyond
  clarity *unless* #41's setter command is the trigger that finally makes
  clarity worth the diff. That trigger is real but is itself a judgment
  call, not a technical fact.

### Shared constraint: the orthogonality invariant applies identically to both options

Neither option touches `set_parent`, `_resolve_parent`, or
`remove_peer`'s child-promotion path. Both add exactly one new,
explicit write path for the autonomy field (`set_role` in A,
`set_autonomy` in B) that a human or agent must call on purpose — nothing
added by either option makes `role`/`autonomy` change as a side effect of a
structural operation.

## Recommendation

**Ship Option A now.** It satisfies #41's acceptance criteria exactly as
proposed in the issue text (`downbeat peers set-role`), keeps the diff
reviewable and low-risk, and does not foreclose Option B later — a future
rename is a pure refactor on top of Option A's already-correct behavior
(the setter's *logic* doesn't change, only the field/key names it touches).
Option B's case is real but is a documentation/clarity investment best
made deliberately, with its own review of the `SKILL.md`/`relay-monitor.md`
contract and hook backward-compat story, not bundled into a feature PR whose
acceptance criteria don't require it. Sequencing A before B also gives B a
concrete answer to "was the rename worth it" — namely, whether `set-role`
ends up being a recurring point of confusion in practice.

## Data model / CLI / TUI changes (Option A, as recommended)

**`core/store.py`:**
- Add `set_role(name: str, role: str) -> Peer`, as shown above. Raise
  `InvalidRole` (new) for any value other than `"parent"`/`"child"`,
  `PeerNotFound` if `name` isn't registered.
- Close the `register_peer` footgun identified in "Context": add a
  doc-comment on `register_peer` making explicit that a re-register with a
  different `--role` *does* change an existing peer's autonomy today (it
  always has), and that `set_role` is now the *intended* path — re-register
  is for session/pid/cwd changes, not autonomy changes. Whether to also add
  a `register_peer` behavior change (e.g. warn or require `--force` to
  change `role` on an existing peer) is left to the maintainer — see "Open
  decisions" below; this spec does not mandate a behavior change to
  `register_peer` itself, only the doc-comment.

**`core/errors.py`:** add `InvalidRole(RelayError)`, sibling to
`InvalidParent`.

**CLI (`cli/__main__.py`, `cli/commands/relay_cmds.py`):**
- `__main__.py`: add `sp_peers_setrole = sp_peers_sub.add_parser("set-role",
  ...)` next to the existing `sp_peers_setparent` (lines 97-103), with
  positional args `name` and `role` (`choices=["parent", "child"]`,
  matching `sp_reg.add_argument("--role", choices=["parent", "child"], ...)`
  at line 56).
- `relay_cmds.py cmd_peers`: add an `elif getattr(args, "peers_action", None)
  == "set-role":` branch beside the existing `set-parent` branch (lines
  123-130), calling `store.set_role`, catching `(PeerNotFound, InvalidRole)`,
  printing `f"{peer.name}: role set to {peer.role}"` to match the
  `set-parent` branch's `f"{peer.name}: parent set to {peer.parent}"` style.

**TUI:**
- `screens/peers.py`: add a binding, e.g. `("r,R", "set_role", "Set role")`,
  to `BINDINGS` (alongside `rebind_session`'s `u` binding, lines 15-23).
  `action_set_role` follows `action_rebind_session`'s shape (lines 128-135):
  require a selected peer, push a new small modal, refresh + notify on
  return.
- New `tui/widgets/set_role_modal.py` (or fold into `peer_admin.py`
  alongside `RemovePeerConfirm`/`GcStaleModal`): a `ModalScreen` showing the
  peer's current role and a `Select`/toggle for the new value, `y`/Enter to
  confirm, `Esc` to cancel — same interaction shape as `RemovePeerConfirm`.
  Calls `store.set_role`, catches `InvalidRole`/`PeerNotFound` and
  `self.notify(..., severity="error")` the same way `AddPeerModal.submit`
  does (lines 81-84).
- No change needed to `acting_as_candidates()` (`store.py:189-198`) or the
  acting-as union filters added by the 2026-07-15 spec — changing `role`
  after the fact is exactly the kind of update those filters are already
  built to react to correctly (a peer that gains `role=="parent"` via
  `set_role` becomes acting-as-eligible on the next read, with no separate
  wiring).

## Testing

Extend the 2026-07-15 spec's test matrix (`core/store.py` tests) rather than
replacing it:

- `set_role` happy path: register a peer `role="child"`, call
  `set_role(name, "parent")`, assert `get_peer(name).role == "parent"` and
  `parent` field unchanged.
- `set_role` invalid role: `set_role(name, "bogus")` raises `InvalidRole`.
- `set_role` unknown peer: raises `PeerNotFound`.
- **Orthogonality, extended**: register a peer, give it a child via
  `set_parent`, call `set_role` on it, assert the child's `parent` pointer
  is untouched and the peer's own `parent` is untouched — `set_role` must
  only ever write the `role` key.
- **Reverse orthogonality**: call `set_role`, then `set_parent` on the same
  peer, assert `role` is unchanged by the `set_parent` call — confirms the
  new setter didn't accidentally get invoked by, or get merged into, the
  structural path.
- CLI: `downbeat peers set-role <name> parent` exit 0 + expected stdout;
  unknown peer name exit 1 with `error: ...`; invalid role value rejected by
  argparse `choices` before reaching the store.
- TUI: `set_role_modal` confirm calls `store.set_role` with the selected
  value and dismisses with the peer name; cancel calls neither.

## Migration / backward-compat

Option A requires none: `Peer`'s shape is unchanged, `role`'s two literal
values are unchanged, and every existing `sessions.json` entry already has a
valid `role`. No `Peer.from_dict` change, no `sessions.json` rewrite.

(Option B's migration/back-compat burden — compat reads, hook-asset
version skew, `SKILL.md`/`relay-monitor.md` contract changes — is detailed
under "Option B" above and does not apply if A ships as recommended.)

## Open decisions for the maintainer

1. **A vs. B — ship the minimal setter now, or do the `role`→`autonomy`
   rename in the same pass?** This spec recommends A now, B later-if-ever.
   Confirm or override.
2. **`register_peer` re-register behavior**: should re-registering an
   existing peer with a different `--role` be *left as-is* (documented
   footgun, `set_role` becomes the intended path per this spec), *warned*
   (non-fatal notice that autonomy changed), or *hard-blocked* (require
   `set_role` explicitly, reject a `--role` mismatch on re-register)? This
   spec proposes documentation-only as the minimal option; a stricter
   behavior is a legitimate but separate call.
3. **Value naming, if B is ever taken**: keep the literal strings
   `"parent"`/`"child"` under a renamed field (`autonomy: str  # "parent" |
   "child"`, minimizing value-level churn), or also rename the values
   themselves (e.g. `"auto"`/`"ask"`, more literally describing the
   autonomy behavior but a larger blast radius across
   `relay-monitor.md`/`relay-inbox.py`/`SKILL.md` string comparisons)?
4. **TUI binding key**: `r` is proposed for "set role" on `PeersScreen`
   (`BINDINGS`, `screens/peers.py:15-23`) — it's currently unused there, but
   confirm no conflict with a planned future binding before landing.
