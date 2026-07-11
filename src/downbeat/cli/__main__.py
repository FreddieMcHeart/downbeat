"""downbeat command-line entry point."""
from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version

from rich_argparse import RichHelpFormatter

from ..core import logging as relay_logging
from ..core.errors import RelayError
from .commands import relay_cmds


class _RichArgumentParser(argparse.ArgumentParser):
    """ArgumentParser defaulting to RichHelpFormatter.

    Passed as `parser_class` to every add_subparsers() call so every
    subcommand (including nested ones, e.g. quarantine's list/requeue/purge)
    gets the same colorized --help rendering as the top-level parser — a
    functools.partial would work at runtime too, but doesn't satisfy
    add_subparsers()'s `type[ArgumentParser]` parser_class annotation.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", RichHelpFormatter)
        super().__init__(*args, **kwargs)


def _version_string() -> str:
    try:
        return f"downbeat {version('downbeat')}"
    except PackageNotFoundError:
        return "downbeat (unknown version — not installed as a package)"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="downbeat", formatter_class=RichHelpFormatter)
    p.add_argument("--version", action="version", version=_version_string())
    p.add_argument("--debug", action="store_true",
                   help="enable DEBUG-level logging")

    # Shared parent so every subparser also accepts --debug after the verb.
    # Built as _RichArgumentParser (not plain ArgumentParser) so its type
    # matches what add_subparsers(parser_class=_RichArgumentParser) expects
    # for the `parents=` argument on every add_parser() call below.
    debug_parent = _RichArgumentParser(add_help=False)
    debug_parent.add_argument("--debug", action="store_true",
                              help="enable DEBUG-level logging")

    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_RichArgumentParser)

    sp_reg = sub.add_parser("register", help="register this session as a peer",
                            parents=[debug_parent])
    sp_reg.add_argument("name")
    sp_reg.add_argument("--role", choices=["parent", "child"], default="child")
    sp_reg.add_argument("--parent", default=None,
                        help="name of the role=parent peer this child is joining "
                             "(required for --role child unless exactly one parent "
                             "peer is currently registered)")
    sp_reg.set_defaults(func=relay_cmds.cmd_register)

    sp_send = sub.add_parser("send", help="send a message",
                             parents=[debug_parent])
    sp_send.add_argument("to")
    sp_send.add_argument("subject")
    sp_send.add_argument("body")
    sp_send.add_argument("--from", dest="from_peer", default=None,
                         help="sender peer name; auto-detected if omitted")
    sp_send.add_argument("--kind", default="task",
                         help='message kind: "task" (default), "backflow-ready", '
                              'or any future kind (open string)')
    sp_send.set_defaults(func=relay_cmds.cmd_send)

    sp_reply = sub.add_parser("reply", help="reply to a message",
                              parents=[debug_parent])
    sp_reply.add_argument("msg_id")
    sp_reply.add_argument("body")
    sp_reply.add_argument("--from", dest="from_peer", default=None)
    sp_reply.add_argument("--kind", default="task",
                          help='message kind: "task" (default), "backflow-ready", '
                               'or any future kind (open string)')
    sp_reply.set_defaults(func=relay_cmds.cmd_reply)

    sp_inbox = sub.add_parser("inbox", help="list messages for a peer",
                              parents=[debug_parent])
    sp_inbox.add_argument("--peer", default=None,
                          help="peer name; auto-detected if omitted")
    sp_inbox.add_argument("--all", action="store_true",
                          help="include archived messages")
    sp_inbox.set_defaults(func=relay_cmds.cmd_inbox)

    sp_peers = sub.add_parser("peers", help="list registered peers",
                              parents=[debug_parent])
    sp_peers_sub = sp_peers.add_subparsers(dest="peers_action", required=False,
                                           parser_class=_RichArgumentParser)
    sp_peers_setparent = sp_peers_sub.add_parser(
        "set-parent",
        help="backfill/repoint an existing child peer's parent without full re-register",
        parents=[debug_parent])
    sp_peers_setparent.add_argument("child_name")
    sp_peers_setparent.add_argument("parent_name")
    sp_peers.set_defaults(func=relay_cmds.cmd_peers)

    sp_gc = sub.add_parser("gc-stale", help="prune stale sessions",
                           parents=[debug_parent])
    sp_gc.add_argument("--hours", type=int, default=None)
    sp_gc.add_argument("--days", type=int, default=None)
    sp_gc.set_defaults(func=relay_cmds.cmd_gc_stale)

    sp_gcm = sub.add_parser("gc-markers", help="prune stale session markers",
                            parents=[debug_parent])
    sp_gcm.set_defaults(func=relay_cmds.cmd_gc_markers)

    sp_rebind = sub.add_parser("rebind",
                               help="update a peer's session_id (preserves role/cwd)",
                               parents=[debug_parent])
    sp_rebind.add_argument("name")
    sp_rebind.add_argument("--session-id", dest="session_id", default=None,
                           help="explicit session_id; auto-detected if omitted")
    sp_rebind.set_defaults(func=relay_cmds.cmd_rebind)

    sp_quar = sub.add_parser("quarantine",
                             help="manage quarantined messages",
                             parents=[debug_parent])
    sp_quar.add_argument("--peer", default=None,
                         help="peer name; auto-detected if omitted")
    sp_quar_sub = sp_quar.add_subparsers(dest="quarantine_action", required=True,
                                         parser_class=_RichArgumentParser)

    sp_qlist = sp_quar_sub.add_parser("list", help="list quarantined messages",
                                      parents=[debug_parent])
    sp_qlist.set_defaults(id=None)  # no --id for list

    sp_qreq = sp_quar_sub.add_parser("requeue",
                                     help="move quarantined messages back to inbox",
                                     parents=[debug_parent])
    sp_qreq.add_argument("--id", nargs="*", dest="id", default=None,
                         help="specific message ids; omit for all")

    sp_qpurge = sp_quar_sub.add_parser("purge",
                                       help="permanently delete quarantined messages",
                                       parents=[debug_parent])
    sp_qpurge.add_argument("--id", nargs="*", dest="id", default=None,
                           help="specific message ids; omit for all")

    sp_quar.set_defaults(func=relay_cmds.cmd_quarantine)

    sp_whoami = sub.add_parser("whoami",
                               help="print this session's peer name and role",
                               parents=[debug_parent])
    sp_whoami.add_argument("--json", action="store_true",
                           help='output as JSON {"name": ..., "role": ...}')
    sp_whoami.set_defaults(func=relay_cmds.cmd_whoami)

    sp_tui = sub.add_parser("tui", help="launch the TUI",
                            parents=[debug_parent])
    sp_tui.set_defaults(func=relay_cmds.cmd_tui)

    sp_drain = sub.add_parser("drain", help="drain inbox to delivered (used by hook)",
                              parents=[debug_parent])
    sp_drain.add_argument("--peer", required=True)
    sp_drain.add_argument("--session-id", required=True, dest="session_id")
    sp_drain.add_argument("--max", type=int, default=20)
    sp_drain.set_defaults(func=relay_cmds.cmd_drain)

    sp_ack = sub.add_parser("ack", help="confirm consumption of delivered messages",
                            parents=[debug_parent])
    sp_ack.add_argument("ids", nargs="+")
    sp_ack.set_defaults(func=relay_cmds.cmd_ack)

    sp_rec = sub.add_parser("reconcile", help="re-queue or quarantine stale delivered messages",
                            parents=[debug_parent])
    sp_rec.add_argument("--window-minutes", type=int, default=30)
    sp_rec.add_argument("--max-redelivery", type=int, default=3)
    sp_rec.set_defaults(func=relay_cmds.cmd_reconcile)

    sp_watch = sub.add_parser("watch", help="watch inbox for new messages",
                              parents=[debug_parent])
    sp_watch.add_argument("--peer", default=None,
                          help="peer name; auto-detected if omitted")
    sp_watch.add_argument("--interval", type=int, default=90,
                          help="poll interval in seconds (default: 90)")
    sp_watch.add_argument("--once", action="store_true",
                          help="poll once and exit (announces all current NEW)")
    sp_watch.add_argument("--quiet", action="store_true",
                          help="suppress idle output; print only on new messages")
    sp_watch.add_argument("--poll", action="store_true",
                          help="force poll fallback instead of event-driven")
    sp_watch.set_defaults(func=relay_cmds.cmd_watch)

    sp_init = sub.add_parser("init", help="bootstrap relay dir, skill, shim",
                             parents=[debug_parent])
    sp_init.add_argument("--force", action="store_true")
    sp_init.add_argument("--migrate-to-plugin", action="store_true",
                         dest="migrate_to_plugin",
                         help="remove legacy hand-merged relay hooks now that the "
                              "Claude Code plugin owns hook registration; standalone "
                              "mode, does not also run the rest of init")
    sp_init.set_defaults(func=relay_cmds.cmd_init)

    sp_uninst = sub.add_parser("uninstall", help="remove skill + restore shim",
                               parents=[debug_parent])
    sp_uninst.set_defaults(func=relay_cmds.cmd_uninstall)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    relay_logging.setup(level="DEBUG" if args.debug else "INFO")
    try:
        return args.func(args)
    except (SystemExit, KeyboardInterrupt):
        raise
    except RelayError as e:
        # Any RelayError subclass a subcommand forgot to catch locally still
        # lands here — defense in depth so a bug never surfaces as a raw
        # traceback to an end user.
        print(f"error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
