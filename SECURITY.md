# Security Policy

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting:

1. Go to the [**Security** tab](../../security) of this repository.
2. Click **"Report a vulnerability"**.
3. Fill in as much detail as you can — steps to reproduce, affected version,
   and potential impact.

This opens a private advisory visible only to you and the maintainer, so the
issue can be discussed and fixed before public disclosure.

If GitHub's private reporting is unavailable for any reason, you may instead
contact the maintainer directly through the contact information on their
GitHub profile.

## Scope

This tool is a **local, filesystem-backed** message broker — it has no server
component and does not transmit data over the network by design. Relevant
security-sensitive areas include:

- Message/session data stored under `~/.claude/relay/` (local filesystem
  permissions).
- The `init`/`uninstall` commands, which write files into `~/.claude/hooks/`,
  `~/.claude/commands/`, and merge entries into `~/.claude/settings.json`.
- Any code path that shells out or reads/writes outside the relay's own data
  directory.

## Supported Versions

Security fixes are made against the latest released version on PyPI. There is
no long-term-support branch at this stage of the project.

## Response

This is a solo-maintained open-source project. There is no guaranteed
response SLA, but reports are triaged as soon as possible after they're
received.
