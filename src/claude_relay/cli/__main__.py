"""claude-relay command-line entry point."""
from __future__ import annotations

import argparse
import sys

from ..core import logging as relay_logging
from .commands import relay_cmds


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="claude-relay")
    p.add_argument("--debug", action="store_true",
                   help="enable DEBUG-level logging")

    # Shared parent so every subparser also accepts --debug after the verb.
    debug_parent = argparse.ArgumentParser(add_help=False)
    debug_parent.add_argument("--debug", action="store_true",
                              help="enable DEBUG-level logging")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp_reg = sub.add_parser("register", help="register this session as a peer",
                            parents=[debug_parent])
    sp_reg.add_argument("name")
    sp_reg.add_argument("--role", choices=["parent", "child"], default="child")
    sp_reg.set_defaults(func=relay_cmds.cmd_register)

    sp_send = sub.add_parser("send", help="send a message",
                             parents=[debug_parent])
    sp_send.add_argument("to")
    sp_send.add_argument("subject")
    sp_send.add_argument("body")
    sp_send.add_argument("--from", dest="from_peer", default=None,
                         help="sender peer name; auto-detected if omitted")
    sp_send.set_defaults(func=relay_cmds.cmd_send)

    sp_reply = sub.add_parser("reply", help="reply to a message",
                              parents=[debug_parent])
    sp_reply.add_argument("msg_id")
    sp_reply.add_argument("body")
    sp_reply.add_argument("--from", dest="from_peer", default=None)
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
    sp_peers.set_defaults(func=relay_cmds.cmd_peers)

    sp_gc = sub.add_parser("gc-stale", help="prune stale sessions",
                           parents=[debug_parent])
    sp_gc.add_argument("--hours", type=int, default=None)
    sp_gc.add_argument("--days", type=int, default=None)
    sp_gc.set_defaults(func=relay_cmds.cmd_gc_stale)

    sp_rebind = sub.add_parser("rebind",
                               help="update a peer's session_id (preserves role/cwd)",
                               parents=[debug_parent])
    sp_rebind.add_argument("name")
    sp_rebind.add_argument("--session-id", dest="session_id", default=None,
                           help="explicit session_id; auto-detected if omitted")
    sp_rebind.set_defaults(func=relay_cmds.cmd_rebind)

    sp_tui = sub.add_parser("tui", help="launch the TUI",
                            parents=[debug_parent])
    sp_tui.set_defaults(func=relay_cmds.cmd_tui)

    sp_init = sub.add_parser("init", help="bootstrap relay dir, skill, shim",
                             parents=[debug_parent])
    sp_init.add_argument("--force", action="store_true")
    sp_init.set_defaults(func=relay_cmds.cmd_init)

    sp_uninst = sub.add_parser("uninstall", help="remove skill + restore shim",
                               parents=[debug_parent])
    sp_uninst.set_defaults(func=relay_cmds.cmd_uninstall)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    relay_logging.setup(level="DEBUG" if args.debug else "INFO")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
