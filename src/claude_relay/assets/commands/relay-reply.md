---
description: Reply to a relay message you previously received
argument-hint: <msg_id> <body...>
---

Reply to a previously received relay message. Arguments: $ARGUMENTS

## If `$ARGUMENTS` is EMPTY — treat this as an INBOX CHECK, not a reply

A bare `/relay-reply` (no `<msg_id>`) is the user's inbox-check shortcut. Do this:

1. Look at the CURRENT turn's context for a `### Relay inbox — N new message(s)` banner (the hook drains the inbox into context on each prompt). That block IS your pending mail.
2. If none is in context, verify directly: `claude-relay whoami` for your peer name, then check `~/.claude/relay/inbox/<me>/` and `~/.claude/relay/delivered/<me>/` for `.json` files.
3. **If there ARE pending messages** (especially from the parent) → surface them and reply/handle as appropriate (fall through to the reply flow below with the real `<msg_id>`).
4. **If there are NONE → SKIP. Take no action.** Do not fabricate a reply, do not invent a `<msg_id>`, and do NOT send proactive/unsolicited messages to the parent. Just report "inbox empty, nothing to reply to" and stop.

## If `$ARGUMENTS` has a msg_id + body — reply normally

Parse `$ARGUMENTS` as: `<msg_id> <body...>` where `<msg_id>` is the 16-char hex id from a message in your inbox (look at the most recent relay message context), and the rest is the reply body.

If the body is long or multi-line:

```
~/.claude/relay/relay.py reply <msg_id> "$(cat <<'EOF'
<body>
EOF
)"
```

Otherwise:

```
~/.claude/relay/relay.py reply <msg_id> "<body>"
```

The reply is routed to the original sender's inbox using the `from` field of the message stored under `~/.claude/relay/processed/<your_name>/<msg_id>.json`. If the CLI errors with "msg_id not found", the message was either never received here or already replied to in a way that moved it.
