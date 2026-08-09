"""Implementation of every `downbeat <subcommand>`."""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta

from ...core import session, store
from ...core.errors import (
    AmbiguousParent,
    InvalidParent,
    InvalidPeerName,
    MessageNotFound,
    PeerNameCollision,
    PeerNotFound,
    PeerReparentConflict,
    PeerSessionTakeover,
)
from ...core.models import CURRENT_SCHEMA_VERSION


def _detect_peer_or_error(name: str | None, *, flag: str = "--peer") -> str:
    # `flag` is the override option the CALLING subcommand exposes for passing
    # the peer name explicitly — `--peer` for inbox/quarantine/whoami, `--from`
    # for send/reply. It only names the right escape hatch in the error text;
    # a shared hardcoded flag would tell an inbox caller to "pass --from", which
    # inbox doesn't accept (the exact trap a background session fell into).
    if name:
        return name
    sid = session.detect_session_id()
    if not sid:
        print(f"error: could not detect session id; pass {flag} explicitly",
              file=sys.stderr)
        raise SystemExit(2)
    # Fast path: direct session_id match
    for peer in store.list_peers():
        if peer.session_id == sid:
            return peer.name
    # A history hit is a LEAD, not a licence to take the record (#88).
    #
    # `session_id_history` cannot distinguish "the same agent, resumed under a
    # new id" from "a different agent that once held this name" — on disk they
    # are the same shape. Auto-rebinding on that signal made routing
    # nondeterministic whenever two live sessions were both in one record's
    # history: each session's next command took the record back, and printed
    # the theft as a success. Measured in production as six rebinds on one
    # record, five of them alternating between two live ids, none an error.
    #
    # #71 settled that a guess is worse than a refusal, because a guess binds a
    # session to the WRONG identity. This is exactly that case, so it reports
    # and hands the decision to a human. The word "provable" in the message
    # this replaces was the tell: the history proves this id once held the
    # name, which is not the question being asked.
    history_candidates = store.find_peer_by_session_history(sid)
    if len(history_candidates) == 1:
        peer = history_candidates[0]
        print(f"error: session {sid[:8]} is not registered.\n"
              f"  It appears in the session_id_history of peer {peer.name!r}, "
              f"currently bound to session {peer.session_id[:8]}.\n"
              f"  That is a lead, not proof — the history cannot tell a "
              f"resumed session apart from a different one that once held the "
              f"name, so the identity is not reassigned automatically.\n"
              f"  If this session IS {peer.name!r}:  downbeat rebind "
              f"{peer.name!r}\n"
              f"  If it is not, register under a different name.",
              file=sys.stderr)
        raise SystemExit(2)
    if len(history_candidates) > 1:
        names = [c.name for c in history_candidates]
        print(f"error: ambiguous — session {sid} appears in the "
              f"session_id_history of multiple peers ({names}); pass {flag} "
              "explicitly to disambiguate", file=sys.stderr)
        raise SystemExit(2)
    # Slow path: try auto-rebind via (claude_pid, claude_pid_start) tuple
    # (/clear: same OS process, new session id)
    claude_pid = session.detect_live_claude_pid()
    if claude_pid is None:
        print(f"error: session {sid} is not registered; run "
              "`downbeat register`", file=sys.stderr)
        raise SystemExit(2)
    claude_pid_start = session.process_start_time(claude_pid)
    candidates = store.find_peer_by_claude_pid(claude_pid, claude_pid_start)
    if len(candidates) == 1:
        peer = candidates[0]
        store.rebind_session(peer.name, new_session_id=sid)
        print(f"[rebind] {peer.name}: session_id updated "
              f"{peer.session_id[:8]}→{sid[:8]} "
              f"(claude PID {claude_pid} unchanged)",
              file=sys.stderr)
        return peer.name
    if len(candidates) > 1:
        names = [c.name for c in candidates]
        print(f"error: multiple peers ({names}) share claude_pid={claude_pid}; "
              f"pass {flag} explicitly to disambiguate", file=sys.stderr)
        raise SystemExit(2)
    print(f"error: session {sid} is not registered; run "
          "`downbeat register`", file=sys.stderr)
    raise SystemExit(2)


def cmd_gc_markers(args: argparse.Namespace) -> int:
    counts = session.gc_stale_markers()
    print(f"pruned stale markers: tmp={counts['tmp']} relay={counts['relay']}")
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    import os
    # Sweep stale markers first so subsequent detects don't trust them
    session.gc_stale_markers()
    sid = session.detect_session_id()
    if sid is None:
        # Best-effort: synthesize from our pid
        sid = f"unknown-{os.getpid()}"
    cwd = os.getcwd()
    claude_pid = session.detect_live_claude_pid()
    claude_pid_start = session.process_start_time(claude_pid) if claude_pid else None
    try:
        peer = store.register_peer(
            name=args.name, session_id=sid, cwd=cwd, role=args.role,
            claude_pid=claude_pid, claude_pid_start=claude_pid_start,
            parent=getattr(args, "parent", None),
        )
    except (AmbiguousParent, InvalidParent, PeerReparentConflict,
            PeerSessionTakeover) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    session.write_marker_for_self(sid)
    parent_suffix = f", parent={peer.parent}" if peer.parent else ""
    print(f"registered: {peer.name} (session={peer.session_id}, role={peer.role}{parent_suffix})")
    if claude_pid:
        print(f"  claude_pid={claude_pid} start={claude_pid_start}")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    sender = _detect_peer_or_error(args.from_peer, flag="--from")
    try:
        msg = store.send_message(from_peer=sender, to_peer=args.to,
                                 subject=args.subject, body=args.body,
                                 kind=args.kind)
    except PeerNotFound:
        print(f"error: no peer named {args.to!r}", file=sys.stderr)
        return 2
    print(f"sent: {msg.id}")
    return 0


