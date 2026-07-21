---
description: Reply to a relay message you previously received
argument-hint: <msg_id> <body...>
---

Reply to a previously received relay message. Arguments: $ARGUMENTS

## If `$ARGUMENTS` is EMPTY — treat this as an INBOX CHECK, not a reply

**This command is overloaded on purpose:** with no `<msg_id>` it does NOT reply —
it checks your inbox. (There is deliberately no separate `/relay-inbox` command;
a bare `/relay-reply` is the inbox-check shortcut.) Do this:

1. Look at the CURRENT turn's context for a `### Relay inbox — N new message(s)` banner (the hook drains the inbox into context on each prompt). That block IS your pending mail.
2. If none is in context, verify directly: run `downbeat inbox --peer <me>` (peer name from `downbeat whoami` if unknown). Do NOT `ls`/read raw JSON under `inbox/<me>/` or `delivered/<me>/` by hand — the default view already excludes `processed/` (archived-on-reply) and is the correct "still genuinely open" set; manually inspecting only `inbox/<me>/` misses messages the relay-inbox hook already drained into `delivered/<me>/`, which are unreplied but not "new."
3. **If there ARE pending messages** (especially from the parent) → surface them and reply/handle as appropriate (fall through to the reply flow below with the real `<msg_id>`).
4. **If there are NONE → SKIP. Take no action.** Do not fabricate a reply, do not invent a `<msg_id>`, and do NOT send proactive/unsolicited messages to the parent. Just report "inbox empty, nothing to reply to" and stop.

## If `$ARGUMENTS` has a msg_id + body — reply normally

Parse `$ARGUMENTS` as: `<msg_id> <body...>` where `<msg_id>` is the 16-char hex id from a message in your inbox (look at the most recent relay message context), and the rest is the reply body.

If the body is long or multi-line:

```
downbeat reply <msg_id> "$(cat <<'EOF'
<body>
EOF
)"
```

Otherwise:

```
downbeat reply <msg_id> "<body>"
```

The reply is routed to the original sender's inbox using the `from` field of the message stored under `~/.claude/relay/processed/<your_name>/<msg_id>.json` (that path is the relay's on-disk data dir, not a CLI). If the CLI errors with "msg_id not found", the message was either never received here or already replied to in a way that moved it.

<!-- Legacy alias: `~/.claude/relay/relay.py reply …` (a shim `downbeat init` installs) still works, but `downbeat` is canonical — prefer it. -->
