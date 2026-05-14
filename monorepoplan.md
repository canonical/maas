## Plan: Migrate MAAS UI from Submodule to Monorepo

Bring `canonical/maas-ui` directly into `src/maasui/` via `git subtree`, removing the submodule, eliminating the daily sync workflow, and migrating relevant CI workflows into the MAAS repo.

### Steps
1. **Prepare branch** — create a feature branch (e.g. `feat/monorepo-maasui`) in the MAAS repo.
2. **Replace submodule with subtree** — deinit/remove the submodule at `src/maasui/src`, remove its `.gitmodules` entry and `.git/modules/` objects, then run `git subtree add --prefix=src/maasui https://github.com/canonical/maas-ui main --squash` to inline the content with history.
3. **Reconcile `src/maasui/Makefile`** — remove the `git submodule update` target, update `SRC_DIR` from `$(BASE_DIR)/src` to `$(BASE_DIR)`, update `UI_REVISION` to derive from the MAAS repo SHA or a version file instead of the submodule HEAD.
4. **Add UI path filter to `.github/workflows/ci.yaml`** — add a `ui: ['src/maasui/**']` entry to the `changes` job so downstream jobs can condition on UI changes.
5. **Migrate CI workflows** — copy from `canonical/maas-ui/.github/workflows/` into `.github/workflows/`, scoped to `paths: ['src/maasui/**']` and `working-directory: src/maasui`:
   - **`ui-test.yml`** (from `test.yml`): vitest unit tests
   - **`ui-lint.yml`** (from `pr-lint.yml`): ESLint + type-check
   - **`ui-coverage.yml`** (from `coverage.yaml`): vitest coverage
   - **`ui-cypress.yml`** (from `cypress.yml`): e2e tests
   - **`ui-accessibility.yml`** (from `accessibility.yml`): a11y audit
   - Drop: `upload.yml` (build upload no longer needed), `cla-check.yml` (MAAS has `cla.yaml`), `links-checker.yml`, `sitespeed.yml`
   - Update the `ci-check` gate job to include the new UI jobs.
6. **Update `.github/workflows/api-client-sync.yaml`** — replace the `Checkout canonical/maas-ui` step with the already-present `src/maasui/` path; update all `working-directory: fe-repo` references to `src/maasui`; redirect PR creation to `canonical/maas`.
7. **Delete `.github/workflows/maas-ui-sync.yaml`** — the daily submodule sync is no longer needed.
8. **Handle `.gitignore`** — following the existing monorepo pattern (docs/, src/maasagent/, src/host-info/ each have their own), add a `src/maasui/.gitignore` carrying the upstream maas-ui entries (`/node_modules`, `coverage/`, `/test-results/`, `/playwright-report/`, `cypress/screenshots`, etc.). Move the three existing root-level maasui paths (`/src/maasui/build`, `/src/maasui/tarballs`, `/src/maasui/nodejs`) down into that file as well.
9. **Verify snap and root Makefile** — confirm `snap/snapcraft.yaml` (`cd src/maasui && make`) and root `Makefile` (`$(MAKE) -C src/maasui build`) still work unchanged after Step 3.

### Step 10 — Migrate supported version branches (3.4, 3.5, 3.6, 3.7)
Steps 2–9 must also be applied to each supported version branch. There are a few branch-specific differences to account for:

- **3.7** has a dedicated `3.7` branch in `canonical/maas-ui` (`.gitmodules` sets `branch = 3.7`). Use `git subtree add --prefix=src/maasui https://github.com/canonical/maas-ui 3.7 --squash` on this branch.
- **3.4, 3.5, 3.6** all have `.gitmodules` pointing to `branch = main`, but each is pinned to a specific commit. All three pinned commits have been confirmed as ancestors of the corresponding `3.4`, `3.5`, `3.6` branches in `canonical/maas-ui` (i.e. those branches have since moved ahead):
  - 3.4 pinned: `9cbb8e3`, maas-ui `3.4` tip: `8bc462e`
  - 3.5 pinned: `ccb6f80` (identical to maas-ui `3.5` tip — no divergence)
  - 3.6 pinned: `6582db9`, maas-ui `3.6` tip: `e0371fd`

  **Step 10a — Reconcile pin vs. branch tip**: Before running `git subtree add`, review the commits between the pinned SHA and the maas-ui branch tip for each version to confirm they are safe to include (i.e. no unintended features or breaking changes). Once confirmed, use the branch name (e.g. `3.4`) rather than the pinned SHA with `git subtree add`, so the inline content is aligned with the canonical version branch going forward. If any commits between the pin and the tip are undesirable, cherry-pick only the desired commits onto a MAAS-local branch of maas-ui content instead.
- **Node.js version** differs per branch (e.g. Node 16 on 3.4, Node 20 on 3.7) — preserve the existing `NODEJS_VERSION` value in each branch's `src/maasui/Makefile` when making Step 3 changes; do not normalise to a single version across branches.
- **`fetch-build` on version branches** — tarballs for historical commits were already uploaded to `assets.ubuntu.com` by the old `upload.yml` and remain valid. The `fetch-build` path will continue working for those frozen SHAs. Any new commits on a version branch (e.g. backports) will not have a pre-uploaded tarball and will fall back to `build-local` automatically.
- **CI workflows** — the new `ui-*.yml` workflows added in Step 5 should use `branches` filters matching each version branch as well as `master`, so they trigger on UI changes to all supported branches.
- **`maas-ui-sync.yaml` deletion** (Step 7) — this workflow runs across all branches, so deleting it from `master` and each version branch covers all cases.

### Further Considerations
1. **`canonical/maas-ui` repo fate** — once migrated, consider archiving or making it read-only to prevent confusion from developers opening PRs there.
2. **Cypress e2e backend** — `ui-cypress.yml` requires a running MAAS; clarify whether to spin up via LXD/snap in CI (as `maas-ui-sync.yaml` did) or skip e2e in the monorepo CI and rely on integration test runs.
