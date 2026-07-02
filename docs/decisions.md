# downbeat — OSS-prep decisions (locked)

> Decided 2026-07-01 with the maintainer, walking [oss-readiness-research.md](./oss-readiness-research.md)
> topic by topic. This is the execution backlog. Where a decision overrides the research's
> recommendation, it's marked **[override]**. Name + identity: see
> [product-identity](./superpowers/specs/2026-07-01-downbeat-product-identity.md); GTM: [launch-plan.md](./launch-plan.md).

## Decision table

| # | Area | Decision | Phase |
|---|---|---|---|
| — | **Name** | `downbeat` (rename from claude-relay is its own phase) | 1 |
| 1 | License | **MIT** — add real `LICENSE` file, migrate to PEP 639 SPDX (`license = "MIT"` + `license-files`), add classifiers/keywords/`[project.urls]` | 1 |
| 2 | Contribution sign-off | **DCO** (one CONTRIBUTING line + DCO bot); lock before first external PR | 1 |
| 3 | Community-health | **Minimal baseline**: CONTRIBUTING, CODE_OF_CONDUCT (Contributor Covenant 2.1), SECURITY (GitHub Private Vulnerability Reporting) + **Issue Forms** (bugs, with TUI/CLI/lib/skill surface dropdown) + **Discussions** (ideas). README borrows Best-README-Template badge/ToC conventions | 1 |
| 4 | Versioning | **[override]** Dynamic, owned by **python-semantic-release** (derived from Conventional Commits) — not static | 1 |
| 5 | Type checker | **pyright** (~98% conformance vs ty ~53%) | 2 |
| 6 | Coverage | **pytest-cov + coverage-comment-action** (no external account/Codecov) | 2 |
| 7 | Release automation | **[override]** **python-semantic-release, FULL-AUTO (7a)** — qualifying merge to `main` → version bump + CHANGELOG + tag + build + publish to PyPI. Auth via **Trusted Publishing (OIDC)** | 1 |
| 8 | OS matrix | Add **macOS** leg (keep Linux; py3.11–3.13) | 1 |
| 9 | Dependency updates | **Dependabot** | 2 |
| 10 | Demo recording | **VHS** (`.tape` → GIF, regenerated in CI via vhs-action) | 2 |
| 11 | CLI polish | **rich-argparse** + **`--version`/`-V`** (importlib.metadata) + error-message wrapping (no raw tracebacks) | 1 (version+errors) / 2 (rich) |
| 12 | Install channel | **PyPI-only** (`uv tool install` headline, pipx/pip fallback, `uvx …` zero-install trial) + DX polish (`examples/` parent/child transcript, troubleshooting, uninstall docs). Skip Homebrew + single-file binaries | 1 (release) / 2 (DX) |
| 13 | Docs site | **[chosen]** **MkDocs Material** (Diátaxis structure), hosted on **GitHub Pages** (`mkdocs gh-deploy`) | 2 |
| 14 | Positioning | Ship **comparison table** vs `agent-message-queue` + `cc2cc` (lead on the **TUI** + one-command `init` differentiator); position as the **substrate** under orchestration frameworks, not a competitor. Full launch package → Phase 3 | 2–3 |
| 15 | Claude Code integration | **[override]** **Option A — real Claude Code plugin** (`.claude-plugin/plugin.json` + `hooks/hooks.json` + `skills/`), install via `/plugin marketplace add`; auto-merge/clean hooks, **no settings.json surgery**. Keep `init` as a thin hardened fallback for standalone users. **SUPERSEDES the settings.json-merge installer (`290fc9c`)** | 2 |
| — | Config path | Keep `~/.claude/relay/` (intentional Claude Code coupling); revisit during plugin repackaging | — |
| — | Launch timing | Ship Phase 1 + minimal README → iterate publicly (don't hold for Phase 2) | — |
| — | Sponsorship | No `FUNDING.yml` for now; revisit on demand | — |
| — | CHANGELOG | **Auto-generated** by semantic-release (supersedes manual Keep-a-Changelog) | 1 |

## Key interactions / consequences

- **semantic-release cluster (#4 + #7 + CHANGELOG):** pulls **Conventional Commits** in *now* (not deferred). Version, CHANGELOG, tags, and PyPI publish all derive from commit history (`fix:`→patch, `feat:`→minor, `feat!:`/`BREAKING CHANGE:`→major). Add **commitlint** to `.pre-commit-config.yaml` to enforce. Full-auto (7a) = a merge to `main` can publish to PyPI with no human gate — accepted trade; mitigate with strong CI as the gate (tests + pyright + coverage must pass before merge).
- **#15 supersedes the installer:** the Claude Code plugin (Option A) replaces the `downbeat init` settings.json-merge approach shipped in `290fc9c`. The parent wired `mondu-harness` git-ignores around that installer — those become obsolete when the plugin lands (Phase 2). **Heads-up to the parent recommended.** `init` survives only as a standalone fallback.
- **Name migration** (`claude-relay → downbeat`) is tracked separately in launch-plan.md; it must precede the first PyPI release (#12) and the plugin marketplace slug (#15).
- **#4/#7 pipeline is code-complete but not yet LIVE:** `release.yml` + the semantic-release config landed in `8883258`, but three GitHub/PyPI web-console steps (Trusted Publisher registration, `pypi` environment, branch-protection status checks) can't be done from a CLI session — see [release-setup.md](./release-setup.md) for the exact runbook. Do those steps AFTER the rename (Step 1 registers the PyPI project name).

## Phase mapping (execution order)

**Phase 1 — launch-blockers**
LICENSE + PEP 639 metadata (#1), classifiers/urls, community-health core + Issue Forms (#2, #3), `--version` + error-wrapping (#11), macOS CI leg (#8), Conventional-Commits + commitlint, **semantic-release pipeline + Trusted Publishing** (#4, #7), verify wheel data assets, name migration, first PyPI release (#12).

**Phase 2 — polish**
MkDocs Material docs site (#13), VHS demo (#10), rich-argparse (#11), `examples/` + troubleshooting + uninstall (#12), pyright + coverage-comment + pre-commit (#5, #6), Dependabot (#9), **Claude Code plugin repackaging (#15 Option A)**, README restructure.

**Phase 3 — growth**
Comparison-table + launch package (#14): badges, social-preview, `awesome-cli-coding-agents` + `awesome-claude-code` PRs, Show HN + Reddit (see launch-plan.md).
