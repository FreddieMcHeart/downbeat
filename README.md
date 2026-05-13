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

| Key            | Action                              |
|----------------|-------------------------------------|
| Up/Down        | Move cursor through message bubbles |
| Tab/Shift+Tab  | Cycle peer tabs                     |
| Enter          | Send (in composer)                  |
| e              | Edit focused message (only NEW)     |
| d              | Delete focused message (confirm)    |
| v              | View full body of focused message   |
| Shift+B        | Broadcast status for selected       |
| Ctrl+P         | Peers screen (add / remove / gc)    |
| f              | Find message by id                  |
| F1             | Help                                |
| F5             | Refresh                             |
| F6             | Toggle log viewer                   |
| q              | Quit                                |

## Uninstall

```bash
claude-relay uninstall    # removes skill + shim; leaves data in ~/.claude/relay
```

## Layout

- Source: `src/claude_relay/{core,cli,tui,skill}`
- Tests: `tests/`
- State: `~/.claude/relay/{sessions.json, inbox/, processed/, logs/, groups.json}`
