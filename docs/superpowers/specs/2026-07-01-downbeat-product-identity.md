---
title: downbeat — product identity & positioning
date: 2026-07-01
status: approved
supersedes_name: claude-relay
tags: [spec, product-identity, positioning, open-source]
---

# downbeat — product identity

> The foundational "what is this / why does it exist / what are its boundaries" definition.
> Everything downstream — README, positioning, naming, docs structure, and which UX bugs to
> fix first — flows from this. Approved via brainstorm 2026-07-01.

## Name & tagline

- **Name:** `downbeat` (was `claude-relay`; rename is tracked in [launch-plan.md](../../launch-plan.md)).
  The conductor's downward baton stroke that starts the ensemble together and sets the tempo.
- **Tagline:** *"Stop copy-pasting between AI terminals — orchestrate a team of parallel
  coding agents from one place, locally, where you're the conductor. Nothing happens without you."*

## What it is (elevator)

A **local, no-infrastructure layer** through which a **human** coordinates several parallel
AI-coding-agent sessions on one machine: one session hands work to another, gets a report back,
with reliable delivery and the human on every consequential gate. The core is **agent-neutral**;
the first live integration is Claude Code.

## Why it's needed (pain hierarchy)

1. **P1 (primary) — handoff friction between parallel sessions.** Today you copy-paste between
   terminals, lose the thread of "who is doing what," and messages slip by. This is the headline.
2. **P2 — no structure for human-led delegation.** You want to run a PM/architect session that
   delegates to executor sessions and gets reports back — but there's no scaffolding for it.
3. **P3 — unreliability / message loss.** Fire-and-forget drops, duplicates, or forgets messages.
   Solved by the `delivered → ack → reconcile → quarantine` delivery state machine.

## Who it's for

A developer **already** running 2+ parallel AI-coding sessions (Claude Code today) who wants to
drive them as a lightweight team — without going to the cloud and without giving up control.

## What it is NOT (boundaries)

- **NOT an autonomous swarm.** A human is required in the loop; agents do not act without a gate.
  *(This is the core differentiator — cf. autonomous frameworks rejected on this exact axis.)*
- **NOT cloud / SaaS.** Local only: filesystem-backed, private, offline.
- **NOT an agent framework** (LangGraph / AutoGen). It does not write or run agents; it coordinates
  already-running sessions.
- **NOT a task tracker / Jira.** Messages and handoffs, not backlogs and sprints.
- **NOT Claude-only at the core.** Claude Code is today's integration; the core is agent-neutral.

## Origin

Born from a real parent/child workflow: one Claude session acting as PM/architect delegated tasks
to executor sessions on one machine, and the children reported back. A `relay.py` script grew into
a TUI + CLI + library + skill with delivery semantics. **The tool came from practice, not from an
idea** — which is why the boundaries above are lived, not theoretical.

## The wedge (differentiator)

`human-in-the-loop` + `local / no-infra` + `delivery guarantees`. Against autonomous swarms: you
never lose control. Against cloud orchestrators: nothing leaves your machine.

## Identity trajectory

- **Now (C):** agent-neutral core, single working integration = Claude Code, honestly stated
  ("works with Claude Code today; architecture is agent-neutral; other integrations welcome").
- **North star (B):** several first-class agent integrations (Cursor, Codex, Aider, …).

## Downstream implications (not decided here)

- **README / positioning** should lead with P1 (handoff) + the human-in-the-loop wedge.
- **Naming migration** `claude-relay → downbeat`: tracked in launch-plan.md (its own phase).
- **UX-fix prioritisation** should favor the P1/P2 paths (handoff + delegation) first.
- **Docs** should make the "you are the conductor" mental model explicit early.
