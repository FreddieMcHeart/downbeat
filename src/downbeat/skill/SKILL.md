---
name: downbeat
description: Use when coordinating or handing off work between parallel Claude Code sessions on one machine — sending a task or prompt to another running session, replying with results, or checking whether the other terminal received or answered. Triggers on phrasings like "send this to the other terminal/session/tab/window/pane", "hand off this task/phase", "ask/tell the other Claude session", "send to my child/parent session", "did the other session receive/reply?", "what did the other terminal say?", "check the relay inbox", "is my other session done?", "relay message", and any /relay-* slash command. Runs the local `downbeat` CLI.
---

# Claude Relay

Local file-based message broker for handing off work between parallel Claude Code sessions on the same machine.

## Quick reference

The CLI is `downbeat` (the `/relay-*` slash commands wrap these):

| Need | Command |
|---|---|
| Who am I here? | `downbeat whoami` (`--json` for `{name, role}`) |
| Who can I reach? | `downbeat peers` |
| Send work to a peer | `downbeat send <peer> "<subject>" "<body>"` |
| Reply to a message | `downbeat reply <id> "<body>"` (auto-acks the original) |
| Check my mail | `downbeat inbox` |
| Confirm consumption | `downbeat ack <id>…` (only if you won't reply) |
| Full management UI | `downbeat tui` |

> Legacy alias: `~/.claude/relay/relay.py <cmd>` is a shim `downbeat init` installs so
> old slash commands keep working. `downbeat` is canonical — a fresh install that skipped
> `downbeat init` has no shim, so always prefer `downbeat`.

## When to use

- User asks to hand off work to another running Claude Code terminal
- User asks "did the other session reply?", "ask the X terminal", "send this to my child session"
- User invokes any `/relay-*` slash command
- You see a system context block titled `### Relay inbox — N new message(s)` — that IS an inbound relay message; treat it as authoritative

## When NOT to use

- Ephemeral scout work → use the `Agent` tool, not relay
- Background async tasks → relay is sync at next-turn (the user's prompt is the trigger)
- Cross-machine handoffs → same-host only
- Plain copy-paste of a short prompt → no value over manual paste

## Context-aware offer: schedule an inbox poll when you're about to wait

Do NOT offer a /loop poll by default. Only offer it when the conversation is about to idle waiting for a peer reply. Concretely, offer the poll AFTER one of these moments:

1. The user just sent a message via `send` (or `/relay-send`) and gave no follow-up task to work on locally. The conversation pauses on the receiving peer.
2. The user just sent a reply via `reply` (or `/relay-reply`) and the parent peer is expected to acknowledge or assign next work.
3. The user explicitly says any of: "let me know when X replies", "ping me when done", "wait for the other session", "watch the inbox", "babysit this".

DO NOT offer when:
- The current invocation is a read-only check (`peers`, `inbox` with no follow-up)
- A `/loop` related to relay is already running in this session
- A relay message just arrived (the user is responding, not waiting)
- The user already declined the offer earlier in this session
- The user has zero peers registered (suggest registering instead)

When you DO offer, use AskUserQuestion with:

> "You just sent a message to <peer>. Want me to check the inbox every 3 minutes for a reply and surface it when it arrives?"

Options:
- "Yes, poll every 3 min" — invoke /loop with:
  `/loop 3m Check the relay inbox via downbeat inbox. If there are new messages addressed to a peer I'm registered as, surface them concisely (sender, subject, id) and ask the user how to handle each. If the inbox is empty, stay silent — do not interrupt with "no messages".`
- "Yes, poll every 5 min" — same instruction, /loop 5m
- "No, I'll check manually" — do not start a loop. Record this choice so we don't re-offer in this session.

After the question is answered (Yes or No), remember the decision for the rest of the session. If the user later types `/loop stop` or closes the session, the loop is gone — no need to re-offer until a new "about to wait" moment.

## Registration + automatic idle-notify

After a child registers (`downbeat register <name>`), no manual step is needed for
always-on mail awareness: if `downbeat tui` is open, its resident watcher fires a
native OS notification the moment mail arrives for an idle (>10min) peer; if the TUI
isn't open, the same notification fires from a Claude Code session's own hook on its
next `send`/`reply`. Notify-only in both cases — the human still drives action.
`/relay-monitor` is the separate in-session role-aware auto-acting option, costing a
model turn per tick.

## Continuous self-monitoring

Running `/relay-monitor [interval]` makes THIS session keep processing its own inbox on an
interval — no external observer needed. Behaviour is role-asymmetric:

- **child (executor):** auto-executes each arriving task per role briefing, then replies and
  acks. Autonomous — the human gave consent at startup.
- **parent:** surfaces new messages concisely (from / subject / id) and waits for the human
  to decide how to handle each. Never auto-executes.

Stop with `/relay-monitor stop`. Note: `/relay-monitor` is a Claude Code slash command, not a
CLI subcommand.

`downbeat whoami` prints this session's `<name> <role>` (machine-parseable, one line).
Use `--json` for `{"name": ..., "role": ...}`.

## Three flows

### 1. SEND (you are the Parent)

For multi-line bodies, always use heredoc — naive quoting breaks on backticks/quotes/`$`:

```bash
downbeat send <peer_name> "<short subject>" "$(cat <<'EOF'
<full multi-line prompt>
EOF
)"
```

After sending, tell the user the msg_id from the CLI output. The peer will see it on their next prompt. Do not poll.

If `send` errors with "no peer named X", run `downbeat peers` to show registered names.

### 2. RECEIVE + REPLY (you are the Child)

When the user's turn includes a system block titled `### Relay inbox — N new message(s)`, that block has `from:`, `id:`, `subject:` and the body. After completing the work:

```bash
downbeat reply <id> "$(cat <<'EOF'
<your report — what was done, files changed, blockers>
EOF
)"
```

### 3. CHECK / MANAGE

- `downbeat peers` — list registered peers
- `downbeat inbox` — your pending messages
- `downbeat tui` — full management TUI (read, edit, delete, broadcast)

## Delivery acknowledgement

When you process a Relay inbox banner (the `### Relay inbox — N new message(s)`
block), after you've taken action on the messages (replied, internalized, or
decided to ignore), run:

    downbeat ack <id1> <id2> ...

This confirms consumption. Without an ack, the relay's reconciler re-queues
unacknowledged messages after 30 minutes (up to 3 redeliveries, then
quarantine). Replying via `reply` auto-acks the original — no separate ack
needed in that case.

If you decide to ignore a message but want to stop the redelivery loop,
ack it explicitly. The ack is the model's promise that the message was
seen and acted upon.
