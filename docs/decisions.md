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
- **#15 correction (2026-07-06, PR #4): the plugin does NOT supersede the installer** — this
  row's original framing ("SUPERSEDES the settings.json-merge installer", "no settings.json
  surgery") turned out wrong once actually scoped with the sibling `claude-core-hooks` plugin
  session over relay. downbeat is a general-purpose PyPI tool (`uv tool install downbeat`),
  not Claude-Code-only, so `init`'s hand-merge into `settings.json` has to keep working
  permanently for non-plugin installs — it is a **co-equal baseline path**, not a fallback
  being phased out. What actually shipped: `_is_plugin_enabled()` (`claude plugin list --json`,
  fails open) gates `init`'s hand-merge — skip it if the plugin's already active, but if
  hand-merged entries from a *prior* `init` run already exist alongside a newly-installed
  plugin, print an explicit double-fire **WARNING** (caught in peer review — `HOOK_NAMES`
  substring detection isn't safe enough to auto-remove entries) rather than silently doing
  nothing. `hooks/`, `commands/`, `skills/downbeat/` are symlinks into the existing
  `src/downbeat/assets/`-packaged files — one source of truth for both distribution channels.
  No marketplace registration yet (local-path/git install only). `--migrate-to-plugin` (exact
  command-string match + drop-empty-groups, not substring) is an explicit fast-follow, not in
  this PR. See [plugin.md](./plugin.md) and PR #4.
- **Name migration** (`claude-relay → downbeat`) is tracked separately in launch-plan.md; it must precede the first PyPI release (#12) and the plugin marketplace slug (#15).
- **#4/#7 pipeline is code-complete but not yet LIVE:** `release.yml` + the semantic-release config landed in `8883258`, but three GitHub/PyPI web-console steps (Trusted Publisher registration, `pypi` environment, branch-protection status checks) can't be done from a CLI session — see [release-setup.md](./release-setup.md) for the exact runbook. Do those steps AFTER the rename (Step 1 registers the PyPI project name).

## Operational lessons (durable — carry forward to the next relocation)

- **`uv sync` does not always regenerate `.venv/bin/` script shims after a directory move.**
  Discovered during the `~/mama/claude-relay` → `~/mama/downbeat` rename (2026-07-02).
  After `mv`-ing the checkout and running `uv sync --extra dev` from the new path, `uv run
  pytest` failed with `Failed to spawn: pytest — No such file or directory`. Root cause:
  `.venv/bin/pytest` is a Python script whose shebang line hardcodes the **absolute** venv
  interpreter path (`#!/Users/.../OLD_PATH/.venv/bin/python3`); `uv sync` reused the
  existing shim rather than regenerating it, since it only re-resolves/re-installs
  *packages* it considers changed — a pure directory move doesn't look like a dependency
  change to it. `ruff` was unaffected because it's a compiled binary with no shebang, which
  is exactly why the symptom is inconsistent across tools and easy to half-verify (checking
  one tool works is not evidence the venv is healthy).
  **Fix:** after any directory move, don't trust `uv sync` alone — `rm -rf .venv && uv sync
  --extra dev` for a guaranteed-fresh rebuild, or explicitly check `head -1 .venv/bin/<tool>`
  for every script-based (non-compiled) console-script shim you rely on.
  **This is a THIRD editable-install binding**, alongside the two already documented from
  the `mama/mondu` relocation (global `uv tool install --editable`, project `.venv` package
  metadata) — the venv's own script shims are a distinct failure mode from "is the package
  installed," and `uv sync` succeeding (exit 0) is not sufficient evidence they're correct.
  **Caught live, a FOURTH instance of the same class, mid-commit of this very lesson:**
  `git commit` failed with `` `pre-commit` not found. Did you forget to activate your
  virtualenv? `` — `.git/hooks/commit-msg` (generated by `pre-commit install`) *also*
  hardcodes an absolute interpreter path (`INSTALL_PYTHON=.../OLD_PATH/.venv/bin/python3`)
  at install time, and rebuilding `.venv` doesn't touch `.git/hooks/`. Fix: re-run `uv run
  pre-commit install --hook-type commit-msg` after any directory move. **General pattern:**
  any tool that generates a shim/hook embedding an absolute interpreter path at install time
  (venv console-scripts, pre-commit git hooks, and plausibly others not yet hit — check
  editor/IDE run configs, systemd units, launchd plists, direnv caches) needs an explicit
  re-install step after a relocation; none of these self-heal from `uv sync` alone.

- **`pytest -q`'s buffered dot output is not a reliable hang locator; add `pytest-timeout`
  proactively, don't debug silent CI hangs by eye.** Discovered 2026-07-03: the first `main`
  push after the rename hung an ubuntu CI job for 47+ minutes with zero output past a
  partial `[ 39%]` progress line — no error, no traceback. Guessing the stuck test from the
  visible dot count was unreliable (stdout is block-buffered, not line-buffered, when piped
  to a CI log) and burned real debugging time chasing the wrong test. **Fix:** added
  `pytest-timeout` (`timeout = 30`, `timeout_method = "thread"` in `[tool.pytest.ini_options]`)
  — on the *next* hang it killed the run at 30s and dumped every thread's stack via
  `faulthandler`, which immediately named the real culprit. **Root cause found this way:**
  `watchdog`'s inotify `Observer.stop()` has a known Linux-only deadlock — the stopping
  thread can block forever acquiring an internal lock still held by an emitter thread parked
  in a blocking inotify read. Our `FsWatcher.stop()` only bounded the `.join()` *after*
  `observer.stop()`, not the `stop()` call itself, so the deadlock passed straight through.
  Macos jobs never hit it (FSEvents backend, no inotify). **Fix:** run `observer.stop()` in
  a daemon thread with its own 2s join; if it doesn't return, log and abandon rather than
  block the caller — a real user hitting Ctrl-C in `downbeat watch` on Linux would otherwise
  hang the same way, not just CI. **General lesson:** any watcher/observer `.stop()` built on
  a third-party library should be treated as untrusted-to-return; bound *every* blocking call
  in a shutdown path, not just the final `.join()`. And: add `pytest-timeout` to any project
  with background threads *before* the first mystery hang, not after burning an hour on one.

## Phase mapping (execution order)

**Phase 1 — launch-blockers — ✅ DONE (2026-07-03)**
LICENSE + PEP 639 metadata (#1), classifiers/urls, community-health core + Issue Forms (#2, #3), `--version` + error-wrapping (#11), macOS CI leg (#8), Conventional-Commits + commitlint, **semantic-release pipeline + Trusted Publishing** (#4, #7), verify wheel data assets, name migration, first PyPI release (#12).

First real release confirmed live: **`downbeat v0.1.1`** on PyPI (sdist + wheel), released via the
full automated pipeline (semantic-release → tag → build → OIDC Trusted Publishing) with zero
manual publish steps. Getting there required chasing four separate bugs surfaced only by the
first real (non-dry-run) run — see "Operational lessons" above for the watchdog/pytest-timeout
one; the release-pipeline-specific ones (PSR's Docker container not seeing host `uv`, missing
`contents:read` on the publish job, and the branch-ruleset bypass not covering `github-actions[bot]`
— fixed via a `RELEASE_TOKEN` PAT, see release-setup.md Step 4) are captured in their own commit
messages (`24fb3a7`, `ef5102c`, `8adb0de`) rather than duplicated here.

**Two more releases (0.1.2, 0.1.3) were needed before the pipeline was actually self-healing** —
both real bugs, not repeats of the above. (1) `uv.lock` doesn't get updated when PSR bumps
`pyproject.toml`'s version; PSR's own uv-integration docs prescribe fixing this via
`build_command = "uv lock --upgrade-package \"$PACKAGE_NAME\" && git add uv.lock && uv build"`
(`8cf5384`) — except `$PACKAGE_NAME` is a **PSR v10+ feature that
`python-semantic-release/python-semantic-release@v9`** (the pinned Action major version) doesn't
export, so it silently expanded to `""`, `uv lock --upgrade-package ""` PEP508-errored, and
because `build_command` runs via `bash -c` with no `set -e`, the failure was swallowed — `git add`
+ `uv build` kept going and the job still reported success. **Lesson: verify a fix against the
job log, not just "the step didn't fail"** — a multi-line `build_command` needs an explicit
`set -e` (or check each line's own success) to actually surface a mid-script failure; don't trust
docs written against a newer version of a pinned Action/package without checking what the pinned
version actually supports. Fixed by hardcoding the literal package name (`4739a92`/`a2dc364`).
Confirmed genuinely self-healing only once the ci run triggered by the bot's OWN version-bump
commit (not just the release job) went green on its own, unassisted.

**Phase 2 — polish — ✅ DONE (2026-07-07)**
MkDocs Material docs site (#13, `0549e2d` — a `feat:` commit, released **v0.2.0**), VHS demo
(#10, `1c6c610`, `docs:` — no release), `examples/` + README restructure (#12, `07b494f`,
`docs:` — no release),
rich-argparse + pyright + pre-commit-in-CI + coverage-comment + Dependabot (#5, #6, #9, #11,
`bcb732a` — a `feat:` commit, released **v0.3.0**), **Claude Code plugin repackaging (#15,
PR #4, merged `f12da1d` — a `feat(plugin):` commit, released **v0.4.0**, see correction
above)**.

Deliberate scope calls made landing these, worth keeping as precedent: (1) `pyright` is scoped
to `cli/`+`core/` only (`[tool.pyright].include` in pyproject.toml) — `tui/` has 64
pre-existing errors, almost all Textual's `query_one() -> Widget | None` narrowing; fixing
those is a separate, larger pass, not something to fold silently into a CI-wiring change. (2)
`ruff-format` is **not** wired into pre-commit/CI yet — `ruff format --check .` found 62 files
(mostly `tests/`) non-conformant; reformatting all of them is its own visible decision, not a
side effect of adding hygiene hooks. (3) The MkDocs site reuses root `.md` files via
`pymdownx.snippets` (`--8<-- "README.md"` etc.) instead of copying content — one file, two
render contexts; a same-named-file's relative links can't resolve identically from repo-root
(GitHub) and from `docs/` (the site), so `mkdocs.yml`'s `validation.links.not_found` is
deliberately downgraded to `info` rather than fighting each link with a symlink.

**Gotcha hit mid-Phase-2, worth flagging for the next relocation-adjacent change:** the
globally-installed `downbeat` (`uv tool install --editable`, used by the live `~/.claude/relay/
relay.py` shim) is a **separate environment from the repo's dev `.venv`**. Adding
`rich-argparse` to `pyproject.toml` and running `uv sync` only updated the dev venv — the
global tool install broke (`ModuleNotFoundError: rich_argparse`) the moment the peer-relay
`send`/`reply` commands were invoked through it, since those route through the same installed
binary. Fix: `uv tool upgrade downbeat` after any dependency change, not just `uv sync`. Same
lesson as the earlier IAM-migration finding (memory: `project_iam_migration.md`) generalized —
an editable/dev environment and its "live", separately-materialized install are not the same
thing and don't sync automatically.

**CI follow-up (2026-07-07, PR #5): docs-only diffs no longer run the python matrix.**
`ci.yml` gained a `changes` job (`dorny/paths-filter`, `code` output true unless every changed
file is README/CONTRIBUTING/CODE_OF_CONDUCT/SECURITY/`docs/**`/`mkdocs.yml`) gating
`pre-commit`/`typecheck`/`coverage`/`test` behind `if: needs.changes.outputs.code == 'true'`.
**Two real gotchas surfaced getting this right, both about how GitHub's required-status-checks
actually interact with skipped/conditional jobs:**
1. `paths-filter` with no explicit `base:` diffs the **whole branch against `main`**, not just
   the latest push's incremental commit — confirmed from the action's own log ("Changes will be
   detected between main and \<branch\>"). This is correct for how this repo merges (squash),
   but means you can't test the "skip" path on a branch that itself modifies `ci.yml` — that
   file's own diff always makes `code=true` on that branch, by construction. Verification of the
   skip path required a real doc-only PR opened *after* the new `ci.yml` reached `main`.
2. The `main-protection` ruleset requires **exact expanded matrix context names**
   (`test (ubuntu-latest, 3.11)`, etc.). A **job-level** `if:` on a matrix job skips matrix
   expansion entirely — those named contexts never get created, and GitHub leaves the PR stuck
   on "Expected — Waiting for status to be reported" forever, not merged and not failed. Fix:
   added a single fan-in `ci-required` job (`needs: [pre-commit, typecheck, coverage, test]`,
   `if: always() && (cancelled() || contains(needs.*.result, 'cancelled') || contains(needs.*.result, 'failure'))`)
   that is itself **skipped** (GitHub reports a skipped job as "Success") on the happy path and
   only runs — to deliberately fail loudly — if something upstream genuinely failed. Repointed
   the ruleset's `required_status_checks` at this one job instead of the 6 matrix contexts.
   Confirmed both directions empirically in CI logs before merging: `ci-required` correctly
   fired and failed when an unrelated `end-of-file-fixer` regression broke `pre-commit`, and
   correctly stayed skipped (= passing) once fixed.

**CI follow-up part 2 (2026-07-07/08, PR #7): the paths-filter exclusions were a silent no-op
until fixed.** PR #5's `changes` job filter (`"**"` plus `!docs/**` etc.) evaluated `code=true`
on a genuine docs-only PR (#6) even after the file reached `main` — the negation never applied.
Root cause: `dorny/paths-filter`'s `predicate-quantifier` input defaults to `"some"` (a file
counts as matching if it hits *any one* pattern in the list), so the bare `"**"` alone always
satisfied the filter regardless of what `!`-exclusions came after it — gitignore-style negation
only actually applies with `predicate-quantifier: every`. Confirmed via the action's own log
(`Filter code = true`, matching file `docs/decisions.md`) before and after the fix. **Lesson:**
don't assume a `!`-prefixed pattern list gives gitignore semantics by default in a third-party
action just because the syntax looks like `.gitignore` — check the action's own quantifier
default, and verify empirically with a real PR against the real target branch, not just a
syntax read of the YAML.

**Dependabot sibling-PR merge conflicts on adjacent version-bump lines.** Merging PR #2
(`actions/checkout@v4→v7`) and PR #3 (`astral-sh/setup-uv@v5→v7`) back-to-back produced a real
git conflict in `ci.yml`/`docs.yml` — both PRs touch the same `steps:` blocks, one line apart,
so PR #3's branch (opened before PR #2 merged) couldn't fast-forward-update cleanly once PR #2
landed. Dependabot doesn't rebase sibling PRs against each other. Not a config bug, just an
expected outcome of independent action-bump PRs sharing files — resolved by hand (keep both new
versions) rather than tooled. Worth remembering next time multiple Dependabot PRs are open
simultaneously in a file with multiple `uses:` lines close together.

**Public docs nav should not carry maintainer-only content (2026-07-08, PR #9).** The site's
"Maintainer docs" nav section (`release-setup.md`, `docs-site-setup.md`, `decisions.md` — this
very file) was removed from `mkdocs.yml`'s `nav:` after checking how comparable OSS CLI tools
(`uv`, `hatch`, `ruff`) structure their published docs sites: none surface a release-runbook or
raw decisions/bug journal in the main public nav. `ruff`'s closest analog is one curated
`CONTRIBUTING.md`-style page, not a split-out internal log. Moved discoverability to a new
"Maintainer-only references" section in `CONTRIBUTING.md` instead — the pages themselves stay
on disk and still build as **orphan pages** (MkDocs still builds+deploys a `docs_dir` file even
if it's absent from `nav:`, just reachable only by direct URL, not the sidebar); added
`validation.nav.omitted_files: info` to `mkdocs.yml` to downgrade the resulting expected warning
in strict builds, mirroring the existing `validation.links.not_found: info` pattern.

**`--migrate-to-plugin` design drafted and peer-reviewed, not yet implemented (2026-07-08).**
See [2026-07-08-migrate-to-plugin-design.md](./superpowers/specs/2026-07-08-migrate-to-plugin-design.md)
(PR #8) — reviewed with the `claude-core-hooks` maintainer session over relay. Key shape: reuses
`hooks_manifest.json` as the single source of truth for both registration (`_register_hooks`)
and migration, exact-command-string match instead of `_unregister_hooks`'s substring match,
drop-empty-groups logic extracted into one shared `_remove_matching_hooks` helper instead of a
second implementation. Peer review's main catch: nothing enforces parity between
`hooks_manifest.json` (hand-merge) and `hooks/hooks.json` (plugin) — they agree today but could
silently drift if a third hook binding is ever added to one and not the other; a parity test is
scoped as a required companion, not optional polish. Implementation deliberately on hold — user
said "hold off" 2026-07-08, scoping only for now.

**Phase 3 — growth**
Comparison-table + launch package (#14): badges, social-preview, `awesome-cli-coding-agents` + `awesome-claude-code` PRs, Show HN + Reddit (see launch-plan.md).
