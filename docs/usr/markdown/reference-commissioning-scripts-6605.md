> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/using-commissioning-scripts" target = "_blank">Let us know.</a>*

This page documents the metadata fields associated with MAAS commissioning scripts.

## General information

| Field         | Description |
|---------------|-------------|
| `name`        | The name of the script. |
| `title`       | Human-friendly descriptive version of the name, used within the web UI. |
| `description` | Brief outline of what the script does. |

## Script type and execution

| Field          | Description |
|----------------|-------------|
| `type`         | Either commissioning or testing. |
| `timeout`      | Length of time before MAAS automatically fails and kills execution of the script. The time may be specified in seconds or using the HH:MM:SS format. |
| `destructive`  | True or False, depending on whether the script will overwrite system data. You can't run destructive tests on a deployed machine. |
| `parallel`     | Enables scripts to be run in parallel and can be one of the following: `disabled`, `instance`, `any`. |
| `may_reboot`   | When True, indicates to MAAS that the script may reboot the machine. MAAS will allow up to 20 minutes between heartbeats while running a script with `may_reboot` set to True. |
| `recommission` | After all commissioning scripts have finished running rerun. |
| `script_type`  | commissioning or test. Indicates whether the script should run during commissioning or hardware testing. |

## Tagging and hardware specification

| Field           | Description |
|-----------------|-------------|
| `tags`          | List of tags associated with the script. |
| `hardware_type` | Defines the type of hardware the script configures or tests. Types are `node`, `cpu`, `memory`, `storage`, `network`. |
| `for_hardware`  | Specifies the hardware that must be on the machine for the script to run. Various formats accepted. |

#### for_hardware sub-parameters

| Sub-Parameter       | Description                                                                                       |
|---------------------|---------------------------------------------------------------------------------------------------|
| `modalias`          | Starts with 'modalias:' may optionally contain wild cards.                                       |
| `PCI ID`            | Must be in the format of 'pci:VVVV:PPPP' where VVVV is the vendor ID, and PPPP is the product ID. |
| `USB ID`            | Must be in the format of 'usb:VVVV:PPPP' where VVVV is the vendor ID, and PPPP is the product ID. |
| `System Vendor`     | Starts with 'system_vendor:'.                                                                    |
| `System Product`    | Starts with 'system_product:'.                                                                   |
| `System Version`    | Starts with 'system_version:'.                                                                   |
| `Mainboard Vendor`  | Starts with 'mainboard_vendor:'.                                                                 |
| `Mainboard Product` | Starts with 'mainboard_product:'.                                                                |

## Parameters and results

| Field        | Description |
|--------------|-------------|
| `parameters` | What parameters the script accepts. |
| `results`    | What results the script will return. |

## Additional information

| Field     | Description |
|-----------|-------------|
| `comment`  | Describes changes made in this revision of the script. A comment can be passed via the API when uploading the script. MAAS doesn’t look at the script metadata for this field. |
| `packages` | List of packages to be installed or extracted before running the script. Packages must be specified as a dictionary. Various package sources accepted like `apt`, `snap`, `url`. |

## Script params

Your scripts can be parameter-rich. Make it flexible by defining types such as `storage`, `interface`, and `URL`.

For example, in Python:
```python
#!/usr/bin/env python3
# Metadata block here
import argparse
parser = argparse.ArgumentParser(description='')
parser.add_argument('--storage', required=True, help='path to storage device')
args = parser.parse_args()
print(f"Testing: {args.storage}")
```
  
Or in Bash:
```bash
#!/bin/bash
# Metadata block here
echo "Model: $1"
echo "Serial: $2"
```

## Available Environment Variables

- **OUTPUT_STDOUT_PATH**: Log path for STDOUT.
- **OUTPUT_STDERR_PATH**: Log path for STDERR.
- **RESULT_PATH**: Where to write result YAML.

## Real-world Example: Intel C610/X99 HPA Controller

Here's how to configure an Intel C610/X99 HPA controller on HP systems:

```bash
#!/bin/bash -ex
# Metadata here
output=$(sudo hprest get EmbeddedSata --selector HpB...
```

And there you have it: A quick rundown for handling commissioning scripts in MAAS, simplified for easy use.
