# claude-relay — Open-Source Readiness Decision Report

## Executive summary

claude-relay is functionally strong (161 passing tests, four clean surfaces: TUI, CLI, library, Claude Code skill) but pre-launch on every OSS-hygiene axis. The single highest-leverage, lowest-cost fixes are metadata and community-health files: add a real `LICENSE`, migrate `pyproject.toml` to PEP 639 SPDX license syntax, add `[project.urls]`/classifiers/keywords, and land CONTRIBUTING/CODE_OF_CONDUCT/SECURITY. The one genuine strategic risk is the **name**: `claude-relay` collides with several public repos, most notably the much larger Wei-Shaw/claude-relay-service (an unrelated API proxy) — resolve this *before* going public, when it is cheapest. Publishing should use uv-native Trusted Publishing (OIDC), keep version static for now, and verify data assets actually land in the wheel. Recommended sequencing is Phase 1 launch-blockers → Phase 2 docs/UX polish (VHS demo, rich-argparse, examples) → Phase 3 branding/GTM.

## Current OSS-readiness checklist

| Area | Status | Notes |
|---|---|---|
| Source + tests | Have | 161 pass / 16 skip, 26 test files |
| README | Have (needs upgrade) | 156 lines, 9 headings, zero visual media, no badges |
| CI workflow | Have (needs upgrade) | ruff + pytest 3.11–3.13, Linux-only, pip not uv |
| License declared in pyproject | Needs upgrade | Legacy `license = {text="MIT"}`; migrate to SPDX `license = "MIT"` |
| LICENSE file | Missing | Blocks PyPI/GitHub detection, corp legal scans |
| CONTRIBUTING.md | Missing | Also decide DCO vs CLA now |
| CODE_OF_CONDUCT.md | Missing | Contributor Covenant 2.1 verbatim |
| SECURITY.md | Missing | Point at GitHub Private Vulnerability Reporting |
| CHANGELOG.md | Missing | Keep a Changelog, manual for now |
| Issue/PR templates | Missing | Hybrid: Forms YAML for bugs, markdown/Discussions for ideas |
| `[project.urls]` / classifiers / keywords | Missing | Pure metadata; required for good PyPI page |
| PyPI release | Missing | Documented `uv tool install` doesn't work until first release |
| Type checking | Missing | Add pyright |
| Coverage reporting | Missing | pytest-cov + coverage-comment action |
| Pre-commit config | Missing | ruff check/format locally |
| Release automation | Missing | release-please (human-gated) |
| Dependency updates | Missing | Dependabot |
| `--version` flag | Missing | Wire to `importlib.metadata` |
| Demo GIF / asciinema | Missing | VHS `.tape` (TUI value is visual) |
| examples/ directory | Missing | Parent/child transcript = best marketing asset |
| Name uniqueness | Needs decision | Collides with Wei-Shaw/claude-relay-service + 3 others; PyPI name unconfirmed |

---

## License & legal setup

The repo intends MIT (declared in `pyproject.toml`) but has **no LICENSE file** and uses the legacy PEP 621 table syntax that PEP 639 deprecates. GitHub's detector, PyPI's badge, and corporate dependency scanners all key off the actual file, not the TOML field. No patent-sensitive surface area exists in a local filesystem broker, so there is no real pull toward Apache-2.0.

| Option | Summary | Effort | Pros (top 2) | Cons (top 2) | Recommended? |
|---|---|---|---|---|---|
| MIT (keep, fix gaps) | Add LICENSE file, migrate to SPDX string, skip per-file headers | low | Zero re-licensing decision; dominant in this exact ecosystem (Textual/Rich/Ruff) | No explicit patent grant; no NOTICE mechanism | ✅ |
| Apache-2.0 (re-license) | Switch for explicit patent grant + retaliation clause | medium | Corporate legal comfort; used by K8s/CNCF | Longer text + NOTICE upkeep for solo maintainer; deviates from peer convention | |
| BSD-3-Clause | MIT-equivalent + non-endorsement clause | low | Same freedoms as MIT; HTTPie precedent | No patent grant without MIT's brevity; reverses already-declared MIT for marginal gain | |

