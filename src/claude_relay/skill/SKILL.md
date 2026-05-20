---
name: claude-relay
description: Use when handing off work between parallel Claude Code sessions on this machine — Parent (planning/Opus) sending implementation prompts to a Child (executing) session, Child replying with results, or the user asking "did the other terminal receive/reply." Triggers on phrases like "send to other terminal", "hand off this phase", "ask the other Claude session", "send this to my child session", "relay message", and any /relay-* slash command. Invokes the local CLI `claude-relay`.
---

# Claude Relay

Local file-based message broker for handing off work between parallel Claude Code sessions on the same machine.

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

## First-invocation offer: schedule a 3-minute inbox poll

On the FIRST time this skill triggers in a session AND the user has at least one peer registered (`~/.claude/relay/relay.py peers` returns non-empty), use the AskUserQuestion tool to ask:

> "Start an automatic inbox check every 3 minutes? When new relay messages arrive, I'll surface them and ask how to handle them."

Options:
- "Yes, poll every 3 min (Recommended)" — invoke /loop with 3-minute cadence:
  `/loop 3m Check the relay inbox via ~/.claude/relay/relay.py inbox. If there are new messages addressed to a peer I am registered as, surface them concisely (sender, subject, id) and ask the user how to handle each. If the inbox is empty, stay silent — do not interrupt with a "no messages" notification.`
- "Yes, poll every 5 min" — same instruction, /loop 5m
- "No, manual only" — do not start a loop

After the user picks, remember the choice for this session (do not re-ask in the same session). If the user explicitly wants to stop the loop later, they can type `/loop stop` or close the session.

Do NOT offer this if:
- A relay /loop is already running this session
- The user has zero peers registered (offer to register one instead)
- This is itself a /loop tick (i.e., the skill was triggered BY the loop)

## Three flows

### 1. SEND (you are the Parent)

For multi-line bodies, always use heredoc — naive quoting breaks on backticks/quotes/`$`:

```bash
claude-relay send <peer_name> "<short subject>" "$(cat <<'EOF'
<full multi-line prompt>
EOF
)"
```

After sending, tell the user the msg_id from the CLI output. The peer will see it on their next prompt. Do not poll.

If `send` errors with "no peer named X", run `claude-relay peers` to show registered names.

### 2. RECEIVE + REPLY (you are the Child)

When the user's turn includes a system block titled `### Relay inbox — N new message(s)`, that block has `from:`, `id:`, `subject:` and the body. After completing the work:

```bash
claude-relay reply <id> "$(cat <<'EOF'
<your report — what was done, files changed, blockers>
EOF
)"
```

### 3. CHECK / MANAGE

- `claude-relay peers` — list registered peers
- `claude-relay inbox` — your pending messages
- `claude-relay tui` — full management TUI (read, edit, delete, broadcast)
