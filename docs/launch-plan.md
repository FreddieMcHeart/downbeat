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

## Rename migration: `claude-relay` → `downbeat`

Big, mechanical, test-guarded. Executed as a coordinated pass (parent pinged
before/after — it touches the live relay channel).

**Scoped IN** (source/package identity — the actual launch-blocker):
- [ ] Repo rename (`gh repo rename`) + update `origin` remote + local checkout dir
- [ ] Python package/module rename `claude_relay` → `downbeat` (entry point, imports,
  all test files)
- [ ] pyproject.toml: `name`, `[project.scripts]` binary, `[tool.hatch...packages]`, `[project.urls]`
- [ ] `SHIM_TEMPLATE` content in `init_cmd.py` + the already-installed live shim file
  (same path `~/.claude/relay/relay.py`, new content pointing at the `downbeat` binary)
- [ ] Re-point editable install (`uv tool install --editable`) + rebuild `.venv` (both
  bindings — see the mama/mondu relocation lesson)
- [ ] Update README / CONTRIBUTING / docs referencing the `claude-relay` CLI command
- [ ] PyPI first publish under `downbeat` (blocked on release-setup.md's manual steps)

**Also IN scope** (correctness — these describe a fact about the CLI binary that's
changing, so leaving them stale would be a bug, not a style choice):
- [ ] Every `claude-relay <verb>` CLI-invocation example inside asset file CONTENT
  (SKILL.md, `assets/commands/relay-*.md`, `assets/hooks_manifest.json`'s comment) →
  `downbeat <verb>`.
- [ ] The packaged skill's own identity (`SKILL.md`'s `name:` frontmatter) → `downbeat`,
  and `_skill_install_dir()` in `init_cmd.py` → `skills/downbeat` (low-risk, avoids a
  confusing mismatch between "the skill named downbeat" living in a folder called
  "claude-relay"). The now-orphaned `~/.claude/skills/claude-relay/` gets removed as
  part of the live-sync step.

**Deliberately scoped OUT** (deferred to Phase 2's Claude Code plugin repackaging —
decisions.md #15 — since these get restructured there anyway; renaming twice is wasted
work):
- `~/.claude/relay/` runtime data directory path (`RELAY_DIR`) — stays as-is. Renaming
  it now would orphan every live peer's `sessions.json`/inbox mid-conversation for zero
  Phase-1 benefit.
- Hook script FILENAMES (`relay-inbox.py`, `relay-poll-offer.py`) — filenames stay;
  their content is still updated per the "also in scope" note above.
- Slash-command FILENAMES (`relay-register.md` etc., invoked as `/relay-send` etc.) —
  filenames stay (still `/relay-send`); Phase 2's plugin packaging will likely
  re-namespace these anyway (`/downbeat:send` or similar), so renaming the .md files
  now would be redone.
- Peer names / `sessions.json` content — entirely unrelated to the package name, not
  touched by this migration at all.

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