**Recommendation:** Keep MIT. Add a root `LICENSE` (real MIT text, maintainer name/year), migrate to `license = "MIT"` + `license-files = ["LICENSE"]`, add classifiers/urls while in the file, skip SPDX per-file headers. Separately, adopt **DCO not CLA** (one CONTRIBUTING.md line + free DCO app) and lock it in before the first external PR — retrofitting after unsigned merges is painful.

**Sources:**
- https://opensource.org/license/mit/
- https://github.com/Textualize/textual/blob/main/LICENSE
- https://github.com/astral-sh/ruff/blob/main/LICENSE
- https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- https://www.apache.org/licenses/LICENSE-2.0
- https://opensource.org/license/bsd-3-clause/
- https://github.com/httpie/cli/blob/master/LICENSE

---

## GitHub community health files

The community-profile checklist is near-empty: only README + CI exist. This is a single solo repo, so files belong in the repo root or `.github/`, not an org-wide `.github` meta-repo. This layer is the most leveraged low-effort pre-launch investment — it is the first thing GitHub's UI and new visitors surface.

| Option | Summary | Effort | Pros (top 2) | Cons (top 2) | Recommended? |
|---|---|---|---|---|---|
| Minimal solo baseline | Hand-write core 4 + classic MD templates; Keep a Changelog manual | low | Covers community-profile checklist with near-zero upkeep; Contributor Covenant is a 10-min copy-paste | Manual changelog/version-bump; MD templates yield lower-signal bug reports | ✅ (base) |
| Best-README-Template + Issue Forms + release-please | Marketing-style README, YAML Forms, auto changelog/version | medium | Structured per-surface triage; removes changelog toil | Requires Conventional Commits discipline; template cruft risk | ✅ (borrow Forms only) |
| Standard Readme spec + `.github/` meta-repo | Linter-checkable README, files in `.github/`, FUNDING.yml | medium | Machine-checkable structure; scales to multi-repo | Lower mindshare; premature multi-repo assumption | |
| readme.so draft + hybrid templates | Visual README draft, Forms for bugs + Discussions for ideas | low | Fast well-ordered draft; hybrid matches bug/idea asymmetry | No linter; manual changelog risk | ✅ (borrow hybrid templates) |

**Recommendation:** Start with the **Minimal baseline** for pure risk-reduction (LICENSE, Contributor Covenant 2.1, SECURITY.md → GitHub Private Vulnerability Reporting, short CONTRIBUTING) — ~30–60 min. Borrow **Best-README-Template's badge/ToC conventions only** (not the hero-banner style — this is an infra tool). Borrow **Option 4's hybrid issue templates**: one Forms YAML for bugs with a "which surface (TUI/CLI/lib/skill)" dropdown, feature requests as markdown/Discussions. Keep CHANGELOG manual; defer release-please + Conventional Commits until a second contributor or frequent PyPI cadence appears. FUNDING.yml only if sponsorship is wanted.

**Sources:**
- https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories
- https://www.contributor-covenant.org/version/2/1/code_of_conduct/
- https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability
- https://www.makeareadme.com/
- https://github.com/othneildrew/Best-README-Template
- https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- https://github.com/googleapis/release-please-action
- https://github.com/RichardLitt/standard-readme
- https://readme.so/
- https://keepachangelog.com/en/1.1.0/

---

## Python packaging & PyPI publishing readiness

Metadata is minimum-viable, not release-ready: legacy license table, no LICENSE file, no `[project.urls]`/keywords/classifiers (PyPI page would render nearly blank), static version, and — critically — the wheel ships non-Python data (`skill/`, `assets/hooks`, `assets/commands`, `hooks_manifest.json`) that must be verified to actually land at runtime paths. hatchling is the right backend; no PyPI project exists yet, so Trusted Publishing can be wired from a clean slate.

