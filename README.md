# claude-relay

Local filesystem-backed message broker + TUI + CLI + skill for handing off work between parallel Claude Code sessions on the same machine.

## Install

```bash
uv tool install claude-relay     # or: pipx install claude-relay
claude-relay init                # bootstraps ~/.claude/relay, installs the skill, replaces relay.py shim
```

## Use

```bash
claude-relay register parent --role parent
claude-relay register child  --role child
claude-relay send child "task" "do the thing"
claude-relay inbox --peer child
claude-relay reply <msg_id> "done"
claude-relay tui                 # full management UI
```

`kind` is an open string: `task` (default for all normal messages) and `backflow-ready`
(structured RLM findings from a child — see the claude-relay skill). Future kinds
(`workflow-request`, `workflow-result`) are planned for Phase 3.

### Always-on inbox watch

Give a child session always-on inbox awareness after pairing:

```bash
claude-relay watch                     # event-driven (fswatch/FSEvents); instant, ~0 idle cost
claude-relay watch --peer child-1      # parent watching a child's inbox
claude-relay watch --poll              # force poll fallback (every --interval seconds)
claude-relay watch --interval 30       # poll fallback interval (default: 90s)
claude-relay watch --once              # one-shot: print all current NEW, then exit
```

Run `claude-relay watch` in the child terminal (or as a Monitor job) immediately
after `claude-relay register`. The watcher notifies only — it never drains, acks,
or takes any action. The human (or the session's hook at the next prompt) drives action.
Stop with Ctrl+C.

`watch` is event-driven by default (uses watchdog FSEvents/inotify — fires instantly on
inbox changes, near-zero idle CPU). If watchdog is unavailable it falls back to polling
automatically and prints `[watch] polling every Ns` on startup so you always know which
backend is active. Use `--poll` to force the interval fallback regardless.

**watch-vs-monitor cost table:**

| Want | Use | Cost on idle channel |
|---|---|---|
| Cheap notify-to-wake, you act when woken | `claude-relay watch` as a Monitor | ~0 (blocks on FS event; model turn only on real mail) |
| Session auto-acts role-aware on a cadence | `/relay-monitor` (/loop) | a model turn every interval |

### Background inbox polling

The first time you invoke a relay action in a Claude Code session, the skill
offers to start a 3-minute inbox poll via `/loop`. Accept to get notified of
incoming messages without having to manually check.

### Continuous self-monitoring (/relay-monitor)

In a registered Claude Code session, run the `/relay-monitor` slash command to make that
session continuously pull its own inbox and act on new messages:

```
/relay-monitor          # start monitoring, default 3-minute interval
/relay-monitor 5m       # custom interval
/relay-monitor stop     # stop
```

Behaviour is role-asymmetric:

- **child session:** auto-executes arriving tasks per its role briefing and replies with results
  (consent-at-startup autonomy).
- **parent session:** surfaces new messages concisely and asks the human how to handle each;
  never auto-executes.

Before starting the monitor, check your identity with:

```bash
claude-relay whoami          # prints: <name> <role>
claude-relay whoami --json   # prints: {"name": "...", "role": "..."}
```

**watch vs /relay-monitor — key distinction:**

| | `claude-relay watch` | `/relay-monitor` |
|---|---|---|
| Runs as | external process (pane / Monitor job) | in-session `/loop` |
| Backend | event-driven (FSEvents/inotify), poll fallback | timer-based loop |
| Does | prints new mail to a pane (human reads) | session pulls mail into its own context + acts per role |
| Acts? | never | child: yes (autonomous); parent: no (surfaces) |
| Idle cost | ~0 (event-driven; model turn only on real mail) | a model turn every interval |
| Use when | operator watching from outside | a session should self-drive on its inbox |

Both tools are complementary and can be run simultaneously.

### TUI keybindings

| Key           | Action                                               |
|---------------|------------------------------------------------------|
| Tab/Shift+Tab | Cycle focus: Messages → Composer                     |
| s             | Switch acting-as parent                              |
| Left/Right    | Prev / next group member                             |
| Up/Down       | Within focused region (messages, composer)           |
| Enter         | Send (in composer) / Open message detail (in message list) |
| Escape / q    | Back (in message detail)                             |
| e             | Edit (in message detail, only NEW)                   |
| r             | Reply (in message detail)                            |
| d             | Delete with confirm (in message detail)              |
| Shift+B       | Broadcast status (in message detail, when applicable) |
| y             | Yank (copy) message body to clipboard (chat view and message detail) |
| c             | Copy message id to clipboard (in message detail)     |
| Up/k, Down/j  | Scroll up / down in message detail                   |
| Ctrl+B / PgUp | Page up in message detail (Fn+↑ alias)               |
| Ctrl+F / PgDn | Page down in message detail (Fn+↓ alias)             |
| g / Home      | Top of message detail (Fn+← alias)                  |
| G / End       | Bottom of message detail (Fn+→ alias)                |
| Ctrl+P        | Peers screen (add / remove / gc)                     |
| f             | Find message by id                                   |
| ? / F1        | Help                                                 |
| Ctrl+R        | Refresh                                              |
| Ctrl+L / F6   | Toggle log viewer                                    |
| q             | Quit                                                 |

## Uninstall

```bash
claude-relay uninstall    # removes skill + shim; leaves data in ~/.claude/relay
```

## Layout

- Source: `src/claude_relay/{core,cli,tui,skill}`
- Tests: `tests/`
- State: `~/.claude/relay/{sessions.json, inbox/, processed/, logs/, groups.json}`
