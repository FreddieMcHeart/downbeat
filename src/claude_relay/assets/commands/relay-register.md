---
description: Register this Claude Code session in the relay so peers can send it messages
argument-hint: <name> [--role parent|child]
---

Register this session in the relay with name and role from: $ARGUMENTS

Run exactly:

```
~/.claude/relay/relay.py register $ARGUMENTS
```

If the user provided no `--role`, the CLI defaults to `child`.

Report the CLI's output back verbatim. Do not retry on failure — surface the error to the user.
