---
description: Reply to a relay message you previously received
argument-hint: <msg_id> <body...>
---

Reply to a previously received relay message. Arguments: $ARGUMENTS

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
