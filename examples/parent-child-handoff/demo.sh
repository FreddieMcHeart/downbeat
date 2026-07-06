#!/usr/bin/env bash
# Runnable version of this directory's README walkthrough: register two peers,
# hand a task from parent to child, reply, read the result back.
set -euo pipefail

echo "== register demo-parent =="
downbeat register demo-parent --role parent

echo "== register demo-child =="
downbeat register demo-child --role child

echo "== send: demo-parent -> demo-child =="
downbeat send demo-child "task" "Write a haiku about parallel agents" --from demo-parent

echo "== demo-child's inbox =="
downbeat inbox --peer demo-child

# `downbeat inbox` has no --json output yet, so pick the newest message file for
# this peer directly off disk to get its id for the reply below. `ls -t` is safe
# here (not find+stat, for macOS/Linux portability): msg_id filenames are always
# plain hex, never contain spaces/newlines/globs.
# shellcheck disable=SC2012
msg_id="$(basename "$(ls -t ~/.claude/relay/inbox/demo-child/*.json | head -1)" .json)"

echo "== reply: demo-child -> demo-parent (msg_id=$msg_id) =="
downbeat reply "$msg_id" "Three agents typing / one human watching closely / tempo never lost" --from demo-child

echo "== demo-parent's inbox =="
downbeat inbox --peer demo-parent

echo
echo "Done. Try 'downbeat tui' to see the same conversation in the management UI."
