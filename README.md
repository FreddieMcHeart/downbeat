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

### TUI keybindings

| Key     | Action                        |
|---------|-------------------------------|
| Enter   | Open / mark read              |
| n       | New message                   |
| r       | Reply                         |
| e       | Edit (only NEW)               |
| d       | Delete (confirm)              |
| b       | Toggle broadcast in composer  |
| Shift+B | Broadcast status for selected |
| F1      | Help                          |
| F5      | Refresh                       |
| F6      | Toggle log viewer             |
| q       | Quit                          |

## Uninstall

```bash
claude-relay uninstall    # removes skill + shim; leaves data in ~/.claude/relay
```

## Layout

- Source: `src/claude_relay/{core,cli,tui,skill}`
- Tests: `tests/`
- State: `~/.claude/relay/{sessions.json, inbox/, processed/, logs/, groups.json}`
