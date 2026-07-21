---
description: Continuously monitor THIS session's relay inbox in-session (child=auto-execute, parent=surface-and-ask)
argument-hint: [interval e.g. 3m | stop]
---

Start (or stop) continuous in-session monitoring of this session's own relay inbox. Arguments: $ARGUMENTS

This composes two existing primitives: the `/loop` skill (re-fires a prompt on an interval) + the `relay-inbox` hook (drains inbox→delivered and injects new mail as context on every prompt). The result: this session keeps pulling its own new relay mail into context and acting on it per its role — without you re-prompting each tick.

## Steps

1. **Parse `$ARGUMENTS`:**
   - If it is the literal `stop` → invoke `/loop stop` to end the running monitor, report "relay monitor stopped", and finish.
   - Otherwise treat it as the interval (default `3m` if empty).

2. **Resolve this session's role:**
   ```
   downbeat whoami
   ```
   Output is `<name> <role>`. If it errors (exit 2), tell the user to `/relay-register <name> --role <parent|child>` first and stop.

3. **If a relay `/loop` is already running this session**, do NOT stack a second one — tell the user it's already monitoring (and they can `/relay-monitor stop` to reset). Otherwise start `/loop <interval>` with the role-appropriate prompt below.

4. **Start the loop** — `/loop <interval> "<prompt>"`:

   - **role == child** (autonomous executor — consent-at-startup per constitution Art. 11):
     > Process your relay inbox now. The relay-inbox hook has injected any new messages as context above. For each NEW message: execute the task per your role briefing (you are an executor — route reads through reader sub-agents, follow cost discipline, no [TICKET] in this repo's commits), then `downbeat reply <id> "<results>"` (replying auto-acks). If there are NO new messages this tick, do nothing and stay quiet. Never re-do an already-handled message. If a task is ambiguous or carries irreversible/destructive risk, do NOT auto-execute it — surface it and wait for the human instead.

   - **role == parent** (gated — surface only):
     > Check your relay inbox. If the hook injected new messages, surface them concisely (from / subject / id) and ask me how to handle each. Do NOT auto-execute, reply, or act on my behalf. If nothing new, stay quiet.

5. Report that the monitor is running, the interval, the role-mode (child=auto-execute / parent=surface-and-ask), and that `/relay-monitor stop` ends it.

## Notes

- This is the **in-session self-driver**. For a passive nudge instead — a native OS notification when mail arrives for an idle peer — no separate command is needed: `downbeat tui` notifies automatically while open, and a Claude Code session's own hook covers the headless case.
- The child autonomy here is **consent-at-startup**: you explicitly started the monitor on an executor session. It is scoped to executors, never auto-executes for a parent, and is stoppable. See `docs/platform/constitution.md` Art. 11.

<!-- Legacy alias: `~/.claude/relay/relay.py <cmd>` (a shim `downbeat init` installs) still works, but `downbeat` is canonical — prefer it. -->
