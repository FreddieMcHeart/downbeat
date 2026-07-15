# Example: parent → child task handoff

The core downbeat loop in five commands: register two peers, hand off a task, reply,
read the result back. Run it as-is in one terminal (it's just two local peer
identities, not two real Claude Code sessions), or split the `demo-parent` and
`demo-child` commands across two real terminals/sessions to see it end to end.

Run the whole thing with `./demo.sh`, or follow along by hand:

```bash
downbeat register demo-parent --role parent
downbeat register demo-child  --role child
```

```
registered: demo-parent (session=<your-session-id>, role=parent)
  claude_pid=<pid> start=<timestamp>
registered: demo-child (session=<your-session-id>, role=child)
  claude_pid=<pid> start=<timestamp>
```

Send a task from parent to child:

```bash
downbeat send demo-child "task" "Write a haiku about parallel agents" --from demo-parent
```

```
sent: 2109acbe49b7
```

Check the child's inbox:

```bash
downbeat inbox --peer demo-child
```

```
* 2109acbe49b7  2026-07-06T09:57:03.191747+00:00  demo-parent       task
```

Reply from the child (real usage: a registered Claude Code session does this itself,
driven by the `relay-inbox.py` hook surfacing the message at the next prompt — see the
[docs site](https://freddiemcheart.github.io/downbeat/)):

```bash
downbeat reply 2109acbe49b7 "Three agents typing / one human watching closely / tempo never lost" --from demo-child
```

```
replied: bcf95c86d663
```

Read the reply back on the parent side:

```bash
downbeat inbox --peer demo-parent
```

```
* bcf95c86d663  2026-07-06T09:57:16.479584+00:00  demo-child        Re: task
```

That's the whole lifecycle: `inbox/<peer>/*.json` on send, moved to
`processed/<peer>/*.json` once handled — see the
[architecture notes](../../docs/decisions.md) for the full state model.

## Next steps

- `downbeat tui` — full management UI over the same data instead of raw CLI calls;
  also fires an automatic native notification for idle-peer mail while it's open.
- `/relay-monitor` (inside a registered Claude Code session) — the self-driving,
  role-aware version of the same loop; see the main [README](../../README.md).
