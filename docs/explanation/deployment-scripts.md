# Deployment scripts

Deployment scripts are small programs that MAAS runs on a machine *while it is being deployed*. They let you inject custom logic into the deployment process, before and after the operating system is installed, so you can prepare hardware, tweak firmware, or run any one-off task that every machine should perform on its way to a running state.

Deployment scripts are the deployment-time counterpart to [commissioning scripts](/explanation/commissioning-scripts.md): they share the same script format, upload mechanism, and result storage, but they run during deployment rather than during commissioning.

## Why deployment scripts matter

Commissioning gathers hardware information; deployment turns a machine into a running system. Some tasks only make sense at deployment time, for example:

- Applying firmware or BIOS settings that must be in place before the OS is installed.
- Preparing attached hardware (such as flashing a DPU) as part of every deployment.
- Running site-specific setup that has to happen on every machine, without baking it into a custom image.

Deployment scripts give you a single, repeatable place to put that logic. Every machine being deployed runs the uploaded deployment scripts, so behaviour is consistent across your fleet.

## When deployment scripts run

Deployment scripts execute in the machine's **ephemeral environment**, the same in-memory environment used for commissioning, not on the freshly installed OS. Anything a deployment script writes to the ephemeral root filesystem is discarded when the machine reboots into its deployed OS. Its lasting effects are whatever it changes *outside* that throwaway filesystem: firmware, attached devices, or the target disk.

MAAS ships a built-in deployment script, `50-curtin-install`, which downloads and runs curtin, the tool that actually installs the operating system onto the target disk. This built-in script is the pivot point of the deployment:

- Scripts that sort **before** `50-curtin-install` run **before** the OS is installed (pre-install).
- Scripts that sort **after** `50-curtin-install` run **after** the OS is installed (post-install).

curtin still uploads its logs as usual, they are stored in the installation script results, and also captured in the deployment script result for `50-curtin-install`.

## Execution order

Deployment scripts run **sequentially, in alphabetical order by name**. Because ordering is purely alphabetical, script names use numeric prefixes to make the order explicit, exactly like commissioning scripts:

- `40-my-pre-install-task` runs before curtin.
- `50-curtin-install` installs the OS (built-in).
- `60-my-post-install-task` runs after curtin.

Choose prefixes deliberately so your scripts land on the correct side of `50-curtin-install`.

## Script structure

A deployment script is an ordinary shell, Python, or similar program with a MAAS metadata header. The only thing that marks it as a deployment script is the `script_type: deployment` field:

```shell
#!/usr/bin/env bash

# --- Start MAAS 1.0 script metadata ---
# name: 60-configure-something
# title: Configure something after install
# description: Run a site-specific task after the OS is installed
# script_type: deployment
# timeout: 00:30:00
# --- End MAAS 1.0 script metadata ---

set -euo pipefail
echo "Running post-install configuration"
```

The metadata block supports the same fields as other MAAS scripts (name, title, description, timeout, tags, and so on). After the metadata, you write the executable code; MAAS handles execution, logging, and result collection.

## Results

Each deployment script produces a result, stored as a **deployment** script result on the machine (result type *Deployment*). You can inspect these results in the MAAS UI under the machine's details, or retrieve them with the CLI and API, just as you would for commissioning and testing results. This gives you per-machine visibility into what each deployment script did and whether it succeeded.

## Key takeaway

Deployment scripts extend the deployment process the same way commissioning scripts extend commissioning. By uploading a script with `script_type: deployment` and choosing its name relative to the built-in `50-curtin-install`, you can run custom logic before or after the OS is installed, consistently on every machine you deploy.
