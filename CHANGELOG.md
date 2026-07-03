# CHANGELOG


## v0.1.3 (2026-07-03)

### Bug Fixes

- **release**: Hardcode package name in build_command, $PACKAGE_NAME unset on @v9
  ([`a2dc364`](https://github.com/FreddieMcHeart/downbeat/commit/a2dc364a92623731f571caab77604fbaf9fda431))

Confirmed via the actual job log for 8cf5384's release run: PSR's build_command runs with
  $PACKAGE_NAME expanding to empty, since python-semantic-release/python-semantic-release@v9 (pinned
  in release.yml) doesn't export that env var — apparently a v10+ action feature the uv-integration
  docs assume. `uv lock --upgrade-package ""` hard-errored every time (PEP508 validation), but
  build_command has no set -e, so git add + uv build kept running after the failure and the job
  still reported success — silently shipping a stale uv.lock in both 0.1.1 and 0.1.2. Hardcoding the
  literal package name sidesteps the missing env var entirely.

### Chores

- **ci**: Sync uv.lock with the 0.1.2 version bump
  ([`6cf48b2`](https://github.com/FreddieMcHeart/downbeat/commit/6cf48b29e4094de9586a8667247c869cf7080cc7))

Same lockfile-mismatch pattern as db95371, now on v0.1.2. chore: type deliberately, not fix: — the
  actual pipeline fix (4739a92, hardcoded package name) already prevents this recurring on 0.1.3+;
  this commit just repairs the currently-red main without triggering yet another release before that
  fix has been verified end-to-end.


## v0.1.2 (2026-07-03)

### Bug Fixes

- **ci**: Sync uv.lock with the 0.1.1 version bump
  ([`db95371`](https://github.com/FreddieMcHeart/downbeat/commit/db953717311e9b5d5ba28239011c122e43d769d1))

Semantic-release bumped pyproject.toml's version but didn't touch uv.lock — CI's uv sync --locked
  correctly rejected the mismatch, failing all 6 matrix legs on main (1f5354c). uv.lock's own
  recorded version for the downbeat workspace member was still 0.1.0.

- **release**: Keep uv.lock in sync on every future release
  ([`8cf5384`](https://github.com/FreddieMcHeart/downbeat/commit/8cf5384e4af4735581debafb8800c30628eb08af))

PSR's own uv-integration docs prescribe this exact fix: add uv lock --upgrade-package
  "$PACKAGE_NAME" + git add uv.lock to build_command, so the regenerated lockfile gets staged and
  picked up by PSR's own commit step alongside the version bump + changelog. Without this, every
  future release repeats db95371's all-6-legs CI failure on main.

### Documentation

- Mark Phase 1 done — downbeat v0.1.1 live on PyPI
  ([`9a24111`](https://github.com/FreddieMcHeart/downbeat/commit/9a241111ed6fbf8c465cdb72535833e49b134f80))


## v0.1.1 (2026-07-03)

### Bug Fixes

- **release**: Grant contents:read to the publish job
  ([`ef5102c`](https://github.com/FreddieMcHeart/downbeat/commit/ef5102c1c3b0ae780d37e9ccf58c38cea81cc931))

An explicit job-level permissions: block zeroes every unlisted scope — publish only had id-token:
  write, so GITHUB_TOKEN had no repo-read access. actions/checkout@v4 failed with "Repository not
  found" (a 404, not 403 — GitHub hides private-repo existence from tokens that can't see it) before
  ever reaching the PyPI publish step.

Confirmed on the first real release run: the release job itself now works end-to-end (version 0.1.0
  committed, CHANGELOG.md generated, v0.1.0 tagged and pushed to origin/main) — this was the last
  blocker before the publish job's own known gap (PyPI Trusted Publisher / pypi environment not yet
  configured, tracked in docs/release-setup.md).

- **release**: Push the version-bump commit via a PAT covered by the bypass
  ([`8adb0de`](https://github.com/FreddieMcHeart/downbeat/commit/8adb0de503ce6b21b7a4b146cfdf9f958965d87a))

github-actions[bot] (the default GITHUB_TOKEN identity) isn't covered by main's ruleset bypass
  (RepositoryRole:Admin only), and the fresh version-bump commit has no CI run of its own to satisfy
  the 6 required status checks — so `release` job's push GH013-rejected on the first real release
  attempt (0.1.1, triggered by ef5102c).

Both actions/checkout's `token:` (which persists the credentials git push actually uses) and
  semantic-release's `github_token:` now read from a RELEASE_TOKEN repo secret — a fine-grained PAT
  belonging to the human admin. Documented as Step 4 in release-setup.md; the secret itself has to
  be created and stored by hand (PAT generation + `gh secret set`), same manual-step pattern as
  Steps 1-3.


## v0.1.0 (2026-07-03)

### Bug Fixes

- Tolerate legacy ts field and accept --debug after subcommand
  ([`88b806a`](https://github.com/FreddieMcHeart/downbeat/commit/88b806af953999f36b57e7f5c7897f37da1ef804))

- **ci**: Add pytest-timeout as a hang circuit-breaker
  ([`beeed71`](https://github.com/FreddieMcHeart/downbeat/commit/beeed7121ceee98ff11e435e6f25c3a8d8d7a24e))

Two consecutive ubuntu CI jobs hung silently in pytest for 47+ minutes with zero output past a
  partial dot-progress line (macOS jobs and some ubuntu jobs finish in under a minute; which ubuntu
  job hangs is non-deterministic run to run). Root cause not yet identified — pytest -q's dot output
  is line-buffered when piped, so the last visible dot count doesn't reliably indicate the actual
  hung test.

30s per-test timeout with thread-method dumps every thread's stack via faulthandler before killing
  the run, so the next occurrence fails loud with a real traceback instead of burning the Actions
  time budget in silence. Diagnostic tool, not a fix for the underlying hang.

- **core**: Backfill missing peer name from dict key in legacy sessions.json
  ([`851dc45`](https://github.com/FreddieMcHeart/downbeat/commit/851dc4533fcc746a7344f8dbed7ee707e74eeafb))

- **core**: Verify marker PID is a live claude process before trusting it (+ gc-markers cmd)
  ([`2b2c304`](https://github.com/FreddieMcHeart/downbeat/commit/2b2c304d7f50ab4439f034a82744d0c20fe38dc5))

- **init**: Shim_template delegates via os.execvp so init --force doesn't break shim
  ([`920a872`](https://github.com/FreddieMcHeart/downbeat/commit/920a8725d315ea156695aba5a60bc27ea6c14c6c))

- **release**: Install uv inside PSR's build_command, not on the runner
  ([`24fb3a7`](https://github.com/FreddieMcHeart/downbeat/commit/24fb3a794d6a88827ee2e65d988dd93c01c52e8c))

python-semantic-release/python-semantic-release@v9 is a Docker container action (runs.using: docker)
  — it executes build_command INSIDE that container, isolated from the runner's PATH.
  astral-sh/setup-uv on the host (added in 3af7f34) has zero effect there, so `uv build` kept
  failing with "command not found" even after that fix.

PSR's own docs document this exact gap and prescribe installing uv inside build_command itself:
  build_command = "pip install uv && uv build". Removed the now-pointless setup-uv step from the
  release job (the publish job's setup-uv is unaffected — that job runs on a normal runner, not in
  PSR's container).

- **session**: _process_is_claude must match basename, not full comm path
  ([`57f7c6a`](https://github.com/FreddieMcHeart/downbeat/commit/57f7c6a234c7fc6f9b58e1870525cbda6aebdd6d))

Found while verifying CI parity: `uv run pytest` (what CI will actually execute) diverged from
  `.venv/bin/python -m pytest` — one extra failure in test_session.py, deterministically. Root
  cause: `ps -o comm=` reports the FULL resolved binary path when a process is invoked via `uv run`
  (vs. the short name under a direct .venv/bin/python invocation). The checkout directory for this
  repo is literally named `claude-relay`, so the resolved path (.../claude-relay/.venv/bin/python3)
  contains the substring "claude" — a plain `"claude" in comm` match false-positives on ANY process
  running from that directory (pytest, uv itself, a stray shell), none of which are actually Claude
  Code.

Fix: match against os.path.basename(comm), not the whole string. Same mitigation already documented
  in brain/pid-keyed-session-marker.md for the sibling 'ambient marker' bug class. +2 regression
  tests pinning both the false-positive (full-path-contains-claude) and the true-positive
  (basename==claude) cases. Both .venv/bin and uv run now agree: 166 passed.

- **session**: _process_is_claude — match exact path SEGMENT, not basename
  ([`2fd579a`](https://github.com/FreddieMcHeart/downbeat/commit/2fd579a0781ea288c6c286fe2e1e4d7b992a40b8))

Follow-up to 57f7c6a, which traded one false-positive for a false-negative. Discovered live,
  in-session: my own `claude-relay whoami`/`reply` started failing with 'could not detect session
  id' right after the basename fix landed. Root cause: the real Claude Code install on this machine
  resolves via `ps -o comm=` to `.../local/share/claude/versions/2.1.197` — "claude" is a middle
  PATH SEGMENT, and the basename is just the version number ("2.1.197"). Matching only the basename
  (57f7c6a's fix) rejects this genuinely-live Claude Code process.

Neither whole-string substring (the original bug) nor basename-only (57f7c6a) is correct. The right
  check is an EXACT path segment match — split comm on "/" and require "claude" to be one full
  segment: - ".../claude-relay/.venv/bin/python3" → segments include "claude-relay", not "claude" →
  False (rejects the checkout-dir false-positive) - ".../claude/versions/2.1.197" → segments include
  "claude" exactly → True (accepts the real install) - "claude" (simple PATH-resolved short name) →
  single segment "claude" → True (unchanged)

+1 regression test pinning the versioned-install case; the earlier basename test's docstring
  corrected to describe segment-matching, not basename-only. Verified live: `claude-relay whoami`
  works again (was broken between 57f7c6a and this commit). 167 passed, 16 skipped, uv run +
  .venv/bin agree.

- **tui**: Bind broadcast status to 'B' alias and improve empty-state feedback
  ([`0e90a34`](https://github.com/FreddieMcHeart/downbeat/commit/0e90a343cee5894f4d533c6687d20426c3e05e80))

- **tui**: Dedup inbox + hide archived by default + 'a' toggle
  ([`169bcab`](https://github.com/FreddieMcHeart/downbeat/commit/169bcab9db8b0e6c76d82f2d5fb81dd95873d93b))

- **tui**: Differential ChatStream refresh — no more flicker on long threads
  ([`61ede41`](https://github.com/FreddieMcHeart/downbeat/commit/61ede41307bbab9d8b0811269b5da0dfc51fae2b))

Replace full remove_children()+remount with a diff-based update that only
  removes/mounts/in-place-updates the bubbles that actually changed. Also replace the O(n)
  _highlight_cursor (iterated all children) with _highlight_cursor_diff that touches only the two
  cursor positions that changed. Preserves original scroll-position guard (restore offset when user
  is scrolled up) and conditional mark-read (only on peer change).

- **tui**: Drop bulk mark-read on tab open; rely on cursor-driven marking
  ([`d10b4a4`](https://github.com/FreddieMcHeart/downbeat/commit/d10b4a42fde2242a114eef1da08e556584197c6a))

- **tui**: Enable vertical scroll on MessageDetailScreen + ↑↓/PgUp/PgDn/Home/End bindings
  ([`3923ba0`](https://github.com/FreddieMcHeart/downbeat/commit/3923ba0790cf1fd7745e5b10a6c2c18b38fd6214))

- **tui**: Escape Rich markup in user content to prevent MarkupError crashes
  ([`d822bcc`](https://github.com/FreddieMcHeart/downbeat/commit/d822bccf00505794300b7ab3f348ec278b8dd71c))

- **tui**: Exclude acting-as parent from its own tab list
  ([`ddf967f`](https://github.com/FreddieMcHeart/downbeat/commit/ddf967f8631a998ceee960e6ff386eff2f71196a))

- **tui**: Flatten MessageDetailScreen layout to avoid Textual render-tree crash
  ([`1f64f85`](https://github.com/FreddieMcHeart/downbeat/commit/1f64f85423f32d17a4c292bd41d14847264d89dd))

- **tui**: Follow-tail scroll model — preserve scroll when user is reading history
  ([`b6c395c`](https://github.com/FreddieMcHeart/downbeat/commit/b6c395c277b647a24a1d62e34a09d96bece671c7))

Watcher-driven refreshes no longer snap viewport to bottom when the user has scrolled up; scroll_end
  only fires on peer change or when already at tail. _mark_focused_read is also limited to
  peer-change events to avoid spurious read-marks on background refreshes.

- **tui**: Preserve inbox selection across refresh by message id
  ([`c0fe6c0`](https://github.com/FreddieMcHeart/downbeat/commit/c0fe6c012bd9bb1e4d24265f19b032850e718cdd))

- **tui**: Render confirm-modal hint correctly and add y-keybinding smoke test
  ([`9091c67`](https://github.com/FreddieMcHeart/downbeat/commit/9091c671f5ee528837e7273a771c2eff3fec471c))

- **tui**: Restore auto-mark-read on thread open after acting-as refactor
  ([`3030033`](https://github.com/FreddieMcHeart/downbeat/commit/3030033e9d6ff8f9196d47d47af3cb7e452b02d7))

Root cause: now_iso() used seconds precision, so two messages sent in the same second got identical
  created_at timestamps. list_thread sorts by created_at, so with equal timestamps the order was
  determined by lexicographic UUID filename sort — non-deterministic relative to insertion order.
  The cursor landed on whichever message sorted last (not always b), so _mark_focused_read marked
  the wrong message, causing the test to fail ~60% of the time. Fix: switch now_iso() to
  microseconds precision so successive messages always have distinct timestamps and stable ordering.

- **tui**: Route DataTable.RowSelected to open_message and auto-focus inbox
  ([`75efa0d`](https://github.com/FreddieMcHeart/downbeat/commit/75efa0d164a3be15e175f18494a332577737001e))

- **tui**: Show only arrow glyphs (←/→) in member-nav footer, keep h/l aliases working
  ([`d82d2f3`](https://github.com/FreddieMcHeart/downbeat/commit/d82d2f379ce5f868bbc02080258d90f6a9d48e37))

- **tui**: Snappy mouse scroll — step by 3 lines, no animation
  ([`82dd4d6`](https://github.com/FreddieMcHeart/downbeat/commit/82dd4d629ef3c0169c8a00cf3f73e948b77e68cb))

- **tui**: Truncation suffix used literal brackets inside markup — switch to parens
  ([`b9aadf2`](https://github.com/FreddieMcHeart/downbeat/commit/b9aadf271ac4fe11356611909924b2cf6fdd0675))

- **tui**: Ungrouped parent shows only ungrouped peers as tabs
  ([`00f71d0`](https://github.com/FreddieMcHeart/downbeat/commit/00f71d0d528f6f557861be35e174bbde9da5c5cc))

- **tui**: Unmistakable selected-bubble indicator (arrow + bg + bold)
  ([`5cae921`](https://github.com/FreddieMcHeart/downbeat/commit/5cae9216d0b6a2c5b9e7f0f2796d417bfe3baf17))

Add ▶ cursor arrow prefix that appears on focused bubble, replace $boost background with $accent 30%
  for higher contrast, and add text-style: bold.

- **tui**: Use rich.text.Text composition to bypass Textual 8 markup parser for user content
  ([`80157cd`](https://github.com/FreddieMcHeart/downbeat/commit/80157cd405fbfaf3e4b92d8d678090207236f27a))

- **tui**: Use Text.append(style=...) API instead of split markup tags in detail title
  ([`a08f2c2`](https://github.com/FreddieMcHeart/downbeat/commit/a08f2c2e2b46dc58e260a82fd6c3365493209e4b))

- **watcher**: Bound FsWatcher.stop() against the watchdog/inotify deadlock
  ([`7134224`](https://github.com/FreddieMcHeart/downbeat/commit/713422437950c8c996f43c7e4f143d9d3de2dc68))

pytest-timeout's stack dump (added in beeed71) caught the real culprit: watchdog's Observer.stop()
  can deadlock on Linux inotify — MainThread blocks forever acquiring an internal lock still held by
  an emitter thread parked in a blocking inotify read. Our stop() only bounded the join() after it,
  not the stop() call itself, so the deadlock propagated straight through — not just a CI-hygiene
  issue, a real user hitting Ctrl-C in `downbeat watch` on Linux could hang the same way.

Runs observer.stop() in a daemon thread with a 2s join; if it doesn't return, log and abandon rather
  than block the caller. The leaked daemon thread is harmless at process exit.

- **watcher**: Take PollWatcher baseline snapshot synchronously in start()
  ([`3af7f34`](https://github.com/FreddieMcHeart/downbeat/commit/3af7f3495c00729e901a49df7e9dc210b162eca8))

Taking the baseline inside the background thread (_run) races the caller: if thread scheduling
  delays the first tick past the caller's next write, that write lands in the baseline itself and is
  never detected as a change. Surfaced as a flaky CI failure on a loaded ubuntu runner
  (test_poll_watcher_detects_new_message).

fix(ci): install uv in the release job before invoking python-semantic-release, since its configured
  build_command (`uv build`) shells out and needs uv on PATH — publish job already had setup-uv,
  release job didn't.

### Chores

- Remaining safe ruff auto-fixes from the CI lint gate
  ([`9ec39b9`](https://github.com/FreddieMcHeart/downbeat/commit/9ec39b9d4a1833ad9f9879179ac2a9d7b045aebf))

Rest of the same ruff --fix batch (UP017 datetime.UTC, I001 import order, B009 attribute-vs-getattr)
  that got left unstaged after the previous commit. Zero behavior change — datetime.UTC and
  datetime.timezone.utc are the same object in py3.11+; getattr(x, "_msg") vs x._msg is identical
  when the attribute always exists.

- **ci**: Uv-native CI + macOS matrix leg; fix pre-existing ruff violations
  ([`16fd7e7`](https://github.com/FreddieMcHeart/downbeat/commit/16fd7e7af5bbd3ced6e4a3316bef430bd5174a92))

Phase-1 launch-blocker (decisions.md #8). CI now uses astral-sh/setup-uv + `uv sync --locked --extra
  dev` (matches local dev toolchain, 10-100x faster than pip) instead of `pip install -e`. Added a
  macOS leg to the matrix — the biggest real test gap, since textual/watchdog have platform-specific
  paths and the audience runs this locally, often on macOS.

Switching to `uv run ruff check .` in CI surfaced 17 pre-existing lint violations that plain
  `pytest` runs never caught (only `ruff check` was ever run ad hoc, never gated). 15 auto-fixed
  safely (B009/F401/I001/UP017); the remaining 7 (F841 unused-variable, E501 line-too-long) fixed by
  hand: unused `as pilot`/`msg`/`m1` test bindings dropped one-by-one BY LINE NUMBER (a blanket sed
  on the repeated `as pilot:` pattern would have broken sibling occurrences that ARE used later via
  pilot.pause() — reverted that attempt and did it surgically instead), and one over-длину print
  wrapped in init_cmd.py. `ruff check .` is now clean; `uv run pytest` and `.venv/bin/python -m
  pytest` agree exactly (166 passed, 16 skipped).

### Documentation

- Add Claude Code integration-story research section (topic 9)
  ([`24c9c80`](https://github.com/FreddieMcHeart/downbeat/commit/24c9c805c247225d647438942863fe1c7fa09bce))

Fills the topic that failed schema-retry in the workflow. Key finding: the current downbeat init
  (copy files + hand-mutate settings.json) is the pattern Anthropic now steers away from; canonical
  path is a real Claude Code plugin (.claude-plugin/plugin.json + hooks/hooks.json + skills/) with
  auto-merge/clean. Options A(plugin)/B(harden init)/C(dual)/D(list-only); rec = A.

- Document Message kind field (task default + backflow-ready) in README
  ([`2242c2d`](https://github.com/FreddieMcHeart/downbeat/commit/2242c2dd4a9395a3166f306361ea2529ac6ad81c))

- Durable lesson — absolute-path shims (venv scripts + git hooks) break on relocation
  ([`7aec70d`](https://github.com/FreddieMcHeart/downbeat/commit/7aec70de3bd0c2b493f3035554856c6f80d1c13b))

Per parent's request to log this durably (not just in the relay thread) so it survives to the next
  relocation: uv sync succeeding (exit 0) after a directory move is not sufficient evidence the venv
  is healthy. Script-based console shims (pytest) hardcode an absolute shebang path that uv sync
  doesn't always regenerate; compiled-binary shims (ruff) have no such dependency, so one tool
  passing is not evidence the venv is fully fixed. Caught a fourth instance of the same class live,
  mid-commit of this exact lesson: pre-commit's generated .git/hooks/commit-msg also hardcodes an
  absolute interpreter path and broke the commit until re-installed. General pattern: any
  absolute-path shim/hook generated at install time needs explicit re-install after a relocation;
  none self-heal from uv sync alone. Fix applied: rm -rf .venv && uv sync --extra dev, plus uv run
  pre-commit install --hook-type commit-msg.

- Durable lesson — pytest-timeout + watchdog/inotify Observer.stop() deadlock
  ([`ca5fa93`](https://github.com/FreddieMcHeart/downbeat/commit/ca5fa93d395a87b209935733d4b8a303ac8ee6ec))

- Lock OSS-prep decisions (track A)
  ([`e712328`](https://github.com/FreddieMcHeart/downbeat/commit/e7123288b0496b86b36ad9221a0ce06242dff7a9))

Decided checklist from walking the research topic-by-topic. Notable overrides: - #4/#7
  semantic-release (full-auto, 7a) → dynamic versioning + auto CHANGELOG + Conventional Commits now
  required; PyPI via Trusted Publishing. - #13 docs site = MkDocs Material on GitHub Pages. - #15
  Claude Code integration = real plugin (Option A), Phase 2 — supersedes the settings.json-merge
  installer (290fc9c). Rest = research recommendations (MIT, DCO, minimal community-health, pyright,
  coverage-comment, VHS, PyPI-only, Dependabot, +macOS). Phased in the doc.

- Product identity (downbeat) + launch/GTM plan + OSS-readiness research
  ([`18f4c7b`](https://github.com/FreddieMcHeart/downbeat/commit/18f4c7baef7f627a4739769e302da1676fd393bd))

Brainstorm outcome — product identity locked: - Name: downbeat (was claude-relay; rename tracked as
  future phase). Chosen over 'baton' after availability checks found baton taken in our exact niche
  (getbaton.dev + mraza007/baton) + on PyPI. downbeat: PyPI free, niche clean. - Tagline (T2+T3):
  local, human-in-the-loop orchestration of parallel AI coding agents. - Identity = A+C fused,
  human-in-the-loop as the spine; agnostic core, Claude Code today (C) → multi-integration
  north-star (B). Pain hierarchy P1>P2>P3. - Boundaries (NOT a swarm / cloud / agent-framework /
  task-tracker / Claude-only).

Files: - docs/superpowers/specs/2026-07-01-downbeat-product-identity.md (canonical identity) -
  docs/launch-plan.md (durable GTM home: awesome-cli-coding-agents PR, launch channels, rename
  migration) - docs/oss-readiness-research.md (9-topic web research, multi-option, from the
  workflow)

- Readme and CI
  ([`52fd2af`](https://github.com/FreddieMcHeart/downbeat/commit/52fd2aff7ce3cc17d8f193694c2b697eb77ba8a3))

- Write release-setup.md — the 3 manual GitHub/PyPI steps runbook
  ([`a741280`](https://github.com/FreddieMcHeart/downbeat/commit/a741280b01941c22caaac313d634d03de5782c9d))

Precise, byte-exact instructions for the steps release.yml's pipeline needs but a CLI session can't
  perform: (1) register a PyPI pending Trusted Publisher (exact owner/repo/workflow/environment
  fields — a mismatch on any one breaks OIDC auth at publish time), (2) create the 'pypi' GitHub
  environment (with an optional required-reviewer gate, matching this project's human-in-the-loop
  philosophy without contradicting the 'full-auto' release-job decision), (3) require ci.yml's
  status checks before merging to main (the trust boundary release.yml relies on, since it doesn't
  re-run tests itself). Flags the ordering dependency explicitly: do this AFTER the rename, since
  Step 1 is keyed to the final PyPI project name (downbeat) — registering it now under claude-relay
  would need to be redone. Cross-linked from decisions.md and launch-plan.md's Phase-1 sequencing.

- **commands**: Bare /relay-reply = inbox-check, skip if empty
  ([`1f9a1f5`](https://github.com/FreddieMcHeart/downbeat/commit/1f9a1f55de75abfd621a41ace299422aef5f4250))

Nazarii uses a bare /relay-reply (no msg_id) as an inbox-check shortcut: surface + handle pending
  mail (esp. from the parent) if any, otherwise take NO action. The command now branches on empty
  $ARGUMENTS — check the turn's relay-inbox banner / inbox+delivered dirs; if empty, report 'nothing
  to reply to' and stop (no fabricated reply, no unsolicited proactive sends).

### Features

- Add 'rebind' to update peer session_id without re-registering
  ([`7069ffb`](https://github.com/FreddieMcHeart/downbeat/commit/7069ffb3aa641a0bb6d2c3189c6e82188fa85a55))

- Add __init__.py stubs to subpackages so imports resolve
  ([`bb2bc8a`](https://github.com/FreddieMcHeart/downbeat/commit/bb2bc8acdec03859c557c7812c4d6ce7d8b7a452))

- Add MIT LICENSE file
  ([`8b3a995`](https://github.com/FreddieMcHeart/downbeat/commit/8b3a995a3cf430083a3e93c0e4283a128895896c))

Phase-1 launch-blocker (decisions.md #1). Real MIT text; GitHub/PyPI/scan detection keys off the
  file, not the pyproject field. PEP 639 SPDX migration + classifiers/urls follow with the metadata
  pass.

- Bootstrap claude-relay package skeleton
  ([`6fc3b4f`](https://github.com/FreddieMcHeart/downbeat/commit/6fc3b4f3c4e1c3b670ceccff16c986ed2e6763f2))

- Rename package claude-relay → downbeat
  ([`8338ac6`](https://github.com/FreddieMcHeart/downbeat/commit/8338ac643aacc01f30d006a624166480421accad))

Product identity locked (docs/superpowers/specs/2026-07-01-downbeat-product-identity.md): local,
  human-in-the-loop orchestration for parallel AI coding agents. Renaming resolves the
  launch-blocker name collision with the much larger, unrelated Wei-Shaw/claude-relay-service on
  GitHub/PyPI.

Scope (see docs/launch-plan.md's "Rename migration" for the full reasoning): - Python package
  src/claude_relay/ -> src/downbeat/, module rename throughout (imports, entry point, all ~30 test
  files) - pyproject.toml: name, [project.scripts] binary (claude-relay -> downbeat),
  [tool.hatch...packages], [project.urls] - CLI-invocation examples in SKILL.md /
  assets/commands/*.md / hooks_manifest.json comment (claude-relay <verb> -> downbeat <verb>) —
  these describe a fact about the binary name that's changing, not cosmetic - Skill identity:
  SKILL.md name: field + _skill_install_dir() -> skills/downbeat - README/CONTRIBUTING/.github
  workflow+templates

Deliberately KEPT unchanged (deferred to Phase 2's Claude Code plugin repackaging per decisions.md
  #15, which restructures these anyway): - ~/.claude/relay/ runtime data directory (RELAY_DIR /
  CLAUDE_RELAY_DIR env var) - Hook script filenames (relay-inbox.py, relay-poll-offer.py) -
  Slash-command filenames (relay-register.md etc., still /relay-send etc.) - Peer names /
  sessions.json content — unrelated to the package name

Docs that discuss the rename itself as a historical/planning record (decisions.md, launch-plan.md's
  migration checklist, oss-readiness-research.md, release-setup.md, the product-identity spec)
  intentionally still say "claude-relay -> downbeat" — not touched by the bulk replace, since
  rewriting them would be self-referential nonsense.

BREAKING CHANGE: the CLI binary is now `downbeat`, not `claude-relay`. The Python package/module is
  `downbeat`, not `claude_relay`. Anyone with the old binary installed needs to reinstall.

Live-environment sync performed (not just source): global uv-tool editable install re-pointed
  (claude-relay -> downbeat binary), .venv rebuilt via `uv sync --extra dev` + `uv lock`, the
  installed shim at ~/.claude/relay/relay.py rewritten to exec `downbeat` (was broken for ~2 minutes
  between the src/ rename and this fix — no relay traffic lost, verified via inbox/delivered
  counts), orphaned ~/.claude/skills/claude-relay/ removed, hooks/commands/skill force-synced to the
  renamed bundled content (diffs verified to be pure rename before --force, nothing else).

167 passed, 16 skipped, ruff clean. downbeat --version / whoami verified live.

- **cli**: Add 'watch' notifier command for always-on inbox surfacing (pure-peek, notify-only)
  ([`acc5191`](https://github.com/FreddieMcHeart/downbeat/commit/acc51917c19a454d8303eee4eb936bfb6f536e61))

- **cli**: Add 'whoami' (name+role) + document /relay-monitor in-session self-monitor
  ([`a2269bf`](https://github.com/FreddieMcHeart/downbeat/commit/a2269bf087cbd3289e63d94c7213a735506654b0))

- **cli**: Add --version flag + top-level error-message wrapping
  ([`8e528fe`](https://github.com/FreddieMcHeart/downbeat/commit/8e528feb4d005a868764ec2537519db15ba74b30))

Phase-1 launch-blocker (decisions.md #11). --version via importlib.metadata, falls back gracefully
  if not installed as a package. main() gains a defense-in-depth safety net: any RelayError subclass
  a subcommand forgot to catch locally, plus OSError (permission/filesystem failures), now print a
  clean 'error: <msg>' to stderr and exit 1 instead of a raw traceback. SystemExit/KeyboardInterrupt
  pass through untouched (used by argparse, --version, and cmd_watch's Ctrl+C handling). +3 tests,
  164 passed.

- **cli**: Add init + uninstall with skill bundling and shim install
  ([`49e261c`](https://github.com/FreddieMcHeart/downbeat/commit/49e261c853e3dc0f8303c62cc5e682750fa7bc37))

- **cli**: Argparse dispatch + register/send/reply/inbox/peers/gc-stale
  ([`b2709e1`](https://github.com/FreddieMcHeart/downbeat/commit/b2709e1c34f988f6a6dc8b2a71e489ea6083bd85))

- **cli**: Watch is now event-driven (FsWatcher + poll fallback) — instant, ~0 idle cost
  ([`99f9952`](https://github.com/FreddieMcHeart/downbeat/commit/99f99528d8a793fba2461718e2c65c3f130e671e))

- **community**: Add CODE_OF_CONDUCT, SECURITY, CONTRIBUTING + DCO, Issue Forms
  ([`2843223`](https://github.com/FreddieMcHeart/downbeat/commit/2843223b9c469bf1e8243fadce5183565fab1174))

Phase-1 launch-blocker (decisions.md #2, #3) — the minimal solo-maintainer community-health
  baseline: - CODE_OF_CONDUCT.md: Contributor Covenant 2.1 verbatim. - SECURITY.md: routes reports
  to GitHub Private Vulnerability Reporting, scopes the local-filesystem-broker's actual sensitive
  surfaces. - CONTRIBUTING.md: real dev-setup commands (uv sync/pytest/ruff), DCO sign-off
  requirement, and — since semantic-release now owns versioning/CHANGELOG — documents that
  Conventional Commits are REQUIRED on main, not a style nit. -
  .github/ISSUE_TEMPLATE/bug_report.yml: Issue Forms with a surface dropdown
  (TUI/CLI/library/skill-hooks-commands/packaging); config.yml disables blank issues and routes
  feature ideas to Discussions instead. Also: .DS_Store was untracked-but-ignorable; added to
  .gitignore and swept the stray file out of .github/ before it could get committed.

- **core**: /clear auto-rebind via (claude_pid, start_time) identity + TUI/CLI/log notifications
  ([`1281ec8`](https://github.com/FreddieMcHeart/downbeat/commit/1281ec891589d0a8058df6255f727183b571b7c9))

- **core**: Add atomic peer CRUD to store
  ([`4f01b14`](https://github.com/FreddieMcHeart/downbeat/commit/4f01b142e4c99cc958e24a3480abcdede67e2dfb))

- **core**: Add broadcast fan-out and reply aggregation
  ([`291cc30`](https://github.com/FreddieMcHeart/downbeat/commit/291cc301e137484201c40ef1fc35f78a76bbeec5))

- **core**: Add message CRUD with state-aware edit lock
  ([`98abbf6`](https://github.com/FreddieMcHeart/downbeat/commit/98abbf622cc31321c3a57b0150ee9fff8fd8ba31))

- **core**: Add Message, Peer, Broadcast dataclasses with backward-compatible JSON
  ([`0cb6ce6`](https://github.com/FreddieMcHeart/downbeat/commit/0cb6ce6bc087437bc1904539e5843eb59dec0ebd))

- **core**: Add Message.kind field (default 'task', legacy-safe)
  ([`ffb35db`](https://github.com/FreddieMcHeart/downbeat/commit/ffb35db5dbcb541527c3451fe2831918a7e9b1e2))

- **core**: Add paths and errors modules
  ([`234ada1`](https://github.com/FreddieMcHeart/downbeat/commit/234ada161d2dccaac67065a107e90797e0fd77da))

- **core**: Add watchdog-based watcher with poll fallback
  ([`81b62b5`](https://github.com/FreddieMcHeart/downbeat/commit/81b62b5b99424e12d32dc2358c9222a52559c930))

- **core**: Port session-id detection from relay.py
  ([`95a487b`](https://github.com/FreddieMcHeart/downbeat/commit/95a487b767626296b85b0cded80c84555d6f5c8e))

- **core**: Quarantine management — list/requeue/purge via store API, CLI, and TUI 'Q' screen
  ([`d58039c`](https://github.com/FreddieMcHeart/downbeat/commit/d58039cd44037a50ae3e48dfb5bae56f04359bec))

- **core**: Rotating logger and store mutation audit lines
  ([`08f0b55`](https://github.com/FreddieMcHeart/downbeat/commit/08f0b555bcb3bc5f527810f8a183c38e0161fbf5))

- **core**: Thread --kind through CLI + store send/reply with log observability
  ([`df5acbe`](https://github.com/FreddieMcHeart/downbeat/commit/df5acbe0876d68c9286512618b759ebeb74f5aca))

- **core**: Two-phase delivery — delivered/ state + ack + reconcile + auto-ack-on-reply
  ([`61bf52b`](https://github.com/FreddieMcHeart/downbeat/commit/61bf52bf5d18d0f66cf28f8ce9c0b131dd433512))

- **init**: Make the package the single source of truth for the relay runtime
  ([`290fc9c`](https://github.com/FreddieMcHeart/downbeat/commit/290fc9cc562569b7a1c6653dc36770e89fa2d14b))

claude-relay init now installs the WHOLE runtime, not just skill+shim: bundled hooks
  (relay-inbox.py, relay-poll-offer.py) → ~/.claude/hooks/ (chmod +x), bundled slash commands
  (relay-*.md) → ~/.claude/commands/, and idempotent registration of the relay hooks in
  ~/.claude/settings.json.

settings.json merge mirrors the real nested layout (settings.hooks[event] = [{matcher?,
  hooks:[...]}]): detects existing relay regs by command-substring so re-runs are no-ops,
  interleaves into a matching-matcher entry without clobbering non-relay neighbours (cost-discipline
  etc.), backs up + writes atomically, and on malformed JSON backs up + errors without a partial
  write. Don't-clobber rule: a hook differing from the bundled copy is kept unless --force.
  uninstall is symmetric (removes hooks/commands/regs, keeps data+backups).

Mondu-specific cost-discipline + RLM-backflow banner block is fenced behind a # MONDU-ADAPTER
  (Phase-4 extraction point) marker in the bundled relay-inbox.py so the later generic-core/adapter
  split is a cut, not a rewrite.

Also fixes a latent packaging bug: the force-include table double-added skill/ and assets/ (already
  shipped via packages=["src/claude_relay"]), which broke any real wheel build — removed it;
  verified the wheel now bundles both.

assets seeded verbatim from the current live files. Live init verified as an idempotent no-op on
  real state. 7 new fixture-based settings-merge tests.

- **packaging**: Pep 639 SPDX license + classifiers + keywords + urls
  ([`5120e12`](https://github.com/FreddieMcHeart/downbeat/commit/5120e127e465e2546915a232742be892312a34a7))

Phase-1 launch-blocker (decisions.md #1, #3). Migrates the legacy license={text="MIT"} table to the
  SPDX license = "MIT" string + license-files = ["LICENSE"], pins hatchling>=1.26 (PEP 639 support),
  adds classifiers/keywords/[project.urls], and rewrites the one-line description to match the
  locked product identity (human-in-the-loop, agent-neutral, not Claude-only). Verified via a real :
  METADATA shows License-Expression: MIT + License-File: LICENSE correctly, data assets
  (skill/hooks/commands) still land in the wheel. project.urls point at the current private origin
  (FreddieMcHeart/claude-relay) — will get a sed pass during the planned rename, per decisions.md's
  Path-2 tradeoff.

- **release**: Wire semantic-release + Trusted Publishing pipeline
  ([`8883258`](https://github.com/FreddieMcHeart/downbeat/commit/8883258311f651d1f5460c9cdfc83adfa19c5a93))

Phase-1 launch-blocker (decisions.md #4, #7 full-auto). On every push to main: 1.
  .github/workflows/release.yml 'release' job runs python-semantic-release, which parses
  Conventional Commits since the last tag, bumps [project].version in pyproject.toml in place
  (version_toml config — simpler than hatch-vcs, no dynamic-version/fetch-depth complexity),
  generates CHANGELOG.md, commits, and tags. 2. 'publish' job (only if a release happened) builds
  via `uv build` and publishes to PyPI via Trusted Publishing (OIDC, id-token: write) — no
  long-lived API token stored as a secret.

Two config decisions that mattered, both caught by an actual local dry-run (`uv run semantic-release
  version --print`), not guessed: - allow_zero_version = true — PSR defaults this to False, which
  forces the FIRST release straight to 1.0.0 regardless of commit history. That contradicts this
  project's own "Development Status :: 3 - Alpha" classifier. Verified the dry-run now computes
  0.2.0 (a correct minor bump from 0.1.0 given the feat: commits so far), not 1.0.0. -
  changelog.default_templates.changelog_file, not the deprecated changelog.changelog_file (warns it
  breaks in PSR v10) — fixed proactively.

Also adds .pre-commit-config.yaml (compilerla/conventional-pre-commit, commit-msg stage) since
  semantic-release's version/changelog output is only correct if commit messages actually follow the
  convention — verified live: a non-conventional message is rejected, a conventional one passes.
  CONTRIBUTING.md documents the one-time `pre-commit install --hook-type commit-msg` step.

MANUAL FOLLOW-UP (cannot be done from a CLI/agent session, needs GitHub/PyPI web console access): -
  Register a PyPI Trusted Publisher for this repo (org/repo, workflow "release.yml", environment
  "pypi") — required before the publish job's first successful run. - Create a "pypi" environment in
  repo Settings → Environments. - Enable branch protection on main requiring ci.yml's checks to pass
  before merge — release.yml itself does not re-run tests, it trusts that gate.

167 passed, ruff clean, wheel builds with all 9 data-asset files.

- **skill**: Make poll-loop offer context-aware instead of session-start default
  ([`6b21817`](https://github.com/FreddieMcHeart/downbeat/commit/6b2181795856604f682f8b810b7af068b0072ad9))

- **skill**: Offer 3-minute inbox poll loop on first invocation
  ([`3fe0fc8`](https://github.com/FreddieMcHeart/downbeat/commit/3fe0fc88ccbcb25c9981d89fde9b78f8a453580b))

- **tui**: Add 'a' archived-toggle to own-inbox tab
  ([`e239297`](https://github.com/FreddieMcHeart/downbeat/commit/e23929731200e010317a3bcd28f74ffeaa60b26a))

The own-inbox tab showed only pending (inbox/ + delivered/) mail, so a sink peer (e.g.
  content-inbox) read empty once its mail was consumed→ archived. Press 'a' on the inbox tab to fold
  processed/ + quarantine/ into view (full received history), again to hide. No-op on member-peer
  threads, which already include archived via list_thread.

- **tui**: Add 'c' clear-inbox to archive a peer's report-backlog
  ([`5480960`](https://github.com/FreddieMcHeart/downbeat/commit/5480960307e78c172de4397144e4d96fcd34fb6d))

A dead/inactive peer's inbox accumulates child→parent status reports that never get delivered (the
  drain hook only fires for live sessions) — they sit as NEW forever and only the TUI 'acting as'
  view surfaces them. Press 'c' on the 📥 inbox tab to archive the whole pending backlog (inbox +
  delivered) → processed/ for the acting peer. Recoverable (not deleted), confirm-gated, and
  role-aware: a CHILD inbox holds parent→child TASKS so the confirm warns loudly that clearing may
  lose unstarted work (direction-asymmetry guard).

store.archive_messages(ids) moves NEW/READ/DELIVERED → processed/ with archived=True (auto-acking
  delivered-but-unacked). +4 tests (2 store, 2 TUI).

- **tui**: Add id column and cross-inbox Find Message dialog (f)
  ([`b9fa74a`](https://github.com/FreddieMcHeart/downbeat/commit/b9fa74a51e319794028f95c10668fbde0eb3d2b8))

- **tui**: Addpeer Enter-to-submit, drop g/G scroll bindings, edit returns to chat
  ([`c0005cd`](https://github.com/FreddieMcHeart/downbeat/commit/c0005cd57b396a2caf90d6d097dcd02c21e2d246))

- **tui**: Always-present own-inbox tab so member-less peers can read their inbox
  ([`02ae551`](https://github.com/FreddieMcHeart/downbeat/commit/02ae5519ea1729e0f45fc0d9dec8f50f39a12378))

- **tui**: Auto-mark-read on cursor move and thread open
  ([`bf77bf6`](https://github.com/FreddieMcHeart/downbeat/commit/bf77bf6332e2297e0bece06018d6a53e2065fb5e))

- **tui**: Broadcast status screen and groups.json store
  ([`8f48a17`](https://github.com/FreddieMcHeart/downbeat/commit/8f48a175f98198c93ba2e1b853ad718600b54baf))

- **tui**: Composer modal with reply and broadcast modes
  ([`a08cd6b`](https://github.com/FreddieMcHeart/downbeat/commit/a08cd6bd890517630429bbab2fba49fbe63ae3d1))

- **tui**: Ctrl+b broadcast to all group children
  ([`381074a`](https://github.com/FreddieMcHeart/downbeat/commit/381074a96d1514dba7f3d3b4d4669946799ae3bb))

- **tui**: Dedicated message detail screen with per-message actions (Enter)
  ([`648614d`](https://github.com/FreddieMcHeart/downbeat/commit/648614d36b0c873ae997dbc49a3803e3bf324952))

Add MessageDetailScreen reachable by pressing Enter on the chat message list. Shows full body +
  metadata; provides Edit, Reply, Delete, Broadcast status, and Copy-id actions. Remove the old
  v/e/d/Shift+B bindings from ChatScreen — those actions now live in the detail screen.

- **tui**: Dedicated Peers screen reachable via Ctrl+P
  ([`a502890`](https://github.com/FreddieMcHeart/downbeat/commit/a5028906c9d249c859f1465b3dba77aca0453815))

Move peer add/remove/gc actions out of ChatScreen into a new PeersScreen. ChatScreen now has a
  single Ctrl+P binding to push PeersScreen. Update help text, README keybindings table, and tests
  accordingly.

- **tui**: Distinguish sent vs received bubbles with accent borders and indentation
  ([`4355664`](https://github.com/FreddieMcHeart/downbeat/commit/4355664e98751773d274a16f0eddedd060c05728))

- **tui**: Drop blank divider rows in Peers — indent + sort group enough
  ([`c6e327d`](https://github.com/FreddieMcHeart/downbeat/commit/c6e327ded7a6eb382e5dab851ef99397cabda5b4))

- **tui**: Edit modal with lock check and delete with confirm gate
  ([`3d5a001`](https://github.com/FreddieMcHeart/downbeat/commit/3d5a001a8dc44ee940f7048872a9de58f368ba33))

- **tui**: F1 help screen with keybinding reference
  ([`43bbfb1`](https://github.com/FreddieMcHeart/downbeat/commit/43bbfb1087384bfdc51d9d19d7b20858d4f94b11))

- **tui**: F6 log viewer with live tail and inline grep
  ([`ab47586`](https://github.com/FreddieMcHeart/downbeat/commit/ab4758659a5730c2387401273d9ea0442ab3be9b))

- **tui**: Group peers by name prefix in Peers screen with role-sorted ordering
  ([`73836a3`](https://github.com/FreddieMcHeart/downbeat/commit/73836a384f361c1680f79595e738f812ffd49040))

- **tui**: Inboxlist DataTable wired to acting-as peer
  ([`c63b9e6`](https://github.com/FreddieMcHeart/downbeat/commit/c63b9e6a6fffde7893d88420423057675382e302))

- **tui**: Mac-keyboard friendly primary keys for help/logs/scroll (F-keys + Home/End kept as
  aliases)
  ([`1d9d07c`](https://github.com/FreddieMcHeart/downbeat/commit/1d9d07c148a7f7969cbbeba4a804bfdf0004dc59))

- **tui**: Messageview with mark-read-on-open
  ([`44a9e00`](https://github.com/FreddieMcHeart/downbeat/commit/44a9e00ad5781493eeaf36fa401d5abc537da391))

- **tui**: Multi-line composer with shift+enter newline and ctrl+e \$EDITOR
  ([`a7f5235`](https://github.com/FreddieMcHeart/downbeat/commit/a7f5235875b73acbd68bfa014644dbbfded17622))

- **tui**: Peer management — add/remove peers and GC stale dialog
  ([`a17d924`](https://github.com/FreddieMcHeart/downbeat/commit/a17d924115247642b0a40ca297e55004520b70c4))

- **tui**: Peerlist widget with acting-as selector and unread counts
  ([`cc9288e`](https://github.com/FreddieMcHeart/downbeat/commit/cc9288e7612a272ad88d964f9100b0481dfb1537))

- **tui**: Persist acting-as and active-peer across launches
  ([`b7318f3`](https://github.com/FreddieMcHeart/downbeat/commit/b7318f3608009882397b3f40ede35dad357e11b0))

- **tui**: Rebind refresh from F5 to Ctrl+R
  ([`bd1b158`](https://github.com/FreddieMcHeart/downbeat/commit/bd1b158e34bdba2c7515a9db249a59c85b261502))

- **tui**: Remove theme toggle and command palette — focused tool, fewer chips
  ([`989294d`](https://github.com/FreddieMcHeart/downbeat/commit/989294d175276451719584b63f1b41516f82b0a3))

- **tui**: Rename ←/→ chip from 'peer' to 'member' for clarity
  ([`20804ce`](https://github.com/FreddieMcHeart/downbeat/commit/20804ce66c20265d98169f6ec05fc6afdcc46f03))

- **tui**: Replace acting-as dropdown with compact chip + 's' modal switcher
  ([`80ff5b8`](https://github.com/FreddieMcHeart/downbeat/commit/80ff5b8d0c05b39d4217d3e3294062f72d1d712e))

Removes the always-visible Select widget and replaces it with a Static chip showing the current
  acting-as parent; pressing 's' opens SwitchActingAsModal to pick a different parent on demand.

- **tui**: Rework keynav — Tab cycles focus, ←/→ peer tabs, ↑/↓ within region
  ([`ad50a56`](https://github.com/FreddieMcHeart/downbeat/commit/ad50a56174f41da46cc99024d10bd649f5ebe0dc))

- **tui**: Rework main view to chat/conversation layout
  ([`763abbd`](https://github.com/FreddieMcHeart/downbeat/commit/763abbd8e1d02b66b1e46e7f75981e7177296590))

Replaces the three-pane mail-client MainScreen with a ChatScreen that shows message bubbles between
  the acting-as peer and the selected tab peer. Adds PeerTabs, ChatStream, and ChatComposer widgets.
  Adds store.list_thread() for bidirectional thread retrieval. Old three-pane tests are skipped (not
  deleted); new chat-view tests added.

- **tui**: Shell with three-pane layout and Claude theme
  ([`c353637`](https://github.com/FreddieMcHeart/downbeat/commit/c3536377757912ef3a63cc864af55978facdd505))

- **tui**: Show all group members (parent + children) in peer list, not just children
  ([`43d655a`](https://github.com/FreddieMcHeart/downbeat/commit/43d655a3f3ce209f902ea6bfe82d67bce7af06fa))

- **tui**: Show only parents in acting-as dropdown and only related children in list
  ([`c975cac`](https://github.com/FreddieMcHeart/downbeat/commit/c975cac7c869f36c0d131df82ce015c7c4ac6edf))

- **tui**: Ux pass — fill inbox pane, widen subject, empty-state hint, compact peer rows
  ([`775f425`](https://github.com/FreddieMcHeart/downbeat/commit/775f4250a69c5f8e2912416780895e97aa539b99))

- **tui**: Wire filesystem watcher to drive reactive updates
  ([`56be286`](https://github.com/FreddieMcHeart/downbeat/commit/56be28686b344bfcbb036d106bc53cebedc7c62c))

- **tui**: Y to yank focused message body to clipboard (pbcopy/xclip/pyperclip)
  ([`2a7f1c4`](https://github.com/FreddieMcHeart/downbeat/commit/2a7f1c4f759e43694f34bab69307e79c9a922b3d))

### Refactoring

- **hook**: Genericize relay-inbox banner — strip Mondu adapter block
  ([`a809060`](https://github.com/FreddieMcHeart/downbeat/commit/a80906058129a6c0513faea3510d2e0c72423f34))

Neutralize the # MONDU-ADAPTER fence in relay-inbox.py now that Mondu is retired. Replace the
  Mondu-specific cost-discipline reader table
  (kubectl-reader/gh-reader/datadog-reader/slack-reader/jira-reader, /mondu-commit, /rlm, wiki refs)
  + the adapter marker comments with a project-agnostic cost-discipline nudge (route expensive reads
  to cheap reader sub-agents; delegate fan-out; --kind backflow-ready protocol kept, worded
  generically). Also genericized the two backflow-render lines (dropped 'wiki'/'RLM run' wording).

Banner is pure injected context — no enforcement logic touched, byte-behavior-safe / fail-open. 0
  Mondu-markers remain (grep-verified). 161 tests green.

### Testing

- Fix session-marker pollution and conftest teardown
  ([`fc63544`](https://github.com/FreddieMcHeart/downbeat/commit/fc63544f527cd421a2327846a494c14ce17486eb))

### Breaking Changes

- The CLI binary is now `downbeat`, not `claude-relay`. The Python package/module is `downbeat`, not
  `claude_relay`. Anyone with the old binary installed needs to reinstall.
