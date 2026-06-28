"""Implementation of every `claude-relay <subcommand>`."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime, timedelta

from ...core import session, store
from ...core.errors import MessageNotFound, PeerNotFound
from ...core.models import MessageState


def _detect_peer_or_error(name: str | None) -> str:
    if name:
        return name
    sid = session.detect_session_id()
    if not sid:
        print("error: could not detect session id; pass --from explicitly",
              file=sys.stderr)
        raise SystemExit(2)
    # Fast path: direct session_id match
    for peer in store.list_peers():
        if peer.session_id == sid:
            return peer.name
    # Slow path: try auto-rebind via (claude_pid, claude_pid_start) tuple
    claude_pid = session.detect_live_claude_pid()
    if claude_pid is None:
        print(f"error: session {sid} is not registered; run "
              "`claude-relay register`", file=sys.stderr)
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
              "pass --from explicitly to disambiguate", file=sys.stderr)
        raise SystemExit(2)
    print(f"error: session {sid} is not registered; run "
          "`claude-relay register`", file=sys.stderr)
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
    peer = store.register_peer(
        name=args.name, session_id=sid, cwd=cwd, role=args.role,
        claude_pid=claude_pid, claude_pid_start=claude_pid_start,
    )
    session.write_marker_for_self(sid)
    print(f"registered: {peer.name} (session={peer.session_id}, role={peer.role})")
    if claude_pid:
        print(f"  claude_pid={claude_pid} start={claude_pid_start}")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    sender = _detect_peer_or_error(args.from_peer)
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
    sender = _detect_peer_or_error(args.from_peer)
    try:
        reply = store.reply_to(args.msg_id, body=args.body, from_peer=sender,
                               kind=args.kind)
    except MessageNotFound:
        print(f"error: no message with id {args.msg_id!r}", file=sys.stderr)
        return 2
    print(f"replied: {reply.id}")
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    peer = _detect_peer_or_error(args.peer)
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
    peers = store.list_peers()
    if not peers:
        print("no peers registered")
        return 0
    for p in peers:
        print(f"{p.name:<24}  role={p.role:<6}  session={p.session_id}  "
              f"last_seen={p.last_seen}")
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
    results = store.ack_messages(args.ids)
    okay = sum(1 for v in results.values() if v)
    print(f"acked {okay}/{len(args.ids)}")
    for mid, ok in results.items():
        marker = "✓" if ok else "·"
        print(f"  {marker} {mid}")
    return 0 if okay == len(args.ids) else 2


def cmd_reconcile(args: argparse.Namespace) -> int:
    counts = store.reconcile(window_minutes=args.window_minutes,
                             max_redelivery=args.max_redelivery)
    print(f"reconciled: promoted={counts['promoted']} "
          f"requeued={counts['requeued']} quarantined={counts['quarantined']}")
    if counts["quarantined"] > 0:
        print(f"⚠ {counts['quarantined']} message(s) quarantined — "
              "check ~/.claude/relay/quarantine/")
    return 0


def cmd_quarantine(args: argparse.Namespace) -> int:
    peer = _detect_peer_or_error(args.peer)
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
    name = _detect_peer_or_error(None)
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


def cmd_watch(args: argparse.Namespace) -> int:
    peer = _detect_peer_or_error(args.peer)

    if args.once:
        # --once: announce everything currently NEW (start with empty seen)
        seen: set[str] = set()
        new_msgs, _ = store.poll_new(peer, seen)
        if new_msgs:
            print("NEW RELAY MESSAGE(S):")
            for m in new_msgs:
                print(f"* {m.id}  {m.created_at}  {m.from_peer}  {m.subject}")
        return 0

    # Seed seen with current NEW ids so a pre-populated inbox is NOT re-announced.
    seed = {m.id for m in store.list_inbox(peer)
            if m.state == MessageState.NEW}
    seen = seed

    try:
        while True:
            time.sleep(args.interval)
            new_msgs, seen = store.poll_new(peer, seen)
            if new_msgs:
                print("NEW RELAY MESSAGE(S):")
                for m in new_msgs:
                    print(f"* {m.id}  {m.created_at}  {m.from_peer}  {m.subject}")
            elif not args.quiet:
                pass  # suppress idle heartbeat; keep output clean
    except KeyboardInterrupt:
        print("[watch] stopped")
        return 0


def cmd_init(args: argparse.Namespace) -> int:
    from .init_cmd import run_init
    return run_init(force=args.force)


def cmd_uninstall(args: argparse.Namespace) -> int:
    from .init_cmd import run_uninstall
    return run_uninstall()