| Option | Summary | Effort | Pros (top 2) | Cons (top 2) | Recommended? |
|---|---|---|---|---|---|
| Trusted Publishing via `uv publish` | OIDC token exchange, `uv build`+`uv publish`, tag-triggered, `pypi` environment | low | No long-lived token; uv-native (matches toolchain) | One-time PyPI publisher setup; OIDC mental model newer | ✅ |
| Trusted Publishing via `pypa/gh-action-pypi-publish` | Same OIDC, twine-based upload action | low | Most battle-tested integration; decouples build/publish tools | Adds twine to an otherwise uv-native loop; no functional gain here | (fallback) |
| Static version, manual bump | `version = "0.1.0"` bumped by hand / `hatch version` | low | Zero new dep; fully deterministic in-repo | Easy to forget bump → duplicate-version rejection | ✅ |
| hatch-vcs dynamic versioning | Version derived from git tags | low | Single source of truth; pairs with tag-triggered CI | Needs `fetch-depth: 0` (CI footgun); overkill for infrequent releases | (later) |

**Recommendation:** Fix metadata first (LICENSE, SPDX license, urls/keywords/classifiers) — ~30 min, zero risk. Publish via **`uv publish` + Trusted Publishing** (register a "pending" publisher now, gate on git tag + `pypi` environment with `id-token: write`, dry-run on TestPyPI). Keep **static version** for early 0.x; migrate to hatch-vcs later if cadence rises. **Verify wheel contents regardless** (`uv build` then `python -m zipfile -l dist/*.whl`) to confirm data assets land — use `[tool.hatch.build.targets.wheel].artifacts`/`force-include`, pin hatchling, re-verify after upgrades (known regressions pypa/hatch#478, #1130).

**Sources:**
- https://docs.pypi.org/trusted-publishers/
- https://docs.astral.sh/uv/guides/integration/github/
- https://docs.astral.sh/uv/guides/package/
- https://github.com/astral-sh/trusted-publishing-examples
- https://github.com/pypa/gh-action-pypi-publish
- https://github.com/ofek/hatch-vcs
- https://hatch.pypa.io/1.16/config/build/

---

## CI/CD & quality automation

Current CI (ruff + pytest across 3.11–3.13, Linux-only, pip install) is a fine floor but behind norms: no uv in CI (despite uv local dev), no type checking, no coverage, no pre-commit, no release automation, no dependency bot, no OS matrix (textual/watchdog have platform-specific paths and the audience runs locally, often macOS). Goal: close gaps with minimal ongoing burden, not enterprise release engineering.

| Option | Summary | Effort | Pros (top 2) | Cons (top 2) | Recommended? |
|---|---|---|---|---|---|
| Astral-native minimal | uv + ruff + ty, GitHub-native coverage, Dependabot, tag-triggered publish, no pre-commit.ci | low | Same-vendor toolchain; uv in CI 10–100x faster than pip | ty beta (~53% conformance) misses bugs; native coverage less battle-tested | ✅ (base) |
| Established tooling | uv + ruff + pyright + pre-commit.ci + Codecov + release-please | medium | Most battle-tested per axis; release-please gives human-gated Release PR | Requires Conventional Commits; extra services/accounts | ✅ (borrow pyright + release-please) |
| Full auto (python-semantic-release + Renovate) | Auto-release on qualifying merge; Renovate for deps | high | Zero release ceremony; Renovate updates action SHAs | Auto-publish of a bad merge with no human gate; strict commit discipline | |

**Recommendation:** Take the **Astral-native base** and borrow two items from Established tooling. Concretely: (1) switch CI to `astral-sh/setup-uv` + `uv sync --locked` (commit `uv.lock`); (2) add a **macOS matrix leg** (biggest real test gap); (3) type-check with **pyright** not ty (98% vs ~53% conformance); (4) coverage via **pytest-cov + coverage-comment-action** (skip Codecov); (5) releases via **release-please** (human-approved Release PR) wired to `uv build && uv publish` behind Trusted Publishing — never full auto-publish this early; (6) **Dependabot** not Renovate; (7) add `.pre-commit-config.yaml` (ruff check/format) but skip pre-commit.ci for now; (8) fill classifiers/keywords/urls before first release.

**Sources:**
- https://docs.astral.sh/uv/guides/integration/github/
- https://github.com/astral-sh/setup-uv
- https://docs.pypi.org/trusted-publishers/
- https://pydevtools.com/handbook/explanation/how-do-mypy-pyright-and-ty-compare/
- https://pre-commit.ci/
- https://about.codecov.io/blog/python-code-coverage-using-github-actions-and-codecov/
- https://github.com/googleapis/release-please
- https://docs.renovatebot.com/bot-comparison/
- https://github.com/dbrgn/coverage-comment-action

---

## TUI/CLI UX polish

Strong TUI bones (dedicated help screen, `BINDINGS`+`Footer` across screens, modal widgets) but weak "first 60 seconds": no README media despite an inherently visual TUI, **no `--version` flag** anywhere, stock argparse help, minimal error handling (`sys.exit(main())` likely surfaces raw tracebacks), unverified NO_COLOR handling. The `~/.claude/relay/` path is an intentional Claude Code coupling, not an XDG oversight.

| Option | Summary | Effort | Pros (top 2) | Cons (top 2) | Recommended? |
|---|---|---|---|---|---|
| VHS (Charmbracelet) demo | Scripted `.tape` → GIF/MP4, regenerated in CI | medium | Reproducible; official vhs-action keeps demo fresh | Go/Docker toolchain dep; GIF text not copyable | ✅ (demo) |
| asciinema (+agg/svg-term) | Records real sessions, copyable text | low | Copyable commands; tiny files | Not CI-reproducible → drifts; needs conversion to embed | (secondary) |
| termtosvg / terminalizer | Styled static/animated exports | low | Crisp SVG / polished window chrome | Both declining/less-maintained; no CI story | |
| rich-argparse | Colorized argparse help, drop-in formatter | low | 10-line change; rich already a dep | Cosmetic only; doesn't add examples/--version | ✅ (complementary) |

**Recommendation:** These are complementary except the demo tool (either/or). Pick **VHS** — the value is visual/choreographed (`register`→`send`→`tui`→live inbox) and a committed `.tape` + vhs-action stays fresh for a solo maintainer; use asciinema only later for copyable CLI examples. Add **rich-argparse** now, plus **`--version`/`-V`** via `importlib.metadata.version("claude-relay")` and a top-level epilog with 2–3 real examples. **Wrap `main()` dispatch** to print human messages (+ suggested fix) for `FileNotFoundError`/`PermissionError`/relay errors instead of tracebacks. **Verify** `NO_COLOR=1` works and note it in README. Keybinding discoverability is largely done — just confirm every screen's Footer + help screen agree. Leave the `~/.claude/relay/` path as-is; add one README sentence explaining the intentional coupling.

**Sources:**
- https://github.com/charmbracelet/vhs
- https://github.com/charmbracelet/vhs-action
- https://github.com/orangekame3/awesome-terminal-recorder
- https://github.com/faressoft/terminalizer/issues/21
- https://pypi.org/project/rich-argparse/
- https://github.com/hamdanal/rich-argparse

---

## Install channels + onboarding/quickstart UX

The README already leads with the correct 2025–2026 convention (`uv tool install` headline, `pipx` fallback, then `claude-relay init`). Gaps: no LICENSE (blocks packaging + scans), no documented `uvx` zero-install trial, no `examples/`, no troubleshooting section, no documented uninstall despite a subcommand existing. Crucially, **no PyPI release exists yet**, so the documented install commands don't work as written today.

| Option | Summary | Effort | Pros (top 2) | Cons (top 2) | Recommended? |
|---|---|---|---|---|---|
| PyPI-first (uv headline, pipx/pip fallback) | Publish to PyPI; `uvx claude-relay@latest <cmd>` as trial | low | Matches audience's installed tooling; zero new build infra | New-name typosquat risk (mitigate w/ Trusted Publishing); Windows users need uv first | ✅ |
| Homebrew tap (secondary) | `brew install <maint>/tap/claude-relay` | medium | Free upgrade UX; some devs live in brew | Fiddly for a Python (not Go/Rust) formula; second channel to keep in lockstep | |
| PyInstaller/shiv single binary | Standalone executable per OS on Releases | high | Removes Python prerequisite | Textual+watchdog native bindings make freezing fragile; conflicts with library surface | |
| DX polish (LICENSE, examples/, troubleshooting, uninstall) | Close docs gaps regardless of channel | low | Highest-leverage; LICENSE currently blocks everything else; examples/ is best marketing asset | Doesn't solve distribution alone; content needs periodic re-verification | ✅ |

**Recommendation:** Do **PyPI-first (Option 1)** as the only channel, paired with **DX polish (Option 4)** in the same push. Add LICENSE, `[project.urls]`+classifiers, cut a first PyPI release via `uv build && uv publish` + Trusted Publishing, document `uvx claude-relay@latest whoami` as the zero-install trial, add `examples/` (real parent/child transcript), a troubleshooting section (watchdog-unavailable poll fallback, stale-lock recovery, what `claude-relay uninstall` removes). **Skip Homebrew and single-file binaries** — real effort for a distribution problem this audience (already has Python/uv) doesn't have.

**Sources:**
- https://docs.astral.sh/uv/guides/tools/
- https://docs.astral.sh/ruff/installation/
- https://github.com/simonw/llm/blob/main/README.md
- https://til.simonwillison.net/homebrew/packaging-python-cli-for-homebrew
- https://pyinstaller.org/en/stable/usage.html
- https://github.com/othneildrew/Best-README-Template
- https://www.tilburgsciencehub.com/topics/collaborate-share/share-your-work/content-creation/readme-best-practices/

---

## Positioning, branding & go-to-market

Pre-launch with zero GTM assets. The biggest strategic risk is the **name**: `claude-relay` collides with npow/claude-relay, gvorwaller/claude-relay, chadbyte's project, and most importantly the much larger, actively-maintained **Wei-Shaw/claude-relay-service** (an unrelated API proxy that will out-rank a new repo). PyPI name availability is **unconfirmed and must be checked directly**. In the actual problem space (local file-based agent messaging), two live competitors exist — avivsinai/agent-message-queue (~64★) and non4me/cc2cc (~11★) — neither has a TUI, which is claude-relay's genuine differentiator. Explicitly do **not** compete with orchestration frameworks (Agent Teams, claude-flow, Claude Squad); position as the communication substrate underneath them.

| Option | Summary | Effort | Pros (top 2) | Cons (top 2) | Recommended? |
|---|---|---|---|---|---|
| Keep name, differentiate on category + TUI | README disambiguates ("not a proxy, not an orchestrator"); launch narrow | low | Zero cost/no re-tagging; descriptive & memorable | Wei-Shaw dominates search long-term; collapses if PyPI name taken | |
| Rename before launch | Pick a PyPI+GitHub-clear name now while private | medium | Cheapest moment (no users/links); fully own-able in search | Touches pyproject/scripts/skill paths/repo/docs; loses internal recognition | ✅ |
| Position vs AMQ + cc2cc (comparison table) | Explicit landscape table on TUI / one-command install / lifecycle cmds | low | Turns competitors into market validation; pre-empts "how is this different" | Tables age fast; must stay neutral in tone | ✅ (ship regardless) |
| Full launch package + channel sequencing | LICENSE, 4–5 badges, social image, PyPI→awesome-list→Show HN→Reddit | high | Concrete solo checklist; PyPI-before-HN avoids bounce | Depends on naming resolved first; multi-day effort | ✅ (after naming) |

**Recommendation:** Sequence these — they are stages, not alternatives. **Step 0 (today):** run `pip index versions claude-relay`, check npm + GitHub search. Given Wei-Shaw's dominance, lean toward **rename now** (Option 2) — candidates like `ccmailbox`, `relaymux`, `agentrelay` (verify GitHub+PyPI+npm free). **Step 1 (cheap, ship regardless):** the **competitive-positioning section** (Option 3) vs AMQ and cc2cc, leaning on the TUI + one-command `init`. **Step 2 (after name locked):** the **launch package** (Option 4) — LICENSE, 4–5 shields.io badges (build/PyPI version/downloads/license/Python), social image, PyPI release, awesome-claude-code PR, then a "Show HN: `<name>` – local filesystem-backed message broker for coordinating parallel Claude Code sessions" cross-posted to r/ClaudeAI and r/commandline. Skip Product Hunt; Lobsters only if an account already exists.

**Sources:**
- https://github.com/Wei-Shaw/claude-relay-service
- https://github.com/npow/claude-relay
- https://github.com/gvorwaller/claude-relay
- https://github.com/avivsinai/agent-message-queue
- https://github.com/non4me/cc2cc
- https://github.com/hesreallyhim/awesome-claude-code
- https://www.markepear.dev/blog/dev-tool-hacker-news-launch
- https://shields.io/
- https://github.com/orgs/goreleaser/discussions/3240

---

## Claude Code integration story

`downbeat` already ships a genuinely first-class Claude Code bundle (skill + two hooks + five slash-commands), but it currently delivers that bundle via a `downbeat init` script that copies files into `~/.claude/` and hand-mutates `~/.claude/settings.json` to register hooks — the exact pattern Anthropic now steers projects *away* from. As of 2025-2026, Anthropic's canonical answer is to package this as a proper **plugin** (`.claude-plugin/plugin.json` + `hooks/hooks.json` + `skills/`), which auto-merges hooks on enable and cleanly removes them on disable, sidestepping settings.json surgery entirely. The core being agent-neutral maps cleanly onto the emerging "one source of truth, N harnesses" framing (wshobson/agents), where Claude Code is badged "native" and other agents "supported." The current init-script approach isn't wrong, but it's the higher-maintenance path and will require explicit disclosure if listed on `awesome-claude-code`, whose rules mandate flagging any tool that "modifies shared system files."

| Option | Summary | Effort | Pros (top 2) | Cons (top 2) | Recommended? |
|---|---|---|---|---|---|
| A. Ship as a proper Claude Code **plugin** (`.claude-plugin/plugin.json` + `hooks/hooks.json` + `skills/`), install via `/plugin marketplace add` | Repackage the existing bundle into plugin layout; hooks auto-merge/auto-clean, no settings.json editing | med | Clean install/uninstall with zero settings.json surgery; native `/plugin` discovery + marketplace-eligible | Requires a hosting repo with `marketplace.json`; plugin hooks less flexible than raw settings.json for edge cases | ✅ |
| B. Harden the `downbeat init` script | Retain current installer, add exact-command dedup + `uninstall`/`repair`, never overwrite | low | Preserves single-command UX + standalone-core story; no marketplace dependency | Must hand-merge settings.json (no official tooling); awesome-claude-code requires disclosing system-file modification | |
| C. Dual-track (plugin + init) | Offer both, wshobson/agents "harness-native artifacts, one source of truth" model | high | Widest reach; expresses "agent-neutral core, first-class Claude Code"; future-proofs Cursor/Codex | Two install paths to document + keep in sync; more maintenance for a solo maintainer | |
| D. List-only | Keep current install; focus on `awesome-claude-code` listing + "Works with Claude Code" README + badge | low | Fast visibility, near-zero code; forces writing the integration README section | Doesn't fix the settings.json risk; listing not guaranteed + needs modification disclosure | |

**Recommendation:** **Option A** — repackage skill+hooks+commands as a real Claude Code plugin. Highest-leverage: eliminates fragile `settings.json` hand-editing (biggest correctness + uninstall liability), gives clean `/plugin` install/removal, makes downbeat marketplace-eligible. Keep `downbeat init` only as a thin fallback for genuinely standalone (non-plugin) users, and if retained, adopt the claude-mem idempotency pattern (dedup by exact command string + explicit `uninstall`). Frame README with "agent-neutral core, first-class Claude Code" tiering (native vs supported). Defer the full dual-track matrix (C) until a second live harness exists.

**Sources:**
- https://code.claude.com/docs/en/plugins
- https://code.claude.com/docs/en/plugin-marketplaces
- https://code.claude.com/docs/en/plugins-reference
- https://code.claude.com/docs/en/hooks
- https://github.com/anthropics/claude-plugins-community/blob/main/.claude-plugin/marketplace.json
- https://github.com/hesreallyhim/awesome-claude-code
- https://github.com/wshobson/agents
- https://github.com/obra/superpowers

---

## Phased adoption roadmap

### Phase 1 — Launch-blockers (before repo goes public / first PyPI release)
- **Resolve the name** (Positioning §, Step 0/Option 2): check PyPI/npm/GitHub; rename now if colliding — cheapest while private.
- **LICENSE file + PEP 639 migration** (License §): real MIT text, `license = "MIT"` + `license-files`.
- **pyproject metadata** (Packaging §): `[project.urls]`, classifiers, keywords.
- **Core community-health files** (Community §): CONTRIBUTING (+DCO), CODE_OF_CONDUCT (Covenant 2.1), SECURITY (enable GitHub Private Vulnerability Reporting).
- **CLI basics** (UX §): `--version` flag, error-message wrapping (no raw tracebacks).
- **Verify wheel contents** (Packaging §): confirm `skill/`/`assets/`/`hooks_manifest.json` land at runtime paths.
- **First PyPI release** via `uv publish` + Trusted Publishing (Packaging § / Install §).
- **CI upgrade** (CI §): uv in CI + macOS matrix leg (biggest real test gap).

### Phase 2 — Polish (docs site, demos, UX)
- **VHS demo GIF** + vhs-action in CI (UX §).
- **rich-argparse** + epilog examples; verify `NO_COLOR` (UX §).
- **README restructure**: badges → pitch → demo → install → 4 surfaces → config → contributing → license (Community § / Install §).
- **examples/ directory** (parent/child transcript) + Troubleshooting + uninstall docs (Install §).
- **pyright** type checking + **coverage-comment-action** + `.pre-commit-config.yaml` (CI §).
- **Hybrid issue templates** (Forms for bugs w/ surface dropdown; Discussions for ideas) (Community §).

### Phase 3 — Growth (branding, GTM, community)
- **Competitive-positioning section** vs AMQ/cc2cc (Positioning § Option 3).
- **Launch package**: 4–5 badges, social-preview image, awesome-claude-code PR, Show HN + Reddit sequencing (Positioning § Option 4).
- **release-please** human-gated Release PR + **Dependabot** (CI §) — adopt once cadence/contributors justify it.
- **FUNDING.yml** if sponsorship desired; revisit Homebrew tap / hatch-vcs only on real demand signals.

---

## Open questions for the maintainer

1. **Name:** Is `claude-relay` free on PyPI/npm? Willing to rename before launch given the Wei-Shaw collision, or accept the search/disambiguation tax?
2. **License:** Confirm MIT (vs any future enterprise-adopter pull toward Apache-2.0)?
3. **Contribution sign-off:** Adopt DCO now, or stay no-sign-off until a second contributor appears?
4. **Sponsorship:** Add FUNDING.yml / want sponsor visibility, or keep it purely non-commercial?
5. **Release philosophy:** Comfortable with release-please's human-approved Release PR later, or prefer to stay fully manual for the 0.x line?
6. **Config path coupling:** Keep `~/.claude/relay/` as intentional Claude Code coupling (recommended) — confirm this is by design, not a candidate for XDG migration?
7. **Launch timing:** Ship Phase 1 + a minimal README first and iterate publicly, or hold private until Phase 2 polish is done before any Show HN?
