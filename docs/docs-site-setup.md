# Docs site — manual one-time setup

> One GitHub web-console step needed before `.github/workflows/docs.yml` can actually
> make the site visible. Cannot be done from a CLI/agent session — requires a human
> with repo-admin access. Do this **once**.

## Step 1 — Point GitHub Pages at the `gh-pages` branch

`.github/workflows/docs.yml` builds the site with MkDocs Material and pushes the
result to a `gh-pages` branch via `mkdocs gh-deploy` (this creates the branch on its
first successful run — nothing to create by hand). GitHub Pages itself still needs to
be told to serve from that branch.

1. Push to `main` (or run the workflow once via **Actions → docs → Run workflow**) so
   the `gh-pages` branch exists.
2. In the repo on GitHub: **Settings → Pages**.
3. Under **Build and deployment → Source**, select **Deploy from a branch**.
4. Under **Branch**, select `gh-pages` / `(root)`.
5. Save.

**Verify:** the same page shows "Your site is live at
`https://freddiemcheart.github.io/downbeat/`" within a minute or two. Subsequent
pushes to `main` that touch `docs/**`, `mkdocs.yml`, or the community-health files
redeploy automatically — no further manual steps.

**If the workflow fails on the `gh-deploy` push:** the `docs` job only needs
`contents: write` on the default `GITHUB_TOKEN` (unlike `release.yml`, this doesn't
push to `main`, so it isn't affected by `main`'s branch ruleset / admin-bypass
issue documented in [release-setup.md](release-setup.md) Step 4).
