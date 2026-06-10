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

### Background inbox polling

The first time you invoke a relay action in a Claude Code session, the skill
offers to start a 3-minute inbox poll via `/loop`. Accept to get notified of
incoming messages without having to manually check.

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
