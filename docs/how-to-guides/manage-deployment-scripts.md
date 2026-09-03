# Manage deployment scripts

Deployment scripts let you run custom logic on every machine as it is deployed. This guide shows how to write, upload, order, and inspect them. For the concepts behind the feature, see [Deployment scripts](/explanation/deployment-scripts.md).

Uploaded deployment scripts run on **every** machine being deployed, in alphabetical order by name, in the machine's ephemeral environment. The built-in `50-curtin-install` script installs the OS, so scripts named before it run before installation and scripts named after it run after installation.

## Write a deployment script

A deployment script is any executable (shell, Python, etc.) with a MAAS metadata header. Set `script_type: deployment` to make it a deployment script, and pick a name prefix that places it correctly relative to `50-curtin-install`.

Pre-install example (runs before the OS is installed):

```shell
#!/usr/bin/env bash

# --- Start MAAS 1.0 script metadata ---
# name: 40-pre-install-check
# title: Pre-install check
# description: Verify a precondition before the OS is installed
# script_type: deployment
# timeout: 00:10:00
# --- End MAAS 1.0 script metadata ---

set -euo pipefail
echo "Running before curtin installs the OS"
```

Post-install example (runs after the OS is installed):

```shell
#!/usr/bin/env bash

# --- Start MAAS 1.0 script metadata ---
# name: 60-post-install-task
# title: Post-install task
# description: Run a site-specific task after the OS is installed
# script_type: deployment
# timeout: 00:30:00
# --- End MAAS 1.0 script metadata ---

set -euo pipefail
echo "Running after curtin installs the OS"
```

## Upload a deployment script

Upload with the CLI using `node-scripts create`. The `type=deployment` keyword registers it as a deployment script:

```bash
maas $PROFILE node-scripts create \
    name=60-post-install-task \
    type=deployment \
    script@=/path/to/60-post-install-task.sh
```

If your file already contains the metadata header (including `script_type: deployment`), MAAS reads the type and name from the header, so you can simply upload the file:

```bash
maas $PROFILE node-scripts create script@=/path/to/60-post-install-task.sh
```

You can also upload and manage deployment scripts from the MAAS UI under *Settings → Scripts*.

## List deployment scripts

List the deployment scripts currently registered in MAAS:

```bash
maas $PROFILE node-scripts read type=deployment
```

## Control execution order

Deployment scripts run in alphabetical order by name. Use numeric prefixes to control ordering and to place each script on the correct side of the built-in installer:

- `40-...` runs **before** `50-curtin-install` (pre-install).
- `50-curtin-install` installs the OS (built-in — do not remove or shadow it).
- `60-...` runs **after** `50-curtin-install` (post-install).

## Deploy and inspect results

Deploy a machine as usual; the uploaded deployment scripts run automatically:

```bash
maas $PROFILE machine deploy $SYSTEM_ID
```

Each script produces a **deployment** result on the machine. View results in the UI under the machine's details, or retrieve them with the CLI:

```bash
maas $PROFILE node-script-results read $SYSTEM_ID type=deployment
```

## Remove a deployment script

Delete a script you no longer need by name:

```bash
maas $PROFILE node-script delete 60-post-install-task
```

## Best practices

- Remember scripts run in the **ephemeral** environment: changes to the ephemeral root filesystem do not persist into the deployed OS. Target firmware, attached hardware, or the installed disk if you need lasting effects.
- Name scripts deliberately (`40-`, `60-`, …) so they run on the intended side of `50-curtin-install`.
- Keep each script focused, and fail fast with clear messages so deployment stops on real errors.
- Test iteratively on a single machine before rolling a script out to your whole fleet.
