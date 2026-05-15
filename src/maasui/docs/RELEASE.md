# Release Process

## MAAS UI Integration with MAAS

- Whenever changes are pushed to `main` or `3.x` branch, a new JavaScript bundle is automatically created and pushed to the [Ubuntu assets server](https://assets.ubuntu.com/manager?tag=auto-upload&q=maas&type=tar.gz). This process is managed by the [upload.yml](https://github.com/canonical/maas-ui/blob/main/.github/workflows/upload.yml) GitHub Action.

- MAAS integrates the MAAS UI using this JavaScript bundle. For the main development branch (latest/edge), MAAS automatically pulls the latest bundle and creates a commit, triggering a new MAAS release.

## Tracking MAAS core

When MAAS core releases an initial release candidate (e.g. `2.8.0-rc1`), a corresponding branch of maas-ui named after the MAAS
version should be created.

### Note

No new dependencies (unless in the case of a CVE), or features should land in
the release branch once created. Bugfixes should be made on main and backported to release branches where needed.

## Creating a release

### Process

#### Create the branch

Create a new branch from main using the MAAS version as the name (e.g. `git checkout -b 3.2 main`).

Push the branch to the repo at `canonical/maas-ui`.

#### Update the version

Create a new local branch e.g. release-0.1.2.

Run `yarn release [version]` where version is in the form `0.1.2`. This will bump the version in `package.json` and create a tag with a 'v' prefix.

The workflows in `.github/workflows` need to be updated to only run against the version
branch. This might look something like the following:

```yaml
on:
  push:
    branches:
      - 3.2
  pull_request:
    branches:
      - 3.2
```

Update the workflows to set the snap channel for the `maas` and
`maas-test-db` snaps (e.g. `--channel=3.2/edge`).

Propose this against the appropriate version branch and merge once approved.

#### Update main version to the next expected version

Create a new branch off of main, and update the version in package.json to the next expected version.

#### Add branch protection

Create new branch protection rules for the new version branch, copying the rules from the previous branch: https://github.com/canonical/maas-ui/settings/branches.

#### Update Usabilla ID

Usabilla button IDs can be found in the Usabilla dashboard.

Update the `VITE_APP_USABILLA_ID` on the new release branch with a Usabilla button ID that matches the new version (e.g. "MAAS 3.4").

Update the `VITE_APP_USABILLA_ID` on the main branch with a Usabilla button ID that matches the next expected version, e.g. "MAAS 3.5" button id.

You may need to create new buttons in Usabilla if they don't yet exist.

#### Run the UI sync job for bug fixes

The UI sync jenkins job will automatically run when changes are detected on the main branch. For bug fixes to version branches (e.g. 3.5), you'll need to run the job manually and set the parameters.

1. Get the jenkins URL from a MAAS colleague and log in
2. Find the job `maas-ui-sync` (should be on the dashboard) and click on it
3. Click "Build with parameters" in the side bar
4. Set `MAAS_UI_REF` and `LP_BRANCH_DEST` to the version you committed to (e.g. 3.5)
5. Click "Build"

#### Generating release notes

Given that we use conventional commits in maas-ui, generating release notes is fairly easy. You should only do this step once we have a final release candidate, and someone has asked for the UI release notes.

1. Run `git merge-base main <version - 1>` to find the merge base of the branch you want to release (if you're releasing v5.2, you should run `git merge-base main 5.1`)
2. Copy the commit hash somewhere
3. Check out the branch for the version you're releasing
4. Run `git cliff <hash>..` to generate release notes (e.g. `git cliff 4ab754cd124cd32..`)
