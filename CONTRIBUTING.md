# Contributing

Thanks for considering a contribution. This is a solo-maintained project, so
please keep changes focused and open an issue first for anything non-trivial
(new features, breaking changes) before investing time in a PR.

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