def cmd_reply(args: argparse.Namespace) -> int:
    sender = _detect_peer_or_error(args.from_peer, flag="--from")
    try:
        reply = store.reply_to(args.msg_id, body=args.body, from_peer=sender,
                               kind=args.kind)
    except MessageNotFound:
        print(f"error: no message with id {args.msg_id!r}", file=sys.stderr)
        return 2
    print(f"replied: {reply.id}")
    return 0


def cmd_broadcast(args: argparse.Namespace) -> int:
    sender = _detect_peer_or_error(args.from_peer, flag="--from")
    # No default target set (#97 Decision 2): a broadcast with an implicit
    # target is precisely the shape where one mistake reaches every peer at
    # once, so the caller must say who -- --to, --all-children, or both,
    # union'd and deduplicated, never a silent guess in either direction.
    targets = list(dict.fromkeys(args.to or []))
    if args.all_children:
        for peer in store.children_of(sender):
            if peer.name != sender and peer.name not in targets:
                targets.append(peer.name)
    if not targets:
        print("error: no targets given; pass --to (repeatable) or "
              "--all-children", file=sys.stderr)
        return 2
    # Pre-flight every target before sending any (--to is free text, unlike
    # the TUI's list-picker, so a typo is newly reachable here): send_message
    # resolves each recipient in turn, so without this a bad name mid-list
    # left earlier targets already delivered while the error discarded the
    # broadcast_id, leaving no way to name what had landed. Not
    # transactional -- a peer removed between this check and the send below
    # still splits the fan-out -- this closes the reachable case (a typo),
    # not the whole class.
    unknown = [name for name in targets if not _peer_exists(name)]
    if unknown:
        print(f"error: no peer(s) named {', '.join(repr(n) for n in unknown)}",
              file=sys.stderr)
        return 2
    try:
        bc = store.broadcast(from_peer=sender, to_peers=targets,
                             subject=args.subject, body=args.body,
                             kind=args.kind)
    except PeerNotFound as e:
        print(f"error: no peer named {str(e)!r}", file=sys.stderr)
        return 2
    print(f"broadcast: {bc.id}")
    return 0


def _peer_exists(name: str) -> bool:
    try:
        store.get_peer(name)
        return True
    except PeerNotFound:
        return False


def cmd_inbox(args: argparse.Namespace) -> int:
    peer = _detect_peer_or_error(args.peer, flag="--peer")
    msgs = store.list_inbox(peer, include_archived=args.all)
    if not msgs:
        print(f"inbox empty for {peer}")
        return 0
    for m in msgs:
        flag = {"new": "*", "read": " ", "delivered": "~",
                "quarantined": "!", "archived": "."}[m.state.value]
        print(f"{flag} {m.id}  {m.created_at}  {m.from_peer:<16}  {m.subject}")
    return 0


def cmd_peers(args: argparse.Namespace) -> int:
    if getattr(args, "peers_action", None) == "set-parent":
        try:
            peer = store.set_parent(args.child_name, args.parent_name)
        except (PeerNotFound, InvalidParent) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"{peer.name}: parent set to {peer.parent}")
        return 0
    if getattr(args, "peers_action", None) == "rename":
        try:
            peer = store.rename_peer(args.old_name, args.new_name)
        except (PeerNotFound, PeerNameCollision, InvalidPeerName) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"renamed: {args.old_name} → {peer.name} "
              "(messages, directories, parent pointers, and groups migrated)")
        return 0
    peers = store.list_peers()
    if not peers:
        print("no peers registered")
        return 0
    for p in peers:
        parent_suffix = f"  parent={p.parent}" if p.parent else ""
        print(f"{p.name:<24}  id={p.peer_id}  role={p.role:<6}  "
              f"session={p.session_id}  "
              f"last_seen={p.last_seen}{parent_suffix}")
    return 0


def cmd_gc_stale(args: argparse.Namespace) -> int:
    threshold = datetime.now(UTC)
    if args.days is not None:
        threshold -= timedelta(days=args.days)
    elif args.hours is not None:
        threshold -= timedelta(hours=args.hours)
    else:
        threshold -= timedelta(days=14)
    pruned = []
    for p in store.list_peers():
        try:
            ls = datetime.fromisoformat(p.last_seen)
        except ValueError:
            continue
        if ls < threshold:
            store.remove_peer(p.name)
            pruned.append(p.name)
    print(f"pruned {len(pruned)} stale peers: {pruned}")
    return 0


