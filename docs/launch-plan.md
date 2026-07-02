# downbeat — launch & GTM plan

> **Status:** pre-launch planning. This file is the durable home for go-to-market /
> launch-channel items — the "GTM place." Full option analysis lives in
> [oss-readiness-research.md](./oss-readiness-research.md) (§Positioning + §Phased roadmap).

## Name decision (2026-07-01)

**Name: `downbeat`** — the conductor's downward baton stroke that starts the whole
ensemble together and sets the tempo. Maps to the product: *you give the downbeat →
your parallel agents start in sync → you keep the tempo.* Human-in-the-loop +
orchestration in one word.

Chosen over `baton` (the first pick) after availability checks: **`baton` is taken in
our exact niche** — `getbaton.dev` ("Run AI Coding Agents in Parallel") and
`mraza007/baton` ("autonomous coding agent orchestrator... runs Claude Code CLI"),
plus PyPI `baton` (iRODS wrapper). `downbeat` verdict:

| Check | Result |
|---|---|
| PyPI `downbeat` | FREE ✅ (the critical one) |
| Niche (AI-agent / CLI space) | clean ✅ — no collision |
| GitHub org `downbeat` | taken by an unrelated user (CAN-bus/gaze) → use `<owner>/downbeat`; bare org not required |
| npm `downbeat` | undetermined (Python tool — low priority) |
| Domain `downbeat.dev` | TODO: check at registrar |

**Tagline (T2+T3):** *"Stop copy-pasting between AI terminals — orchestrate a team of
parallel coding agents from one place, locally, where you're the conductor. Nothing
happens without you."*

## Rename migration: `claude-relay` → `downbeat` (future work — its own phase)

Big, mechanical, test-guarded. NOT a launch blocker for identity; do as a dedicated phase.

- [ ] Repo rename + update `origin` remote
- [ ] Python package/module rename `claude_relay` → `downbeat` (entry point, imports, 26 test files, shim, `init` paths, hook/command filenames + settings.json regs)
- [ ] Re-point editable install (`uv tool install --editable`) + rebuild `.venv` (both bindings — see the relocation lesson)
- [ ] PyPI first publish under `downbeat`
- [ ] Update README / docs / skill references / banner strings

## GTM / launch channels (Phase 3 — after OSS-hygiene + docs land)

- [ ] **List in [`bradAGI/awesome-cli-coding-agents`](https://github.com/bradAGI/awesome-cli-coding-agents)** — curated directory of "terminal-native AI coding agents and the harnesses that orchestrate them... parallel runners, autonomous loops, agent infrastructure." **This is exactly our shelf.** Open a PR to add `downbeat` once the repo is public. *(This is the "GTM find" from the OSS research — now captured here.)*
- [ ] Other awesome-lists: `awesome-claude-code`, `awesome-tuis`, `awesome-python`
- [ ] Show HN — draft: *"Show HN: downbeat — a local, human-in-the-loop message bus for your parallel AI coding agents"*
- [ ] Reddit: r/commandline, r/ClaudeAI
- [ ] shields.io badges: PyPI version, CI status, license, Python versions
- [ ] Social-preview (Open Graph) image for the GitHub repo
- [ ] Demo GIF (VHS `.tape`) embedded in README + PyPI
- [ ] Domain `downbeat.dev` (optional landing / redirect to repo)

## Sequencing (from the research roadmap)

1. **Phase 1 — launch-blockers:** LICENSE file ✅, PEP 639 SPDX + classifiers/urls ✅, CONTRIBUTING/COC/SECURITY ✅, `--version` + error-wrap ✅, CI (uv + macOS matrix) ✅, semantic-release + Trusted Publishing pipeline (code ✅, manual GitHub/PyPI setup pending — see [release-setup.md](./release-setup.md)), name decision ✅ (downbeat), rename execution (pending, coordinate with parent first), first PyPI release (blocked on rename + release-setup.md).
2. **Phase 2 — polish:** docs site, VHS demo, examples/, README upgrade, UX fixes, Claude Code plugin repackaging.
3. **Phase 3 — growth:** the GTM/launch-channels list above (incl. the awesome-list PR).
