# Contributing

Thanks for considering a contribution. This is a solo-maintained project, so
please keep changes focused and open an issue first for anything non-trivial
(new features, breaking changes) before investing time in a PR.

## Before you start

Check the [open issues](../../issues) **and** the [open PRs](../../pulls) for
your change first. Two people recently fixed the same bug independently and one
PR's effort was wasted — a 30-second look would have caught it. If an issue
exists, say you're picking it up; if a PR already addresses it, add your
review there instead of opening a competing one.

## Development setup

```bash
git clone <this-repo>
cd downbeat
uv sync --extra dev      # installs the package (editable) + dev dependencies
uv run pre-commit install --hook-type commit-msg   # enforces Conventional Commits (see below)
```

Run the test suite:

```bash
uv run pytest
```

Lint + format:

```bash
uv run ruff check .
uv run ruff format .
```

All tests must pass (`uv run pytest`) and `ruff check .` must be clean before
a PR is reviewed.

## Writing tests

Every bug fix and every feature needs a test. A few expectations that matter
more here than the line count:

- **Prove the test fails without your change.** Stash the fix, run the test,
  watch it fail with the symptom you're fixing, then restore the fix. A test
  that passes whether or not the bug is present guards nothing.
- **Don't fake the thing under test.** If you stub the exact behaviour you're
  checking — hand-writing the output a real component would produce, mocking
  the call whose result is the point — the test passes for the wrong reason
  and stays green when the code breaks. Drive the real path where you can.
- **Match the patterns already in the neighbouring code.** Before changing how
  `store.py` moves a message between directories, read the functions next to
  the one you're touching — they encode invariants (e.g. write the replacement
  *before* unlinking the source, and watch for the same-path case) that aren't
  obvious from the one function in isolation.
- **TUI changes: the pytest harness is necessary but not sufficient.** Textual
  defers `mount()`/`remove()`, so the harness doesn't perfectly reproduce real
  render timing — a routine can pass in tests and blank the screen in the app,
  or vice versa. If you touch rendering, also run `downbeat tui` and look.

## Commit messages: Conventional Commits are required

This project's version, CHANGELOG, and PyPI releases are generated
automatically from commit history via
[semantic-release](https://python-semantic-release.readthedocs.io/), so every
commit on `main` must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Common types: `feat` (new feature → minor version bump), `fix` (bug fix →
patch bump), `docs`, `refactor`, `test`, `chore`. A breaking change is
signalled with `!` after the type/scope (`feat!:`) or a `BREAKING CHANGE:`
footer, and triggers a major version bump.

PRs are typically squash-merged, so the **squash-merge commit message** is
what matters — make sure it follows the convention even if your in-branch
commits don't.

## Developer Certificate of Origin (DCO)

By contributing, you certify that you wrote the contribution yourself (or have
the right to submit it) under the project's [MIT license](LICENSE) — the
standard [Developer Certificate of Origin](https://developercertificate.org/).

Sign off your commits with `git commit -s` (adds a `Signed-off-by:` trailer).
PRs with unsigned commits will be asked to amend before merge.

## Reporting bugs / requesting features

- **Bugs:** open an issue using the Bug Report template — please note which
  surface is affected (TUI, CLI, library, or the Claude Code skill/hooks).
- **Ideas / feature requests:** start a [Discussion](../../discussions)
  rather than an issue, so we can talk through scope before committing to it.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Maintainer-only references

Not needed to make a PR — these are internal notes for whoever is running
releases or the docs site, not user-facing documentation:

- [Release process](docs/release-setup.md) — one-time PyPI/GitHub setup steps
- [Docs site setup](docs/docs-site-setup.md) — how the GitHub Pages site itself is built/deployed
- [Decisions log](docs/decisions.md) — internal design-decision + bug history, not a changelog
