# Commissioning scripts

Commissioning scripts are small programs that MAAS runs when a machine is first commissioned. They detect hardware, configure settings, and prepare machines for deployment. MAAS comes with a number of built-in scripts, but you can also create your own to extend or customise commissioning.

## Why commissioning scripts matter

When MAAS commissions a machine, it needs reliable data about:

- CPU, memory, and NUMA layout.
- Network interfaces and firmware.
- Vendor- or model-specific quirks (e.g. enabling embedded controllers).

Commissioning scripts gather this information and can also run hardware-specific configuration tasks. Well-written scripts ensure that MAAS knows exactly what resources are available and that machines are ready to deploy workloads.

## Standard commissioning scripts

MAAS provides a set of standard commissioning scripts out of the box. These scripts:

- Detect CPU, memory, and NUMA layout.
- Collect storage and PCI/USB device data.
- Run smartctl checks on disks.
- Validate network devices and links.
- Apply firmware updates or controller settings on specific hardware.

Each built-in script has a name and a title (friendly name shown in the UI). You can inspect these in the MAAS interface under *Settings → Scripts* or via the CLI.

## Script structure

A commissioning script is just a shell, Python, or similar program with a metadata header. The metadata tells MAAS when and how to run the script. For example:

```yaml
name: 50-my-storage-check
title: Storage health check
description: Verify that the selected storage device is present and writable
type: commissioning
timeout: 00:10:00
tags: [storage]
hardware_type: storage
```

After the metadata, you write the executable code. MAAS handles execution, logging, and result collection.

## Naming conventions

Scripts are sorted alphabetically by name. To control execution order:

- Built-in scripts typically use prefixes like `00-`, `10-`, `20-`.
- Custom scripts should start later in the order (e.g. `50-` or higher) so they run *after* the built-ins.

For example:

- `00-maas-01-power-info` (built-in).
- `50-my-storage-check` (custom).

## Key metadata fields

The metadata block supports several important fields:

- type: `commissioning` or `testing`. Determines when the script runs.
- timeout: Time limit (seconds or HH:MM:SS).
- destructive: Whether the script alters system data (can’t run on deployed machines).
- parallel: Whether scripts can run concurrently (`disabled`, `instance`, `any`).
- may_reboot: If true, MAAS tolerates up to 20 minutes of downtime during reboots.
- tags: Labels for searching and filtering scripts.
- hardware_type / for_hardware: Restrict execution to specific hardware classes or devices.

## Parameters and results

Scripts can take parameters and must produce results in YAML. For example:

Python example with argparse:

```python
#!/usr/bin/env python3
# Metadata block here
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--storage', required=True)
args = parser.parse_args()
print(f"Testing: {args.storage}")
```

Bash example:

```bash
#!/bin/bash
# Metadata block here
echo "Model: $1"
echo "Serial: $2"
```

## Environment variables

MAAS sets a number of environment variables to help your script:

- `OUTPUT_STDOUT_PATH` – log path for standard output.
- `OUTPUT_STDERR_PATH` – log path for error output.
- `RESULT_PATH` – location for writing result YAML.

Use these to return structured results and logs that MAAS can display in the UI.

## Example: vendor-specific configuration

Here’s a real-world example of configuring an Intel C610/X99 HPA controller on HP systems:

```bash
#!/bin/bash -ex
# Metadata block here
output=$(sudo hprest get EmbeddedSata --selector HpBios)
echo "$output" > $RESULT_PATH
```

This script interacts with vendor tools to configure hardware during commissioning.

## Best practices

- Keep scripts simple and focused. One task per script.
- Fail fast. Return clear error messages if requirements aren’t met.
- Avoid destructive operations unless absolutely necessary (and mark them as such).
- Name scripts carefully. Use prefixes (`50-`, `60-`) to control order.
- Test iteratively. Run your script manually in a commissioning environment before uploading.

## Key takeaway

Commissioning scripts are the extensibility point of MAAS: they let you adapt commissioning to your hardware and environment. By understanding script metadata, naming rules, and built-in behaviours, you can write your own scripts to make MAAS commissioning as thorough and reliable as your fleet demands.
