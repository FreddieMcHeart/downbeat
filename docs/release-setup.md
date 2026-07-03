# Release pipeline — manual one-time setup

> Four GitHub/PyPI web-console steps needed before `.github/workflows/release.yml`
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

## Step 4 — Give `release.yml` a PAT that the branch ruleset actually trusts

**Discovered on the first real release (2026-07-03), not anticipated in the original
three steps.** `main`'s branch ruleset requires all 6 `ci.yml` status checks and
allows only `RepositoryRole:Admin` to bypass. The `release` job pushes the
version-bump/CHANGELOG commit as `github-actions[bot]` via the default
`secrets.GITHUB_TOKEN` — that identity is **not** covered by the admin bypass, and
the fresh commit has never had its own CI run to satisfy the check anyway. Result:
`release` job fails with a GH013 ruleset rejection on every real release, right
after successfully computing the version and building the changelog.

**Fix:** push as a real admin-owned token instead of the bot's default token.

1. Log in to **github.com** as the repo owner (the account with `RepositoryRole:Admin`
   on `FreddieMcHeart/downbeat`).
2. Go to **Settings → Developer settings → Personal access tokens → Fine-grained
   tokens → Generate new token**.
3. Configure:

   | Field | Value |
   |---|---|
   | Resource owner | the account/org that owns `downbeat` |
   | Repository access | Only select repositories → `downbeat` |
   | Permissions | **Contents: Read and write** (this is the only scope `release.yml` needs — it just needs to push a commit + tag) |
   | Expiration | your call — a long-lived token is lower-maintenance but review this periodically since it's effectively a standing admin credential |

4. Generate, copy the token (shown once).
5. Store it as a repo secret — **do not paste the token into chat/a Claude session**;
   run this yourself in a terminal so it never touches conversation history:
   ```
   gh secret set RELEASE_TOKEN --repo FreddieMcHeart/downbeat
   ```
   (pastes/prompts for the value directly, or pipe it in — see `gh secret set --help`)
6. Confirm `.github/workflows/release.yml`'s `release` job step uses
   `github_token: ${{ secrets.RELEASE_TOKEN }}` (not the default `GITHUB_TOKEN`) —
   this repo's copy was already updated to reference `RELEASE_TOKEN`.

**Verify:** the entry appears under **Settings → Secrets and variables → Actions →
Repository secrets** as `RELEASE_TOKEN`. The next `fix:`/`feat:` merge to `main`
should let the `release` job's push through the ruleset instead of GH013-rejecting.

**If this token is ever revoked/expires and the push starts failing again:** the
alternative is finding a bypass-actor entry in the ruleset UI that covers the
`github-actions` app identity directly (Settings → Rules → Rulesets → edit the
bypass list) — untested, PAT is the confirmed-working path.

---

## After all four are done

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