def cmd_rebind(args: argparse.Namespace) -> int:
    from ...core.errors import RelayError
    try:
        peer = store.rebind_session(args.name, args.session_id)
    except PeerNotFound:
        print(f"error: no peer named {args.name!r}", file=sys.stderr)
        return 2
    except RelayError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    # Also write a self-marker so future auto-detect finds the new mapping
    if args.session_id is None:
        session.write_marker_for_self(peer.session_id)
    print(f"rebound: {peer.name} (session={peer.session_id}, role={peer.role})")
    return 0


def cmd_drain(args: argparse.Namespace) -> int:
    msgs = store.deliver_messages(peer_name=args.peer, session_id=args.session_id,
                                  max=args.max)
    print(f"delivered {len(msgs)} messages to {args.peer}")
    for m in msgs:
        print(f"  {m.id}  from={m.from_peer}  subject={m.subject!r}")
    return 0


def cmd_ack(args: argparse.Namespace) -> int:
    # ack only acts on delivered/. When it can't ack an id, say WHY — a bare
    # "· <id>" reads as a mystery failure. The common background-session case
    # is mail still sitting in inbox/ (never drained to delivered/), which ack
    # legitimately can't touch; without this the recipient thinks ack is broken.
    results = store.ack_messages(args.ids)
    okay = sum(1 for v in results.values() if v)
    print(f"acked {okay}/{len(args.ids)}")
    for mid, ok in results.items():
        if ok:
            print(f"  ✓ {mid}")
            continue
        loc = store.locate_message(mid)
        if loc == "inbox":
            reason = ("still in inbox — never delivered, so there is nothing to "
                      "ack. Replying auto-acks; or drain it from the recipient "
                      "session (a turn there, or its TUI)")
        elif loc == "processed":
            reason = "already processed/acked"
        elif loc == "quarantine":
            reason = "in quarantine — `downbeat quarantine requeue` first"
        elif loc is None:
            reason = "not found in this relay"
        else:
            reason = f"in {loc}"
        print(f"  · {mid} — {reason}")
    return 0 if okay == len(args.ids) else 2


def cmd_reconcile(args: argparse.Namespace) -> int:
    counts = store.reconcile(window_minutes=args.window_minutes,
                             max_redelivery=args.max_redelivery)
    print(f"reconciled: promoted={counts['promoted']} "
          f"auto_acked={counts['auto_acked']} "
          f"requeued={counts['requeued']} quarantined={counts['quarantined']}")
    if counts["quarantined"] > 0:
        print(f"⚠ {counts['quarantined']} message(s) quarantined — "
              "check ~/.claude/relay/quarantine/")
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    counts = store.migrate_store(dry_run=args.dry_run)
    print(f"scanned {counts['scanned']} message file(s) across "
          "inbox/ delivered/ processed/ quarantine/")
    verb = "would migrate" if args.dry_run else "migrated"
    print(f"{verb} {counts['migrated']} file(s) to schema "
          f"v{CURRENT_SCHEMA_VERSION}; "
          f"{counts['current']} already current")
    if counts["ids_backfilled"]:
        # Counts MESSAGES touched, not id fields written — a message can gain
        # both ends. Say which, so the number can't be read as the other.
        print(f"resolved identity for {counts['ids_backfilled']} message(s) "
              "from the peer registry")
    if args.dry_run:
        print("dry run — nothing written")
    if counts["unreadable"]:
        print(f"⚠ {counts['unreadable']} file(s) could not be read — left "
              "untouched (corrupt, or written by a newer downbeat)")
    return 0


def cmd_quarantine(args: argparse.Namespace) -> int:
    peer = _detect_peer_or_error(args.peer, flag="--peer")
    action = args.quarantine_action
    if action == "list":
        msgs = store.list_quarantined(peer)
        if not msgs:
            print(f"no quarantined messages for {peer}")
            return 0
        for m in msgs:
            print(f"! {m.id}  {m.quarantined_at or ''}  "
                  f"{m.from_peer:<16}  {m.subject}")
        return 0
    ids = args.id if args.id else None
    if action == "requeue":
        count = store.requeue_quarantined(peer, ids=ids)
        print(f"requeued {count} quarantined message(s) to inbox for {peer}")
    elif action == "purge":
        count = store.purge_quarantined(peer, ids=ids)
        print(f"purged {count} quarantined message(s) for {peer}")
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    import json
    name = _detect_peer_or_error(args.peer, flag="--peer")
    peer = store.get_peer(name)
    if args.json:
        print(json.dumps({"name": peer.name, "role": peer.role}))
    else:
        print(f"{peer.name} {peer.role}")
    return 0


def cmd_tui(args: argparse.Namespace) -> int:
    from ...tui.app import RelayApp
    RelayApp().run()
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    from .init_cmd import run_init, run_migrate_to_plugin
    if args.migrate_to_plugin:
        return run_migrate_to_plugin()
    return run_init(force=args.force)


def cmd_uninstall(args: argparse.Namespace) -> int:
    from .init_cmd import run_uninstall
    return run_uninstall()
