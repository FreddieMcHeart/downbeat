# Release pipeline — manual one-time setup

> Three GitHub/PyPI web-console steps needed before `.github/workflows/release.yml`
> can actually publish. None of these can be done from a CLI/agent session — they
> require a human with GitHub repo-admin access and a PyPI account. Do these **once**,
> after the [rename to `downbeat`](./launch-plan.md) lands (see the timing note below).

## ⚠️ Do this AFTER the rename, not before

Step 1 registers a PyPI "trusted publisher" tied to a specific **PyPI project name**.
If you register it now under `claude-relay` and then rename the package to `downbeat`,
the registration is for the wrong name and has to be redone. The GitHub-side steps
(2 and 3) are name-independent and could technically be done anytime, but for a single
clean pass, do all three together post-rename.

---

## Step 1 — Register a PyPI Trusted Publisher (pending publisher)

Trusted Publishing lets GitHub Actions authenticate to PyPI via OIDC — no API token
to generate, store, or rotate. Since this package has never been published, use PyPI's
**pending publisher** flow, which pre-registers the link before the project exists;
the first successful publish from that exact workflow creates the PyPI project
automatically.

1. Log in to **pypi.org** with the account that should own this package.
2. Go to **<https://pypi.org/manage/account/publishing/>**.
3. Under "Add a new pending publisher", fill in:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `downbeat` (the final package name, post-rename) |
   | Owner | the GitHub org/user the repo lives under |
   | Repository name | the repo name (e.g. `downbeat`) |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. Click **Add**. The pending publisher now exists — nothing publishes until the
   `publish` job in `release.yml` actually runs successfully (which also requires
   Step 2 below).

**Verify:** the entry appears under "Pending publishers" on that same page, showing
the exact owner/repo/workflow/environment you entered. If any of those four values
don't match `release.yml` exactly, the OIDC handshake fails at publish time with an
authentication error — the four fields **must be byte-exact**.

---

## Step 2 — Create the `pypi` GitHub Environment

`release.yml`'s `publish` job runs `environment: { name: pypi }` — this environment
must exist in the repo, or the job fails immediately ("Environment not found").

1. In the repo on GitHub: **Settings → Environments → New environment**.
2. Name it exactly `pypi` (must match Step 1's "Environment name" and the workflow
   file — case-sensitive).
3. Click **Configure environment**.
4. Optional but worth considering, given this project's own human-in-the-loop
   philosophy: under **Deployment protection rules**, add **Required reviewers**
   (yourself) so every PyPI publish needs a manual click-to-approve, even though the
   *version bump + CHANGELOG* stay fully automatic (decisions.md's "full-auto" choice
   was about the release job, not necessarily the publish step). This is optional —
   skip it if you want the pipeline to be genuinely hands-off end to end.
5. Save.

**Verify:** the environment shows up in **Settings → Environments** with no errors.
If you added a required reviewer, the first `publish` job run will pause and show
"Waiting for approval" instead of failing outright — that's expected, not a bug.

---

## Step 3 — Require CI to pass before merging to `main`

`release.yml` triggers on every push to `main` and does **not** re-run the test
suite itself — it trusts that anything landing on `main` already passed `ci.yml`.
That trust only holds if GitHub enforces it.

1. **Settings → Branches → Add branch protection rule** (or **Add rule** under
   "Branch protection rules" on newer GitHub UI).
2. Branch name pattern: `main`.
3. Enable **Require status checks to pass before merging**.
4. In the status-check search box, select every matrix leg from `ci.yml`'s `test`
   job — GitHub lists each `(os, python-version)` combination as a separate check
   (e.g. `test (ubuntu-latest, 3.11)`, `test (macos-latest, 3.13)`, etc.). Select
   all of them; if the list is empty, push one throwaway commit first so GitHub has
   seen the job names at least once.
5. Enable **Require branches to be up to date before merging**.
6. (Recommended for a solo repo) Leave **"Do not allow bypassing the above
   settings"** unchecked if you sometimes need to push directly as the owner in an
   emergency — enable it only if you want the rule to bind even to yourself.
7. Save.

**Verify:** open a throwaway PR with a failing test and confirm GitHub blocks the
merge button until `ci.yml` goes green.

---

## After all three are done

Push a commit with a `feat:`/`fix:` message to `main` (through a normal PR, once
branch protection is on) and watch the **Actions** tab:

1. `release.yml`'s `release` job should compute the next version (0.x per
   `allow_zero_version = true`), write `CHANGELOG.md`, commit, and tag.
2. The `publish` job should then build and `uv publish` to PyPI — pause here for
   your approval if you added a required reviewer in Step 2.
3. Confirm the new version shows up at `https://pypi.org/project/downbeat/`.

If the publish job fails with an OIDC/authentication error, re-check Step 1's four
fields against `release.yml` — a single-character mismatch (repo name casing,
workflow filename, environment name) is the most common cause.
