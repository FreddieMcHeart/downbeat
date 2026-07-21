---
description: Send a relay message to a peer Claude Code session
argument-hint: <to> <subject> <body...>
---

Send a relay message. Arguments: $ARGUMENTS

Parse `$ARGUMENTS` as: `<to> <subject> <body...>` where `<to>` is the peer name, `<subject>` is a single token (use quotes if multi-word), and everything after is the body.

If the body is long or multi-line, pass it via a heredoc — naive quoting breaks on backticks, quotes, and `$`:

```
downbeat send <to> "<subject>" "$(cat <<'EOF'
<body>
EOF
)"
```

Otherwise call directly:

```
downbeat send <to> "<subject>" "<body>"
```

Report the CLI's output (it includes the message id). The peer will receive the message on their next prompt or session start, prepended as system context by the `relay-inbox` hook.

<!-- Legacy alias: `~/.claude/relay/relay.py send …` (a shim `downbeat init` installs) still works, but `downbeat` is canonical — prefer it. -->
